"""Integration tests for pipeline CRUD REST endpoints.

Requires a running REST API server AND a live Neo4j connection: the script seeds
the temporary PGSRaw/SpectralRaw input nodes the process endpoints need, then
removes them (and the test pipeline) on exit.

Pass the token and host_ip on the command line.
Run: uv run tests/api/test_pipeline_endpoints.py <token> [host_ip]
"""
import argparse
import atexit

import requests
from datetime import datetime

from educelab import hercdb

parser = argparse.ArgumentParser(description="Integration tests for pipeline CRUD REST endpoints.")
parser.add_argument("token", help="Bearer token for the REST API")
parser.add_argument("host_ip", nargs="?", default="localhost", help="Host IP of the REST API server (default: localhost)")
args = parser.parse_args()

token = args.token
host_ip = args.host_ip

BASE = f"http://{host_ip}:8000"
HEADERS = {"Authorization": f"Bearer {token}"}

# Test constants
TEST_ARTIFACT_UUID = "d65a2db0-ffec-5c15-8d3e-b28cf9326a32"
TEST_PIPELINE_ID = f"TEST-API-{datetime.now().strftime('%Y%m%d%H%M%S')}"
TEST_DATETIME = datetime.now().isoformat()

# These paths must match PGSRaw/SpectralRaw nodes linked to the test UUID.
# This script seeds them in the DB below and tears them down on exit.
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


# --- DB seed: create the temporary raw input datasets the process endpoints
# need, and register cleanup so they (and the test pipeline) are removed on exit
# even if an assertion fails. ---

hercdb.config._load_config()
db = hercdb.connect()
db.verify_connection()

artifact = db.find_artifact_name_by_uuid(TEST_ARTIFACT_UUID)
assert artifact is not None, (
    f"Test artifact UUID {TEST_ARTIFACT_UUID} not found in DB. "
    "Update TEST_ARTIFACT_UUID to a valid EduceLabID."
)
print(f"Using artifact: {artifact} (UUID: {TEST_ARTIFACT_UUID})")
print(f"Test pipeline ID: {TEST_PIPELINE_ID}\n")

db._run_query("""
    MATCH (e:EduceLabID {uuid: $uuid})
    MERGE (pgs:PGSRaw {path: $pgs_path})
    MERGE (spec:SpectralRaw {path: $spec_path})
    MERGE (pgs)-[:BELONGS_TO]->(e)
    MERGE (spec)-[:BELONGS_TO]->(e)
    """, uuid=TEST_ARTIFACT_UUID, pgs_path=PGS_RAW_INPUT, spec_path=SPEC_RAW_INPUT)


def _cleanup():
    """Remove all test nodes created during the run. Runs on exit (incl. failure)."""
    db._run_query("""
        MATCH (p:Pipeline {pipeline_id: $pipeline_id})
        OPTIONAL MATCH (p)<-[:STAGE_OF]-(proc:Process)
        OPTIONAL MATCH (proc)-[:OUTPUT]->(out)
        DETACH DELETE proc, out, p
        """, pipeline_id=TEST_PIPELINE_ID)
    for path in [PGS_RAW_INPUT, SPEC_RAW_INPUT, PGS_PROCESSED_OUTPUT,
                 SPEC_PROCESSED_OUTPUT, REGISTERED_OUTPUT, WEB_OUTPUT]:
        db._run_query("MATCH (n {path: $path}) DETACH DELETE n", path=path)
    print(f"\nCleaned up test pipeline: {TEST_PIPELINE_ID}")
    db.close()


atexit.register(_cleanup)


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
    "proc_type": "PGS",
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
    "proc_type": "SPEC",
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

# --- POST /pipelines/{id}/processes (REG) ---
# REG consumes both the PGS and SPEC processed outputs, so its stage should
# report two input dataset paths.

print(f"\nPOST /pipelines/{TEST_PIPELINE_ID}/processes (REG):")
resp = post(f"/pipelines/{TEST_PIPELINE_ID}/processes", {
    "proc_type": "REG",
    "input_dataset_paths": [PGS_PROCESSED_OUTPUT, SPEC_PROCESSED_OUTPUT],
    "output_dataset_path": REGISTERED_OUTPUT,
    "slurm_id": "99003",
    "start_datetime": TEST_DATETIME,
})
print(f"  Status: {resp.status_code}")
print(f"  Response: {resp.json()}")
assert resp.status_code == 201
assert resp.json()['proc_type'] == 'REG'
print("  ✓ REG process created")

# Invalid stage
print(f"\nPOST /pipelines/{TEST_PIPELINE_ID}/processes (invalid stage):")
resp = post(f"/pipelines/{TEST_PIPELINE_ID}/processes", {
    "proc_type": "INVALID",
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

# --- GET /pipelines/{id}/stages ---
# Each stage should carry the new dataset-path fields:
#   input_dataset_paths (list[str]), output_dataset_path (str | None).

print(f"\nGET /pipelines/{TEST_PIPELINE_ID}/stages:")
resp = get(f"/pipelines/{TEST_PIPELINE_ID}/stages")
print(f"  Status: {resp.status_code}")
print(f"  Response: {resp.json()}")
assert resp.status_code == 200
stages = {s['proc_type']: s for s in resp.json()}

for stage in stages.values():
    assert 'input_dataset_paths' in stage, "stage missing input_dataset_paths"
    assert isinstance(stage['input_dataset_paths'], list)
    assert 'output_dataset_path' in stage, "stage missing output_dataset_path"

assert stages['PGS']['input_dataset_paths'] == [PGS_RAW_INPUT]
assert stages['PGS']['output_dataset_path'] == PGS_PROCESSED_OUTPUT
assert stages['SPEC']['input_dataset_paths'] == [SPEC_RAW_INPUT]
assert stages['SPEC']['output_dataset_path'] == SPEC_PROCESSED_OUTPUT

# REG consumes both processed outputs -> two input paths (order not guaranteed).
assert set(stages['REG']['input_dataset_paths']) == {PGS_PROCESSED_OUTPUT, SPEC_PROCESSED_OUTPUT}
assert stages['REG']['output_dataset_path'] == REGISTERED_OUTPUT
print("  ✓ Stages carry input_dataset_paths / output_dataset_path (REG has 2 inputs)")

# Not found
print("\nGET /pipelines/nonexistent/stages:")
resp = get("/pipelines/nonexistent/stages")
print(f"  Status: {resp.status_code}")
assert resp.status_code == 404
print("  ✓ Correctly returned 404")

print(f"\nAll pipeline endpoint tests passed! (pipeline: {TEST_PIPELINE_ID})")
