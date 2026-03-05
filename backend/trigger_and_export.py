import os, sys, time, json
import requests

BASE_URL = 'http://127.0.0.1:8000'

# Define scrape parameters (AI sector, India, last 90 days)
from datetime import datetime, timedelta
end_date = datetime.utcnow().date()
start_date = end_date - timedelta(days=90)
payload = {
    'sector': 'artificial intelligence',
    'region': 'india',
    'date_from': start_date.isoformat(),
    'date_to': end_date.isoformat(),
    'search_mode': 'broad'
}

print('Starting scrape job...')
resp = requests.post(f'{BASE_URL}/api/scrape/start', json=payload)
if resp.status_code != 200:
    print('Failed to start job:', resp.status_code, resp.text)
    sys.exit(1)
job_info = resp.json()
job_id = job_info.get('job_id')
print('Job started, id:', job_id)

# Poll job status until completed or failed
status_url = f'{BASE_URL}/api/scrape/job/{job_id}'
while True:
    r = requests.get(status_url)
    if r.status_code != 200:
        print('Error fetching job status:', r.status_code, r.text)
        break
    data = r.json()
    status = data.get('status')
    print('Job status:', status)
    if status in ('completed', 'failed', 'interrupted'):
        break
    time.sleep(10)

print('Job finished with status:', status)
# After job, run export script to generate Excel
export_cmd = 'python backend/export_ai_articles_with_keywords.py'
print('Running export script...')
os.system(export_cmd)
