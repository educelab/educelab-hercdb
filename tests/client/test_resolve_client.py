"""Integration tests for HercClient.resolve.

Requires a running REST API server. Configure host_ip and token below.
Run: uv run tests/client/test_resolve_client.py
"""
import requests

from educelab.hercdb.client import HercClient

token = "<token>"
host_ip = "localhost"

client = HercClient(host=host_ip, token=token)


# --- resolve ---

print("client.resolve('421'):")
results = client.resolve("421")
assert len(results) == 1
assert results[0]["displayName"] == "421"
assert results[0]["score"] == 100
assert results[0]["parent_pherc"] is None
print(f"  ✓ exact match scored 100")

print("\nclient.resolve('118 a') (whitespace normalized):")
results = client.resolve("118 a")
assert results[0]["displayName"] == "118a"
assert results[0]["score"] == 100
print(f"  ✓ '118 a' collapsed to exact '118a' match")

print("\nclient.resolve('Cass', label='Cornice', parent_pherc='72'):")
results = client.resolve("Cass", label="Cornice", parent_pherc="72")
assert len(results) >= 1
top = results[0]
assert top["displayName"] == "Cass.7"
assert top["parent_pherc"] == {"displayName": "72", "score": 100}
print(f"  ✓ {top['displayName']} under PHerc 72 (score={top['score']})")

print("\nclient.resolve(...) bad label -> raises:")
try:
    client.resolve("x", label="Bogus")
    raise AssertionError("Expected HTTPError")
except requests.HTTPError as e:
    assert e.response.status_code == 400
    print(f"  ✓ 400 surfaced as HTTPError")

print("\nclient.resolve(...) no hits -> []:")
results = client.resolve("ZZZZZZZZ", threshold=80)
assert results == []
print("  ✓ empty list, no exception")

print("\nclient.resolve(...) custom limit:")
results = client.resolve("1", threshold=0, limit=3)
assert len(results) <= 3
print(f"  ✓ {len(results)} <= limit=3")

print("\nAll resolve-client tests passed!")
