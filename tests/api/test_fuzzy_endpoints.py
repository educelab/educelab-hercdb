"""Integration tests for the /resolve endpoint.

Requires a running REST API server. Configure token and host_ip below.
Run: uv run tests/api/test_fuzzy_endpoints.py
"""
import requests

token = "<token>"
host_ip = "localhost"

BASE = f"http://{host_ip}:8000"
HEADERS = {"Authorization": f"Bearer {token}"}


def get(path, params=None):
    return requests.get(f"{BASE}{path}", headers=HEADERS, params=params)


def post(path, json):
    return requests.post(f"{BASE}{path}", headers=HEADERS, json=json)


# --- GET /resolve ---

print("GET /resolve exact PHerc '421':")
resp = get("/resolve", params={"name": "421", "label": "PHerc"})
print(f"  Status: {resp.status_code}")
assert resp.status_code == 200
body = resp.json()
assert isinstance(body, list) and len(body) == 1
assert body[0]["displayName"] == "421"
assert body[0]["score"] == 100
assert body[0]["parent_pherc"] is None
assert body[0]["parent_cornice"] is None
assert "nodeID" in body[0]
assert "name" in body[0]
print("  ✓ exact match scored 100, nodeID and name included")

print("\nGET /resolve whitespace variant '118 a' -> 118a exact:")
resp = get("/resolve", params={"name": "118 a", "label": "PHerc"})
print(f"  Status: {resp.status_code}")
assert resp.status_code == 200
body = resp.json()
assert body[0]["displayName"] == "118a"
assert body[0]["score"] == 100
print("  ✓ whitespace-stripped to exact-match short-circuit")

print("\nGET /resolve Cornice 'Cass' under fuzzy parent '72':")
resp = get("/resolve", params={"name": "Cass", "label": "Cornice", "parent_pherc": "72"})
print(f"  Status: {resp.status_code}")
assert resp.status_code == 200
body = resp.json()
assert len(body) >= 1
top = body[0]
assert top["displayName"] == "Cass.7"
assert top["parent_pherc"] == {"displayName": "72", "score": 100}
print(f"  ✓ {top['displayName']} (score={top['score']}) under PHerc 72")

print("\nGET /resolve invalid label -> 400:")
resp = get("/resolve", params={"name": "x", "label": "Bogus"})
print(f"  Status: {resp.status_code}")
assert resp.status_code == 400
assert "Bogus" in resp.json()["detail"]
print("  ✓ Correctly returned 400 with clear message")

print("\nGET /resolve no hits -> 200 []:")
resp = get("/resolve", params={"name": "ZZZZZZZZ", "label": "PHerc", "threshold": 80})
print(f"  Status: {resp.status_code}")
assert resp.status_code == 200
assert resp.json() == []
print("  ✓ Empty result returned as 200 + [] (discovery endpoint)")

print("\nGET /resolve threshold/limit caps output:")
resp = get(
    "/resolve",
    params={"name": "1", "label": "PHerc", "threshold": 0, "limit": 3},
)
assert resp.status_code == 200
assert len(resp.json()) <= 3
print(f"  ✓ Returned {len(resp.json())} <= limit=3")


# --- POST /search strict display_name path ---

print("\nPOST /search strict 'display_name' returns exact match:")
resp = post("/search", {"display_name": "421"})
print(f"  Status: {resp.status_code}")
assert resp.status_code == 200
assert resp.json()["PHercs"] == ["421"]
print("  ✓ Strict path returns exact match")

print("\nAll fuzzy endpoint tests passed!")
