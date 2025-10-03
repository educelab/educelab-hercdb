from educelab import hercdb

hercdb.config._load_config()
db = hercdb.connect()

if db.verify_connection():
  print("Connected!")

# Find cornici and pezzi for a given PHERC
records = db.list_cornici_and_pezzi_for_pherc("238")
for record in records:
    print(f"\nCor-Pezzi Record: {record.data()}")
print("Cornici:", records[0].data()['cr'])
print("Pezzi:", records[0].data()['pz'])

# Get all dataset records. (Notice, the newest_completed and properties_only flags.)
records, summary, keys = db.find_datasets(hercdb.PGSRawType, "1044", cornice="6", newest_completed=False, properties_only=False)
print(f"\ndataset record: {[record.data() for record in records]}")

# Get dataset properties only (Notice, the newest_completed and properties_only flags.)
properties = db.find_datasets(hercdb.PGSRawType, "1044", cornice="6", newest_completed=False, properties_only=True)
print(f"\ndataset properties only: {properties}")