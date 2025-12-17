from neo4j import GraphDatabase

from educelab.hercdb import config

### This is an obsolete script. Use src/educelab/hercdb/api.py instead.

class GraphDataLoader:

    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def verify_conn(self):
        self.driver.verify_connectivity()
        print("connected to Neo4j.")


    def delete_all(self):
        records, summary, keys = self.driver.execute_query("""
            MATCH (n)
            DETACH DELETE n
            """, 
            database_ = "neo4j",
        )

    def return_all(self):
        records, summary, keys = self.driver.execute_query("""
            MATCH (n)
            RETURN  n
            """, 
            database_ = "neo4j",
        )
        log.debug(records)
        log.debug(summary)
        log.debug(keys)


    def count_all(self):
        records, summary, keys = self.driver.execute_query("""
            MATCH (n)
            RETURN  n
            """, 
            database_ = "neo4j",
        )
        print(len(records))


    def get_human_readable_name(self, pherc, cornice=None, pezzo=None):

        pherc_n = None
        corn_n = None
        pezzo_n = None

        if cornice:
            records, summary, keys = self.driver.execute_query("""
                MATCH (ph:PHerc {name: $ph})-[:HAS]->(c:Cornice {name: $cor})
                RETURN ph.human_name, c.human_name            
                """, ph=pherc,cor=cornice,
                database_ = "neo4j",
            )
            if records:
                pherc_n = records[0]["ph.human_name"]
                corn_n = records[0]["c.human_name"]

        if pezzo:
            # Currently this is irrelevant since there are no pezzo with "names"
            records, summary, keys = self.driver.execute_query("""
                MATCH (ph:PHerc {name: $ph})-[:HAS]->(:Cornice)
                                                -[:HAS]->(pz:Pezzo {name: $pz})
                RETURN ph.human_name, pz.human_name            
                """, ph=pherc, pz=pezzo,
                database_ = "neo4j",
            )
            if records:
                pherc_n = records[0]["ph.human_name"]
                pezzo_n = records[0]["pz.human_name"]

        if not pherc_n:
            # If there was neither cornice nor pezzo names given
            records, summary, keys = self.driver.execute_query("""
                MATCH (ph:PHerc {name: $ph})
                RETURN ph.human_name
                """, ph=pherc,
                database_ = "neo4j",
            )
            if records:
                pherc_n = records[0]["ph.human_name"]
            

        return pherc_n, corn_n, pezzo_n

               
    def find_cornici_pezzi(self, pherc):
        # Use display names
        records, summary, keys = self.driver.execute_query("""
            MATCH (ph:PHerc {human_name: $ph})
            OPTIONAL MATCH (ph)-[:HAS]-(c:Cornice)
            OPTIONAL MATCH (c)-[:HAS]-(p:Pezzo)
            RETURN c.human_name, p.human_name            
            """, ph=pherc,
            database_ = "neo4j",
        )
        cornici=[]
        pezzi =[]
        for record in records:
            if record["c.human_name"]:
                cornici.append(record["c.human_name"])
            if record["p.human_name"]:
                pezzi.append(record["p.human_name"])

        return cornici, pezzi 

        
    def find_datasets(self, dataset_t, pherc, cornice=None, pezzo=None):
        # Use display names
        if cornice:
            records, summary, keys = self.driver.execute_query("""
                MATCH (ph:PHerc {human_name: $ph})-[:HAS]-(c:Cornice {human_name: $cor})
                MATCH (c)<-[:ASSIGNED_TO]-(e:EduceLabID)
                MATCH (e)<-[:BELONGS_TO]-(n)
                WHERE $data_t IN LABELS(n)
                RETURN n
                """, data_t=dataset_t, ph=pherc,cor=cornice,
                database_ = "neo4j",
            )

            properties=[]
            for record in records:
                dataset = record[0]
                properties.append(dataset.items())
                
            return properties

        else:
            # Pezzo
            records, summary, keys = self.driver.execute_query("""
                MATCH (ph:PHerc {human_name: $ph})-[:HAS]->(:Cornice)
                                        -[:HAS]->(pz:Pezzo {human_name: $pz})
                MATCH (pz)<-[:ASSIGNED_TO]-(e:EduceLabID)
                MATCH (e)<-[:BELONGS_TO]-(n)
                WHERE $data_t IN LABELS(n)
                RETURN n
                """, data_t=dataset_t, ph=pherc,pz=pezzo,
                database_ = "neo4j",
            )

            properties=[]
            for record in records:
                dataset = record[0]
                properties.append(dataset.items())
                
            return properties
            

if __name__ == "__main__":

    loader = GraphDataLoader(config.server_addr, config.username, config.password)
    loader.verify_conn()

    ### TODO: figure out when to use human-readable names vs. names from UUID

    # Find display names with names (from UUID assignment sheet)
    ph_n, c_n, p_n = loader.get_human_readable_name("467/2", "Scorza", "467/2")
    print(f'PHerc, Cornice, Pezzo (display names): {ph_n}, {c_n}, {p_n}')


    # Find cornici and pezzi display names for a papyrus with the display name
    records = loader.find_cornici_pezzi("76")
    print(records)


    # Choices are "SpectralRaw", "PGSRaw", or "FlatbedScanDataset"
    # Use display names 
    records = loader.find_datasets("SpectralRaw", "1045", cornice="1")
    print(records)
    records = loader.find_datasets("SpectralRaw", "76", pezzo="Left")
    print(records)

    loader.close()
