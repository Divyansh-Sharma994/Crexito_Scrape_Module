import sqlite3
import sys
try:
    conn = sqlite3.connect("news_scraper.db")
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM articles WHERE full_body IS NULL OR length(full_body) < 100")
    print("Null/Short bodies:", cur.fetchone()[0])
    cur.execute("SELECT count(*) FROM articles WHERE full_body IS NOT NULL AND length(full_body) >= 100")
    print("Valid bodies:", cur.fetchone()[0])
    cur.execute("SELECT url, full_body FROM articles WHERE full_body IS NULL OR length(full_body) < 100 LIMIT 10")
    print("\nSample failed URLs:")
    for row in cur.fetchall():
        print(row[0])
    conn.close()
except Exception as e:
    print(e)
