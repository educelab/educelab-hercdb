import argparse

import requests

parser = argparse.ArgumentParser(description="Integration test script for the REST API server.")
parser.add_argument("token", help="Bearer token for the REST API")
parser.add_argument("host_ip", nargs="?", default="localhost", help="Host IP of the REST API server (default: localhost)")
args = parser.parse_args()

token = args.token
host_ip = args.host_ip

headers = {
    "Authorization": f"Bearer {token}"
}

# /check-token endpoint
print("/check-token endpoint:")
print(requests.get(f"http://{host_ip}:8000/check-token", headers=headers).json())

# /home endpoint
print("/home endpoint:") 
print(requests.get(f"http://{host_ip}:8000/home", headers=headers).json())

# /artifacts (by name) endpoint — PHerc
print("/artifacts?pherc=211 endpoint:")
print(requests.get(f"http://{host_ip}:8000/artifacts", headers=headers, params={"pherc": "211"}).json())

# /artifacts (by name) endpoint — Cornice
print("/artifacts?pherc=18&cornice=1 endpoint:")
print(requests.get(f"http://{host_ip}:8000/artifacts", headers=headers, params={"pherc": "18", "cornice": "1"}).json())

# /artifacts (by name) endpoint — Pezzo under Cornice
print("/artifacts?pherc=238&cornice=...&pezzo=... endpoint:")
print(requests.get(f"http://{host_ip}:8000/artifacts", headers=headers,
                   params={"pherc": "238", "cornice": "Scorze da 238 a 239", "pezzo": "5 (238e)"}).json())

# /pherc/<pherc_id>/all-datasets endpoint
print("\n/pherc/<pherc_id>/all-datasets endpoint:")
resp = requests.get(f"http://{host_ip}:8000/pherc/1044/all-datasets", headers=headers)
print(f"  Status: {resp.status_code}")
print(f"  Response: {resp.json()}")

# /pherc/<pherc_id>/all-datasets with type filter
print("\n/pherc/<pherc_id>/all-datasets?dataset_type=PGSRaw endpoint:")
resp = requests.get(f"http://{host_ip}:8000/pherc/1044/all-datasets?dataset_type=PGSRaw", headers=headers)
print(f"  Status: {resp.status_code}")
print(f"  Response: {resp.json()}")

# /pherc/<pherc_id>/all-datasets with newest_completed
print("\n/pherc/<pherc_id>/all-datasets?newest_completed=true endpoint:")
resp = requests.get(f"http://{host_ip}:8000/pherc/1044/all-datasets?newest_completed=true", headers=headers)
print(f"  Status: {resp.status_code}")
print(f"  Response: {resp.json()}")

# /pherc/<pherc_id>/subdivisions endpoint (now returns aliases + educelabids per node)
print("\n/pherc/<pherc_id>/subdivisions endpoint:")
resp = requests.get(f"http://{host_ip}:8000/pherc/1044/subdivisions", headers=headers)
print(f"  Status: {resp.status_code}")
subs = resp.json()
print(f"  Response: {subs}")

# Gather a UUID from subdivisions to exercise the UUID-keyed endpoints
uuids = []
for node in [subs.get("pherc")] + subs.get("cornici", []) + subs.get("pezzi", []):
    if node:
        uuids.extend(node.get("educelabids", []))

if uuids:
    test_uuid = uuids[0]
    # /artifacts/<uuid> endpoint (UUID -> artifact location bridge)
    print(f"\n/artifacts/{test_uuid} endpoint:")
    resp = requests.get(f"http://{host_ip}:8000/artifacts/{test_uuid}", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.json()}")

    # /educelabid/<uuid>/datasets endpoint (chain-pooled, belongs_to_uuid per dataset)
    print(f"\n/educelabid/{test_uuid}/datasets endpoint:")
    resp = requests.get(f"http://{host_ip}:8000/educelabid/{test_uuid}/datasets", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.json()}")

    # With type filter
    print(f"\n/educelabid/{test_uuid}/datasets?dataset_type=PGSRaw endpoint:")
    resp = requests.get(f"http://{host_ip}:8000/educelabid/{test_uuid}/datasets?dataset_type=PGSRaw", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.json()}")

# /pipelines/<pipeline_id>/stages endpoint
print("/pipelines/<pipeline_id>/stages endpoint:")
print(requests.get(f"http://{host_ip}:8000/pipelines/20251222-389/stages", headers=headers).json())

# /pipelines/<pipeline_id>/stages - 3-stage completed pipeline (no WEB)
print("\n/pipelines/20260203-TEST6/stages endpoint (3-stage completed):")
resp = requests.get(f"http://{host_ip}:8000/pipelines/20260203-TEST6/stages", headers=headers)
print(f"  Status: {resp.status_code}")
stages = resp.json()
print(f"  Response: {stages}")
assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}"
assert len(stages) == 3, f"Expected 3 stages but got {len(stages)}"
assert 'WEB' not in [s['stage'] for s in stages], "WEB stage should not be present"
assert all(s['status'] == 'completed' for s in stages), "All stages should be completed"
print("  ✓ 3 stages, all completed, no WEB")

# /pipelines endpoint
print("/pipelines endpoint:")
pipelines = requests.get(f"http://{host_ip}:8000/pipelines", headers=headers).json()
print(pipelines)
test6 = next((p for p in pipelines if p['pipeline_id'] == '20260203-TEST6'), None)
assert test6 is not None, "TEST6 pipeline should appear in /pipelines"
assert test6['status'] == 'completed', f"Expected 'completed' but got '{test6['status']}'"
print(f"  ✓ TEST6 pipeline status: {test6['status']}")
