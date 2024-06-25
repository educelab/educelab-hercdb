import csv
from neo4j import GraphDatabase
import config

class GraphDataLoader:

    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def verify_conn(self):
        self.driver.verify_connectivity()
        print("connected to Neo4j.")


    def find_uuid_assignment_type(self,uuid):
        # Returns a list of node labels (str)

        try:
            records, summary, keys = self.driver.execute_query("""
                MATCH (e:EduceLabID {uuid: $uuid})
                OPTIONAL MATCH (e)-[:ASSIGNED_TO]->(n)
                RETURN labels(n)
                """, uuid=uuid,
                database_="neo4j",
            )

            for record in records:
                return record['labels(n)']

        except Exception as e:
            print(e)
    

    def split_cornice_pezzo_node(self, uuid, papyrus_name, cornice_name, pezzo_name):

        try:
            records, summary, keys = self.driver.execute_query("""
                MATCH (e:EduceLabID {uuid: $uuid})-[old_r:ASSIGNED_TO]->(c:Cornice)<-[:HAS]-(p:PHerc)
                MERGE (c)-[:HAS]->(pz:Pezzo {human_name: $pz})<-[:ASSIGNED_TO]-(e)
                SET p.human_name = $ph 
                SET c.human_name = $cor 
                DELETE old_r
                RETURN p.human_name, c.human_name, pz.human_name, e.uuid
                """, uuid=uuid, ph=papyrus_name, cor=cornice_name, pz=pezzo_name,
                database_="neo4j",
            )

            for record in records:
                return record

        except Exception as e:
            print(e)

if __name__ == "__main__":

    loader = GraphDataLoader("neo4j://localhost:7687", config.username, config.password)
    loader.verify_conn()

    #loader.find_uuid_assignment_type("ebcf800e-3872-5e3d-be95-908b245827af")

    metadata_file = config.metadata_file

    with open(metadata_file, 'r') as metadata:
        csv_reader = csv.DictReader(metadata)
       
        line_count = 0
    
        for row in csv_reader:
    
            if row["Pezzo"]:
                #print(f'Pezzo Row: {row["PapyrusNum"]}, {row["CorniceNum"]}, {row["Pezzo"]}: {row["UUID"]}')

                # Pezzo row with UUID
                if row["UUID"]:
                    discovered_node = loader.find_uuid_assignment_type(row["UUID"])
                    print(f'Discovered node: {discovered_node}')

                    if 'Cornice' in discovered_node:
                        print(f'Pezzo Row: {row["PapyrusNum"]}, {row["CorniceNum"]}, {row["Pezzo"]}: {row["UUID"]}')

                        result = loader.split_cornice_pezzo_node(row["UUID"], row["PapyrusNum"], row["CorniceNum"], row["Pezzo"])
                        print(result)

                
                    else:
                        pass
                        # There are currently no cases, but if EduceLabID is there without any connections.

            if (not row["Pezzo"]) and (not row["Disegni"]) and row["CorniceNum"]:
                #print(f'Cornice Row: {row["PapyrusNum"]}, {row["CorniceNum"]}, {row["UUID"]}')

                if row["UUID"]:
                    discovered_node = loader.find_uuid_assignment_type(row["UUID"])
                    print(f'Discovered node: {discovered_node}')

                    if 'Cornice' in discovered_node:
                        # Already has a Cornice node
                        # TODO: Add human readable name

                    else:
                        # TODO: Create PHerc and Cornice nodes, find UUID node, attach 


            if (row["PapyrusNum"]) and (not row["CorniceNum"]) and  (not row["Pezzo"]) and (not row["Disegni"]):
                #print(f'Papyrus Row: {row["PapyrusNum"]}, {row["CorniceNum"]}, {row["Pezzo"]}: {row["UUID"]}')

                if row["UUID"]:
                    discovered_node = loader.find_uuid_assignment_type(row["UUID"])
                    print(f'Discovered node: {discovered_node}')

                    if 'Cornice' in discovered_node:
                        pass
                        # not likely
                        # Already has a Cornice node
                        # TODO: Add human readable name

                    else:
                        pass
                        # TODO: Create PHerc and Cornice nodes, find UUID node, attach 
                
            line_count +=1
    
