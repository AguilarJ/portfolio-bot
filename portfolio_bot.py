import time
import sqlite3  # <--- NEW: Database Library
import random
from datetime import datetime
from playwright.sync_api import sync_playwright

# --- CONFIGURATION: YOUR PORTFOLIO ---
portfolio_shares = {
    "UBER": 127,
    "VTI": 140,
    "ASML": 11,
    "AMZN": 55,
    "GOOGL": 56,
    "MSFT": 13,
    "VXUS": 130
}
tickers = list(portfolio_shares.keys())

# --- HELPER FUNCTIONS ---
def get_clean_price(raw_text):
    lines = raw_text.split('\n')
    for line in lines:
        clean_line = line.replace(',', '')
        if "." in clean_line:
            try:
                float(clean_line)
                return clean_line
            except ValueError:
                continue
    return "Error"

def get_news(page, ticker):
    try:
        # GOOGLE NEWS STRATEGY
        page.goto(f"https://www.google.com/search?q={ticker}+stock&tbm=nws")
        page.wait_for_selector('#search', timeout=5000)
        headings = page.locator('div[role="heading"]').all_inner_texts()
        for text in headings:
            clean_text = text.strip()
            if not clean_text: continue
            if "feedback" in clean_text.lower(): continue
            if "custom date range" in clean_text.lower(): continue
            if len(clean_text) < 15: continue
            return clean_text
    except:
        return "No news found"
    return "No news found"

def get_price(page, ticker):
    try:
        # STRATEGY: ALL IN ON CNBC
        # Consistent, fast, and handles Uber/ETFs correctly.
        page.goto(f"https://www.cnbc.com/quotes/{ticker}")
        page.wait_for_timeout(2000)
        
        selector = ".QuoteStrip-lastPrice"
        
        if page.locator(selector).count() > 0:
            val = page.locator(selector).first.inner_text()
            return val.replace(',', '')
            
        return "Error"
    except:
        return "Error"

# --- THE JOB ---
def run_portfolio_scan():
    print(f"\n⏰ Waking up! Starting Scan: {datetime.now()}")
    total_portfolio_value = 0.0
    
    # 1. Connect to the Database
    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        page = browser.new_page()

        print("-" * 65)
        print(f"{'TICKER':<8} {'PRICE':<10} {'SHARES':<8} {'VALUE':<12} {'NEWS'}")
        print("-" * 65)

        for ticker in tickers:
            headline = get_news(page, ticker)
            price_str = get_price(page, ticker)
            
            # --- SAFETY NET ---
            if price_str == "Error":
                print(f"   ⚠️  Bot missed {ticker}.")
                price_str = input(f"   ✍️  Type {ticker} price manually: ")
            
            try:
                price_float = float(price_str)
                shares_owned = portfolio_shares[ticker]
                position_value = price_float * shares_owned
                total_portfolio_value += position_value
                
                short_headline = (headline[:20] + '..') if len(headline) > 20 else headline
                print(f"{ticker:<8} ${price_float:<9.2f} {shares_owned:<8} ${position_value:,.2f}    {short_headline}")
                
                # --- NEW: SAVE TO DATABASE ---
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute('''
                    INSERT INTO portfolio_history (scan_time, ticker, price, shares, value, news_headline)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (timestamp, ticker, price_float, shares_owned, position_value, headline))
                conn.commit() # Save changes immediately
                # -----------------------------
                
            except ValueError:
                print(f"{ticker:<8} {price_str:<10} -        ERROR           {headline}")

            time.sleep(2)

        browser.close()
    
    # Close Database Connection
    conn.close()

    print("-" * 65)
    print(f"💰 TOTAL PORTFOLIO VALUE: ${total_portfolio_value:,.2f}")
    print("-" * 65)
    print("✅ Scan Complete. Data saved to SQL Database.")

# --- RUN IT ---
if __name__ == "__main__":
    run_portfolio_scan()