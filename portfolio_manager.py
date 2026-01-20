import os
import requests
import time
import sqlite3
import logging
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
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

        # YOUR DATA
        self.portfolio_data = {
            "VTI":   {"shares": 140,    "cost": 222.57},
            "GOOGL": {"shares": 56,     "cost": 157.14},
            "ASML":  {"shares": 11,     "cost": 697.03},
            "AMZN":  {"shares": 55,     "cost": 182.17},
            "UBER":  {"shares": 127,    "cost": 70.54},
            "VXUS":  {"shares": 130.1,  "cost": 61.37},
            "MSFT":  {"shares": 13,     "cost": 239.37}
        }
        self.tickers = list(self.portfolio_data.keys())

    # ... (Standard Scrapers match previous version) ...
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

    # --- NEW: GRAPH GENERATOR 📊 ---
    def _generate_history_graph(self):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # 1. Fetch RAW data (Every single stock entry)
            cursor.execute('SELECT scan_time, value FROM portfolio_history')
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                print("⚠️ Database is empty.")
                return None

            # 2. PYTHON GROUPING (The "Glue")
            # We bucket data by the MINUTE (YYYY-MM-DD HH:MM)
            history = {}
            for r in rows:
                timestamp = r[0] 
                value = r[1]
                # "2026-01-19 17:40:29" -> "2026-01-19 17:40"
                minute_key = timestamp[:16] 
                
                if minute_key not in history:
                    history[minute_key] = 0.0
                history[minute_key] += value

            # 3. CONVERT TO LISTS
            # Now we have "Total Net Worth per Minute"
            # We sort them by time so the line goes Left -> Right
            sorted_minutes = sorted(history.keys())
            
            dates = []
            values = []
            
            for minute in sorted_minutes:
                total_val = history[minute]
                # Only keep points that look like a FULL portfolio (> $80k)
                # This filters out the "partial scans" automatically
                if total_val > 80000:
                    dates.append(datetime.strptime(minute, "%Y-%m-%d %H:%M"))
                    values.append(total_val)

            if not values:
                print("⚠️ No full scans found (Totals were all < $80k). Graph skipped.")
                return None
                
            print(f"📈 Plotting {len(values)} valid data points...")

            # 4. PLOT IT
            plt.style.use('dark_background')
            fig, ax = plt.subplots(figsize=(10, 5))
            
            ax.plot(dates, values, color='#4caf50', linewidth=2, marker='o', markersize=4)
            ax.fill_between(dates, values, color='#4caf50', alpha=0.1)

            ax.set_title("Net Worth History", color='white', fontsize=14, pad=20)
            ax.grid(True, color='#40444b', linestyle='--', alpha=0.5)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            plt.xticks(rotation=45)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

            # Clean borders
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color('#40444b')
            ax.spines['left'].set_color('#40444b')

            plt.tight_layout()
            graph_path = "history_graph.png"
            plt.savefig(graph_path, facecolor='#2f3136')
            plt.close()
            
            return graph_path
        except Exception as e:
            print(f"❌ Graph Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def send_discord_report(self, total_equity, total_pl, day_pl, report_path, graph_path):
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        if not webhook_url:
            print("❌ No Discord Webhook found.")
            return

        emoji = "🟢" if total_pl > 0 else "🔴"
        day_emoji = "📈" if day_pl > 0 else "📉"
        
        # MESSAGE 1: The Table (Main Priority)
        main_content = (
            f"**🚀 Daily Portfolio Update**\n"
            f"**Net Worth:** ${total_equity:,.2f}\n"
            f"**Total Return:** {emoji} ${total_pl:,.2f}\n"
            f"**Day's Move:** {day_emoji} ${day_pl:,.2f}"
        )
        
        try:
            # Send the Table
            if report_path:
                with open(report_path, 'rb') as f:
                    payload = {"content": main_content}
                    files = {"file": (report_path, f, "image/png")}
                    requests.post(webhook_url, data=payload, files=files)
                print("✅ Discord Table Sent!")
            
            # Send the Graph (as a reply/follow-up)
            if graph_path:
                with open(graph_path, 'rb') as f:
                    payload = {"content": "**📈 Historical Trend**"} # Optional caption
                    files = {"file": (graph_path, f, "image/png")}
                    requests.post(webhook_url, data=payload, files=files)
                print("✅ Discord Graph Sent!")
                
        except Exception as e:
            print(f"❌ Failed to send Discord: {e}")

    def _generate_html(self, portfolio_rows, total_value, total_gain_all, day_gain_all):
        # (Same HTML generation as before)
        rows_html = ""
        for row in portfolio_rows:
            day_color = "#4caf50" if row['day_gain'] >= 0 else "#f44336"
            total_color = "#4caf50" if row['total_gain'] >= 0 else "#f44336"
            
            rows_html += f"""
            <tr>
                <td style="text-align: left; font-weight: bold; color: #fff;">{row['ticker']}</td>
                <td style="text-align: right;">${row['price']:,.2f}</td>
                <td style="text-align: right;">{row['shares']:,.1f}</td>
                <td style="text-align: right;">${row['value']:,.0f}</td>
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
                        <th>TICKER</th> <th>PRICE</th> <th>SHARES</th> <th>VALUE</th> <th>DAY P&L</th> <th>TOTAL P&L</th>
                    </tr>
                    {rows_html}
                </table>
                <div class="footer">
                    <div>Day: <span style="color:{day_color_hex}">${day_gain_all:,.2f}</span></div>
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

                        # Math
                        total_gain = (price - cost_basis) * shares
                        total_pl_all += total_gain

                        if "UNCH" in change_pct_str.upper(): change_pct_str = "0.00%"
                        clean_pct = change_pct_str.replace('%', '').replace('+', '')
                        pct_float = float(clean_pct) / 100.0
                        previous_value = value / (1 + pct_float)
                        day_gain = value - previous_value
                        day_pl_all += day_gain
                        
                        portfolio_rows.append({
                            "ticker": ticker,
                            "price": price,
                            "shares": shares,
                            "value": value,
                            "day_gain": day_gain,
                            "total_gain": total_gain
                        })
                        print(f"✅ {ticker}: ${value:,.0f}")
                        self.save_to_db(ticker, price, shares, value, change_pct_str)
                    except ValueError:
                        print(f"❌ Error {ticker}")
                time.sleep(1)

            # 1. REPORT IMAGE
            print("🎨 Generating HTML Report...")
            html_content = self._generate_html(portfolio_rows, total_equity, total_pl_all, day_pl_all)
            page.set_content(html_content)
            time.sleep(0.5)
            report_path = "portfolio_report.png"
            page.locator(".container").screenshot(path=report_path)
            
            browser.close()

        # 2. GRAPH IMAGE
        print("📈 Generating History Graph...")
        graph_path = self._generate_history_graph()

        # 3. SEND BOTH
        self.send_discord_report(total_equity, total_pl_all, day_pl_all, report_path, graph_path)

if __name__ == "__main__":
    is_cloud = os.getenv('CI') is not None
    bot = PortfolioManager(headless=is_cloud)
    bot.run()