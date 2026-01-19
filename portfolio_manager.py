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
        """Gets the price with a Retry Mechanism to prevent missing data."""
        url = f"https://www.cnbc.com/quotes/{ticker}"
        
        # Try 3 times before giving up
        for attempt in range(3):
            try:
                page.goto(url)
                # Wait up to 5 seconds for the price
                page.wait_for_selector(".QuoteStrip-lastPrice", timeout=5000)
                val = page.locator(".QuoteStrip-lastPrice").first.inner_text()
                clean_val = val.replace(',', '')
                return clean_val
            except Exception as e:
                self.logger.warning(f"Attempt {attempt+1} failed for {ticker}: {e}")
                time.sleep(2) # Wait 2 seconds and try again
        
        return None # Only returns None if all 3 tries fail

    def _get_change_cnbc(self, page):
        """Gets the percentage change."""
        try:
            selector = ".QuoteStrip-changeDown, .QuoteStrip-changeUp, .QuoteStrip-changeUnchanged"
            if page.locator(selector).count() > 0:
                full_text = page.locator(selector).first.inner_text()
                if "(" in full_text and ")" in full_text:
                    return full_text.split("(")[1].replace(")", "")
                return full_text
            return "0.00%"
        except Exception:
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
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        if not webhook_url:
            print("❌ No Discord Webhook found.")
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
        
        # ---------------------------------------------------------
        # 📐 ACCOUNTING FORMAT LAYOUT
        # We separate the "$" from the number so both align perfectly.
        # ---------------------------------------------------------
        # HEADER: Manual spacing to match the data columns below
        # TICK(6) | PRICE (12) | SHARES (8) | VALUE (12) | CHG
        header = "TICK   PRICE          SHARES   VALUE          CHG"
        report_lines.append(header)
        report_lines.append("-" * 52)

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
                        
                        # 1. ACCOUNTING ALIGNMENT
                        # We force the number to the RIGHT (>9) inside a fixed block.
                        # The "$ " is hardcoded at the start.
                        # Result: "$    84.50"
                        # Result: "$ 1,358.55"
                        price_display = f"$ {price:,.2f}".rjust(12) 
                        # Actually, better manual construct to ensure $ is left:
                        # "$ " + 9-char number
                        p_num = f"{price:,.2f}"
                        p_final = f"$ {p_num:>9}"  # Fixed 11 chars width
                        
                        # Value: Same logic
                        v_num = f"{value:,.0f}"
                        v_final = f"$ {v_num:>9}"  # Fixed 11 chars width

                        # Shares: Left align standard
                        if isinstance(shares, float):
                            s_str = f"{shares:.1f}"
                        else:
                            s_str = f"{shares}"

                        # Change: Left align standard
                        if "unch" in change_pct.lower():
                            c_str = "0.00%"
                        else:
                            c_str = change_pct

                        # 2. BUILD THE ROW
                        # TICK(6) GAP p_final GAP s_str(8) GAP v_final GAP c_str
                        line = f"{ticker:<6} {p_final}   {s_str:<8} {v_final}   {c_str}"
                        
                        report_lines.append(line)
                        print(line)

                        self.save_to_db(ticker, price, shares, value, change_pct)
                        
                    except ValueError:
                        self.logger.error(f"Price error: {price_str}")
                else:
                    error_line = f"{ticker:<6} ERR            ---      ---            ---"
                    report_lines.append(error_line)
                    print(f"❌ Could not find price for {ticker}")

                time.sleep(1)
            browser.close()

        report_lines.append("-" * 52)
        report_lines.append(f"💰 TOTAL: ${total_value:,.2f}")
        
        full_report = "\n".join(report_lines)
        print("-" * 52)
        print(f"💰 TOTAL: ${total_value:,.2f}")
        
        self.send_discord_alert(total_value, full_report)
if __name__ == "__main__":
    is_cloud = os.getenv('CI') is not None
    bot = PortfolioManager(headless=is_cloud)
    bot.run()