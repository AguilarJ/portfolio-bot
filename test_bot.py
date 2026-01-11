import csv
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError

def get_clean_price(raw_text):
    # This filters out the "9, 8, 7" countdown clock
    lines = raw_text.split('\n')
    for line in lines:
        clean_line = line.replace(',', '')
        # We only want lines with a decimal point (like 85.54)
        if "." in clean_line:
            try:
                float(clean_line)
                return clean_line
            except ValueError:
                continue
    return "Error"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
   # --- PART 1: GET THE NEWS (ROBUST VERSION) ---
    print("🚀 1. Fetching Top News...")
    page.goto("https://www.google.com/search?q=uber+stock&tbm=nws")
    
    final_headline = "No news found"
    
    try:
        page.wait_for_selector('#search', timeout=5000)
        headings = page.locator('div[role="heading"]').all_inner_texts()
        
        for text in headings:
            # CLEAN IT: Remove whitespace
            clean_text = text.strip()
            
            # FILTER 1: Skip empty
            if not clean_text:
                continue
                
            # FILTER 2: Case-Insensitive Check
            # We convert everything to lowercase just for the check
            if "feedback" in clean_text.lower():
                continue
                
            # FILTER 3: Length Check (Bumped to 25 chars)
            # Real headlines are usually long sentences.
            if len(clean_text) < 25:
                continue
            
            # Found it!
            final_headline = clean_text
            break
            
        print(f"📰 Real News: {final_headline}")
        
    except Exception as e:
        print(f"❌ News Error: {e}")

    # --- PART 2: GET THE PRICE ---
    print("🚀 2. Fetching Price...")
    page.goto("https://www.google.com/search?q=uber+stock+price")
    
    # PAUSE FOR CAPTCHA
    try:
        page.wait_for_selector('#knowledge-finance-wholepage__entity-summary', timeout=5000)
    except:
        input("⚠️ CAPTCHA detected! Solve it, then press ENTER here...")

    # YOUR SELECTOR
    my_selector = "#knowledge-finance-wholepage__entity-summary > div > g-card-section > div > g-card-section > div > div.PZPZlf"
    
    price = "Error" # Default
    try:
        raw_text = page.locator(my_selector).first.inner_text()
        price = get_clean_price(raw_text)
        print(f"💰 Price: ${price}")
    except Exception as e:
        print(f"❌ Price Error: {e}")

    # --- PART 3: SAVE TO FILE ---
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open('portfolio.csv', 'a', newline='') as file:
        writer = csv.writer(file)
        # FIX: We use 'final_headline' here now!
        writer.writerow([timestamp, "UBER", price, final_headline])
        
    print("✅ Saved to portfolio.csv")
    browser.close()