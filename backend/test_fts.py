import sqlite3
import os

db_path = "news_scraper.db"
if not os.path.exists(db_path):
    print("DB not found")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Rebuild the index
print("Rebuilding FTS5 index...")
cur.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
conn.commit()

# Check how many articles we have
cur.execute("SELECT COUNT(*) FROM articles")
total_arts = cur.fetchone()[0]
print(f"Total articles: {total_arts}")

# Search for common word like 'India' across title and full_body
# Standard search first
cur.execute("SELECT COUNT(*) FROM articles WHERE title LIKE '%India%' OR full_body LIKE '%India%'")
print(f"Standard results for 'India': {cur.fetchone()[0]}")

# FTS5 search
# Note: FTS5 query uses double quotes for literal phrases
fts_query = '"India"'
cur.execute("SELECT COUNT(*) FROM articles_fts WHERE articles_fts MATCH ?", (fts_query,))
print(f"FTS5 results for 'India': {cur.fetchone()[0]}")

# Try joining them
cur.execute("""
    SELECT COUNT(*) FROM articles a 
    JOIN articles_fts ON articles_fts.rowid = a.id 
    WHERE articles_fts MATCH ?
""", (fts_query,))
print(f"FTS5 Join results for 'India': {cur.fetchone()[0]}")

conn.close()
