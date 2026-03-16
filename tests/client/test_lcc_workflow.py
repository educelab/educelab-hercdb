"""LCC workflow tests

Requires a running REST API server. Configure host_ip and token below.
Run: uv run tests/client/test_lcc_workflow.py
"""
from datetime import datetime
from educelab.hercdb.client import HercClient

token = "<token>"
host_ip = "localhost"

client = HercClient(host=host_ip, token=token)

# Test constants
PHERC = "1045"
TEST_PIPELINE_ID = "1234567"

# --- Step 1: Fetch and display all datasets for this PHerc ---

print(f"\n{'='*60}")
print(f"  Datasets for PHerc {PHERC}")
print(f"{'='*60}")

all_datasets = client.get_all_datasets_for_pherc(PHERC, newest_completed=True)
artifacts = all_datasets.get("artifacts", [])

if not artifacts:
    print("No artifacts found.")
    exit(1)

for i, artifact in enumerate(artifacts, start=1):
    label_parts = [f"PHerc {artifact['pherc']}"]
    if artifact.get("cornice"):
        label_parts.append(f"Cornice {artifact['cornice']}")
    if artifact.get("pezzo"):
        label_parts.append(f"Pezzo {artifact['pezzo']}")
    label = " / ".join(label_parts)

    print(f"\n  [{i}] {label}")
    print(f"      UUID: {artifact['uuid']}")
    for ds in artifact.get("datasets", []):
        ds_type = ds.get("type", "?")
        ds_path = ds.get("path", "N/A")
        print(f"      - {ds_type}: {ds_path}")

# --- Step 2: Ask user which artifact to create a pipeline for ---

print(f"\n{'='*60}")
choice = input(f"Enter artifact number [1-{len(artifacts)}] to create a pipeline for: ").strip()
try:
    idx = int(choice) - 1
    if idx < 0 or idx >= len(artifacts):
        raise ValueError
except ValueError:
    print("Invalid selection. Exiting.")
    exit(1)

selected = artifacts[idx]
selected_uuid = selected["uuid"]

label_parts = [f"PHerc {selected['pherc']}"]
if selected.get("cornice"):
    label_parts.append(f"Cornice {selected['cornice']}")
if selected.get("pezzo"):
    label_parts.append(f"Pezzo {selected['pezzo']}")

print(f"\nSelected: {' / '.join(label_parts)}  (UUID: {selected_uuid})")

# --- Step 3: Show PGSRaw and SpectralRaw paths for confirmation ---

datasets_by_type = {}
for ds in selected.get("datasets", []):
    datasets_by_type[ds.get("type", "")] = ds.get("path", "")

pgs_raw_path = datasets_by_type.get("PGSRaw", "")
spec_raw_path = datasets_by_type.get("SpectralRaw", "")

print(f"\nExpected input datasets:")
print(f"  PGS Raw:      {pgs_raw_path or '(not found)'}")
print(f"  Spectral Raw: {spec_raw_path or '(not found)'}")

confirm = input("\nAre these the correct input datasets? [Y/n]: ").strip().lower()
if confirm and confirm != "y":
    pgs_raw_path = input("Enter PGS Raw path (leave blank to skip): ").strip()
    spec_raw_path = input("Enter Spectral Raw path (leave blank to skip): ").strip()
    print(f"\n  PGS Raw:      {pgs_raw_path or '(skipped)'}")
    print(f"  Spectral Raw: {spec_raw_path or '(skipped)'}")

# --- Step 4: Create the pipeline ---

print(f"\n{'='*60}")
print(f"  Pipeline to create:")
print(f"    Pipeline ID:  {TEST_PIPELINE_ID}")
print(f"    Artifact UUID: {selected_uuid}")
if pgs_raw_path:
    print(f"    PGS Raw input: {pgs_raw_path}")
if spec_raw_path:
    print(f"    Spec Raw input: {spec_raw_path}")
print(f"{'='*60}")

create = input("\nCreate pipeline? [Y/n]: ").strip().lower()
if create and create != "y":
    print("Aborted.")
    exit(0)

now = datetime.now().isoformat()
result = client.initialize_pipeline(TEST_PIPELINE_ID, selected_uuid, now)
print(f"\nPipeline created:")
print(f"  pipeline_id:  {result['pipeline_id']}")
print(f"  artifact_uuid: {result['artifact_uuid']}")
print(f"  datetime:      {result['datetime']}")
print(f"  status:        {result.get('status', 'N/A')}")


# =====================================================================
#  Helper: confirm input path(s) and ask for correction if needed
# =====================================================================

def confirm_input_paths(label: str, paths: list[str]) -> list[str]:
    """Show input paths and let the user correct them if wrong."""
    print(f"\n  Input dataset(s) for {label}:")
    for p in paths:
        print(f"    - {p}")
    ok = input(f"  Correct? [Y/n]: ").strip().lower()
    if ok and ok != "y":
        corrected = []
        for i, p in enumerate(paths, start=1):
            new_p = input(f"    Path {i} (current: {p}): ").strip()
            corrected.append(new_p if new_p else p)
        return corrected
    return paths


# =====================================================================
#  Helper: create a process, print result
# =====================================================================

