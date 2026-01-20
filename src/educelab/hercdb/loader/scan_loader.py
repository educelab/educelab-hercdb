from datetime import datetime, timezone
import csv
from educelab.hercdb.loader import PhercGraphDatabaseLoader

loader = PhercGraphDatabaseLoader()
loader.verify_conn()

# File paths. Edit as needed.
negatives_file = 'input_data/negatives.csv'
photogrammetry_file = 'input_data/photogrammetry-scans.csv'
spectal_file = 'input_data/spectral-scans.csv'

def clean_datetime(dt_str):
    if not dt_str:
        return None
    # Remove " (UTC)" if present and parse the datetime
    clean_string = dt_str.replace(" (UTC)", "")
    dt = datetime.strptime(clean_string, "%m/%d/%Y, %H:%M:%S")
    dt = dt.replace(tzinfo=timezone.utc)
    return dt if dt else None


# First load the negatives file
with open(negatives_file, 'r') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        image_num = row['Image number']
        uuid = row['UUID'] # may be None
        neg_series = row['Negatives series'] if row['Negatives series'] else "unknown"
        pherc = row['PHerc.']
        cornice = row['cornice']
        neg_storage = row['Storage location'] if row['Storage location'] else "unknown"
        
        if image_num:
            loader.add_flatbed_scan_node(
                image_num=image_num,
                uuid=uuid,
                pherc=pherc,
                cornice=cornice,
                neg_series=neg_series,
                neg_storage=neg_storage
            )

with open(photogrammetry_file, 'r') as csvfile:
    
    
    reader = csv.DictReader(csvfile)
    for row in reader:
        path = row['path']
        scan_uuid = row['uuid'] 
        datetime_start = clean_datetime(row['datetime start'])
        datetime_end = clean_datetime(row['datetime end']) if row['datetime end'] else None
        complete = row['complete'] if row['complete'] else "unknown"
        sample_uuid = row['sample uuid'] if row['sample uuid'] else None # may be None
        
        loader.add_pgs_raw_node(
            pgs_path=path,
            scan_uuid=scan_uuid,
            datetime_start=datetime_start,
            datetime_end=datetime_end,
            complete=complete,
            sample_uuid=sample_uuid
        )
    
with open(spectal_file, 'r') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        path = row['path']
        scan_uuid = row['uuid'] 
        datetime_start = clean_datetime(row['datetime start'])
        datetime_end = clean_datetime(row['datetime end']) if row['datetime end'] else None
        complete = "True" if row['complete']=="TRUE" else False
        sample_uuid = row['sample uuid'] if row['sample uuid'] else None # may be None
        sample_uuid2 = row['sample uuid 2'] if row['sample uuid 2'] else None
        
        loader.add_spectral_raw_node(
            spectral_path=path,
            scan_uuid=scan_uuid,
            datetime_start=datetime_start,
            datetime_end=datetime_end,
            complete=complete,
            sample_uuid=sample_uuid,
            sample_uuid2=sample_uuid2
        )   
        