
import sqlite3
import pandas as pd

def view_data():
    # 1. Connect to the database
    conn = sqlite3.connect('portfolio.db')
    
    # 2. Run a SQL Query
    # "SELECT *" means "Grab everything"
    query = "SELECT * FROM portfolio_history ORDER BY id DESC"
    
    # 3. Use Pandas to make it look pretty
    try:
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("⚠️ Database is empty. Run the bot first!")
        else:
            print("\n📊 CURRENT DATABASE CONTENTS:")
            print("-" * 80)
            # Print the first 20 rows so we don't flood the terminal
            print(df.head(20).to_string(index=False)) 
            print("-" * 80)
            print(f"✅ Total Rows: {len(df)}")
            
    except Exception as e:
        print(f"Error reading database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    view_data()