
import time
import sqlite3
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright

# --- CONFIGURATION (The "State" of the Object) ---
class PortfolioManager:
    def __init__(self, db_name='portfolio.db', headless=False):
        """
        Initialize the bot.
        :param db_name: Where to save data.
        :param headless: True = Invisible browser, False = Visible browser.
        """
        self.db_name = db_name
        self.headless = headless
        
        # Setup Logging (So we can see what happens even if browser is hidden)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("bot_activity.log"), # Save to file
                logging.StreamHandler()                  # Print to terminal
            ]
        )
        self.logger = logging.getLogger()

        # Your Holdings
        self.portfolio_shares = {
            "UBER": 127,
            "VTI": 140,
            "ASML": 11,
            "AMZN": 55,
            "GOOGL": 56,
            "MSFT": 13,
            "VXUS": 130.097
        }
        self.tickers = list(self.portfolio_shares.keys())

    def _get_price_cnbc(self, page, ticker):
        """Private method to get price from CNBC."""
        try:
            url = f"https://www.cnbc.com/quotes/{ticker}"
            page.goto(url)
            # Wait for dynamic content
            page.wait_for_selector(".QuoteStrip-lastPrice", timeout=4000)
            
            val = page.locator(".QuoteStrip-lastPrice").first.inner_text()
            return val.replace(',', '')
        except Exception as e:
            self.logger.warning(f"Failed to get price for {ticker}: {e}")
            return None

    def _get_news_cnbc(self, page):
        """
        Scrapes the news using the 'Wrapper' container.
        """
        try:
            # 1. Scroll slightly to trigger the load
            page.mouse.wheel(0, 500)
            
            # 2. Target the WRAPPER (The Box), not the text directly.
            # You saw this class in the inspector: "LatestNews-headlineWrapper"
            wrapper_selector = ".LatestNews-headlineWrapper"
            
            # Wait for the BOX to be attached to the DOM (even if hidden)
            page.wait_for_selector(wrapper_selector, state='attached', timeout=4000)
            
            # 3. Now grab the text from inside that box
            headline = page.locator(wrapper_selector).first.inner_text()
            return headline
            
        except Exception as e:
            # If that fails, fall back to the "River" class (for VTI/ETFs)
            try:
                return page.locator(".RiverHeadline-headline").first.inner_text()
            except:
                return "No news found"
    def save_to_db(self, ticker, price, shares, value, headline):
        """Saves a single row to the database."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute('''
                INSERT INTO portfolio_history (scan_time, ticker, price, shares, value, news_headline)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (timestamp, ticker, price, shares, value, headline))
            
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Database Error: {e}")

    def run(self):
        """The Main Execution Method."""
        self.logger.info("🚀 Starting Portfolio Scan...")
        total_value = 0.0

        with sync_playwright() as p:
            # Launch with the 'headless' setting we chose in __init__
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()

            print("-" * 65)
            print(f"{'TICKER':<8} {'PRICE':<10} {'SHARES':<8} {'VALUE':<12} {'NEWS'}")
            print("-" * 65)

            for ticker in self.tickers:
                # 1. Get Price (This function LOADS the page)
                price_str = self._get_price_cnbc(page, ticker)
                
                # 2. Get News (This function just READS the page we are already on)
                # We swapped _get_news_google for _get_news_cnbc
                headline = self._get_news_cnbc(page)

                # 3. Process Data
                if price_str:
                    try:
                        price = float(price_str)
                        shares = self.portfolio_shares[ticker]
                        value = price * shares
                        total_value += value
                        
                        # Formatting: If news is super long, trim it
                        clean_headline = headline.replace('\n', ' ').strip()
                        short_news = (clean_headline[:30] + '..') if len(clean_headline) > 30 else clean_headline
                        
                        print(f"{ticker:<8} ${price:<9.2f} {shares:<8} ${value:,.2f}    {short_news}")

                        self.save_to_db(ticker, price, shares, value, clean_headline)
                        
                    except ValueError:
                        self.logger.error(f"Price conversion error for {ticker}: {price_str}")
                else:
                    self.logger.error(f"Could not find price for {ticker}")

                # Polite pause
                time.sleep(1)
            browser.close()

        self.logger.info(f"💰 Scan Complete. Total Net Worth: ${total_value:,.2f}")
        print("-" * 65)
        print(f"💰 TOTAL: ${total_value:,.2f}")

# --- EXECUTION BLOCK ---
if __name__ == "__main__":
    # Now we just instantiate the class and run it. 
    # This is clean, readable, and professional.
    bot = PortfolioManager(headless=False)
    bot.run()