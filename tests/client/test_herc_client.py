"""Integration tests for HercClient dataset-finding methods.

Requires a running REST API server. Configure host_ip and token below.
"""
from educelab.hercdb.client import HercClient

token = "<token>"
host_ip = "<local host or server IP>"

client = HercClient(host=host_ip, token=token)

# --- get_all_datasets_for_pherc ---

print("/pherc/<pherc_id>/all-datasets via client:")
result = client.get_all_datasets_for_pherc("1044")
print(f"  pherc: {result['pherc']}")
print(f"  artifacts: {len(result['artifacts'])}")
for artifact in result['artifacts']:
    print(f"    {artifact['artifact_name']} ({artifact['uuid']}): {len(artifact['datasets'])} datasets")
    for ds in artifact['datasets']:
        assert 'belongs_to_uuid' in ds, "each dataset should carry belongs_to_uuid"
        print(f"      [{ds['type']}] {ds.get('path', '')} (belongs_to {ds['belongs_to_uuid']})")

print("\n/pherc/<pherc_id>/all-datasets with type filter via client:")
result = client.get_all_datasets_for_pherc("1044", dataset_type="PGSRaw")
print(f"  artifacts: {len(result['artifacts'])}")
for artifact in result['artifacts']:
    for ds in artifact['datasets']:
        assert ds['type'] == 'PGSRaw', f"Expected PGSRaw but got {ds['type']}"
    print(f"    {artifact['artifact_name']}: {len(artifact['datasets'])} PGSRaw datasets")

print("\n/pherc/<pherc_id>/all-datasets with newest_completed via client:")
result = client.get_all_datasets_for_pherc("1044", newest_completed=True)
print(f"  artifacts: {len(result['artifacts'])}")
for artifact in result['artifacts']:
    types = [ds['type'] for ds in artifact['datasets']]
    assert len(types) == len(set(types)), f"Duplicate types in newest_completed for {artifact['artifact_name']}"
    print(f"    {artifact['artifact_name']}: {[ds['type'] for ds in artifact['datasets']]}")

print("\n/pherc/<pherc_id>/all-datasets for nonexistent PHerc via client:")
result = client.get_all_datasets_for_pherc("nonexistent_pherc")
print(f"  artifacts: {result['artifacts']}")
assert result['artifacts'] == [], "Expected empty artifacts for nonexistent PHerc"

# --- get_artifact_by_name + get_subdivisions ---

print("\n/artifacts?pherc=1044 via client:")
artifact = client.get_artifact_by_name("1044")
assert artifact['type'] == 'PHerc'
assert 'educelabids' in artifact
print(f"  {artifact['displayName']} ({artifact['type']}): "
      f"{artifact.get('cornici_count')} cornici, {artifact.get('pezzi_count')} pezzi")

print("\n/pherc/<pherc_id>/subdivisions via client:")
subs = client.get_subdivisions("1044")
print(f"  pherc: {subs['pherc']['displayName']}, "
      f"{len(subs['cornici'])} cornici, {len(subs['pezzi'])} pezzi")
for node in subs['cornici'] + subs['pezzi']:
    assert 'displayName' in node
    assert 'aliases' in node
    assert 'educelabids' in node

# Gather a UUID from subdivisions to exercise the UUID-keyed methods
uuids = []
for node in [subs['pherc']] + subs['cornici'] + subs['pezzi']:
    uuids.extend(node.get('educelabids', []))

# --- get_artifact (UUID -> location bridge) + get_datasets_for_educelabid ---

if uuids:
    test_uuid = uuids[0]

    print(f"\n/artifacts/{test_uuid} via client:")
    location = client.get_artifact(test_uuid)
    assert location['uuid'] == test_uuid
    assert 'type' in location and 'location' in location
    print(f"  {location['location']} (parent: {location.get('parent')})")

    print(f"\n/educelabid/{test_uuid}/datasets via client:")
    datasets = client.get_datasets_for_educelabid(test_uuid)
    print(f"  Found {len(datasets)} datasets")
    for ds in datasets:
        assert 'type' in ds
        assert 'belongs_to_uuid' in ds, "each dataset should carry belongs_to_uuid"
        print(f"    [{ds['type']}] {ds.get('path', '')} (belongs_to {ds['belongs_to_uuid']})")

    print(f"\n/educelabid/{test_uuid}/datasets with type filter via client:")
    datasets = client.get_datasets_for_educelabid(test_uuid, dataset_type="PGSRaw")
    print(f"  Found {len(datasets)} PGSRaw datasets")
    for ds in datasets:
        assert ds['type'] == 'PGSRaw', f"Expected PGSRaw but got {ds['type']}"

    print(f"\n/educelabid/{test_uuid}/datasets with newest_completed via client:")
    datasets = client.get_datasets_for_educelabid(test_uuid, newest_completed=True)
    print(f"  Found {len(datasets)} newest completed datasets")
    types = [ds['type'] for ds in datasets]
    assert len(types) == len(set(types)), "Duplicate types in newest_completed"

print(f"\n/educelabid/nonexistent-uuid/datasets via client:")
datasets = client.get_datasets_for_educelabid("nonexistent-uuid")
print(f"  Result: {datasets}")
assert datasets == [], "Expected empty list for nonexistent UUID"

# --- get_pipeline_stages ---

print("\n/pipelines/20260203-TEST6/stages via client (3-stage completed):")
stages = client.get_pipeline_stages("20260203-TEST6")
print(f"  Found {len(stages)} stage(s)")
assert len(stages) == 3, f"Expected 3 stages but got {len(stages)}"
assert 'WEB' not in [s['proc_type'] for s in stages], "WEB stage should not be present"
assert all(s['status'] == 'completed' for s in stages), "All stages should be completed"
for s in stages:
    print(f"    [{s['proc_type']}] {s['status']}")
print("  ✓ 3 stages, all completed, no WEB")

# --- get_pipelines ---

print("\n/pipelines via client:")
pipelines = client.get_pipelines()
print(f"  Found {len(pipelines)} pipeline(s)")
assert isinstance(pipelines, list), "Expected list of pipelines"
test6 = next((p for p in pipelines if p['pipeline_id'] == '20260203-TEST6'), None)
assert test6 is not None, "TEST6 pipeline should appear in get_pipelines()"
assert test6['status'] == 'completed', f"Expected 'completed' but got '{test6['status']}'"
print(f"  ✓ TEST6 pipeline status: {test6['status']}")

print("\nAll client tests passed!")
