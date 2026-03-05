import sqlite3, os, json

DB_PATH = os.path.abspath('news_scraper.db')
print('DB path:', DB_PATH)
if not os.path.exists(DB_PATH):
    raise FileNotFoundError('Database not found')

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
# List tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cur.fetchall()
print('Tables:', tables)
# Print schema for each table
for (tbl,) in tables:
    print('\nSchema for', tbl)
    cur.execute(f"PRAGMA table_info({tbl});")
    cols = cur.fetchall()
    for col in cols:
        print(col)
conn.close()
