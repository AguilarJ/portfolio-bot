import os
import requests
import time
import sqlite3
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright

class PortfolioManager:
    def __init__(self, db_name='portfolio.db', headless=False):
        self.db_name = db_name
        self.headless = headless
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("bot_activity.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger()

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
        try:
            url = f"https://www.cnbc.com/quotes/{ticker}"
            page.goto(url)
            page.wait_for_selector(".QuoteStrip-lastPrice", timeout=4000)
            val = page.locator(".QuoteStrip-lastPrice").first.inner_text()
            return val.replace(',', '')
        except Exception as e:
            self.logger.warning(f"Failed to get price for {ticker}: {e}")
            return None
    def _get_change_cnbc(self, page):
        """Gets the day's percentage change (e.g., +1.50%)."""
        try:
            # CNBC uses different colors (classes) for Up vs Down vs Flat
            # We look for ANY of them.
            selector = ".QuoteStrip-changeDown, .QuoteStrip-changeUp, .QuoteStrip-changeUnchanged"
            
            # This gets the whole text like "-1.24 (-0.56%)"
            full_text = page.locator(selector).first.inner_text()
            
            # We only want the part inside parenthesis: (-0.56%)
            if "(" in full_text and ")" in full_text:
                return full_text.split("(")[1].replace(")", "")
            return full_text
        except Exception as e:
            return "0.00%"
    def save_to_db(self, ticker, price, shares, value, headline):
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

    def send_discord_alert(self, total_equity, table_text):
        """Sends the report to Discord."""
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        
        if not webhook_url:
            print("❌ No Discord Webhook found. Skipping notification.")
            return

        message_content = f"""
**🚀 Daily Portfolio Update**
**Total Net Worth:** ${total_equity:,.2f}

```text
{table_text}
"""
        payload = {"content": message_content}

        try:
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()
            print("✅ Discord notification sent!")
        except Exception as e:
            print(f"❌ Failed to send Discord notification: {e}")

    def run(self):
        self.logger.info("🚀 Starting Portfolio Scan...")
        total_value = 0.0
        
        report_lines = []
        
        # ---------------------------------------------------
        # 📐 THE "BRICK WALL" LAYOUT
        # 1. We define the width of the TEXT, not the gap.
        # 2. We add explicit "  " spacers in the f-string below.
        # ---------------------------------------------------
        w_tick  = 5    # "UBER "
        w_price = 9    # "$1,263.00" (Exact fit for ASML)
        w_share = 6    # "130.1 "
        w_value = 8    # "$47,670 "
        w_chg   = 7    # "-0.15% "
        
        # 1. HEADER
        # Note the "  " strings between the variables. These are the spacers.
        header = f"{'TICK':<{w_tick}}  {'PRICE':<{w_price}}  {'SHARES':<{w_share}}  {'VALUE':<{w_value}}  {'CHANGE':<{w_chg}}"
        report_lines.append(header)
        report_lines.append("-" * 45) # Slightly wider to accommodate spacers

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()

            for ticker in self.tickers:
                price_str = self._get_price_cnbc(page, ticker)
                change_pct = self._get_change_cnbc(page)

                if price_str:
                    try:
                        price = float(price_str)
                        shares = self.portfolio_shares[ticker]
                        value = price * shares
                        total_value += value
                        
                        display_change = change_pct
                        if "unch" in change_pct.lower():
                            display_change = "0.00%"
                        
                        # 2. DATA PREP
                        p_fmt = f"${price:,.2f}"      # $1,263.00
                        v_fmt = f"${value:,.0f}"      # $47,670
                        
                        if isinstance(shares, float):
                            s_fmt = f"{shares:.1f}"
                        else:
                            s_fmt = f"{shares}"

                        # 3. THE ROW WITH "BRICK WALL" SPACERS
                        # We force 2 spaces ("  ") between every block.
                        # Even if p_fmt fills the whole 9 spaces, the "  " protects the next column.
                        line = (
                            f"{ticker:<{w_tick}}  "
                            f"{p_fmt:<{w_price}}  "
                            f"{s_fmt:<{w_share}}  "
                            f"{v_fmt:<{w_value}}  "
                            f"{display_change:<{w_chg}}"
                        )
                        
                        report_lines.append(line)
                        print(line)

                        self.save_to_db(ticker, price, shares, value, change_pct)
                        
                    except ValueError:
                        self.logger.error(f"Price error: {price_str}")
                else:
                    self.logger.error(f"Could not find price for {ticker}")

                time.sleep(1)
            browser.close()

        report_lines.append("-" * 45)
        report_lines.append(f"💰 TOTAL: ${total_value:,.2f}")
        
        full_report = "\n".join(report_lines)
        print("-" * 45)
        print(f"💰 TOTAL: ${total_value:,.2f}")
        
        self.send_discord_alert(total_value, full_report)
if __name__ == "__main__":
    is_cloud = os.getenv('CI') is not None
    bot = PortfolioManager(headless=is_cloud)
    bot.run()