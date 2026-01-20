from educelab import hercdb

#uri = "neo4j://localhost:7687"
#uri = "bolt://localhost:7687" (for Mac)

#hercdb.config.request_required()
hercdb.config._load_config()

db = hercdb.connect()

if db.verify_connection():
  print("Connected!")

print(f"Total number of nodes: {db._node_count()}")