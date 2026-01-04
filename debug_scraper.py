from playwright.sync_api import sync_playwright

def debug_scrape_v2():
    url = "https://magazine.shots.net/the-work"
    print(f"Navigating to {url}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_timeout(5000)

        # Print all class names of div elements to find the grid/list
        print("\n--- Classes found on page ---")
        classes = page.evaluate("""() => {
            const all = document.querySelectorAll('div, section, article');
            const classCounts = {};
            all.forEach(el => {
                if (el.className) {
                    const cls = el.className.split(' ');
                    cls.forEach(c => {
                        classCounts[c] = (classCounts[c] || 0) + 1;
                    });
                }
            });
            return Object.entries(classCounts).sort((a,b) => b[1] - a[1]).slice(0, 20);
        }""",)
        print(classes)
        
        # Dump the structure of the first 3 links that contain text
        print("\n--- First 3 Links Structure ---")
        structure = page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a'));
            const interesting = links.filter(a => a.innerText.length > 5 && a.href.includes('/news/')); 
            // 'the-work' usually links to /news/ or similar on shots.net
            
            return interesting.slice(0, 3).map(a => ({
                text: a.innerText,
                href: a.href,
                parentHTML: a.parentElement.outerHTML.slice(0, 200),
                grandParentClass: a.parentElement.parentElement ? a.parentElement.parentElement.className : 'N/A'
            }));
        }""",)
        
        for s in structure:
            print(s)

        browser.close()

if __name__ == "__main__":
    debug_scrape_v2()