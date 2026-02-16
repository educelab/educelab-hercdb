import csv
from neo4j import GraphDatabase
import logging

from educelab.hercdb import config

# Obsolete. Use educelab.hercdb.loader module instead.

logging.basicConfig(level=logging.INFO)

class GraphDataLoader:

    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def verify_conn(self):
        self.driver.verify_connectivity()
        print("connected to Neo4j.")


    def add_pezzo_with_uuid(self, uuid, papyrus, cornice, pezzo):

        try:
            records, summary, keys = self.driver.execute_query("""
                MERGE (e:EduceLabID {uuid: $uuid})
                MERGE (p:PHerc)-[:HAS]->(c:Cornice)<-[old_r:ASSIGNED_TO]-(e) 
                MERGE (c)-[:HAS]->(pz:Pezzo {human_name: $pz})<-[:ASSIGNED_TO]-(e)
                SET p.human_name = $ph
                SET c.human_name = $cor 
                DELETE old_r
                RETURN p.human_name, c.human_name, pz.human_name, e.uuid
                """, uuid=uuid, ph=papyrus, cor=cornice, pz=pezzo,
                database_="neo4j",
            )

            for record in records:
                return record

        except Exception as e:
            print(e)


    def add_pezzo_without_uuid(self, uuid, papyrus, cornice, pezzo):
        # No such cases found at the moment
        pass


    def add_cornice_with_uuid(self, uuid, papyrus, cornic):

        try:
            records, summary, keys = self.driver.execute_query("""
                MERGE (e:EduceLabID {uuid: $uuid})
                MERGE (e)-[:ASSIGNED_TO]->(c:Cornice)<-[:HAS]-(p:PHerc)
                SET c.human_name = $cor
                SET p.human_name = $ph
                RETURN p.human_name, c.human_name, e.uuid
                """, uuid=uuid, ph=papyrus, cor=cornice,
                database_="neo4j",
            )

            for record in records:
                return record

        except Exception as e:
            print(e)

    
    def add_cornice_without_uuid(self, papyrus, cornice):

        try:
            records, summary, keys = self.driver.execute_query("""
                MERGE(p:PHerc {name: $ph})
                MERGE(c:Cornice {human_name: $cor})<-[:HAS]-(p)
                SET p.human_name = $ph
                RETURN p.human_name, c.human_name
                """,  ph=papyrus, cor=cornice,
                database_="neo4j",
            )

            for record in records:
                return record

        except Exception as e:
            print(e)

    
    def add_pherc_with_uuid(self, uuid, papyrus):

        try:
            records, summary, keys = self.driver.execute_query("""
                MERGE (e:EduceLabID {uuid: $uuid})
                MERGE (e)-[:ASSIGNED_TO]->(p:PHerc)
                SET p.human_name = $ph
                RETURN e.uuid, p.human_name
                """, uuid=uuid, ph=papyrus,
                database_="neo4j",
            )

            for record in records:
                return record

        except Exception as e:
            print(e)

    
    def add_pherc_without_uuid(self, papyrus):

        try:
            records, summary, keys = self.driver.execute_query("""
                MERGE (p:PHerc {name: $ph})
                SET p.human_name=$ph
                RETURN p.human_name
                """, ph=papyrus, 
                database_="neo4j",
            )

            for record in records:
                return record

        except Exception as e:
            print(e)

    


if __name__ == "__main__":

    loader = GraphDataLoader("neo4j://localhost:7687", config.username, config.password)
    loader.verify_conn()

    metadata_file = config.metadata_file

    with open(metadata_file, 'r') as metadata:
        csv_reader = csv.DictReader(metadata)
       
        line_count = 0
    
        for row in csv_reader:
    
            uuid = row["UUID"]
            papyrus = row["PapyrusNum"]
            cornice = row["CorniceNum"]
            pezzo = row["Pezzo"]
            disegni = row["Disegni"]

            if pezzo:
                #logging.info(f'Pezzo Row: {uuid}, {papyrus}, {cornice}, {pezzo}')

                #  Pezzo row with UUID
                if uuid:
                    result = loader.add_pezzo_with_uuid(uuid, papyrus, cornice, pezzo)
                    logging.info(result)
                
                else:
                    # There are currently no cases, but if EduceLabID is there without any connections.
                    pass
           

            elif cornice and (not pezzo) and (not disegni):
                
                if uuid:
                    result = loader.add_cornice_with_uuid(uuid, papyrus, cornice)
                    logging.info(result)

                else:
                    result = loader.add_cornice_without_uuid(papyrus, cornice)
                    logging.info(result)


            elif papyrus and (not cornice) and  (not pezzo) and (not disegni):
                #logging.info(f'Papyrus Row: {uuid}. {papyrus}')

                if uuid:
                    result = loader.add_pherc_with_uuid(uuid, papyrus)
                    logging.info(result)

                else:
                    result = loader.add_pherc_without_uuid(papyrus)
                    logging.info(result)
            
            elif disegni:
                # To be dealt with later
                pass

            ## For initial testing only
            #if line_count > 100:
            #    break

            line_count +=1
            
    loader.close()

