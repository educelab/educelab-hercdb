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
    driver = None

    def __init__(self, uri, user, password):
        """
        Create a new connection to the graph database.
        """
        self.uri = uri
        self.user = user
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.logger.info("Initialized GraphDBConnection to %s as user %s", uri, user)

    def __del__(self):
        """
        Ensure the driver is closed on deletion of the instance.
        """
        self.close()

    def close(self):
        """
        Close the driver connection.
        """
        if self.driver is not None:
            self.driver.close()

    def verify_connection(self):
        """ 
        Verify the connection to the database.
        """
        try:
            self.driver.verify_connectivity()
            return True
        except Exception as e:
            self.logger.debug('failed to connect', exc_info=e)
            return False
    
    def _run_query(self, query, **params):
        try:
            records, summary, keys = self.driver.execute_query(
                query,
                **params,
                database_="neo4j",
            )
            self.logger.info("Query executed successfully: %s", query.strip().replace('\n', ' '))
            return records, summary, keys
        except Exception as e:
            self.logger.error("Query failed: %s", query.strip().replace('\n', ' '), exc_info=e)
            return None, None, None

    def _delete_all(self):
        """
        Delete all nodes and relationships in the database.
        Use with caution!
        """
        records, summary, keys = self.driver.execute_query(
            """
            MATCH (n)
            DETACH DELETE n
            """,
            database_="neo4j",
        )

    def _return_all(self):
        """
        Return all nodes in the database.
        Use for debugging purposes only.
        """
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
        count = record[0]['count(n)']
        assert isinstance(count, int)
        return count

    ######### Soon to be deprecated #########
    def get_human_readable_name(self, pherc, cornice=None, pezzo=None):
        print("Deprecated: use displayName property instead")
        
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

    ######### Soon to be deprecated #########
    def list_cornici_pezzi(self, pherc):
        print("Deprecated: use list_cornici_and_pezzi_for_pherc method instead")
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

    ######### Soon to be deprecated #########
    # def find_datasets(self, ds_type: DatasetType, pherc, cornice=None,
    #                   pezzo=None):
    #     # Use display names
    #     if cornice:
    #         records, summary, keys = self.driver.execute_query(
    #             """
    #             MATCH (ph:PHerc {name: $ph})-[:HAS]-(cr:Cornice {name: $cor})
    #             MATCH (cr)<-[:ASSIGNED_TO]-(e:EduceLabID)
    #             MATCH (e)<-[:BELONGS_TO]-(n)
    #             WHERE $data_t IN LABELS(n)
    #             RETURN n
    #             """, data_t=str(ds_type), ph=pherc, cor=cornice,
    #             database_="neo4j",
    #         )

    #     else:
    #         # Pezzo
    #         records, summary, keys = self.driver.execute_query(
    #             """
    #             MATCH (ph:PHerc {name: $ph})-[:HAS]->(:Cornice)
    #                                     -[:HAS]->(pz:Pezzo {human_name: $pz})
    #             MATCH (pz)<-[:ASSIGNED_TO]-(e:EduceLabID)
    #             MATCH (e)<-[:BELONGS_TO]-(n)
    #             WHERE $data_t IN LABELS(n)
    #             RETURN n
    #             """, data_t=str(ds_type), ph=pherc, pz=pezzo,
    #             database_="neo4j",
    #         )

    #     properties = []
    #     for record in records:
    #         dataset = record[0]
    #         properties.append(dict(dataset))

    #     return properties
    
    
