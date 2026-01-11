
import sqlite3

def init_db():
    # Connect to a file named 'portfolio.db'. 
    # If it doesn't exist, Python creates it automatically.
    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()

    # Create a table to hold the snapshots
    # We store: Timestamp, Ticker, Price, Shares, and News
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_time TEXT,
            ticker TEXT,
            price REAL,
            shares REAL,
            value REAL,
            news_headline TEXT
        )
    ''')

    # Commit the changes and close
    conn.commit()
    conn.close()
    print("✅ Database 'portfolio.db' created successfully.")

if __name__ == "__main__":
    init_db()