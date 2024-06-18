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


    def load_EduceLabID(self, uuid_file):
        try:
            records, summary, keys = self.driver.execute_query("""
                LOAD CSV WITH HEADERS FROM $uuid_f as line
                WITH line
                MERGE (e:EduceLabID {id:line.EduceLab_ID, uuid:line.UUID})
                """, uuid_f=uuid_file,
                database_="neo4j",
            )
        except Exception as e:
            print(e)



if __name__ == "__main__":

    loader = GraphDataLoader("neo4j://localhost:7687", config.username, config.password)
    
    loader.verify_conn()
    loader.load_EduceLabID("file:///MellonUUID_mod.csv")
    loader.count_all()
    loader.close()
