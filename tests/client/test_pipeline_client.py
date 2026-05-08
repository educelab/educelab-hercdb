"""Integration tests for HercClient pipeline CRUD methods.

Requires a running REST API server. Configure host_ip and token below.
Run: uv run tests/client/test_pipeline_client.py
"""
from datetime import datetime
from educelab.hercdb.client import HercClient

token = "<token>"
host_ip = "localhost"

client = HercClient(host=host_ip, token=token)

# Test constants
TEST_ARTIFACT_UUID = "d65a2db0-ffec-5c15-8d3e-b28cf9326a32"
TEST_PIPELINE_ID = f"TEST-CLIENT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
TEST_DATETIME = datetime.now().isoformat()

# These paths must match PGSRaw/SpectralRaw nodes linked to the test UUID
PGS_RAW_INPUT = "/test/pgs_raw/input"
SPEC_RAW_INPUT = "/test/spectral_raw/input"
PGS_PROCESSED_OUTPUT = f"/test/pgs_processed/{TEST_PIPELINE_ID}"
SPEC_PROCESSED_OUTPUT = f"/test/spectral_processed/{TEST_PIPELINE_ID}"
REGISTERED_OUTPUT = f"/test/registered/{TEST_PIPELINE_ID}"

# --- initialize_pipeline ---

print("client.initialize_pipeline():")
result = client.initialize_pipeline(TEST_PIPELINE_ID, TEST_ARTIFACT_UUID, TEST_DATETIME)
print(f"  {result}")
assert result['pipeline_id'] == TEST_PIPELINE_ID
assert result['artifact_uuid'] == TEST_ARTIFACT_UUID
assert result['datetime'] == TEST_DATETIME
print("  ✓ Pipeline created")

# --- initialize_process (PGS) ---

print("\nclient.initialize_process(PGS):")
result = client.initialize_process(
    pipeline_id=TEST_PIPELINE_ID,
    proc_type="PGS",
    input_dataset_paths=[PGS_RAW_INPUT],
    output_dataset_path=PGS_PROCESSED_OUTPUT,
    slurm_id="88001",
    start_datetime=TEST_DATETIME,
)
print(f"  {result}")
assert result['proc_type'] == 'PGS'
assert result['status'] == 'submitted'
print("  ✓ PGS process created")

# --- initialize_process (SPEC) ---

print("\nclient.initialize_process(SPEC):")
result = client.initialize_process(
    pipeline_id=TEST_PIPELINE_ID,
    proc_type="SPEC",
    input_dataset_paths=[SPEC_RAW_INPUT],
    output_dataset_path=SPEC_PROCESSED_OUTPUT,
    slurm_id="88002",
    start_datetime=TEST_DATETIME,
)
print(f"  {result}")
assert result['proc_type'] == 'SPEC'
assert result['status'] == 'submitted'
print("  ✓ SPEC process created")

# --- update_process_status (PGS → completed) ---

print("\nclient.update_process_status(PGS, completed):")
end_dt = datetime.now().isoformat()
result = client.update_process_status(TEST_PIPELINE_ID, "PGS", "completed", end_dt)
print(f"  {result}")
assert result['proc_type'] == 'PGS'
assert result['status'] == 'completed'
print("  ✓ PGS updated to completed")

# --- update_process_status (SPEC → completed) ---

print("\nclient.update_process_status(SPEC, completed):")
result = client.update_process_status(TEST_PIPELINE_ID, "SPEC", "completed", datetime.now().isoformat())
print(f"  {result}")
assert result['status'] == 'completed'
print("  ✓ SPEC updated to completed")

# --- initialize_process (REG) ---

print("\nclient.initialize_process(REG):")
result = client.initialize_process(
    pipeline_id=TEST_PIPELINE_ID,
    proc_type="REG",
    input_dataset_paths=[PGS_PROCESSED_OUTPUT, SPEC_PROCESSED_OUTPUT],
    output_dataset_path=REGISTERED_OUTPUT,
    slurm_id="88003",
    start_datetime=TEST_DATETIME,
)
print(f"  {result}")
assert result['proc_type'] == 'REG'
assert result['status'] == 'submitted'
print("  ✓ REG process created")

# --- update_process_status (REG → completed) ---

print("\nclient.update_process_status(REG, completed):")
result = client.update_process_status(TEST_PIPELINE_ID, "REG", "completed", datetime.now().isoformat())
print(f"  {result}")
assert result['status'] == 'completed'
print("  ✓ REG updated to completed")

# --- get_pipeline_confirmation ---

print("\nclient.get_pipeline_confirmation():")
result = client.get_pipeline_confirmation(TEST_PIPELINE_ID)
print(f"  pipeline_id: {result['pipeline_id']}")
print(f"  artifact_uuid: {result['artifact_uuid']}")
print(f"  datetime: {result['datetime']}")
print(f"  status: {result['status']}")
print(f"  stages: {len(result['stages'])}")
for s in result['stages']:
    print(f"    {s['proc_type']}: {s['status']} (slurm: {s['slurm_id']})")

assert result['pipeline_id'] == TEST_PIPELINE_ID
assert result['artifact_uuid'] == TEST_ARTIFACT_UUID
assert result['status'] == 'completed'
assert len(result['stages']) == 3
proc_types = [s['proc_type'] for s in result['stages']]
assert 'PGS' in proc_types
assert 'SPEC' in proc_types
assert 'REG' in proc_types
print("  ✓ Pipeline confirmation verified — all 3 stages completed")

print(f"\nAll client pipeline tests passed! (pipeline: {TEST_PIPELINE_ID})")
print("NOTE: Test nodes remain in the DB. Run the DB integration test for full cleanup.")
