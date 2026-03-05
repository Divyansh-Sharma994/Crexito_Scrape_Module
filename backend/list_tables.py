import os, sqlite3, sys

DB_PATH = os.path.abspath('news_scraper.db')
print('DB path:', DB_PATH)
if not os.path.exists(DB_PATH):
    sys.exit('Database file not found')

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cur.fetchall()
print('Tables:', tables)
for (tbl,) in tables:
    print('\nSchema for', tbl)
    cur.execute(f"PRAGMA table_info({tbl});")
    for row in cur.fetchall():
        print(row)
conn.close()
