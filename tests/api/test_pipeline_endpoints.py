"""Integration tests for pipeline CRUD REST endpoints.

Requires a running REST API server. Configure token and host_ip below.
Run: uv run tests/api/test_pipeline_endpoints.py
"""
import requests
from datetime import datetime

token = "<token>"
host_ip = "localhost"

BASE = f"http://{host_ip}:8000"
HEADERS = {"Authorization": f"Bearer {token}"}

# Test constants
TEST_ARTIFACT_UUID = "d65a2db0-ffec-5c15-8d3e-b28cf9326a32"
TEST_PIPELINE_ID = f"TEST-API-{datetime.now().strftime('%Y%m%d%H%M%S')}"
TEST_DATETIME = datetime.now().isoformat()

# These paths must match PGSRaw/SpectralRaw nodes linked to the test UUID.
# The DB integration test creates temporary ones; for this test, use paths
# that exist in your DB or run the DB integration test first.
PGS_RAW_INPUT = "/test/pgs_raw/input"
SPEC_RAW_INPUT = "/test/spectral_raw/input"
PGS_PROCESSED_OUTPUT = f"/test/pgs_processed/{TEST_PIPELINE_ID}"
SPEC_PROCESSED_OUTPUT = f"/test/spectral_processed/{TEST_PIPELINE_ID}"
REGISTERED_OUTPUT = f"/test/registered/{TEST_PIPELINE_ID}"
WEB_OUTPUT = f"/test/web_processed/{TEST_PIPELINE_ID}"


def post(path, json):
    resp = requests.post(f"{BASE}{path}", headers=HEADERS, json=json)
    return resp


def put(path, json):
    resp = requests.put(f"{BASE}{path}", headers=HEADERS, json=json)
    return resp


def get(path):
    resp = requests.get(f"{BASE}{path}", headers=HEADERS)
    return resp


# --- POST /pipelines ---

print("POST /pipelines:")
resp = post("/pipelines", {
    "pipeline_id": TEST_PIPELINE_ID,
    "artifact_uuid": TEST_ARTIFACT_UUID,
    "datetime": TEST_DATETIME,
})
print(f"  Status: {resp.status_code}")
print(f"  Response: {resp.json()}")
assert resp.status_code == 201, f"Expected 201 but got {resp.status_code}"
data = resp.json()
assert data['pipeline_id'] == TEST_PIPELINE_ID
assert data['artifact_uuid'] == TEST_ARTIFACT_UUID
assert data['datetime'] == TEST_DATETIME
print("  ✓ Pipeline created")

# Bad UUID
print("\nPOST /pipelines (bad UUID):")
resp = post("/pipelines", {
    "pipeline_id": "SHOULD-NOT-EXIST",
    "artifact_uuid": "nonexistent-uuid",
    "datetime": TEST_DATETIME,
})
print(f"  Status: {resp.status_code}")
assert resp.status_code == 404
print("  ✓ Correctly returned 404")

# --- POST /pipelines/{id}/processes (PGS) ---

print(f"\nPOST /pipelines/{TEST_PIPELINE_ID}/processes (PGS):")
resp = post(f"/pipelines/{TEST_PIPELINE_ID}/processes", {
    "stage": "PGS",
    "input_dataset_paths": [PGS_RAW_INPUT],
    "output_dataset_path": PGS_PROCESSED_OUTPUT,
    "slurm_id": "99001",
    "start_datetime": TEST_DATETIME,
})
print(f"  Status: {resp.status_code}")
print(f"  Response: {resp.json()}")
assert resp.status_code == 201
data = resp.json()
assert data['proc_type'] == 'PGS'
assert data['status'] == 'submitted'
print("  ✓ PGS process created")

# --- POST /pipelines/{id}/processes (SPEC) ---

print(f"\nPOST /pipelines/{TEST_PIPELINE_ID}/processes (SPEC):")
resp = post(f"/pipelines/{TEST_PIPELINE_ID}/processes", {
    "stage": "SPEC",
    "input_dataset_paths": [SPEC_RAW_INPUT],
    "output_dataset_path": SPEC_PROCESSED_OUTPUT,
    "slurm_id": "99002",
    "start_datetime": TEST_DATETIME,
})
print(f"  Status: {resp.status_code}")
print(f"  Response: {resp.json()}")
assert resp.status_code == 201
assert resp.json()['proc_type'] == 'SPEC'
print("  ✓ SPEC process created")

# Invalid stage
print(f"\nPOST /pipelines/{TEST_PIPELINE_ID}/processes (invalid stage):")
resp = post(f"/pipelines/{TEST_PIPELINE_ID}/processes", {
    "stage": "INVALID",
    "input_dataset_paths": ["/fake"],
    "output_dataset_path": "/fake/out",
    "slurm_id": "0",
    "start_datetime": TEST_DATETIME,
})
print(f"  Status: {resp.status_code}")
assert resp.status_code == 400
print("  ✓ Correctly returned 400 for invalid stage")

# --- PUT /pipelines/{id}/processes/PGS/status ---

print(f"\nPUT /pipelines/{TEST_PIPELINE_ID}/processes/PGS/status (completed):")
end_dt = datetime.now().isoformat()
resp = put(f"/pipelines/{TEST_PIPELINE_ID}/processes/PGS/status", {
    "status": "completed",
    "end_datetime": end_dt,
})
print(f"  Status: {resp.status_code}")
print(f"  Response: {resp.json()}")
assert resp.status_code == 200
assert resp.json()['proc_type'] == 'PGS'
assert resp.json()['status'] == 'completed'
print("  ✓ PGS status updated to completed")

# Update SPEC to completed too
print(f"\nPUT /pipelines/{TEST_PIPELINE_ID}/processes/SPEC/status (completed):")
resp = put(f"/pipelines/{TEST_PIPELINE_ID}/processes/SPEC/status", {
    "status": "completed",
    "end_datetime": datetime.now().isoformat(),
})
assert resp.status_code == 200
print("  ✓ SPEC status updated to completed")

# Invalid status
print(f"\nPUT /pipelines/{TEST_PIPELINE_ID}/processes/PGS/status (invalid status):")
resp = put(f"/pipelines/{TEST_PIPELINE_ID}/processes/PGS/status", {
    "status": "running",
    "end_datetime": end_dt,
})
print(f"  Status: {resp.status_code}")
assert resp.status_code == 400
print("  ✓ Correctly returned 400 for invalid status")

# --- GET /pipelines/{id}/confirmation ---

print(f"\nGET /pipelines/{TEST_PIPELINE_ID}/confirmation:")
resp = get(f"/pipelines/{TEST_PIPELINE_ID}/confirmation")
print(f"  Status: {resp.status_code}")
print(f"  Response: {resp.json()}")
assert resp.status_code == 200
data = resp.json()
assert data['pipeline_id'] == TEST_PIPELINE_ID
assert data['artifact_uuid'] == TEST_ARTIFACT_UUID
assert 'stages' in data
assert 'status' in data
proc_types = [s['proc_type'] for s in data['stages']]
assert 'PGS' in proc_types
assert 'SPEC' in proc_types
print(f"  ✓ Pipeline confirmation: status={data['status']}, {len(data['stages'])} stages")

# Not found
print("\nGET /pipelines/nonexistent/confirmation:")
resp = get("/pipelines/nonexistent/confirmation")
print(f"  Status: {resp.status_code}")
assert resp.status_code == 404
print("  ✓ Correctly returned 404")

print(f"\nAll pipeline endpoint tests passed! (pipeline: {TEST_PIPELINE_ID})")
print("NOTE: Test nodes remain in the DB. Run the DB integration test for full cleanup.")
