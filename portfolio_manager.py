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
        
        # Start building the report text
        report_lines = []
        
        # Header Row - COMPACT & RIGHT ALIGNED
        # We put ($) in the header to save space in the rows
        report_lines.append(f"{'TICKER':<5} {'PRICE($)':>8} {'SHARES':>7} {'VALUE($)':>11} {'CHANGE':>7}")
        report_lines.append("-" * 43) # Much shorter line to fit mobile

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
                        
                        # Handle shares formatting
                        if isinstance(shares, float):
                            # For 130.097, show 3 decimals
                            s_fmt = f"{shares:.3f}"
                        else:
                            # For 127, show clean integer
                            s_fmt = f"{shares}"

                        # THE CLEAN FORMATTING:
                        # 1. No Dollar signs (Cleaner alignment)
                        # 2. Tighter spacing (Fits on phone)
                        # 3. Headers match the numbers (Right aligned)
                        line = f"{ticker:<5} {price:>8.2f} {s_fmt:>7} {value:>11,.2f} {display_change:>7}"
                        report_lines.append(line)
                        print(line)

                        self.save_to_db(ticker, price, shares, value, change_pct)
                        
                    except ValueError:
                        self.logger.error(f"Price error: {price_str}")
                else:
                    self.logger.error(f"Could not find price for {ticker}")

                time.sleep(1)
            browser.close()

        report_lines.append("-" * 43)
        report_lines.append(f"💰 TOTAL: ${total_value:,.2f}")
        
        full_report = "\n".join(report_lines)
        print("-" * 43)
        print(f"💰 TOTAL: ${total_value:,.2f}")
        
        self.send_discord_alert(total_value, full_report)
# This part goes at the very, very bottom (no indentation)
if __name__ == "__main__":
    is_cloud = os.getenv('CI') is not None
    bot = PortfolioManager(headless=is_cloud)
    bot.run()