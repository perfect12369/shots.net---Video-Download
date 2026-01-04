import streamlit as st
import os
import time
from datetime import datetime, timedelta
import re
from playwright.sync_api import sync_playwright
import yt_dlp
import nest_asyncio
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Patch asyncio
nest_asyncio.apply()

# --- Config ---
DOWNLOAD_DIR = "downloads"
BASE_URL = "https://magazine.shots.net/the-work"
MAX_WORKERS = 2
DELAY_SECONDS = 3

# --- Helper Functions ---
def parse_relative_date(date_str):
    try:
        clean_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
        current_year = datetime.now().year
        full_str = f"{clean_str} {current_year}"
        dt = datetime.strptime(full_str, "%d %b %Y")
        if dt > datetime.now() + timedelta(days=1): 
            dt = dt.replace(year=current_year - 1)
        return dt.date()
    except Exception:
        return None

def sanitize_filename(name):
    name = re.sub(r'[\\/*?:\"<>|]', "", name)
    return name.strip()

def download_file_directly(url, filepath):
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            if total_size > 0 and total_size < 10 * 1024 * 1024:
                return False, f"跳过: 文件过小 ({total_size/1024/1024:.2f} MB)"
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True, "下载成功 (原片直连)"
    except Exception as e:
        return False, f"下载失败: {e}"

def analyze_page(page_url):
    real_video_url = None
    director_name = "Unknown"
    exact_title = None
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()
        
        candidates = []
        
        def handle_response(response):
            try:
                url = response.url
                if ".mp4" in url or "video" in response.headers.get("content-type", ""):
                    try:
                        size = int(response.headers.get("content-length", 0))
                        if size > 10 * 1024 * 1024: 
                            candidates.append({'url': url, 'size': size})
                    except:
                        pass
            except:
                pass

        page.on("response", handle_response)

        try:
            page.goto(page_url, timeout=45000)
            page.wait_for_timeout(3000)
            
            try:
                h1_text = page.inner_text("h1")
                if h1_text: exact_title = h1_text.strip()
            except: pass

            try:
                d_name = page.evaluate("""() => {
                    const allElems = Array.from(document.querySelectorAll('*'));
                    const directorLabel = allElems.find(el => el.innerText && el.innerText.trim().toUpperCase() === 'DIRECTOR' && el.tagName !== 'SCRIPT');
                    if (directorLabel) {
                        let sibling = directorLabel.nextElementSibling;
                        if (sibling && sibling.innerText.trim()) return sibling.innerText;
                        if (directorLabel.parentElement) {
                            const parentText = directorLabel.parentElement.innerText;
                            const parts = parentText.split(/Director/i);
                            if (parts.length > 1) return parts[1].trim();
                        }
                    }
                    return null;
                }""",)
                if d_name: director_name = d_name.split('\n')[0].strip()
                else:
                    content_text = page.inner_text("body")
                    m = re.search(r'DIRECTOR\s*\n\s*(.+)', content_text, re.IGNORECASE)
                    if m: director_name = m.group(1).split('\n')[0].strip()
            except Exception: pass

            play_btn = page.locator(".video__cover.js-play-video, .video__play, .play-button").first
            if play_btn.is_visible():
                play_btn.click()
                page.wait_for_timeout(8000) 
            
            if candidates:
                candidates.sort(key=lambda x: x['size'], reverse=True)
                real_video_url = candidates[0]['url']
                
        except Exception as e:
            return None, "Unknown", None, f"Error: {e}"
        finally:
            browser.close()
            
    return real_video_url, director_name, exact_title, None

