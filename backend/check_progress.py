import sqlite3
def main():
    conn = sqlite3.connect('news_scraper.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM articles WHERE scrape_job_id="5897d34b-da0a-4f33-98a5-f818a1652455" AND word_count > 0')
    count = cursor.fetchone()[0]
    print(f"Scraped Articles with Word Count > 0: {count}")
    
    if count > 0:
        cursor.execute('SELECT title, agency, author, word_count FROM articles WHERE scrape_job_id="5897d34b-da0a-4f33-98a5-f818a1652455" AND word_count > 0 LIMIT 3')
        for row in cursor.fetchall():
            print(f"Title: {row[0][:50]}...")
            print(f"  Agency: {row[1]} | Author: {row[2]} | Words: {row[3]}")
    conn.close()
if __name__ == "__main__":
    main()
