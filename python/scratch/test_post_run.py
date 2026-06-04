import requests
import json

url = "http://localhost:8000/api/v1/screeners/run"
headers = {"Content-Type": "application/json"}
payload = {} # Empty filter body (triggers full screener run)

try:
    response = requests.post(url, json=payload, headers=headers)
    print("Status Code:", response.status_code)
    try:
        print("Response (JSON):", json.dumps(response.json(), indent=2))
    except Exception:
        print("Response (Text):", response.text)
except Exception as e:
    print("Request failed:", e)
