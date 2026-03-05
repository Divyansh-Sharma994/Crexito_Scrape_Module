import os
import sys
import time
import requests
from datetime import datetime, timedelta

BASE_URL = 'http://127.0.0.1:8000'

# Helper to start a scrape job for a given date range (max 30 days)
def start_job(start_date: str, end_date: str):
    payload = {
        'sector': 'artificial intelligence',
        'region': 'india',
        'date_from': start_date,
        'date_to': end_date,
        'search_mode': 'broad'
    }
    resp = requests.post(f'{BASE_URL}/api/scrape/start', json=payload)
    if resp.status_code != 200:
        print('Failed to start job:', resp.status_code, resp.text)
        sys.exit(1)
    job_id = resp.json().get('job_id')
    print(f'Job started: {job_id} ({start_date} -> {end_date})')
    return job_id

# Poll job status until finished
def wait_job(job_id: str):
    status_url = f'{BASE_URL}/api/scrape/job/{job_id}'
    while True:
        r = requests.get(status_url)
        if r.status_code != 200:
            print('Error fetching status:', r.status_code, r.text)
            break
        data = r.json()
        status = data.get('status')
        print(f'Job {job_id} status: {status}')
        if status in ('completed', 'failed', 'interrupted'):
            return status
        time.sleep(10)

def main():
    # Compute three 30‑day windows covering the last ~90 days
    today = datetime.utcnow().date()
    windows = []
    # First window: today-30 to today
    end = today
    start = end - timedelta(days=30)
    windows.append((start, end))
    # Second window: start-30 to start-1
    end = start - timedelta(days=1)
    start = end - timedelta(days=30)
    windows.append((start, end))
    # Third window: start-30 to start-1
    end = start - timedelta(days=1)
    start = end - timedelta(days=30)
    windows.append((start, end))

    for s, e in windows:
        job_id = start_job(s.isoformat(), e.isoformat())
        final_status = wait_job(job_id)
        print(f'Job {job_id} finished with status: {final_status}')
        if final_status != 'completed':
            print('Stopping further jobs due to failure.')
            sys.exit(1)

    # After all jobs are done, export to Excel
    print('All scrape jobs completed. Exporting to Excel...')
    export_cmd = 'python backend/export_ai_articles_with_keywords.py'
    os.system(export_cmd)
    print('Export finished.')

if __name__ == '__main__':
    main()
