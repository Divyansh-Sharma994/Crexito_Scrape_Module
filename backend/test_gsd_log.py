import requests, json, sys, time
BASE='http://127.0.0.1:8000'
payload = {
    'sector': 'artificial intelligence',
    'region': 'india',
    'date_from': '2026-03-03',
    'date_to': '2026-03-04',
    'search_mode': 'broad'
}
try:
    r = requests.post(f'{BASE}/api/scrape/start', json=payload)
    if r.status_code == 200:
        print('Job started:', r.json())
    else:
        print('Failed to start:', r.status_code, r.text)
except Exception as e:
    print('Error:', e)
