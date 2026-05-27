"""Integration tests for HercClient.resolve and the fuzzy /search kwarg.

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


# --- search with fuzzy kwarg ---

print("\nclient.search(display_name_fuzzy='118 a'):")
res = client.search(display_name_fuzzy="118 a")
assert "118a" in res["PHercs"]
print(f"  ✓ snake_case kwarg translated to REST: {res['PHercs']}")

print("\nclient.search(display_name_fuzzy='4211', display_name_fuzzy_threshold=80):")
res = client.search(display_name_fuzzy="4211", display_name_fuzzy_threshold=80)
assert "421" in res["PHercs"]
print(f"  ✓ explicit threshold widens to: {set(res['PHercs'])}")

print("\nclient.search(language='grc', display_name_fuzzy='421') intersection:")
res = client.search(language="grc", display_name_fuzzy="421")
assert "421" in res["PHercs"]
print(f"  ✓ intersection result: {res['PHercs']}")

print("\nclient.search(**{'display-name': '421'}) strict path untouched:")
res = client.search(**{"display-name": "421"})
assert res["PHercs"] == ["421"]
print("  ✓ existing hyphenated-passthrough still works")

print("\nclient.search(display_name_fuzzy='ZZZZZZZZ') no matches -> raises:")
try:
    client.search(display_name_fuzzy="ZZZZZZZZ")
    raise AssertionError("Expected HTTPError on 404")
except requests.HTTPError as e:
    assert e.response.status_code == 404
    print("  ✓ 404 surfaced as HTTPError (matches existing /search behavior)")

print("\nAll resolve-client tests passed!")
