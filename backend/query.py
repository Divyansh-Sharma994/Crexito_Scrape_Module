import sqlite3, json
db=sqlite3.connect('news_scraper.db')
rows=db.execute("SELECT id, sector, started_at, date_from, date_to, total_found, cumulative_found, total_scraped, phase_stats FROM scrape_jobs WHERE status='running'").fetchall()
with open('output.json', 'w') as f:
    json.dump(rows, f, indent=2)
