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


    def delete_all(self):
        records, summary, keys = self.driver.execute_query("""
            MATCH (n)
            DETACH DELETE n
            """, 
            database_ = "neo4j",
        )
        print(records)
        print(summary)
        print(keys)


    def return_all(self):
        records, summary, keys = self.driver.execute_query("""
            MATCH (n)
            RETURN  n
            """, 
            database_ = "neo4j",
        )
        print(records)
        print(summary)
        print(keys)


    def count_all(self):
        records, summary, keys = self.driver.execute_query("""
            MATCH (n)
            RETURN  n
            """, 
            database_ = "neo4j",
        )
        print(len(records))


    def find_cornici_pezzi(self, pherc):
        records, summary, keys = self.driver.execute_query("""
            MATCH (ph:PHerc {human_name: $ph})
            OPTIONAL MATCH (ph)-[:HAS]-(c:Cornice)
            OPTIONAL MATCH (c)-[:HAS]-(p:Pezzo)
            RETURN c.human_name, p.human_name            
            """, ph=pherc,
            database_ = "neo4j",
        )
        cornices=[]
        pezzi =[]
        for record in records:
            if record["c.human_name"]:
                cornices.append(record["c.human_name"])
            if record["p.human_name"]:
                pezzi.append(record["p.human_name"])

        return cornices, pezzi 

        
    def find_datasets(self, dataset_t, pherc, cornice=None, pezzo=None):
        if cornice:
            records, summary, keys = self.driver.execute_query("""
                MATCH (ph:PHerc {name: $ph})-[:HAS]-(c:Cornice {name: $cor})
                MATCH (c)-[*..2]-(e:EduceLabID)
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
            pass
            # pezzo


        
if __name__ == "__main__":

    loader = GraphDataLoader(config.server_addr, config.username, config.password)
    loader.verify_conn()
    #records = loader.find_cornice_pezzo("76")
    
    # Choices are "SpectralRaw", "PGSRaw", or "FlatbedScanDataset"
    records = loader.find_datasets("SpectralRaw", "1045", cornice="1")
    print(records)
    loader.close()
