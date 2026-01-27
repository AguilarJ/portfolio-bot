import json 
import os
import requests
import time
import sqlite3
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright

class PortfolioManager:
    def __init__(self, db_name='portfolio.db', headless=True):
        self.db_name = db_name
        self.headless = headless
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger()

        self.portfolio_data = {}
        
        try:
            with open('portfolio.json', 'r') as f:
                raw_data = json.load(f)
            
            for ticker, lots in raw_data.items():
                if isinstance(lots, dict): 
                    lots = [lots]
                
                total_shares = 0
                total_invested = 0.0
                
                for lot in lots:
                    s = float(lot['shares'])
                    p = float(lot.get('price', lot.get('cost', 0)))
                    
                    total_shares += s
                    total_invested += (s * p)
                
                if total_shares > 0:
                    avg_cost = total_invested / total_shares
                else:
                    avg_cost = 0
                    
                self.portfolio_data[ticker] = {
                    "shares": total_shares,
                    "cost": avg_cost
                }
                
            self.logger.info("✅ Loaded portfolio data.")
            
        except FileNotFoundError:
            self.logger.error("❌ portfolio.json not found!")
            self.portfolio_data = {}
        
        self.tickers = list(self.portfolio_data.keys())
        
        # Database Setup
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS portfolio_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_time TIMESTAMP,
                    ticker TEXT,
                    price REAL,
                    shares REAL,
                    value REAL,
                    change_pct TEXT
                )
            ''')
            conn.commit()
        self.logger.info("✅ Database initialized successfully.")

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

    def save_to_db(self, ticker, price, shares, value, change_pct):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('''
                INSERT INTO portfolio_history (scan_time, ticker, price, shares, value, change_pct)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (timestamp, ticker, price, shares, value, change_pct))
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Database Error: {e}")

    def send_discord_report(self, total_equity, total_pl, day_pl, total_day_pct, report_path):
        emoji = "🟢" if day_pl >= 0 else "🔴"
        main_content = (f"**💰 Daily Portfolio Scan**\n"
                        f"Total Equity: **${total_equity:,.2f}**\n"
                        f"Day Change: {emoji} **${day_pl:+,.2f}** (`{total_day_pct:+.2f}%`)")
        
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        
        try:
            if report_path:
                with open(report_path, 'rb') as f:
                    payload = {"content": main_content}
                    files = {"file": (report_path, f, "image/png")}
                    requests.post(webhook_url, data=payload, files=files)
                print("✅ Discord Report Sent!")
        except Exception as e:
            print(f"❌ Failed to send Discord: {e}")

    def _generate_html(self, portfolio_rows, total_value, total_gain_all, day_gain_all, total_day_pct):
        rows_html = ""
        for row in portfolio_rows:
            day_color = "#4caf50" if row['day_gain'] >= 0 else "#f44336"
            total_color = "#4caf50" if row['total_gain'] >= 0 else "#f44336"
            
            # --- UPDATE: Added the 'pct_change' column here ---
            rows_html += f"""
            <tr>
                <td style="text-align: left; font-weight: bold; color: #fff;">{row['ticker']}</td>
                <td style="text-align: right;">${row['price']:,.2f}</td>
                <td style="text-align: right;">{row['shares']:,.1f}</td>
                <td style="text-align: right;">${row['value']:,.0f}</td>
                <td style="text-align: right; color: {day_color};">{row['pct_change']}</td>
                <td style="text-align: right; color: {day_color};">${row['day_gain']:,.0f}</td>
                <td style="text-align: right; color: {total_color};">${row['total_gain']:,.0f}</td>
            </tr>
            """
        
        total_color_hex = "#4caf50" if total_gain_all >= 0 else "#f44336"
        day_color_hex = "#4caf50" if day_gain_all >= 0 else "#f44336"

        html = f"""
        <html>
        <head>
            <style>
                body {{ background-color: #2f3136; font-family: sans-serif; padding: 20px; }}
                .container {{ display: inline-block; background-color: #36393f; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
                h2 {{ color: #ffffff; margin-bottom: 10px; border-bottom: 1px solid #7289da; padding-bottom: 10px; }}
                table {{ border-collapse: collapse; width: 600px; color: #dcddde; }}
                th {{ text-align: right; padding: 8px; border-bottom: 1px solid #555; color: #b9bbbe; font-size: 12px; }}
                th:first-child {{ text-align: left; }}
                td {{ padding: 10px 8px; font-size: 14px; border-bottom: 1px solid #40444b; }}
                .footer {{ margin-top: 15px; display: flex; justify-content: space-between; font-weight: bold; color: #fff; font-size: 16px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>📊 Portfolio Report</h2>
                <table>
                    <tr>
                        <th>TICKER</th> <th>PRICE</th> <th>SHARES</th> <th>VALUE</th> <th>DAY %</th> <th>DAY P&L</th> <th>TOTAL P&L</th>
                    </tr>
                    {rows_html}
                </table>
                <div class="footer">
                    <div>Day: <span style="color:{day_color_hex}">${day_gain_all:,.2f} ({total_day_pct:+.2f}%)</span></div>
                    <div>Total: <span style="color:{total_color_hex}">${total_gain_all:,.2f}</span></div>
                    <div>Equity: ${total_value:,.2f}</div>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def run(self):
        self.logger.info("🚀 Starting Portfolio Scan...")
        total_equity = 0.0
        total_pl_all = 0.0
        day_pl_all = 0.0
        portfolio_rows = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()

            for ticker in self.tickers:
                price_str = self._get_price_cnbc(page, ticker)
                change_pct_str = self._get_change_cnbc(page)
                
                if price_str:
                    try:
                        price = float(price_str)
                        data = self.portfolio_data[ticker]
                        shares = data['shares']
                        cost_basis = data['cost']
                        value = price * shares
                        total_equity += value

                        total_gain = (price - cost_basis) * shares
                        total_pl_all += total_gain

                        if "UNCH" in change_pct_str.upper(): change_pct_str = "0.00%"
                        clean_pct = change_pct_str.replace('%', '').replace('+', '')
                        pct_float = float(clean_pct) / 100.0
                        
                        previous_value_stock = value / (1 + pct_float)
                        day_gain = value - previous_value_stock
                        day_pl_all += day_gain
                        
                        # --- UPDATE: Added 'pct_change' to the list ---
                        portfolio_rows.append({
                            "ticker": ticker,
                            "price": price,
                            "shares": shares,
                            "value": value,
                            "day_gain": day_gain,
                            "total_gain": total_gain,
                            "pct_change": change_pct_str
                        })
                        print(f"✅ {ticker}: ${value:,.0f} ({change_pct_str})")
                        self.save_to_db(ticker, price, shares, value, change_pct_str)
                    except ValueError:
                        print(f"❌ Error {ticker}")
                time.sleep(1)

            previous_equity_all = total_equity - day_pl_all
            if previous_equity_all > 0:
                total_day_pct = (day_pl_all / previous_equity_all) * 100
            else:
                total_day_pct = 0.0

            print("🎨 Generating HTML Report...")
            html_content = self._generate_html(portfolio_rows, total_equity, total_pl_all, day_pl_all, total_day_pct)
            page.set_content(html_content)
            time.sleep(0.5)
            report_path = "portfolio_report.png"
            page.locator(".container").screenshot(path=report_path)
            
            browser.close()

        self.send_discord_report(total_equity, total_pl_all, day_pl_all, total_day_pct, report_path)

if __name__ == "__main__":
    is_cloud = os.getenv('CI') is not None
    bot = PortfolioManager(headless=is_cloud)
    bot.run()