def submit_process(stage: str, input_paths: list[str], output_path: str, slurm_id: str):
    """Create a process node (status = submitted) and print the result."""
    start = datetime.now().isoformat()
    result = client.initialize_process(
        pipeline_id=TEST_PIPELINE_ID,
        proc_type=stage,
        input_dataset_paths=input_paths,
        output_dataset_path=output_path,
        slurm_id=slurm_id,
        start_datetime=start,
    )
    print(f"\n  Process created:")
    print(f"    proc_type: {result['proc_type']}")
    print(f"    status:    {result['status']}")
    print(f"    slurm_id:  {result['slurm_id']}")
    return result


# =====================================================================
#  Helper: mark a process as completed
# =====================================================================

def complete_process(stage: str):
    """Update a process status to completed and print the result."""
    end = datetime.now().isoformat()
    result = client.update_process_status(TEST_PIPELINE_ID, stage, "completed", end)
    print(f"\n  {stage} completed:")
    print(f"    proc_type: {result['proc_type']}")
    print(f"    status:    {result['status']}")
    return result


# =====================================================================
#  Step 5: Process PGS — submit
# =====================================================================

print(f"\n{'='*60}")
print(f"  Step 5: PGS Processing")
print(f"{'='*60}")

pgs_input_paths = confirm_input_paths("PGS", [pgs_raw_path])
pgs_output_path = input("  Enter PGS output dataset path: ").strip()
pgs_slurm_id = "88001"

submit_process("PGS", pgs_input_paths, pgs_output_path, pgs_slurm_id)


# =====================================================================
#  Step 6: Process SPEC — submit
# =====================================================================

print(f"\n{'='*60}")
print(f"  Step 6: Spectral Processing")
print(f"{'='*60}")

spec_input_paths = confirm_input_paths("SPEC", [spec_raw_path])
spec_output_path = input("  Enter Spectral output dataset path: ").strip()
spec_slurm_id = "88002"

submit_process("SPEC", spec_input_paths, spec_output_path, spec_slurm_id)


# =====================================================================
#  Step 7: Pretend PGS and SPEC jobs finished — mark completed
# =====================================================================

print(f"\n{'='*60}")
print(f"  Step 7: PGS and SPEC jobs finished")
print(f"{'='*60}")

input("\n  Press Enter to mark PGS as completed...")
complete_process("PGS")

input("  Press Enter to mark SPEC as completed...")
complete_process("SPEC")


# =====================================================================
#  Step 8: Process REG — submit
# =====================================================================

print(f"\n{'='*60}")
print(f"  Step 8: Registration Processing")
print(f"{'='*60}")

reg_input_paths = confirm_input_paths("REG", [pgs_output_path, spec_output_path])
reg_output_path = input("  Enter REG output dataset path: ").strip()
reg_slurm_id = "88003"

submit_process("REG", reg_input_paths, reg_output_path, reg_slurm_id)


# =====================================================================
#  Step 9: Pretend REG job finished — mark completed
# =====================================================================

print(f"\n{'='*60}")
print(f"  Step 9: REG job finished")
print(f"{'='*60}")

input("\n  Press Enter to mark REG as completed...")
complete_process("REG")


# =====================================================================
#  Step 10: Process WEB — submit
# =====================================================================

print(f"\n{'='*60}")
print(f"  Step 10: WEB Processing")
print(f"{'='*60}")

web_input_paths = confirm_input_paths("WEB", [reg_output_path])
web_output_path = input("  Enter WEB output dataset path: ").strip()
web_slurm_id = "88004"

submit_process("WEB", web_input_paths, web_output_path, web_slurm_id)


# =====================================================================
#  Step 11: Pretend WEB job finished — mark completed
# =====================================================================

print(f"\n{'='*60}")
print(f"  Step 11: WEB job finished")
print(f"{'='*60}")

input("\n  Press Enter to mark WEB as completed...")
complete_process("WEB")


# =====================================================================
#  Step 12: Create another version of WEB
# =====================================================================

print(f"\n{'='*60}")
print(f"  Step 12: Second WEB version")
print(f"{'='*60}")

web2_input_paths = confirm_input_paths("WEB (v2)", [reg_output_path])
web2_output_path = input("  Enter WEB v2 output dataset path: ").strip()
web2_slurm_id = "88005"

submit_process("WEB", web2_input_paths, web2_output_path, web2_slurm_id)


# =====================================================================
#  Step 13: Pretend WEB v2 job finished — mark completed
# =====================================================================

print(f"\n{'='*60}")
print(f"  Step 13: WEB v2 job finished")
print(f"{'='*60}")

input("\n  Press Enter to mark WEB v2 as completed...")
complete_process("WEB")


# =====================================================================
#  Done
# =====================================================================

print(f"\n{'='*60}")
print(f"  All pipeline stages completed for pipeline {TEST_PIPELINE_ID}")
print(f"{'='*60}")

# =====================================================================
#  Cleanup: delete the test pipeline and all its nodes
# =====================================================================

cleanup = input("\nDelete test pipeline and all its nodes? [Y/n]: ").strip().lower()
if cleanup and cleanup != "y":
    print("Skipping cleanup. Test nodes remain in the DB.")
else:
    result = client.delete_pipeline(TEST_PIPELINE_ID)
    print(f"\nPipeline deleted:")
    print(f"  pipeline_id:            {result['pipeline_id']}")
    print(f"  processes deleted:      {result['processes_deleted']}")
    print(f"  output datasets deleted: {result['output_datasets_deleted']}")

print("\nDone.")
