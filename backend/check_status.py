import sqlite3
import datetime

def main():
    conn = sqlite3.connect('news_scraper.db')
    cursor = conn.cursor()
    
    print("--- RECENT SCRAPE JOBS (TODAY) ---")
    cursor.execute('SELECT id, sector, started_at, total_found, total_scraped, status, error FROM scrape_jobs WHERE started_at > "2026-03-04" ORDER BY started_at DESC')
    for row in cursor.fetchall():
        print(f"ID: {row[0][:8]} | Sector: {row[1]} | Started: {row[2]} | Found: {row[3]} | Scraped: {row[4]} | Status: {row[5]}")
        if row[6]: print(f"  Error: {row[6]}")

    print("\n--- ACTIVE JOB ARTICLES (TOP 3) ---")
    cursor.execute('SELECT id FROM scrape_jobs ORDER BY started_at DESC LIMIT 1')
    job_id = cursor.fetchone()[0]
    cursor.execute('SELECT title, agency, author, word_count, length(full_body) FROM articles WHERE scrape_job_id = ? AND word_count > 0 ORDER BY id DESC LIMIT 3', (job_id,))
    articles = cursor.fetchall()
    if not articles:
        print("No articles scraped yet for this job.")
    for row in articles:
        print(f"Title: {row[0][:50]}...")
        print(f"  Agency: {row[1]} | Author: {row[2]} | Word Count: {row[3]} | Body Length: {row[4]}")
        
    conn.close()

if __name__ == "__main__":
    main()