########################## New methods #################################



    def _get_node_id(self, node_type, pherc_display_name, cornice_display_name=None, pezzo_display_name=None, disegni_name=None):
        """
        Returns the Neo4j node id for PHerc, Cornice, or Pezzo node.
        
        Args:
            node_type (str): Type of the node ("PHerc", "Cornice", "Pezzo", or "Disegni").
            pherc_display_name (str): Display name of the PHerc.
            cornice_display_name (str, optional): Display name of the Cornice (required if node_type is "Cornice" or "Pezzo" under Cornice).
            pezzo_display_name (str, optional): Display name of the Pezzo (required if node_type is "Pezzo").
            disegni_name (str, optional): Name of the Disegni (required if node_type is "Disegni").    
        """
        if node_type == "PHerc":
            query = "MATCH (n:PHerc {displayName: $pherc_display_name}) RETURN elementId(n) AS node_id"
            params = {"pherc_display_name": pherc_display_name}
        elif node_type == "Cornice":
            query = """
                MATCH (p:PHerc {displayName: $pherc_display_name})-[:HAS]->(n:Cornice {displayName: $cornice_display_name})
                RETURN elementId(n) AS node_id
            """
            params = {"pherc_display_name": pherc_display_name, "cornice_display_name": cornice_display_name}
        elif node_type == "Pezzo":
            if cornice_display_name:
                query = """
                    MATCH (p:PHerc {displayName: $pherc_display_name})-[:HAS]->(c:Cornice {displayName: $cornice_display_name})-[:HAS]->(n:Pezzo {displayName: $pezzo_display_name})
                    RETURN elementId(n) AS node_id
                """
                params = {"pherc_display_name": pherc_display_name, "cornice_display_name": cornice_display_name, "pezzo_display_name": pezzo_display_name}
            else:
                query = """
                    MATCH (p:PHerc {displayName: $pherc_display_name})-[:HAS]->(n:Pezzo {displayName: $pezzo_display_name})
                    RETURN elementId(n) AS node_id
                """
                params = {"pherc_display_name": pherc_display_name, "pezzo_display_name": pezzo_display_name}     
        elif node_type == "Disegni":
            query = """
                MATCH (p:PHerc {displayName: $pherc_display_name})<-[:DEPICTS]-(n:Disegni {name: $disegni_name})
                RETURN elementId(n) AS node_id
            """
            params = {"pherc_display_name": pherc_display_name, "disegni_name": disegni_name}
        else:
            print("Unsupported node type")
            return None

        records, _, _ = self._run_query(query, **params)
        if records and len(records) == 1:
            return records[0]['node_id']
        elif records and len(records) > 1:
            print("Error: Multiple nodes found.")
            return None
        else:
            print("Error: Node not found")
            return None

    def get_directly_attached_nodes(self, node_type, pherc_display_name, cornice_display_name=None, pezzo_display_name=None, disegni_name=None):
        """
        Retrieves all nodes directly attached to a specified node (PHerc, Cornice, Pezzo, or Disegni) based on the provided display names.
        Args:
            node_type (str): Type of the node ("PHerc", "Cornice", "Pezzo", or "Disegni").
            pherc_display_name (str): Display name of the PHerc.
            cornice_display_name (str, optional): Display name of the Cornice (required if node_type is "Cornice" or "Pezzo" under Cornice).
            pezzo_display_name (str, optional): Display name of the Pezzo (required if node_type is "Pezzo").
            disegni_name (str, optional): Name of the Disegni (required if node_type is "Disegni").
        Returns:
            tuple: A tuple containing records, summary, and keys of the query result.
        """
        node_id = self._get_node_id(node_type, pherc_display_name, cornice_display_name, pezzo_display_name, disegni_name)
        if node_id is None:
            print(f"Error: Node of type {node_type} with specified names not found.")
            return None, None, None
        
        query = """
            MATCH (org_node)--(attached_nodes)
            WHERE elementId(org_node) = $node_id
            RETURN org_node, attached_nodes
        """
        params = {"node_id": node_id}

        return  self._run_query(query, **params)

    
    def find_node_type_conntected_to_object_node(self, obj_node_type, display_name, connected_node_type:str):
        """
        Finds nodes of a specific type connected to a given object node type by its display name.
        Args:
            obj_node_type (str): The type of the object node (e.g., "PHerc", "Cornice", "Pezzo", "Disegni").
            display_name (str): The display name of the object node.
            connected_node_type (str): The type of the connected nodes to find (e.g., "Author", "Language").
        Returns: 
            tuple: A tuple containing records, summary, and keys of the query result.
        """
        query = f"""
            MATCH (n:{obj_node_type} {{displayName:$display_name}})--(c:{connected_node_type})
            RETURN c
        """
        records, summary, keys = self._run_query(
            query,
            display_name=display_name
        )
        return records, summary, keys
    

    ############################### Finding specific PHercs ##########################
    
    def find_pherc_by_uuid(self, uuid):
        """
        This method looks up a PHerc by its UUID
        Args:
            uuid (str): The UUID of the PHerc to find.
        Returns:
            tuple: A tuple containing records, summary, and keys of the query result.

        Note:
            This currenly only returns the PHerc node, not Cornice/Pezzo.
        """

        records, summary, keys = self._run_query("""
            MATCH (e:EduceLabID {uuid:$uuid})-[:ASSIGNED_TO]->(n)<-[:HAS*0..2]-(ph:PHerc)
            RETURN ph
            """, uuid=uuid)
        return records, summary, keys

    def find_artifact_name_by_uuid(self, uuid):
        """
        Looks up the PHerc, Cornice, and Pezzo display names for a given UUID.

        Args:
            uuid (str): The UUID to look up.

        Returns:
            dict: A dictionary with keys 'pherc', 'cornice', and 'pezzo'.
                  Values are the display names or None if not applicable.
                  Returns None if the UUID is not found.
        """
        records, summary, keys = self._run_query("""
            MATCH (e:EduceLabID {uuid:$uuid})-[:ASSIGNED_TO]->(n)
            OPTIONAL MATCH (n)<-[:HAS]-(parent1)
            OPTIONAL MATCH (parent1)<-[:HAS]-(parent2)
            WITH n, parent1, parent2,
                 CASE
                     WHEN 'PHerc' IN labels(n) THEN n
                     WHEN 'PHerc' IN labels(parent1) THEN parent1
                     WHEN 'PHerc' IN labels(parent2) THEN parent2
                 END AS pherc,
                 CASE
                     WHEN 'Cornice' IN labels(n) THEN n
                     WHEN 'Cornice' IN labels(parent1) THEN parent1
                 END AS cornice,
                 CASE
                     WHEN 'Pezzo' IN labels(n) THEN n
                 END AS pezzo
            RETURN pherc.displayName AS pherc_name,
                   cornice.displayName AS cornice_name,
                   pezzo.displayName AS pezzo_name
            """, uuid=uuid)

        if records and len(records) > 0:
            record = records[0]
            return {
                'pherc': record['pherc_name'],
                'cornice': record['cornice_name'],
                'pezzo': record['pezzo_name']
            }
        return None

    def find_pherc_by_display_name(self, display_name):
        """
        Looks up a PHerc by its display name.
        Args:
            display_name (str): The display name of the PHerc to find.
        Returns:
            tuple: A tuple containing records, summary, and keys of the query result.
        """
        
        records, summary, keys = self._run_query("""
            MATCH (ph:PHerc {displayName:$display_name})
            RETURN ph
            """, display_name=display_name)
        return records, summary, keys

    def find_pherc_by_property_value(self, property_name, property_value):
        """
        Looks up a PHerc by a specific property value.
        Args:
            property_name (str): The name of the property to search (e.g., "displayName", "unrolling_status").
            property_value (str): The value to search for within the specified property.
        Returns:
            tuple: A tuple containing records, summary, and keys of the query result.
        Note:
            This performs a case-insensitive partial match search.
        """
        # This method looks up a PHerc by a specific property value
        records, summary, keys = self._run_query("""
            MATCH (ph:PHerc)
            WHERE ph[$property_name] =~ '(?i).*' + $property_value + '.*'
            RETURN ph ORDER BY ph.displayName
            """, property_name=property_name, property_value=property_value)
        return records, summary, keys
    
    def find_pherc_by_language(self, lang):
        # names: "grc", "lat", "inc.", "grc?", "inc", "lat?"
        records, summary, keys = self._run_query("""
            MATCH (ph:PHerc)-[:HAS_LANGUAGE]->(l:Language)
            WHERE toLower(l.name) CONTAINS toLower($language)
            RETURN ph ORDER BY ph.displayName
            """, language=lang)
        return records, summary, keys
    
    def find_pherc_by_unroller_name(self, unroller_name):
        # This method looks up a PHerc by the unroller's name
        records, summary, keys = self._run_query("""
            MATCH (ph:PHerc)-[:UNROLLED_BY]->(un:Unroller)
            WHERE un.name =~ '(?i).*' + $unroller_name + '.*'
            RETURN ph ORDER BY ph.displayName
            """, unroller_name=unroller_name)
        return records, summary, keys
    
    def find_pherc_by_unrolling_method(self, unrolling_method):
        # This method looks up a PHerc by the unrolling method
        records, summary, keys = self._run_query("""
            MATCH (ph:PHerc)-[:UNROLLED_BY_METHOD]->(method:UnrollingMethod)
            WHERE method.name =~ '(?i).*' + $unrolling_method + '.*'
            RETURN ph ORDER BY ph.displayName
            """, unrolling_method=unrolling_method)
        return records, summary, keys
    
    def find_pherc_by_author(self, author_name):
        # This method looks up a PHerc by the author's name
        records, summary, keys = self._run_query("""
            MATCH (ph:PHerc)-[:AUTHORED_BY]->(a:Author)
            WHERE a.name =~ '(?i).*' + $author_name + '.*'
            RETURN ph ORDER BY ph.displayName
            """, author_name=author_name)
        return records, summary, keys
    
    def find_pherc_by_cavallo_scribal_style(self, scribal_style):
        # This method looks up a PHerc by the Cavallo scribal style
        records, summary, keys = self._run_query("""
            MATCH (ph:PHerc)-[:STYLE]->(c:CavalloScribalStyle)
            WHERE c.name =~ '(?i).*' + $scribal_style + '.*'
            RETURN ph ORDER BY ph.displayName
            """, scribal_style=scribal_style)
        return records, summary, keys

    def find_pherc_by_custodial_institution(self, institution_name):
        # This method looks up a PHerc by the custodial institution's name
        records, summary, keys = self._run_query("""
            MATCH (ph:PHerc)-[:STORED_AT]->(inst:CustodialInstitution)
            WHERE inst.name =~ '(?i).*' + $institution_name + '.*'
            RETURN ph ORDER BY ph.displayName
            """, institution_name=institution_name)
        return records, summary, keys
    
    def find_pherc_by_numeric_property(self, property, operator, value):
        # This method looks up numerical value properties such as width, weight
        query_string = f"""
            MATCH (ph:PHerc)
            WHERE toFloat(ph.{property}) {operator} {value}
            RETURN ph ORDER BY ph.displayName
        """
        records, summary, keys = self._run_query(
            query_string,
        )
        return records, summary, keys
    
    def find_pherc_by_unrolled_year(self, operator, year):
        # This method deals with unrolled date properties that are stored
        # as "1420, 1820-1858" etc.
        query_string = f"""
            WITH {year} AS targetYear
            MATCH (ph:PHerc)
            WHERE ph.unrolled_date IS NOT NULL
            WITH ph, SPLIT(ph.unrolled_date, ',') AS parts, targetYear
            UNWIND parts AS part
            WITH ph, TRIM(part) AS p, targetYear
            WITH ph, 
                CASE 
                    WHEN p CONTAINS '-' THEN TOINTEGER(SPLIT(p, '-')[1])  // end of range
                    ELSE TOINTEGER(p)
                END AS maxYear,
                CASE 
                    WHEN p CONTAINS '-' THEN TOINTEGER(SPLIT(p, '-')[0])  // start of range
                    ELSE TOINTEGER(p)
                END AS minYear,
                targetYear
            WHERE (
                '{operator}' = '=' AND targetYear >= minYear AND targetYear <= maxYear
                OR '{operator}' = '<=' AND minYear <= targetYear
                OR '{operator}' = '>=' AND maxYear >= targetYear
            )
            RETURN DISTINCT ph ORDER BY ph.displayName
        """
        records, summary, keys = self._run_query(query_string)
        return records, summary, keys

    def find_pherc_with_any_property_value(self, property_name):
        # This method looks up PHercs that have a specific property
        query_string = f"""
            MATCH (ph:PHerc)
            WHERE ph.{property_name} IS NOT NULL
            RETURN ph ORDER BY ph.displayName
        """
        records, summary, keys = self._run_query(
            query_string,
        )
        return records, summary, keys

    def list_cornici_and_pezzi_for_pherc(self, pherc_display_name):
        # lists all Cornici and Pezzi for a given PHerc displayName
        # If there is a need to distinguish between Pezzo directly under PHerc vs under Cornice,
        # we can split p1 and p2 in the output.
        records, summary, keys = self._run_query("""
            MATCH (ph:PHerc {displayName:$pherc_display_name})
            OPTIONAL MATCH (ph)-[:HAS]->(c:Cornice)
            OPTIONAL MATCH (ph)-[:HAS]->(c)-[:HAS]->(p1:Pezzo)
            OPTIONAL MATCH (ph)-[:HAS]->(p2:Pezzo)
            WITH ph, COLLECT(DISTINCT c) AS cr, COLLECT(DISTINCT p1) + COLLECT(DISTINCT p2) AS pz
            RETURN ph, cr, pz

            """, pherc_display_name=pherc_display_name)
        return records
    
    def find_datasets(self, ds_type: DatasetType, pherc, cornice=None, pezzo=None, newest_completed=False, properties_only=True):
        # finds datasets of a specific type (FlatbedScan, PGSRaw, SpectralRaw)
        # For Pezzo, it can be either directly under PHerc or under Cornice. If they need to be distinguished,
        # we can modify the output accordingly.

        if cornice:
            base_query = """
                MATCH (ph:PHerc {displayName: $ph})-[:HAS]-(cr:Cornice {displayName: $cor})
                MATCH (cr)<-[:ASSIGNED_TO]-(e:EduceLabID)
                MATCH (e)<-[:BELONGS_TO]-(n)
                WHERE $data_t IN LABELS(n)
            """
            params = {"data_t": str(ds_type), "ph": pherc, "cor": cornice}
        elif pezzo:
            base_query = """
                MATCH (ph:PHerc {displayName: $ph})-[:HAS1..2]->(pz:Pezzo {displayName: $pz})
                MATCH (pz)<-[:ASSIGNED_TO]-(e:EduceLabID)
                MATCH (e)<-[:BELONGS_TO]-(n)
                WHERE $data_t IN LABELS(n)
            """
            params = {"data_t": str(ds_type), "ph": pherc, "pz": pezzo}
        else:
            base_query = """
                MATCH (ph:PHerc {displayName: $ph})<-[:ASSIGNED_TO]-(e:EduceLabID)
                MATCH (e)<-[:BELONGS_TO]-(n)
                WHERE $data_t IN LABELS(n)
            """
            params = {"data_t": str(ds_type), "ph": pherc}
        
        # Add filtering and ordering if newest_completed is True
        if newest_completed:
            query = base_query + """
                AND n.complete = "True"
                WITH n ORDER BY datetime(n.date_end) DESC
                RETURN n LIMIT 1
            """
        else:
            query = base_query + """
                RETURN n
            """
        
        records, summary, keys = self._run_query(query, **params)
        
        if properties_only:
            properties = []
            for record in records:
                dataset = record[0]
                properties.append(dict(dataset))

            return properties
        
        else:
            return records, summary, keys
   
    def find_pipelines(self):
        """
        Finds all pipelines and returns their pipeline_id and associated artifact_uuid.

        Returns:
            list: A list of dictionaries, each containing:
                - pipeline_id: The pipeline identifier
                - artifact_uuid: The UUID of the associated EduceLabID
        """
        records, _, _ = self._run_query("""
            MATCH (p:Pipeline)<-[:STAGE_OF]-(proc:Process)<-[:INPUT]-(input)
            WHERE 'PGSRaw' IN LABELS(input) OR 'SpectralRaw' IN LABELS(input)
            MATCH (input)-[:BELONGS_TO]->(e:EduceLabID)
            RETURN DISTINCT p.pipeline_id AS pipeline_id, e.uuid AS artifact_uuid
            ORDER BY p.pipeline_id
            """)

        if records:
            pipelines = []
            for record in records:
                pipelines.append({
                    "pipeline_id": record["pipeline_id"],
                    "artifact_uuid": record["artifact_uuid"]
                })
            return pipelines

        return []
    
    def get_pipeline_status(self, pipeline_id):
        """
        Returns the status of all processes in a pipeline.

        Args:
            pipeline_id (str): The pipeline identifier.

        Returns:
            list: A list of process dictionaries. Each process dict contains:
                  - datetime: The process timestamp
                  - stage: The process stage (e.g., "PGS", "SPEC", "REG")
                  - status: The process status (e.g., "completed", "failed")
                  - slurm_id: The SLURM job ID
                  Returns None if pipeline not found.
        """
        records, _, _ = self._run_query("""
            MATCH (p:Pipeline {pipeline_id: $pipeline_id})<-[:STAGE_OF]-(proc:Process)
            RETURN proc
            ORDER BY proc.datetime
            """, pipeline_id=pipeline_id)

        if not records:
            return None

        processes = []
        for record in records:
            proc = record['proc']
            processes.append({
                'datetime': str(proc.get('datetime', '')),
                'stage': proc.get('stage', ''),
                'status': proc.get('status', ''),
                'slurm_id': str(proc.get('slurm_id', ''))
            })

        return processes

    @staticmethod
    def _compute_pipeline_status(processes: list[dict]) -> str:
        """
        Compute overall pipeline status from process list.

        Args:
            processes: List of process dicts with 'stage' and 'status' keys.

        Returns:
            str: One of 'completed', 'partially_completed', 'submitted', 'failed', 'unknown(error)'
        """
        if not processes:
            return 'unknown(error)'

        # Extract statuses by stage
        stage_statuses = {}
        for proc in processes:
            stage = proc.get('stage', '')
            status = proc.get('status', '')
            if stage:
                stage_statuses[stage] = status

        # Check if all required stages (PGS, SPEC, REG, WEB) are completed
        required_stages = ['PGS', 'SPEC', 'REG', 'WEB']
        all_completed = all(
            stage_statuses.get(stage) == 'completed'
            for stage in required_stages
            if stage in stage_statuses
        )
        # For "completed" status, all required stages must exist and be completed
        has_all_required = all(stage in stage_statuses for stage in required_stages)
        if has_all_required and all_completed:
            return 'completed'

        # Check if at least first stage (PGS or SPEC) is completed
        first_stages = ['PGS', 'SPEC']
        has_first_completed = any(
            stage_statuses.get(stage) == 'completed'
            for stage in first_stages
        )
        if has_first_completed:
            return 'partially_completed'

        # Check if all stages are failed
        all_failed = all(
            status == 'failed'
            for status in stage_statuses.values()
        ) if stage_statuses else False
        if all_failed:
            return 'failed'

        # Check if at least one stage is submitted
        has_submitted = any(
            status == 'submitted'
            for status in stage_statuses.values()
        )
        if has_submitted:
            return 'submitted'

        return 'unknown(error)'

    def _format_dataset_name(self, artifact_info: dict) -> str:
        """
        Format artifact info dict as single string.

        Args:
            artifact_info: Dict with 'pherc', 'cornice', 'pezzo' keys.

        Returns:
            str: Formatted dataset name.

        Examples:
            - {'pherc': '421', 'cornice': 'A', 'pezzo': '1'} -> "PHerc421 Cornice A Pezzo 1"
            - {'pherc': '421', 'cornice': 'A', 'pezzo': None} -> "PHerc421 Cornice A"
            - {'pherc': '421', 'cornice': None, 'pezzo': None} -> "PHerc421"
        """
        if not artifact_info:
            return ''

        parts = []
        pherc = artifact_info.get('pherc')
        cornice = artifact_info.get('cornice')
        pezzo = artifact_info.get('pezzo')

        if pherc:
            parts.append(f'PHerc{pherc}')
        if cornice:
            parts.append(f'Cornice {cornice}')
        if pezzo:
            parts.append(f'Pezzo {pezzo}')

        return ' '.join(parts)

    def get_all_pipeline_summaries(self) -> list[dict]:
        """
        Returns list of all pipelines with their status summaries.

        Returns:
            list: List of dicts with keys:
                - datetime: Most recent process timestamp
                - dataset_name: Human-readable artifact name
                - artifact_uuid: UUID of the associated EduceLabID
                - pipeline_id: Pipeline identifier
                - status: Computed status (completed/partially_completed/submitted/failed/unknown(error))
        """
        # Get pipelines with their artifact UUIDs (only those with Process nodes)
        pipelines_with_processes = self.find_pipelines()

        # Build a dict of pipeline_id -> artifact_uuid for quick lookup
        pipeline_artifacts = {p['pipeline_id']: p['artifact_uuid'] for p in pipelines_with_processes}

        # Also find ALL pipeline nodes (including those without Process nodes)
        records, _, _ = self._run_query("""
            MATCH (p:Pipeline)
            RETURN p.pipeline_id AS pipeline_id
            ORDER BY p.pipeline_id
            """)

        all_pipeline_ids = [r['pipeline_id'] for r in records] if records else []

        if not all_pipeline_ids:
            return []

        # For each pipeline, get all processes and compute summary
        summaries = []
        for pipeline_id in all_pipeline_ids:
            artifact_uuid = pipeline_artifacts.get(pipeline_id)

            # Get all processes for this pipeline
            processes = self.get_pipeline_status(pipeline_id)
            if processes is None:
                processes = []

            # Get dataset name from artifact UUID
            dataset_name = ''
            if artifact_uuid:
                artifact_info = self.find_artifact_name_by_uuid(artifact_uuid)
                if artifact_info:
                    dataset_name = self._format_dataset_name(artifact_info)

            # Compute overall status
            status = self._compute_pipeline_status(processes)

            # Find most recent datetime
            most_recent_datetime = ''
            for proc in processes:
                dt = proc.get('datetime', '')
                if dt and (not most_recent_datetime or str(dt) > most_recent_datetime):
                    most_recent_datetime = str(dt)

            summaries.append({
                'datetime': most_recent_datetime,
                'dataset_name': dataset_name,
                'artifact_uuid': artifact_uuid or '',
                'pipeline_id': pipeline_id,
                'status': status
            })

        return summaries
            
    @staticmethod
    def records_to_label_json(records):
        #result = {}
        # Extract org_node properties from the first record (they are the same for all)
        if records:
            org_node = records[0]['org_node']
            org_label = next(iter(org_node.labels))
            # org_props = dict(org_node.items())
            # result['org_node'] = {org_label: org_props}
            result = dict(org_node)

        # Process attached_nodes as before
        for record in records:
            node = record['attached_nodes']
            label = next(iter(node.labels))
            props = dict(node.items())
            if label in result:
                # If already present, append to the list
                if isinstance(result[label], list):
                    result[label].append(props)
                else:
                    result[label] = [result[label], props]
            else:
                result[label] = props
        # Convert single dicts to lists if there are multiple nodes with the same label
        for label, value in list(result.items()):
            if label == "org_node":
                continue
            if isinstance(value, dict):
                continue
            elif isinstance(value, list) and len(value) == 1:
                result[label] = value[0]
        return result   


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
