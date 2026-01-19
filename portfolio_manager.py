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
        url = f"https://www.cnbc.com/quotes/{ticker}"
        for attempt in range(3):
            try:
                page.goto(url)
                page.wait_for_selector(".QuoteStrip-lastPrice", timeout=5000)
                val = page.locator(".QuoteStrip-lastPrice").first.inner_text()
                return val.replace(',', '')
            except Exception:
                time.sleep(2)
        return None

    def _get_change_cnbc(self, page):
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

    def send_discord_image(self, total_equity, image_path):
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        if not webhook_url:
            print("❌ No Discord Webhook found.")
            return

        message_content = f"**🚀 Daily Portfolio Update**\n**Total Net Worth:** ${total_equity:,.2f}"
        
        # Open the image file and send it
        try:
            with open(image_path, 'rb') as f:
                payload = {"content": message_content}
                files = {"file": (image_path, f, "image/png")}
                requests.post(webhook_url, data=payload, files=files)
            print("✅ Discord Image Sent!")
        except Exception as e:
            print(f"❌ Failed to upload image: {e}")

    def _generate_html(self, portfolio_data, total_value):
        # This HTML creates a dark-mode, professional financial table
        rows = ""
        for row in portfolio_data:
            # Color code the change: Green for +, Red for -
            color = "#4caf50" if "+" in row['change'] else "#f44336" if "-" in row['change'] else "#ffffff"
            
            rows += f"""
            <tr>
                <td style="text-align: left; font-weight: bold; color: #fff;">{row['ticker']}</td>
                <td style="text-align: right;">${row['price']:,.2f}</td>
                <td style="text-align: right;">{row['shares']:,.1f}</td>
                <td style="text-align: right;">${row['value']:,.0f}</td>
                <td style="text-align: right; color: {color};">{row['change']}</td>
            </tr>
            """

        html = f"""
        <html>
        <head>
            <style>
                body {{ background-color: #2f3136; font-family: sans-serif; padding: 20px; }}
                .container {{ display: inline-block; background-color: #36393f; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
                h2 {{ color: #ffffff; margin-bottom: 10px; border-bottom: 1px solid #7289da; padding-bottom: 10px; }}
                table {{ border-collapse: collapse; width: 400px; color: #dcddde; }}
                th {{ text-align: right; padding: 8px; border-bottom: 1px solid #555; color: #b9bbbe; font-size: 12px; }}
                th:first-child {{ text-align: left; }}
                td {{ padding: 8px; font-size: 14px; border-bottom: 1px solid #40444b; }}
                .total {{ margin-top: 15px; font-size: 18px; font-weight: bold; color: #ffffff; text-align: right; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>📊 Portfolio Report</h2>
                <table>
                    <tr>
                        <th>TICKER</th> <th>PRICE</th> <th>SHARES</th> <th>VALUE</th> <th>CHG</th>
                    </tr>
                    {rows}
                </table>
                <div class="total">Total Equity: ${total_value:,.2f}</div>
            </div>
        </body>
        </html>
        """
        return html

    def run(self):
        self.logger.info("🚀 Starting Portfolio Scan...")
        total_value = 0.0
        portfolio_data = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()

            # 1. Gather Data
            for ticker in self.tickers:
                price_str = self._get_price_cnbc(page, ticker)
                change_pct = self._get_change_cnbc(page)
                
                if price_str:
                    try:
                        price = float(price_str)
                        shares = self.portfolio_shares[ticker]
                        value = price * shares
                        total_value += value
                        if "UNCH" in change_pct.upper():
                            change_pct = "0.00%"
                        portfolio_data.append({
                            "ticker": ticker,
                            "price": price,
                            "shares": shares,
                            "value": value,
                            "change": change_pct
                        })
                        print(f"✅ Scraped {ticker}: ${value:,.0f}")
                        
                        self.save_to_db(ticker, price, shares, value, change_pct)
                    except ValueError:
                        print(f"❌ Error parsing {ticker}")

                time.sleep(1)

            # 2. Generate HTML Report
            print("🎨 Generating Image Report...")
            html_content = self._generate_html(portfolio_data, total_value)
            
            # Load HTML into page and take screenshot
            page.set_content(html_content)
            # We locate the '.container' so we only screenshot the table, not the whole white page
            screenshot_path = "portfolio_report.png"
            page.locator(".container").screenshot(path=screenshot_path)
            
            browser.close()

        # 3. Send Image to Discord
        self.send_discord_image(total_value, "portfolio_report.png")

if __name__ == "__main__":
    is_cloud = os.getenv('CI') is not None
    bot = PortfolioManager(headless=is_cloud)
    bot.run()