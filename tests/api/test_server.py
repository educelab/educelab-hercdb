import requests

token = "<token>"
host_ip = "<local host or server IP>"

headers = {
    "Authorization": f"Bearer {token}"
}

# /check-token endpoint
print("/check-token endpoint:")
print(requests.get(f"http://{host_ip}:8000/check-token", headers=headers).json())

# /home endpoint
print("/home endpoint:") 
print(requests.get(f"http://{host_ip}:8000/home", headers=headers).json())

# /pherc/<pherc_id> endpoint    
print("/pherc/<pherc_id> endpoint:")
print(requests.get(f"http://{host_ip}:8000/pherc/211", headers=headers).json())

# /pherc/<pherc_id>/cornice/<cornice_id> endpoint
print("/pherc/<pherc_id>/cornice/<cornice_id> endpoint:")
print(requests.get(f"http://{host_ip}:8000/pherc/18/cornice/1", headers=headers).json())

# /pherc/<pherc_id>/cornice/<cornice_id>/pezzo/<pezzo_id> endpoint
print("/pherc/<pherc_id>/cornice/<cornice_id>/pezzo/<pezzo_id> endpoint:")
print(requests.get(f"http://{host_ip}:8000/pherc/238/cornice/Scorze da 238 a 239/pezzo/5 (238e)", headers=headers).json())


# /search endpoint
print("/search endpoint:")
payload = {
    "uuid": "",
    "display-name": "",
    "author": "",
    "language": "",
    "unrolling-status": "",
    "scorze": "",
    "unrolling-method": "",
    "unroller": "",
    "literary-work": "",
    "editions": "",
    "instituion": "",
    "diameter_operator": "",
    "diameter_value": "",
    "height_operator": "",
    "height_value": "",
    "width_operator": "",
    "width_value": "",
    "weight_operator": "",
    "weight_value": "",
    "unrolled_year_operator": "",
    "unrolled_year_value": "",
    'cavallo-scribal-style': "Gruppo N"
}

print(payload)
print(requests.post(f"http://{host_ip}:8000/search", json=payload, headers=headers).json())

# /pherc/<pherc_id>/datasets/<dataset_type> endpoint
print("/pherc/<pherc_id>/datasets/<dataset_type> endpoint:")
print(requests.get(f"http://{host_ip}:8000/pherc/1044/datasets/SpectralRaw?cornice=6", headers=headers).json())

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

# /pherc/<pherc_id>/educelabids endpoint
print("\n/pherc/<pherc_id>/educelabids endpoint:")
resp = requests.get(f"http://{host_ip}:8000/pherc/1044/educelabids", headers=headers)
print(f"  Status: {resp.status_code}")
educelabids = resp.json()
print(f"  Response: {educelabids}")

# /educelabid/<uuid>/datasets endpoint (use first UUID from above)
if educelabids and len(educelabids) > 0:
    test_uuid = educelabids[0]['uuid']
    print(f"\n/educelabid/{test_uuid}/datasets endpoint:")
    resp = requests.get(f"http://{host_ip}:8000/educelabid/{test_uuid}/datasets", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.json()}")

    # With type filter
    print(f"\n/educelabid/{test_uuid}/datasets?dataset_type=PGSRaw endpoint:")
    resp = requests.get(f"http://{host_ip}:8000/educelabid/{test_uuid}/datasets?dataset_type=PGSRaw", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.json()}")

# /pherc/<pherc_id>/subdivisions endpoint
print("/pherc/<pherc_id>/subdivisions endpoint:")
print(requests.get(f"http://{host_ip}:8000/pherc/238/subdivisions", headers=headers).json())

# /pipelines/<pipeline_id>/stages endpoint
print("/pipelines/<pipeline_id>/stages endpoint:")
print(requests.get(f"http://{host_ip}:8000/pipelines/20251222-389/stages", headers=headers).json())

# /pipelines endpoint
print("/pipelines endpoint:")
print(requests.get(f"http://{host_ip}:8000/pipelines", headers=headers).json())
