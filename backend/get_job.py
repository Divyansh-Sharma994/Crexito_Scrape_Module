import sqlite3
def main():
    conn = sqlite3.connect('news_scraper.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, started_at, total_found, total_scraped, status, error FROM scrape_jobs WHERE id LIKE "5897%"')
    row = cursor.fetchone()
    if row:
        print(f"ID: {row[0]}")
        print(f"Started: {row[1]}")
        print(f"Found: {row[2]}")
        print(f"Scraped: {row[3]}")
        print(f"Status: {row[4]}")
        print(f"Error: {row[5]}")
    else:
        print("Job not found.")
    conn.close()
if __name__ == "__main__":
    main()
