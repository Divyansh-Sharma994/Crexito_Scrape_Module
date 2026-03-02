import httpx
try:
    r = httpx.get("http://127.0.0.1:8000/api/articles/export/xlsx")
    print(f"Status: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")
