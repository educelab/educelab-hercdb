import logging
from enum import Enum

from neo4j import GraphDatabase


class DatasetType(Enum):
    FlatbedScan = 'FlatbedScanDataset'
    PGSRaw = 'PGSRaw'
    SpectralRaw = 'SpectralRaw'

    def __str__(self):
        return f'{self.value}'


FlatbedScanType = DatasetType.FlatbedScan
PGSRawType = DatasetType.PGSRaw
SpectralRawType = DatasetType.SpectralRaw


class GraphDBConnection:
    logger = logging.getLogger('educelab.hercdb')
    uri: str = None
    user: str = None

    def __init__(self, uri, user, password):
        self.uri = uri
        self.user = user
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def __del__(self):
        self.close()

    def close(self):
        self.driver.close()

    def verify_connection(self):
        try:
            self.driver.verify_connectivity()
            return True
        except Exception as e:
            self.logger.debug('failed to connect', exc_info=e)
            return False

    def _delete_all(self):
        records, summary, keys = self.driver.execute_query(
            """
            MATCH (n)
            DETACH DELETE n
            """,
            database_="neo4j",
        )

    def _return_all(self):
        records, summary, keys = self.driver.execute_query(
            """
            MATCH (n)
            RETURN  n
            """,
            database_="neo4j",
        )
        self.logger.debug(records)
        self.logger.debug(summary)
        self.logger.debug(keys)

    def _node_count(self) -> int:
        record, keys, summary = self.driver.execute_query(
            """
            MATCH (n)
            RETURN count(n)
            """,
            database_="neo4j",
        )
        count = record[0]
        assert isinstance(count, int)
        return count

    def get_human_readable_name(self, pherc, cornice=None, pezzo=None):

        pherc_n = None
        corn_n = None
        pezzo_n = None

        if cornice:
            records, summary, keys = self.driver.execute_query(
                """
                MATCH (ph:PHerc {name: $ph})-[:HAS]->(cr:Cornice {name: $cor})
                RETURN ph.human_name, cr.human_name            
                """, ph=pherc, cor=cornice,
                database_="neo4j",
            )
            if records:
                pherc_n = records[0]["ph.human_name"]
                corn_n = records[0]["c.human_name"]

        if pezzo is not None:
            # Currently this is irrelevant since there are no pezzo with "names"
            records, summary, keys = self.driver.execute_query(
                """
                MATCH (ph:PHerc {name: $ph})-[:HAS]->(:Cornice)
                                                -[:HAS]->(pz:Pezzo {name: $pz})
                RETURN ph.human_name, pz.human_name            
                """, ph=pherc, pz=pezzo,
                database_="neo4j",
            )
            if records:
                pherc_n = records[0]["ph.human_name"]
                pezzo_n = records[0]["pz.human_name"]

        if not pherc_n:
            # If there was neither cornice nor pezzo names given
            records, summary, keys = self.driver.execute_query(
                """
                MATCH (ph:PHerc {name: $ph})
                RETURN ph.human_name
                """, ph=pherc,
                database_="neo4j",
            )
            if records:
                pherc_n = records[0]["ph.human_name"]

        return pherc_n, corn_n, pezzo_n

    def list_cornici_pezzi(self, pherc):
        # Use display names
        records, summary, keys = self.driver.execute_query(
            """
            MATCH (ph:PHerc {human_name: $ph})
            OPTIONAL MATCH (ph)-[:HAS]-(cr:Cornice)
            OPTIONAL MATCH (cr)-[:HAS]-(pz:Pezzo)
            RETURN ph, cr, pz       
            """, ph=pherc,
            database_="neo4j",
        )
        return records

    def find_datasets(self, ds_type: DatasetType, pherc, cornice=None,
                      pezzo=None):
        # Use display names
        if cornice:
            records, summary, keys = self.driver.execute_query(
                """
                MATCH (ph:PHerc {name: $ph})-[:HAS]-(cr:Cornice {name: $cor})
                MATCH (cr)<-[:ASSIGNED_TO]-(e:EduceLabID)
                MATCH (e)<-[:BELONGS_TO]-(n)
                WHERE $data_t IN LABELS(n)
                RETURN n
                """, data_t=str(ds_type), ph=pherc, cor=cornice,
                database_="neo4j",
            )

        else:
            # Pezzo
            records, summary, keys = self.driver.execute_query(
                """
                MATCH (ph:PHerc {name: $ph})-[:HAS]->(:Cornice)
                                        -[:HAS]->(pz:Pezzo {human_name: $pz})
                MATCH (pz)<-[:ASSIGNED_TO]-(e:EduceLabID)
                MATCH (e)<-[:BELONGS_TO]-(n)
                WHERE $data_t IN LABELS(n)
                RETURN n
                """, data_t=str(ds_type), ph=pherc, pz=pezzo,
                database_="neo4j",
            )

        properties = []
        for record in records:
            dataset = record[0]
            properties.append(dict(dataset))

        return properties


def connect(uri=None, user=None, password=None) -> GraphDBConnection:
    # use system config values if not provided
    from educelab.hercdb import config
    if uri is None:
        uri = config.uri
    if user is None:
        user = config.username
    if password is None:
        password = config.password

    # open new connection
    db = GraphDBConnection(uri, user, password)
    return db
