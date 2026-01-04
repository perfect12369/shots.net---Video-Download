from playwright.sync_api import sync_playwright
import time

def inspect_video_page():
    url = "https://shots.net/news/view/karni-and-saul-capture-a-species-in-deep-waters"
    print(f"Navigating to {url}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_timeout(3000)

        # 1. Look for iframes initially
        frames = page.frames
        print(f"Initial frames: {len(frames)}")
        for f in frames:
            print(f" - Frame: {f.url}")

        # 2. Look for a play button overlay
        # Common classes: .play-button, .video-overlay, etc.
        print("\n--- Potential Play Buttons ---")
        buttons = page.evaluate("""() => {
            const candidates = document.querySelectorAll('div, button, span, a');
            const results = [];
            candidates.forEach(c => {
                if (c.className && (c.className.includes('play') || c.className.includes('overlay'))) {
                    results.push({
                        tag: c.tagName,
                        class: c.className,
                        text: c.innerText
                    });
                }
            });
            return results.slice(0, 10);
        }""")
        for b in buttons:
            print(b)
            
        # 3. Simulate click if we find a likely candidate
        # The user mentioned a screenshot, usually it's the main media container.
        # Let's try to click the main hero/media image or specific play icon.
        
        print("\n--- Trying to click .slate-video-player or similar ---")
        # I'll look for a common player class used by Slate (the platform shots.net seems to use)
        
        try:
            # Try to find a slate player container
            player = page.locator(".slate-video-player, .video-player, [data-component='VideoPlayer']").first
            if player.count() > 0:
                print("Found player container.")
                # Look for play button inside
                play_btn = player.locator(".play-button, .vjs-big-play-button").first
                if play_btn.count() > 0:
                    play_btn.click()
                    print("Clicked play button!")
                    page.wait_for_timeout(3000)
                    
                    # Check frames again
                    print(f"Frames after click: {len(page.frames)}")
                    for f in page.frames:
                        print(f" - Frame: {f.url}")
        except Exception as e:
            print(f"Error during interaction: {e}")

        browser.close()

if __name__ == "__main__":
    inspect_video_page()
