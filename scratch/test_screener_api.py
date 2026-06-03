from fastapi.testclient import TestClient
from stocks.api.main import app

def test():
    client = TestClient(app)
    
    # Test only_nr7
    r = client.post("/api/v1/screeners/run", json={"only_nr7": True})
    print(f"only_nr7 status: {r.status_code}")
    if r.status_code == 200:
        res = r.json()
        print(f"only_nr7 results count: {len(res)}")
        if res:
            print(f"First match: {res[0]['symbol']} (is_nr7: {res[0].get('is_nr7')})")

    # Test only_inside_bar
    r = client.post("/api/v1/screeners/run", json={"only_inside_bar": True})
    print(f"only_inside_bar status: {r.status_code}")
    if r.status_code == 200:
        res = r.json()
        print(f"only_inside_bar results count: {len(res)}")
        if res:
            print(f"First match: {res[0]['symbol']} (is_inside_bar: {res[0].get('is_inside_bar')})")

    # Test only_gap_up
    r = client.post("/api/v1/screeners/run", json={"only_gap_up": True})
    print(f"only_gap_up status: {r.status_code}")
    if r.status_code == 200:
        res = r.json()
        print(f"only_gap_up results count: {len(res)}")
        if res:
            print(f"First match: {res[0]['symbol']} (is_gap_up: {res[0].get('is_gap_up')})")

    # Test only_gap_down
    r = client.post("/api/v1/screeners/run", json={"only_gap_down": True})
    print(f"only_gap_down status: {r.status_code}")
    if r.status_code == 200:
        res = r.json()
        print(f"only_gap_down results count: {len(res)}")
        if res:
            print(f"First match: {res[0]['symbol']} (is_gap_down: {res[0].get('is_gap_down')})")

if __name__ == "__main__":
    test()
