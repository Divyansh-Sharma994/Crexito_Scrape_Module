import os, sqlite3

# Determine absolute path to DB (same as backend/database.py)
DB_PATH = os.path.abspath('news_scraper.db')
print('Looking at DB:', DB_PATH)
if not os.path.exists(DB_PATH):
    raise FileNotFoundError('Database file not found')

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
print('Tables:', cur.fetchall())
# Show schema for each table
for (tbl,) in cur.fetchall():
    print('\nSchema for', tbl)
    cur.execute(f"PRAGMA table_info({tbl});")
    for row in cur.fetchall():
        print(row)
conn.close()
