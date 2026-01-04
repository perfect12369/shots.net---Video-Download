from playwright.sync_api import sync_playwright

def inspect_credits():
    url = "https://shots.net/news/view/natuur-en-bos-reflects-on-life-and-growth"
    print(f"Navigating to {url}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_timeout(3000)

        # 1. Search for "Director" text
        print("\n--- Searching for 'Director' text ---")
        element = page.get_by_text("Director", exact=False).first
        if element.count() > 0:
            print(f"Found 'Director' text: {element.inner_text()}")
            # Get parent or sibling
            try:
                parent = element.locator("..").inner_text()
                print(f"Parent text: {parent}")
            except:
                pass

        # 2. Dump likely credit containers
        print("\n--- Dumping credit classes ---")
        credits = page.evaluate("() => {\n            const nodes = document.querySelectorAll('.credits, .credits__item, .meta, .listing__meta');\n            return Array.from(nodes).map(n => n.innerText);\n        }")
        for c in credits:
            print(f"Credit Block: {c}")

        browser.close()

if __name__ == "__main__":
    inspect_credits()
