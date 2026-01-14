# 📈 Automated Portfolio Tracker

A Python-based financial automation tool that scrapes real-time stock data, calculates total portfolio equity, and sends daily reports to Discord via GitHub Actions.

## 🚀 Features
* **Automated Scheduling:** Runs automatically every weekday at market close (1:00 PM PST) via GitHub Actions CRON.
* **Headless Scraping:** Uses Playwright to scrape data from CNBC without API costs.
* **Cloud Deployment:** Fully containerized workflow running on Ubuntu runners.
* **Secure:** Uses GitHub Secrets to protect Webhook URLs.
* **Discord Integration:** Delivers formatted, readable tables directly to a private Discord server.

## 🛠️ Tech Stack
* **Language:** Python 3.9
* **Automation:** GitHub Actions (CI/CD)
* **Browser Automation:** Playwright
* **Notifications:** Discord Webhooks
* **Database:** SQLite

## 📊 Sample Output
**🚀 Daily Portfolio Update**
**Total Net Worth:** $121,213.22

| TICKER | PRICE   | SHARES | VALUE      | NEWS |
| :--- | :--- | :--- | :--- | :--- |
| UBER   | $84.55  | 127    | $10,737.85 | Nvidia CEO said... |
| VTI    | $342.46 | 140    | $47,944.40 | Vanguard Total... |

## 💻 How it Works
The `daily_scan.yml` workflow triggers the `PortfolioManager` class, which initializes a headless browser to scrape data for configured tickers. Data is processed, saved to a local SQLite database for history, and formatted into a payload sent to a Discord Webhook.
