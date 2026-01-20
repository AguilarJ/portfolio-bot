from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    print("Navigating to UBER...")
    # 1. Go to the URL (Look at your main file for the URL format)
    page.goto("https://www.cnbc.com/quotes/UBER")

    # 2. We need to WAIT for the price to load so the bot doesn't crash.
    # Look for "wait_for_selector" in your main file. 
    # What is the weird text inside the quotes? That's the Class Name.
    page.wait_for_selector(".QuoteStrip-lastPrice", timeout=5000) 

    # 3. Now we grab the text. 
    # Look for "page.locator" and ".inner_text()" in your main file.
    price_text = page.locator(".QuoteStrip-lastPrice").first.inner_text()

    print(f"The price of UBER is: {price_text}")

    browser.close()