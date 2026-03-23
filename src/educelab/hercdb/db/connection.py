import logging
from collections import OrderedDict
from enum import Enum

from neo4j import GraphDatabase


class DatasetType(Enum):
    FlatbedScan = 'FlatbedScanDataset'
    PGSRaw = 'PGSRaw'
    SpectralRaw = 'SpectralRaw'

    def __str__(self):
        return f'{self.value}'



class GraphDBConnection:
    logger = logging.getLogger('educelab.hercdb')
    uri: str = None
    user: str = None
    driver = None

    def __init__(self, uri, user, password) -> None:
        """Create a new connection to the graph database."""
        self.uri = uri
        self.user = user
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.logger.info("Initialized GraphDBConnection to %s as user %s", uri, user)

    def __del__(self) -> None:
        """Ensure the driver is closed on deletion of the instance."""
        self.close()

    def close(self) -> None:
        """Close the driver connection."""
        if self.driver is not None:
            self.driver.close()

    def verify_connection(self) -> bool:
        """Verify the connection to the database."""
        try:
            self.driver.verify_connectivity()
            return True
        except Exception as e:
            self.logger.debug('failed to connect', exc_info=e)
            return False
    
    def _run_query(self, query, **params) -> tuple:
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

    def _delete_all(self) -> None:
        """Delete all nodes and relationships in the database. Use with caution!"""
        records, summary, keys = self.driver.execute_query(
            """
            MATCH (n)
            DETACH DELETE n
            """,
            database_="neo4j",
        )

    def _return_all(self) -> None:
        """Return all nodes in the database. Use for debugging only."""
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

    # TODO: migrate cli/search.py to use list_cornici_and_pezzi_for_pherc, then remove this
    def list_cornici_pezzi(self, pherc) -> list:
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

    def _find_pherc_by_related_node(self, rel_type, label, value) -> tuple:
        """Find PHercs connected to a node via relationship, case-insensitive partial match."""
        query = f"""
            MATCH (ph:PHerc)-[:{rel_type}]->(n:{label})
            WHERE n.name =~ '(?i).*' + $value + '.*'
            RETURN ph ORDER BY ph.displayName
        """
        return self._run_query(query, value=value)

    @staticmethod
    def _serialize_dataset(record) -> dict:
        """Convert a Neo4j dataset record to a JSON-safe dict."""
        ds = dict(record['d'])
        ds['type'] = record['ds_type']
        for key, value in ds.items():
            if not isinstance(value, (str, int, float, bool, type(None), list, dict)):
                ds[key] = str(value)
        return ds

    def _get_node_id(self, node_type, pherc_display_name, cornice_display_name=None, pezzo_display_name=None, disegni_name=None) -> str | None:
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

    def get_directly_attached_nodes(self, node_type, pherc_display_name, cornice_display_name=None, pezzo_display_name=None, disegni_name=None) -> tuple:
        """Retrieve all nodes directly attached to a specified node."""
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

    
    def find_node_type_connected_to_object_node(self, obj_node_type, display_name, connected_node_type: str) -> tuple:
        """Find nodes of a specific type connected to an object node by its display name."""
        query = f"""
            MATCH (n:{obj_node_type} {{displayName:$display_name}})--(c:{connected_node_type})
            RETURN c
        """
        records, summary, keys = self._run_query(
            query,
            display_name=display_name
        )
        return records, summary, keys
    
    def find_pherc_by_uuid(self, uuid) -> tuple:
        """Look up a PHerc by its UUID. Currently only returns the PHerc node."""
        records, summary, keys = self._run_query("""
            MATCH (e:EduceLabID {uuid:$uuid})-[:ASSIGNED_TO]->(n)<-[:HAS*0..2]-(ph:PHerc)
            RETURN ph
            """, uuid=uuid)
        return records, summary, keys

    def find_artifact_name_by_uuid(self, uuid) -> dict | None:
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

    def find_pherc_by_display_name(self, display_name) -> tuple:
        """Look up a PHerc by its display name."""
        
        records, summary, keys = self._run_query("""
            MATCH (ph:PHerc {displayName:$display_name})
            RETURN ph
            """, display_name=display_name)
        return records, summary, keys

    def find_pherc_by_property_value(self, property_name, property_value) -> tuple:
        """Look up a PHerc by a property value (case-insensitive partial match)."""
        records, summary, keys = self._run_query("""
            MATCH (ph:PHerc)
            WHERE ph[$property_name] =~ '(?i).*' + $property_value + '.*'
            RETURN ph ORDER BY ph.displayName
            """, property_name=property_name, property_value=property_value)
        return records, summary, keys
    
    def find_pherc_by_language(self, lang) -> tuple:
        # names: "grc", "lat", "inc.", "grc?", "inc", "lat?"
        records, summary, keys = self._run_query("""
            MATCH (ph:PHerc)-[:HAS_LANGUAGE]->(l:Language)
            WHERE toLower(l.name) CONTAINS toLower($language)
            RETURN ph ORDER BY ph.displayName
            """, language=lang)
        return records, summary, keys
    
    def find_pherc_by_unroller_name(self, unroller_name) -> tuple:
        return self._find_pherc_by_related_node("UNROLLED_BY", "Unroller", unroller_name)

    def find_pherc_by_unrolling_method(self, unrolling_method) -> tuple:
        return self._find_pherc_by_related_node("UNROLLED_BY_METHOD", "UnrollingMethod", unrolling_method)

    def find_pherc_by_author(self, author_name) -> tuple:
        return self._find_pherc_by_related_node("AUTHORED_BY", "Author", author_name)

    def find_pherc_by_cavallo_scribal_style(self, scribal_style) -> tuple:
        return self._find_pherc_by_related_node("STYLE", "CavalloScribalStyle", scribal_style)

    def find_pherc_by_custodial_institution(self, institution_name) -> tuple:
        return self._find_pherc_by_related_node("STORED_AT", "CustodialInstitution", institution_name)
    
    def find_pherc_by_numeric_property(self, property, operator, value) -> tuple:
        """Look up PHercs by a numeric property (e.g. width, weight)."""
        query_string = f"""
            MATCH (ph:PHerc)
            WHERE toFloat(ph.{property}) {operator} {value}
            RETURN ph ORDER BY ph.displayName
        """
        records, summary, keys = self._run_query(
            query_string,
        )
        return records, summary, keys
    
    def find_pherc_by_unrolled_year(self, operator, year) -> tuple:
        """Find PHercs by unrolled year, handling date ranges like '1420, 1820-1858'."""
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

    def find_pherc_with_any_property_value(self, property_name) -> tuple:
        """Find all PHercs that have a non-null value for the given property."""
        query_string = f"""
            MATCH (ph:PHerc)
            WHERE ph.{property_name} IS NOT NULL
            RETURN ph ORDER BY ph.displayName
        """
        records, summary, keys = self._run_query(
            query_string,
        )
        return records, summary, keys

    def list_cornici_and_pezzi_for_pherc(self, pherc_display_name) -> list:
        """List all Cornici and Pezzi for a given PHerc displayName."""
        records, summary, keys = self._run_query("""
            MATCH (ph:PHerc {displayName:$pherc_display_name})
            OPTIONAL MATCH (ph)-[:HAS]->(c:Cornice)
            OPTIONAL MATCH (ph)-[:HAS]->(c)-[:HAS]->(p1:Pezzo)
            OPTIONAL MATCH (ph)-[:HAS]->(p2:Pezzo)
            WITH ph, COLLECT(DISTINCT c) AS cr, COLLECT(DISTINCT p1) + COLLECT(DISTINCT p2) AS pz
            RETURN ph, cr, pz

            """, pherc_display_name=pherc_display_name)
        return records
    
    def find_datasets(self, ds_type: DatasetType, pherc, cornice=None, pezzo=None, newest_completed=False, properties_only=True) -> list[dict] | tuple:
        """Find datasets of a specific type for a PHerc, Cornice, or Pezzo."""

        if cornice:
            base_query = """
                MATCH (ph:PHerc {displayName: $ph})-[:HAS]->(cr:Cornice {displayName: $cor})
                MATCH (cr)<-[:ASSIGNED_TO]-(e:EduceLabID)
                MATCH (e)<-[:BELONGS_TO]-(n)
                WHERE $data_t IN LABELS(n)
            """
            params = {"data_t": str(ds_type), "ph": pherc, "cor": cornice}
        elif pezzo:
            base_query = """
                MATCH (ph:PHerc {displayName: $ph})-[:HAS*1..2]->(pz:Pezzo {displayName: $pz})
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
        if newest_completed:
            query = base_query + """
                AND n.complete = "True"
                WITH e, n ORDER BY datetime(n.date_end) DESC
                RETURN n, e.uuid AS educelabid_uuid LIMIT 1
            """
        else:
            query = base_query + """
                RETURN n, e.uuid AS educelabid_uuid
            """

        records, summary, keys = self._run_query(query, **params)

        if not records:
            return [] if properties_only else ([], summary, keys)

        if properties_only:
            properties = []
            for record in records:
                dataset = dict(record["n"])
                dataset["educelabid_uuid"] = record["educelabid_uuid"]
                properties.append(dataset)

            return properties

        else:
            return records, summary, keys
   
    def find_pipelines(self) -> list[dict]:
        """Find all pipelines and return their pipeline_id and associated artifact_uuid."""
        records, _, _ = self._run_query("""
            MATCH (p:Pipeline)<-[:STAGE_OF]-(proc:Process)<-[:INPUT]-(input)
            WHERE 'PGSRaw' IN LABELS(input) OR 'SpectralRaw' IN LABELS(input)
            MATCH (e:EduceLabID)<-[:BELONGS_TO]-(input)
            RETURN DISTINCT p.pipeline_id AS pipeline_id, e.uuid AS artifact_uuid
            ORDER BY p.pipeline_id
            """)

        if not records:
            return []
        return [{"pipeline_id": r["pipeline_id"], "artifact_uuid": r["artifact_uuid"]} for r in records]
    
    def get_pipeline_status(self, pipeline_id) -> list[dict] | None:
        """Return the status of all processes in a pipeline, or None if not found."""
        records, _, _ = self._run_query("""
            MATCH (p:Pipeline {pipeline_id: $pipeline_id})<-[:STAGE_OF]-(proc:Process)
            RETURN proc
            ORDER BY proc.start_time
            """, pipeline_id=pipeline_id)

        if not records:
            return None

        processes = []
        for record in records:
            proc = record['proc']
            end_time = proc.get('end_time')
            processes.append({
                'start_time': str(proc.get('start_time', '')),
                'stage': proc.get('stage', ''),
                'status': proc.get('status', ''),
                'slurm_id': str(proc.get('slurm_id', '')),
                'end_time': str(end_time) if end_time else None
            })

        return processes

    @staticmethod
    def _compute_pipeline_status(processes: list[dict]) -> str:
        """
        Compute overall pipeline status from process list.

        Args:
            processes: List of process dicts with 'stage' and 'status' keys.

        Returns:
            str: One of 'completed', 'partially_completed', 'running', 'failed', 'unknown(error)'
                - completed: All stages in the pipeline finished successfully.
                - partially_completed: At least one stage completed but one or more failed.
                - running: At least one stage is still submitted and none have completed yet.
                - failed: No stage completed successfully (first stage likely failed).
                - unknown(error): No processes found or unrecognizable state.
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

        if not stage_statuses:
            return 'unknown(error)'

        statuses = list(stage_statuses.values())

        # All stages completed successfully
        if all(s == 'completed' for s in statuses):
            return 'completed'

        # At least one completed but one or more failed
        has_completed = any(s == 'completed' for s in statuses)
        has_failed = any(s == 'failed' for s in statuses)
        if has_completed and has_failed:
            return 'partially_completed'

        # No stage completed, all failed
        if all(s == 'failed' for s in statuses):
            return 'failed'

        # At least one stage is still submitted (running)
        has_submitted = any(s == 'submitted' for s in statuses)
        if has_submitted:
            return 'running'

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
                - start_time: Most recent process start_time timestamp
                - dataset_name: Human-readable artifact name
                - artifact_uuid: UUID of the associated EduceLabID
                - pipeline_id: Pipeline identifier
                - status: Computed status (completed/partially_completed/running/failed/unknown(error))
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

            # Find most recent start_time
            most_recent_datetime = ''
            for proc in processes:
                dt = proc.get('start_time', '')
                if dt and (not most_recent_datetime or str(dt) > most_recent_datetime):
                    most_recent_datetime = str(dt)

            summaries.append({
                'start_time': most_recent_datetime,
                'dataset_name': dataset_name,
                'artifact_uuid': artifact_uuid or '',
                'pipeline_id': pipeline_id,
                'status': status
            })

        return summaries

    def find_educelabids_for_pherc(self, pherc_display_name: str) -> list[dict]:
        """Find all EduceLabIDs under a PHerc umbrella (PHerc, Cornici, Pezzi)."""
        records, _, _ = self._run_query("""
            MATCH (ph:PHerc {displayName: $pherc_display_name})
            MATCH (ph)-[:HAS*0..2]->(artifact)
            WHERE artifact:PHerc OR artifact:Cornice OR artifact:Pezzo
            MATCH (eid:EduceLabID)-[:ASSIGNED_TO]->(artifact)
            OPTIONAL MATCH (artifact)<-[:HAS]-(parent1)
            OPTIONAL MATCH (parent1)<-[:HAS]-(parent2)
            WITH eid, artifact, parent1, parent2,
                 CASE
                     WHEN 'PHerc' IN labels(artifact) THEN artifact
                     WHEN 'PHerc' IN labels(parent1) THEN parent1
                     WHEN 'PHerc' IN labels(parent2) THEN parent2
                 END AS pherc_node,
                 CASE
                     WHEN 'Cornice' IN labels(artifact) THEN artifact
                     WHEN 'Cornice' IN labels(parent1) THEN parent1
                 END AS cornice_node,
                 CASE
                     WHEN 'Pezzo' IN labels(artifact) THEN artifact
                 END AS pezzo_node
            RETURN DISTINCT eid.uuid AS uuid,
                   pherc_node.displayName AS pherc_name,
                   cornice_node.displayName AS cornice_name,
                   pezzo_node.displayName AS pezzo_name
            ORDER BY pherc_name, cornice_name, pezzo_name
            """, pherc_display_name=pherc_display_name)

        if not records:
            return []

        results = []
        for record in records:
            info = {
                'pherc': record['pherc_name'],
                'cornice': record['cornice_name'],
                'pezzo': record['pezzo_name'],
            }
            results.append({
                'uuid': record['uuid'],
                'pherc': record['pherc_name'],
                'cornice': record['cornice_name'],
                'pezzo': record['pezzo_name'],
                'artifact_name': self._format_dataset_name(info),
            })
        return results

    def find_datasets_for_educelabid(self, uuid: str, ds_type: DatasetType = None, newest_completed: bool = False) -> list[dict]:
        """Find all datasets for a specific EduceLabID."""
        dataset_labels = ['FlatbedScanDataset', 'PGSRaw', 'SpectralRaw']
        type_filter = "AND $data_t IN LABELS(d)" if ds_type else ""
        completed_filter = 'AND d.complete = "True"' if newest_completed else ""

        grouping = """
            ORDER BY datetime(d.date_end) DESC
            WITH ds_type, collect(d)[0] AS d
            RETURN d, ds_type
        """ if newest_completed else "RETURN d, ds_type"

        query = f"""
            MATCH (e:EduceLabID {{uuid: $uuid}})<-[:BELONGS_TO]-(d)
            WHERE (d:FlatbedScanDataset OR d:PGSRaw OR d:SpectralRaw)
            {completed_filter}
            {type_filter}
            WITH d,
                 [l IN labels(d) WHERE l IN $dataset_labels][0] AS ds_type
            {grouping}
        """

        params = {"uuid": uuid, "dataset_labels": dataset_labels}
        if ds_type:
            params["data_t"] = str(ds_type)

        records, _, _ = self._run_query(query, **params)

        if not records:
            return []

        return [self._serialize_dataset(record) for record in records]

    def find_all_datasets_for_pherc(self, pherc_display_name: str, ds_type: DatasetType = None, newest_completed: bool = False) -> list[dict]:
        """
        Find all datasets under a PHerc umbrella, grouped by EduceLabID.

        Traverses the full PHerc hierarchy (PHerc, Cornici, Pezzi) and returns
        all datasets, nested by the physical artifact they belong to.

        Args:
            pherc_display_name: Display name of the PHerc.
            ds_type: Optional DatasetType filter.
            newest_completed: If True, return only the newest completed dataset
                per type per artifact.

        Returns:
            list: List of artifact dicts, each with keys: uuid, artifact_name,
                pherc, cornice, pezzo, datasets.
        """
        dataset_labels = ['FlatbedScanDataset', 'PGSRaw', 'SpectralRaw']
        type_filter = "AND $data_t IN LABELS(d)" if ds_type else ""
        completed_filter = 'AND d.complete = "True"' if newest_completed else ""

        query = f"""
            MATCH (ph:PHerc {{displayName: $pherc_display_name}})
            MATCH (ph)-[:HAS*0..2]->(artifact)
            WHERE artifact:PHerc OR artifact:Cornice OR artifact:Pezzo
            MATCH (eid:EduceLabID)-[:ASSIGNED_TO]->(artifact)
            MATCH (eid)<-[:BELONGS_TO]-(d)
            WHERE (d:FlatbedScanDataset OR d:PGSRaw OR d:SpectralRaw)
            {type_filter}
            {completed_filter}
            OPTIONAL MATCH (artifact)<-[:HAS]-(parent1)
            OPTIONAL MATCH (parent1)<-[:HAS]-(parent2)
            WITH eid, d, artifact, parent1, parent2,
                 [l IN labels(d) WHERE l IN $dataset_labels][0] AS ds_type,
                 CASE
                     WHEN 'PHerc' IN labels(artifact) THEN artifact
                     WHEN 'PHerc' IN labels(parent1) THEN parent1
                     WHEN 'PHerc' IN labels(parent2) THEN parent2
                 END AS pherc_node,
                 CASE
                     WHEN 'Cornice' IN labels(artifact) THEN artifact
                     WHEN 'Cornice' IN labels(parent1) THEN parent1
                 END AS cornice_node,
                 CASE
                     WHEN 'Pezzo' IN labels(artifact) THEN artifact
                 END AS pezzo_node
            RETURN eid.uuid AS uuid,
                   pherc_node.displayName AS pherc_name,
                   cornice_node.displayName AS cornice_name,
                   pezzo_node.displayName AS pezzo_name,
                   d AS dataset,
                   ds_type AS dataset_type
            ORDER BY pherc_name, cornice_name, pezzo_name
        """

        params = {
            "pherc_display_name": pherc_display_name,
            "dataset_labels": dataset_labels,
        }
        if ds_type:
            params["data_t"] = str(ds_type)

        records, _, _ = self._run_query(query, **params)

        if not records:
            return []

        # Group by EduceLabID UUID
        grouped = OrderedDict()
        for record in records:
            uuid = record['uuid']
            if uuid not in grouped:
                info = {
                    'pherc': record['pherc_name'],
                    'cornice': record['cornice_name'],
                    'pezzo': record['pezzo_name'],
                }
                grouped[uuid] = {
                    'uuid': uuid,
                    'artifact_name': self._format_dataset_name(info),
                    'pherc': record['pherc_name'],
                    'cornice': record['cornice_name'],
                    'pezzo': record['pezzo_name'],
                    'datasets': [],
                }

            ds = self._serialize_dataset({'d': record['dataset'], 'ds_type': record['dataset_type']})
            grouped[uuid]['datasets'].append(ds)

        results = list(grouped.values())

        # If newest_completed, keep only the newest dataset per type per artifact
        if newest_completed:
            for artifact in results:
                newest_by_type = {}
                for ds in artifact['datasets']:
                    dt = ds.get('type', '')
                    existing = newest_by_type.get(dt)
                    if existing is None or ds.get('date_end', '') > existing.get('date_end', ''):
                        newest_by_type[dt] = ds
                artifact['datasets'] = list(newest_by_type.values())

        return results

    def initialize_pipeline(self, pipeline_id: str, artifact_uuid: str, datetime: str) -> dict | None:
        """Create a Pipeline node and link it to an EduceLabID."""
        records, _, _ = self._run_query("""
            MATCH (e:EduceLabID {uuid: $artifact_uuid})
            MERGE (p:Pipeline {pipeline_id: $pipeline_id})
            SET p.datetime = $datetime
            MERGE (p)-[:FOR]->(e)
            RETURN p, e.uuid AS artifact_uuid
            """, pipeline_id=pipeline_id, artifact_uuid=artifact_uuid, datetime=datetime)

        if not records:
            return None
        record = records[0]
        pipeline = dict(record['p'])
        return {
            'pipeline_id': pipeline.get('pipeline_id'),
            'artifact_uuid': record['artifact_uuid'],
            'datetime': pipeline.get('datetime'),
        }

    def initialize_process(self, pipeline_id: str, proc_type: str, input_dataset_paths: list[str],
                           output_dataset_path: str, slurm_id: str, start_datetime: str) -> dict | None:
        """Create a Process node linked to input/output datasets and a Pipeline.

        Args:
            pipeline_id: Pipeline to attach the process to.
            proc_type: One of PGS, SPEC, REG, WEB.
            input_dataset_paths: List of input dataset paths.
            output_dataset_path: Path for the output dataset node.
            slurm_id: Slurm job ID.
            start_datetime: ISO datetime string for start time.

        Returns:
            Dict with process info, or None on failure.
        """
        base_params = {
            "pipeline_id": pipeline_id,
            "slurm_id": slurm_id,
            "start_datetime": start_datetime,
            "output_path": output_dataset_path,
        }

        if proc_type == "PGS":
            query = """
            MATCH (ppline:Pipeline {pipeline_id: $pipeline_id})-[:FOR]->(e:EduceLabID)
            MATCH (e)<-[:BELONGS_TO]-(input:PGSRaw {path: $input_path})
            MERGE (proc:Process {stage: "PGS", start_time: $start_datetime, slurm_id: $slurm_id, status: "submitted"})
            MERGE (output:PGSProcessed {path: $output_path})
            MERGE (input)-[:INPUT]->(proc)-[:OUTPUT]->(output)
            MERGE (proc)-[:STAGE_OF]->(ppline)
            RETURN proc
            """
            base_params["input_path"] = input_dataset_paths[0]

        elif proc_type == "SPEC":
            query = """
            MATCH (ppline:Pipeline {pipeline_id: $pipeline_id})-[:FOR]->(e:EduceLabID)
            MATCH (e)<-[:BELONGS_TO]-(input:SpectralRaw {path: $input_path})
            MERGE (proc:Process {stage: "SPEC", start_time: $start_datetime, slurm_id: $slurm_id, status: "submitted"})
            MERGE (output:SpectralProcessed {path: $output_path})
            MERGE (input)-[:INPUT]->(proc)-[:OUTPUT]->(output)
            MERGE (proc)-[:STAGE_OF]->(ppline)
            RETURN proc
            """
            base_params["input_path"] = input_dataset_paths[0]

        elif proc_type == "REG":
            query = """
            MATCH (ppline:Pipeline {pipeline_id: $pipeline_id})<-[:STAGE_OF]-(:Process)--(pg_proc:PGSProcessed {path: $input_pgs_path})
            MATCH (ppline)<-[:STAGE_OF]-(:Process)--(spec_proc:SpectralProcessed {path: $input_spec_path})
            MERGE (proc:Process {stage: "REG", start_time: $start_datetime, slurm_id: $slurm_id, status: "submitted"})
            MERGE (reg:Registered {path: $output_path})
            MERGE (pg_proc)-[:INPUT]->(proc)<-[:INPUT]-(spec_proc)
            MERGE (proc)-[:OUTPUT]->(reg)
            MERGE (proc)-[:STAGE_OF]->(ppline)
            RETURN proc
            """
            base_params["input_pgs_path"] = input_dataset_paths[0]
            base_params["input_spec_path"] = input_dataset_paths[1]

        elif proc_type == "WEB":
            query = """
            MATCH (ppline:Pipeline {pipeline_id: $pipeline_id})<-[:STAGE_OF]-(:Process)--(reg:Registered {path: $input_path})
            MERGE (proc:Process {stage: "WEB", start_time: $start_datetime, slurm_id: $slurm_id, status: "submitted"})
            MERGE (web:WebProcessed {path: $output_path})
            MERGE (reg)-[:INPUT]->(proc)-[:OUTPUT]->(web)
            MERGE (proc)-[:STAGE_OF]->(ppline)
            RETURN proc
            """
            base_params["input_path"] = input_dataset_paths[0]

        else:
            self.logger.error("Unsupported proc_type: %s", proc_type)
            return None

        records, _, _ = self._run_query(query, **base_params)

        if not records:
            return None
        proc = dict(records[0]['proc'])
        return {
            'stage': proc.get('stage', ''),
            'slurm_id': str(proc.get('slurm_id', '')),
            'start_time': str(proc.get('start_time', '')),
            'status': proc.get('status', ''),
        }

    def update_process_status(self, pipeline_id: str, stage: str, status: str, end_datetime: str) -> dict | None:
        """Update the status and end_time of a process in a pipeline.

        Args:
            pipeline_id: The pipeline ID.
            stage: The process stage (PGS, SPEC, REG, WEB).
            status: New status (completed or failed).
            end_datetime: ISO datetime string for end time.

        Returns:
            Dict with updated process info, or None on failure.
        """
        records, _, _ = self._run_query("""
            MATCH (ppline:Pipeline {pipeline_id: $pipeline_id})<-[:STAGE_OF]-(proc:Process {stage: $stage})
            SET proc.status = $status, proc.end_time = $end_datetime
            RETURN proc
            """, pipeline_id=pipeline_id, stage=stage, status=status, end_datetime=end_datetime)

        if not records:
            return None
        proc = dict(records[0]['proc'])
        return {
            'stage': proc.get('stage', ''),
            'slurm_id': str(proc.get('slurm_id', '')),
            'start_time': str(proc.get('start_time', '')),
            'end_time': str(proc.get('end_time', '')) if proc.get('end_time') else None,
            'status': proc.get('status', ''),
        }

    def delete_pipeline(self, pipeline_id: str) -> dict | None:
        """Delete a Pipeline and all its Process nodes and output dataset nodes.

        Removes the Pipeline node, every Process linked via STAGE_OF, and every
        output dataset node (PGSProcessed, SpectralProcessed, Registered,
        WebProcessed) produced by those processes.  Input datasets (PGSRaw,
        SpectralRaw, etc.) are NOT deleted.

        Returns:
            Dict with pipeline_id and counts of deleted nodes, or None if the
            pipeline was not found.
        """
        records, _, _ = self._run_query("""
            MATCH (ppline:Pipeline {pipeline_id: $pipeline_id})
            OPTIONAL MATCH (ppline)<-[:STAGE_OF]-(proc:Process)
            OPTIONAL MATCH (proc)-[:OUTPUT]->(out)
            WITH ppline, collect(DISTINCT proc) AS procs, collect(DISTINCT out) AS outs
            WITH ppline, procs, outs,
                 size(procs) AS proc_count, size(outs) AS out_count
            FOREACH (o IN outs | DETACH DELETE o)
            FOREACH (p IN procs | DETACH DELETE p)
            DETACH DELETE ppline
            RETURN $pipeline_id AS pipeline_id, proc_count, out_count
            """, pipeline_id=pipeline_id)

        if not records:
            return None
        record = records[0]
        return {
            'pipeline_id': record['pipeline_id'],
            'processes_deleted': record['proc_count'],
            'output_datasets_deleted': record['out_count'],
        }

    def get_pipeline_confirmation(self, pipeline_id: str) -> dict | None:
        """Return full pipeline summary with all stages.

        Args:
            pipeline_id: The pipeline ID.

        Returns:
            Dict with pipeline_id, artifact_uuid, date, status, and stages list.
            Returns None if the pipeline is not found.
        """
        records, _, _ = self._run_query("""
            MATCH (ppline:Pipeline {pipeline_id: $pipeline_id})
            OPTIONAL MATCH (ppline)-[:FOR]->(e:EduceLabID)
            OPTIONAL MATCH (ppline)<-[:STAGE_OF]-(proc:Process)
            RETURN ppline, e.uuid AS artifact_uuid, collect(proc) AS processes
            """, pipeline_id=pipeline_id)

        if not records:
            return None

        record = records[0]
        pipeline = dict(record['ppline'])

        if not pipeline:
            return None

        processes = []
        for proc_node in record['processes']:
            proc = dict(proc_node)
            end_time = proc.get('end_time')
            processes.append({
                'proc_type': proc.get('stage', ''),
                'slurm_id': str(proc.get('slurm_id', '')),
                'start_time': str(proc.get('start_time', '')),
                'end_time': str(end_time) if end_time else None,
                'status': proc.get('status', ''),
            })

        # Sort by start_time
        processes.sort(key=lambda p: p['start_time'])

        # Compute overall status using existing helper (needs stage key)
        status_input = [{'stage': p['proc_type'], 'status': p['status']} for p in processes]
        overall_status = self._compute_pipeline_status(status_input)

        return {
            'pipeline_id': pipeline.get('pipeline_id'),
            'artifact_uuid': record['artifact_uuid'] or '',
            'datetime': pipeline.get('datetime', ''),
            'status': overall_status,
            'stages': processes,
        }

    @staticmethod
    def records_to_label_json(records) -> dict:
        """Convert Neo4j records (org_node + attached_nodes) to a label-keyed dict."""
        if records:
            org_node = records[0]['org_node']
            result = dict(org_node)

        for record in records:
            node = record['attached_nodes']
            label = next(iter(node.labels))
            props = dict(node.items())
            if label in result:
                if isinstance(result[label], list):
                    result[label].append(props)
                else:
                    result[label] = [result[label], props]
            else:
                result[label] = props
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