def process_download_task(url, date_obj, initial_title):
    date_str_short = date_obj.strftime("%y%m%d")
    real_url, director, exact_title, err = analyze_page(url)
    if err: return False, f"分析失败: {err}", initial_title

    final_title_text = exact_title if exact_title else initial_title
    final_title_text = final_title_text.replace('\n', ' ').strip()
    
    final_name = f"{final_title_text} Director by {director} {date_str_short}.mp4"
    final_name = sanitize_filename(final_name)
    filepath = os.path.join(DOWNLOAD_DIR, final_name)

    if os.path.exists(filepath): return True, f"✅ 已存在: {final_name}", final_name

    if real_url:
        success, msg = download_file_directly(real_url, filepath)
        if success: return True, f"✅ 下载完成: {final_name}", final_name
    
    ydl_opts = {
        'quiet': True, 
        'no_warnings': True, 
        'outtmpl': f'{DOWNLOAD_DIR}/{final_name}', 
        'format': 'bestvideo[filesize>10M]+bestaudio/best[filesize>10M]'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            if os.path.exists(filepath):
                size = os.path.getsize(filepath)
                if size < 10 * 1024 * 1024:
                    os.remove(filepath)
                    return False, f"❌ 失败: 仅找到预览文件 ({size/1024/1024:.2f}MB)", final_name
            return True, f"✅ 下载完成: {final_name}", final_name
    except Exception as e: return False, f"❌ 失败: {e}", final_name

def scrape_videos(start_date, end_date, status_container):
    status_container.write("🔍 正在扫描...")
    found_links = []
    processed_urls = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)
        page.wait_for_timeout(3000)
        
        reached_end = False
        scan_round = 0
        
        while not reached_end:
            scan_round += 1
            status_container.caption(f"正在加载第 {scan_round} 页数据...")
            
            items_data = page.evaluate("""() => {
                const results = [];
                const selectors = ['.listing', '.hero-item'];
                selectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(node => {
                        const link = node.querySelector('a');
                        if (link) {
                            results.push({
                                containerText: node.innerText, 
                                linkText: link.innerText,     
                                href: link.href
                            });
                        }
                    });
                });
                return results;
            }""",)
            
            oldest_date_in_batch = None
            
            for item in items_data:
                if item['href'] in processed_urls: continue
                
                date_match = re.search(r'(\d+)(?:st|nd|rd|th)\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', item['containerText'], re.IGNORECASE)
                if date_match:
                    d_str = f"{date_match.group(1)} {date_match.group(2)}"
                    d_obj = parse_relative_date(d_str)
                    
                    if d_obj:
                        processed_urls.add(item['href'])
                        if oldest_date_in_batch is None or d_obj < oldest_date_in_batch:
                            oldest_date_in_batch = d_obj
                        
                        if start_date <= d_obj <= end_date:
                            raw_title = item['linkText'].strip()
                            if not raw_title: raw_title = item['containerText'].split('\n')[0]
                            clean_title = re.sub(r'^\d+(st|nd|rd|th)\s+\w{3}\s*[-|]*\s*', '', raw_title, flags=re.IGNORECASE)
                            clean_title = clean_title.strip()
                            if not clean_title: clean_title = raw_title
                            found_links.append({'标题': clean_title, '日期': d_obj, '链接': item['href'], '选择': True})
            
            if oldest_date_in_batch:
                status_container.caption(f"已找到 {len(found_links)} 个视频 (当前页最旧日期: {oldest_date_in_batch})")
                
                # Stop Condition: We need to go PAST the start date.
                # To ensure we don't miss anything at the boundary (e.g. Dec 1st items mixed with Nov 30),
                # we will load ONE EXTRA page after we first see an older date.
                if oldest_date_in_batch < start_date:
                    # Mark that we reached the boundary, but don't stop immediately
                    if 'boundary_hit_round' not in locals():
                        boundary_hit_round = scan_round
                        status_container.caption("已触达日期边界，正在加载最后缓冲页以确保完整...")
                    
                    # Stop if we have loaded 1 extra page after hitting boundary
                    if scan_round > boundary_hit_round + 1:
                        reached_end = True
            
            if len(found_links) > 400 or scan_round > 30: 
                reached_end = True

            if not reached_end:
                try:
                    load_more = page.locator("text=Load More Work")
                    if load_more.is_visible():
                        load_more.click()
                        page.wait_for_timeout(2500)
                    else:
                        reached_end = True
                except:
                    reached_end = True
                    
        browser.close()
        return found_links

# --- Main UI ---
st.set_page_config(page_title="Shots Downloader", page_icon="🎬", layout="centered")

st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 8px; }
    .stButton>button:hover { border-color: #FF4B4B; color: #FF4B4B; }
    .main .block-container { padding-top: 2rem; max_width: 800px; }
    h1 { font-size: 1.8rem !important; margin-bottom: 0rem !important; }
</style>
""", unsafe_allow_html=True)

if 'videos' not in st.session_state:
    st.session_state['videos'] = []

st.title("Shots 视频下载助手")

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    st.caption("开始日期")
    start_date = st.date_input("Start", value=datetime.now().date() - timedelta(days=7), label_visibility="collapsed")
with col2:
    st.caption("结束日期")
    end_date = st.date_input("End", value=datetime.now().date(), label_visibility="collapsed")
with col3:
    st.caption(" ")
    if st.button("🔍 查找"):
        with st.spinner("..."):
            videos = scrape_videos(start_date, end_date, st.empty())
            st.session_state['videos'] = videos

if st.session_state['videos']:
    st.divider()
    df = pd.DataFrame(st.session_state['videos'])
    edited_df = st.data_editor(
        df,
        column_config={
            "选择": st.column_config.CheckboxColumn("选", default=True, width="small"),
            "日期": st.column_config.DateColumn("日期", format="MM-DD", width="small"),
            "标题": st.column_config.TextColumn("标题", width="large"),
            "链接": None 
        },
        disabled=["标题", "日期"],
        hide_index=True,
        use_container_width=True,
        height=300
    )
    selected_videos = edited_df[edited_df["选择"] == True]
    st.caption(f"已选 {len(selected_videos)} 个视频")
    
    if st.button("🚀 开始下载", type="primary"):
        if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_box = st.expander("下载日志", expanded=True)
        total = len(selected_videos)
        completed = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            for idx, row in enumerate(selected_videos.itertuples()):
                if idx > 0 and idx % MAX_WORKERS == 0:
                    time.sleep(DELAY_SECONDS)
                elif idx > 0:
                    time.sleep(1)
                future = executor.submit(process_download_task, row.链接, row.日期, row.标题)
                futures.append(future)
            
            for future in as_completed(futures):
                success, msg, fname = future.result()
                completed += 1
                progress_bar.progress(completed / total)
                with log_box:
                    if success: st.success(f"[{completed}/{total}] {msg}")
                    else: st.error(f"[{completed}/{total}] {msg}")
        st.success("下载任务已完成")
        st.balloons()
else:
    st.markdown("---")
    st.info("请在上方选择日期并点击查找。")