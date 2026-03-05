import sqlite3
import pandas as pd
from datetime import datetime, timedelta

DB_PATH = 'news_scraper.db'
OUTPUT_XLSX = 'ai_articles_last3months_india.xlsx'

# Calculate date 3 months ago (approx 90 days)
three_months_ago = (datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%d')

# Connect to SQLite DB
conn = sqlite3.connect(DB_PATH)

# Build query: sector = 'artificial intelligence', region = 'india', published_at >= three_months_ago
query = """
SELECT title, url, full_body, author, agency, published_at, sector, region, word_count, summary, title_hash, scraped_at, scrape_job_id
FROM articles
WHERE sector = 'artificial intelligence'
  AND region = 'india'
  AND date(published_at) >= date(?)
"""

df = pd.read_sql_query(query, conn, params=(three_months_ago,))

# Optional: filter rows containing any of the large keyword lists in title or full_body (skip for speed)
# Save to Excel
df.to_excel(OUTPUT_XLSX, index=False)
print(f"Exported {len(df)} rows to {OUTPUT_XLSX}")
conn.close()
