import logging
from datetime import datetime
from neo4j import GraphDatabase
from educelab.hercdb import config

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('educelab.dataloader')

class PhercGraphDatabaseLoader:

    def __init__(self, uri=None, user=None, password=None):
        """
        Create a new connection to the graph database.
        If uri, user, or password are not provided, they will be read from ~/.educedb config file.
        """
        if uri is None:
            uri = config.uri
        if user is None:
            user = config.username
        if password is None:
            password = config.password
            
        self.uri = uri
        self.user = user
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Initialized GraphDBConnection to %s as user %s", uri, user)
        
        
    def close(self):
        self.driver.close()

    def verify_conn(self):
        self.driver.verify_connectivity()
        print("connected to Neo4j.")

    def _run_query(self, query, **params):
        try:
            records, summary, keys = self.driver.execute_query(
                query,
                **params,
                database_="neo4j",
            )
            #print(records, summary, keys)
            return records, summary, keys
        
        except Exception as e:
            print(e)
            return None, None, None
        
    def _delete_all_nodes(self):
        # This method deletes all nodes in the database
        records, summary, keys = self._run_query(
            """
            MATCH (n)
            DETACH DELETE n
            """
        ) 
        print("All nodes deleted.")



############ Specific methods for adding EduceLabIDs from UUID spreadsheet ##################
############ THIS SHOULD RUN AFTER METADATA ###########

    #### For parsing UUID spreadsheet ####
    def look_up_object_by_uuid(self, uuid):
        # This method looks up an item by its UUID
        # Walks up to 2 :HAS hops from the assigned node to find a PHerc or
        # Casetta root, then returns whichever physical-object labels appear.
        records, summary, keys = self._run_query("""
            MATCH path=(e:EduceLabID {uuid:$uuid})-[:ASSIGNED_TO]->(n)<-[:HAS*0..2]-(top)
            WHERE top:PHerc OR top:Casetta
            UNWIND nodes(path) AS node
            RETURN labels(node) AS node_labels, node.displayName AS displayName
            """, uuid=uuid)
        item = {}
        if not records:
            return item
        for record in records:
            labels = record['node_labels']
            if 'EduceLabID' in labels:
                continue
            # Multi-labelled nodes (e.g. :PHerc:Casetta) resolve under :PHerc
            # so existing PHerc-anchored callers keep working unchanged.
            for preferred in ('PHerc', 'Casetta', 'Cornice', 'Pezzo'):
                if preferred in labels:
                    item[preferred] = record['displayName']
                    break

        return item

    def set_alias_on_assigned_node(self, uuid, ph_name, alias_name):
        """
        UUID phase helper: when an EduceLabID is already assigned to a
        Cornice/Pezzo (linked during the metadata phase), record the UUID
        sheet's short name as `name` on the existing node instead of MERGE-
        creating a duplicate keyed off a different displayName. Also sets
        `name` on the ancestor PHerc/Casetta.
        """
        self._run_query("""
            MATCH (e:EduceLabID {uuid: $uuid})-[:ASSIGNED_TO]->(n)
            SET n.name = $alias_name
            WITH n
            OPTIONAL MATCH (n)<-[:HAS*1..2]-(p)
            WHERE p:PHerc OR p:Casetta
            SET p.name = $ph_name
            """, uuid=uuid, alias_name=alias_name, ph_name=ph_name)

    # Add EduceLabID nodes
    # Each EduceLabID node has an id and a uuid
    def add_EduceLabID(self, educelab_id, uuid):
        records, summary, keys = self._run_query("""
            MERGE (e:EduceLabID {uuid:$uuid})
            SET e.educelab_id = $educelab_id                        
            """, educelab_id = educelab_id, uuid=uuid
        )
    
    def set_pherc_and_pezzo_names(self, uuid, pherc_display_name, pherc_name, pezzo_name):
        records, summary, keys = self._run_query("""

            MATCH (e: EduceLabID {uuid:$uuid})-[:ASSIGNED_TO]->(p:Pezzo)<-[:HAS*1..2]-(ph:PHerc {displayName:$pherc_display_name})
            SET p.name = $pezzo_name
            SET ph.name = $pherc_name                                   
            """, uuid=uuid, pherc_display_name=pherc_display_name, pezzo_name=pezzo_name, pherc_name=pherc_name
        )

    def set_pherc_and_cornice_names(self, uuid, pherc_display_name, pherc_name, cornice_name):
        records, summary, keys = self._run_query("""
            MATCH (e:EduceLabID {uuid:$uuid})
            MATCH (ph:PHerc {displayName:$pherc_display_name})
            MERGE (ph)-[:HAS]->(c:Cornice {displayName: $cornice_name})
            MERGE (e)-[:ASSIGNED_TO]->(c)
            SET c.name = $cornice_name
            SET ph.name = $pherc_name
            """, uuid=uuid, pherc_display_name=pherc_display_name, cornice_name=cornice_name, pherc_name=pherc_name
        )    

    def set_ph_name(self, uuid, pherc_name):
        """
        UUID phase: record `pherc_name` as a `name` alias on the PHerc/Casetta
        ancestor of whatever node the EduceLabID is :ASSIGNED_TO. The previous
        version unconditionally MERGE-created `(e)-[:ASSIGNED_TO]->(:PHerc)`
        without a displayName constraint, which produced phantom PHerc nodes
        whenever the EduceLabID was already linked to a Cornice/Pezzo from the
        metadata phase. If the EduceLabID has no PHerc/Casetta ancestor at
        all, fall back to creating one keyed on pherc_name as displayName.
        """
        records, _, _ = self._run_query("""
            MATCH (e:EduceLabID {uuid:$uuid})-[:ASSIGNED_TO]->(n)<-[:HAS*0..2]-(p)
            WHERE p:PHerc OR p:Casetta
            SET p.name = $pherc_name
            RETURN count(p) AS matched
            """, uuid=uuid, pherc_name=pherc_name
        )
        if records and records[0]['matched'] > 0:
            return

        # No PHerc/Casetta ancestor for this UUID — create one.
        self._run_query("""
            MATCH (e:EduceLabID {uuid:$uuid})
            MERGE (e)-[:ASSIGNED_TO]->(ph:PHerc {displayName: $pherc_name})
            SET ph.name = $pherc_name
            """, uuid=uuid, pherc_name=pherc_name
        )

    def add_pherc_and_cornice_nodes_from_uuid_sheet(self, uuid, pherc_name, cornice_name):
        records,summary, keys = self._run_query("""
            MATCH (e:EduceLabID {uuid:$uuid})
            MERGE (ph:PHerc {name:$pherc_name})         
            MERGE (e)-[:ASSIGNED_TO]->(c:Cornice)<-[:HAS]-(ph)
            SET c.name = $cornice_name                                   
            """, uuid=uuid,  cornice_name=cornice_name, pherc_name=pherc_name
        )

    # Add Replacement EduceLabID nodes
    # This method creates a new EduceLabID node and links it to the original one
    # with a REPLACES relationship.
    def add_replacement_EduceLabID(self, original_id, replacement_uuid):
        records, summary, keys = self._run_query("""
            MATCH (orig:EduceLabID {uuid: $original_id})
            MERGE (new:EduceLabID {uuid: $replacement_uuid})
            MERGE (orig)<-[:REPLACES]-(new)
            """, original_id=original_id, replacement_uuid=replacement_uuid)

    def mark_educelabid_retired(self, uuid, reason=""):
        """Flag an EduceLabID as retired (no successor UUID).

        Used when the UUID file's `Replacement UUID` column holds a sentinel
        like "discarded" or "." rather than a real successor UUID.
        """
        self._run_query("""
            MATCH (e:EduceLabID {uuid: $uuid})
            SET e.retired = true, e.retired_reason = $reason
            """, uuid=uuid, reason=reason)


############## From Metadata spreadsheet ################

    # Add PHerc nodes
    # Each PHerc node has a name
    def add_pherc_node(self, uuid, ph_display_name, is_casetta=False):
        casetta_set = "SET p:Casetta" if is_casetta else ""
        if uuid:
            # Very few cases where uuid is provided (currently only PHerc 72, 1362, 1363)
            records, summary, keys = self._run_query(f"""
                MERGE (e:EduceLabID {{uuid: $uuid}})
                MERGE (p:PHerc {{displayName: $ph_display_name}})<-[:ASSIGNED_TO]-(e)
                {casetta_set}
                """, ph_display_name=ph_display_name, uuid=uuid,
            )
        else:
            records, summary, keys = self._run_query(f"""
                MERGE (p:PHerc {{displayName: $ph_display_name}})
                {casetta_set}
                """, ph_display_name=ph_display_name,
            )
 
    # Add Cornice nodes and attach them to PHerc and EduceLabID nodes
    # Note: Perhaps do this from the metadata file side first
    def add_cornice_nodes_and_attach(self, uuid, ph_display_name, cornice_display_name):
        if uuid:
            records, summary, keys = self._run_query("""
                MATCH (p:PHerc {displayName: $ph_display_name})
                MERGE (e:EduceLabID {uuid: $uuid})
                MERGE (p)-[:HAS]->(:Cornice {displayName: $cornice_display_name})<-[:ASSIGNED_TO]-(e)
                """, ph_display_name=ph_display_name, uuid=uuid, cornice_display_name=cornice_display_name,
            )
        else:
            records, summary, keys = self._run_query("""
                MATCH (p:PHerc {displayName: $ph_display_name})
                MERGE (p)-[:HAS]->(:Cornice {displayName: $cornice_display_name})
                """, ph_display_name=ph_display_name, cornice_display_name=cornice_display_name,
            )

    # Note: this has to be from the metadata file
    def add_pezzo_node_and_attach(self, uuid, pezzo_display_name, ph_display_name=None, cornice_display_name=None):

        # Check if at least one of ph_display_name or cornice_display_name is provided
        if ph_display_name is None and cornice_display_name is None:
            print("Error: Either ph_display_name or cornice_display_name must be provided.")
            return

        if cornice_display_name:
            if uuid:
                records, summary, keys = self._run_query("""
                    MATCH (p:PHerc {displayName: $ph_display_name})-[:HAS]->(c:Cornice {displayName: $cornice_display_name})
                    MERGE (e:EduceLabID {uuid: $uuid})
                    MERGE (c)-[:HAS]->(:Pezzo {displayName: $pezzo_display_name})<-[:ASSIGNED_TO]-(e)
                    """, ph_display_name=ph_display_name, cornice_display_name=cornice_display_name, uuid=uuid, pezzo_display_name=pezzo_display_name,
                )
            else:
                records, summary, keys = self._run_query("""
                    MATCH (p:PHerc {displayName: $ph_display_name})-[:HAS]->(c:Cornice {displayName: $cornice_display_name})
                    MERGE (c)-[:HAS]->(:Pezzo {displayName: $pezzo_display_name})
                    """, ph_display_name=ph_display_name, cornice_display_name=cornice_display_name, pezzo_display_name=pezzo_display_name,
                )

        elif ph_display_name:
            # If only ph_display_name is provided, attach Pezzo directly to PHerc
            if uuid:
                records, summary, keys = self._run_query("""          
                    MATCH (p:PHerc {displayName: $ph_display_name})
                    MERGE (e:EduceLabID {uuid: $uuid})
                    MERGE (p)-[:HAS]->(:Pezzo {displayName: $pezzo_display_name})<-[:ASSIGNED_TO]-(e)
                    """, ph_display_name=ph_display_name, uuid=uuid, pezzo_display_name=pezzo_display_name,
                )
            else:
                records, summary, keys = self._run_query("""
                    MATCH (p:PHerc {displayName: $ph_display_name})
                    MERGE (p)-[:HAS]->(:Pezzo {displayName: $pezzo_display_name})
                    """, ph_display_name=ph_display_name, pezzo_display_name=pezzo_display_name,
                )

    # Add Desegni node and attach to PHerc
    # Note: This is necessary because Desgni is a separate row in metadata file
    def add_disegni_node_and_attach(self, ph_display_name, disegni_name):
        records, summary, keys = self._run_query("""
            MATCH (p:PHerc {displayName: $ph_display_name})
            MERGE (p)<-[:DEPICTS]-(:Disegni {name: $disegni_name})
            """, ph_display_name=ph_display_name, disegni_name=disegni_name,
        )


#################### General methods for adding information #####################

    # Get the Neo4j internal node id for PHerc, Cornice, or Pezzo node
    def _get_node_id(self, node_type, pherc_display_name, cornice_display_name=None, pezzo_display_name=None, disegni_name=None):
        """
        Returns the Neo4j internal node id for PHerc, Cornice, or Pezzo node.
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

    def set_node_property(self, node_type, property_name, value, pherc_display_name, cornice_display_name=None,
                             pezzo_display_name=None, disegni_name=None):
        """
        Sets a property for a node identified by its Neo4j internal id.
        """
        node_id = self._get_node_id(node_type, pherc_display_name, cornice_display_name, pezzo_display_name, disegni_name)
        if node_id is None:
            print(f"Error: Node of type {node_type} with specified names not found.")
            return
        # Construct the query to set the property
        query = f"""
            MATCH (n)
            WHERE elementId(n) = $node_id
            SET n.{property_name} = $value
        """
        params = {"node_id": node_id, "value": value}
        self._run_query(query, **params)

###############  Row-specific methods ###################

    def add_custodial_institution_node(self, node_type, pherc_display_name, institution_name, insitution_url=None,
                                       cornice_display_name=None, pezzo_display_name=None, disegni_name=None):
        try:
            node_id = self._get_node_id(node_type, pherc_display_name, cornice_display_name, pezzo_display_name, disegni_name)
        except Exception as e:
            print(f"Error retrieving node ID: {e}")
            return
        query = """
            MATCH (n)
            WHERE elementId(n) = $node_id
            MERGE (i:CustodialInstitution {name: $institution_name})
            MERGE (n)-[:STORED_AT]->(i)
        """
        params = {
            "node_id": node_id,
            "institution_name": institution_name
        }
        if insitution_url:
            query += " SET i.url = $institution_url"
            params["institution_url"] = insitution_url
        self._run_query(query, **params)

    def add_custodial_location_node(self, institution_name, location, location_url=None):
        query = """
            MATCH (i:CustodialInstitution {name: $institution_name})
            MERGE (l:CustodialLocation {name: $location})
            MERGE (i)-[:LOCATED_AT]->(l)          
        """
        params = {"institution_name": institution_name, "location": location}
        if location_url:
            query += " SET l.url = $location_url"
            params["location_url"] = location_url
        self._run_query(query, **params)


    def add_object_format_node_and_attach(self, node_type, pherc_display_name, object_format, object_format_url=None,
                                          cornice_display_name=None, pezzo_display_name=None, disegni_name=None):
        try:
            node_id = self._get_node_id(node_type, pherc_display_name, cornice_display_name, pezzo_display_name, disegni_name)
        except Exception as e:
            print(f"Error retrieving node ID: {e}")
            return        
        query = """
            MATCH (n)
            WHERE elementId(n) = $node_id
            MERGE (o:ObjectFormat {format: $object_format})
            MERGE (n)-[:HAS_OBJECT_FORMAT]->(o)
        """
        params = {
            "node_id": node_id,
            "object_format": object_format
        }
        if object_format_url:
            query += " SET o.url = $object_format_url"
            params["object_format_url"] = object_format_url
        self._run_query(query, **params)

    def add_material_type_node_and_attach(self, node_type, pherc_display_name, material_type, material_type_url=None,
                                          cornice_display_name=None, pezzo_display_name=None, disegni_name=None):
        try:
            node_id = self._get_node_id(node_type, pherc_display_name, cornice_display_name, pezzo_display_name, disegni_name)
        except Exception as e:
            print(f"Error retrieving node ID: {e}")
            return        
        query = """
            MATCH (n)
            WHERE elementId(n) = $node_id
            MERGE (m:MaterialType {format: $material_type})
            MERGE (n)-[:HAS_MATERIAL_TYPE]->(m)
        """
        params = {
            "node_id": node_id,
            "material_type": material_type
        }
        if material_type_url:
            query += " SET m.url = $material_type_url"
            params["material_type_url"] = material_type_url
        self._run_query(query, **params)



    def add_language_node_and_attach(self, language, node_type, pherc_display_name, language_url=None, 
                                     cornice_display_name=None, pezzo_display_name=None, disegni_name=None):
        try:
            node_id = self._get_node_id(node_type, pherc_display_name, cornice_display_name, pezzo_display_name, disegni_name)
        except Exception as e:
            print(f"Error retrieving node ID: {e}")
            return
        query = """
            MATCH (n)
            WHERE elementId(n) = $node_id
            MERGE (l:Language {name: $language})
            MERGE (n)-[:HAS_LANGUAGE]->(l)
        """
        params = {
            "node_id": node_id,
            "language": language
        }
        if language_url:
            query += " SET l.url = $language_url"
            params["language_url"] = language_url
        self._run_query(query, **params)

    def add_unroller_node_and_attach(self, node_type, unroller_name, pherc_display_name, cornice_display_name=None, pezzo_display_name=None, disegni_name=None):
        try:
            node_id = self._get_node_id(node_type, pherc_display_name, cornice_display_name, pezzo_display_name, disegni_name)
        except Exception as e:
            print(f"Error retrieving node ID: {e}")
            return
        
        query = """
            MATCH (n)
            WHERE elementId(n) = $node_id
            MERGE (u:Unroller {name: $unroller_name})
            MERGE (n)-[:UNROLLED_BY]->(u)
        """
        params = {
            "node_id": node_id,
            "unroller_name": unroller_name
        }
        self._run_query(query, **params)

    def add_unrolling_method_node_and_attach(self, node_type, unrolling_method_name, pherc_display_name, cornice_display_name=None, pezzo_display_name=None, disegni_name=None):
        try:
            node_id = self._get_node_id(node_type, pherc_display_name, cornice_display_name, pezzo_display_name, disegni_name)
        except Exception as e:
            print(f"Error retrieving node ID: {e}")
            return
        
        query = """
            MATCH (n)
            WHERE elementId(n) = $node_id
            MERGE (um:UnrollingMethod {name: $unrolling_method_name})
            MERGE (n)-[:UNROLLED_BY_METHOD]->(um)
        """
        params = {
            "node_id": node_id,
            "unrolling_method_name": unrolling_method_name
        }
        self._run_query(query, **params)

    def add_oslo_method_node_and_attach(self, node_type, pherc_display_name, cornice_display_name=None, pezzo_display_name=None, disegni_name=None):
        try:
            node_id = self._get_node_id(node_type, pherc_display_name, cornice_display_name, pezzo_display_name, disegni_name)
        except Exception as e:
            print(f"Error retrieving node ID: {e}")
            return
        
        query = """
            MATCH (n)
            WHERE elementId(n) = $node_id
            MERGE (om:OsloMethod)
            MERGE (n)-[:METHOD]->(om)
        """
        params = {
            "node_id": node_id,
        }
        self._run_query(query, **params)

    def add_author_node_and_attach(self, node_type, author_name, pherc_display_name, cornice_display_name=None, pezzo_display_name=None, disegni_name=None):
        try:
            node_id = self._get_node_id(node_type, pherc_display_name, cornice_display_name, pezzo_display_name, disegni_name)
        except Exception as e:
            print(f"Error retrieving node ID: {e}")
            return
        
        query = """
            MATCH (n)
            WHERE elementId(n) = $node_id
            MERGE (a:Author {name: $author_name})
            MERGE (n)-[:AUTHORED_BY]->(a)
        """
        params = {
            "node_id": node_id,
            "author_name": author_name
        }
        self._run_query(query, **params)

    def add_cavallo_scribal_style_node_and_attach(self, node_type, cavallo_scribal_style, pherc_display_name, cornice_display_name=None, pezzo_display_name=None, disegni_name=None):
        try:
            node_id = self._get_node_id(node_type, pherc_display_name, cornice_display_name, pezzo_display_name, disegni_name)
        except Exception as e:
            print(f"Error retrieving node ID: {e}")
            return
        
        query = """
            MATCH (n)
            WHERE elementId(n) = $node_id
            MERGE (cs:CavalloScribalStyle {name: $cavallo_scribal_style})
            MERGE (n)-[:STYLE]->(cs)
        """
        params = {
            "node_id": node_id,
            "cavallo_scribal_style": cavallo_scribal_style 
        }
        self._run_query(query, **params)


########################### For other CSV files ###########################

    # For negatives CSV file
    def add_flatbed_scan_node(self, image_num, uuid, pherc, cornice, neg_series="unknown", neg_storage="unknown"):
        params = {
        "image_num": image_num,
        "neg_series": neg_series,
        "neg_storage": neg_storage,
        "pherc": pherc,
        "cornice": cornice,
        "uuid": uuid
        }
    
        query = """
            MERGE (f:FlatbedScanDataset {imgNum: $image_num, 
            negSeries: $neg_series, 
            negStorage: $neg_storage,
            pherc: $pherc,
            cornice: $cornice})
        """
        if uuid:
            query = "MATCH (e:EduceLabID {uuid: $uuid}) " + query + " MERGE (e)<-[:BELONGS_TO]-(f)"
        
        self._run_query(query, **params)

    def add_pgs_raw_node(self, pgs_path, scan_uuid, datetime_start, datetime_end=None, complete=False, sample_uuid=None):
        params = {
            "pgs_path": pgs_path,
            "scan_uuid": scan_uuid,
            "datetime_start": datetime_start,
            "datetime_end": datetime_end,
            "complete": complete,
            "sample_uuid": sample_uuid
        }
        
        query = """
            MERGE (pg:PGSRaw {uuid: $scan_uuid,
            path: $pgs_path,
            date_start: $datetime_start})
        """
        if datetime_end:
            query += " SET pg.date_end = $datetime_end"
        if complete:
            query += " SET pg.complete = $complete"
        
        if sample_uuid:
            query = "MATCH (e:EduceLabID {uuid: $sample_uuid}) " + query + " MERGE (e)<-[:BELONGS_TO]-(pg)"
            
        self._run_query(query, **params)
    
    def add_spectral_raw_node(self, spectral_path, scan_uuid, datetime_start, datetime_end=None, complete=False, sample_uuid=None, sample_uuid2=None):    
        params = {
            "spectral_path": spectral_path,
            "scan_uuid": scan_uuid,
            "datetime_start": datetime_start,
            "datetime_end": datetime_end,
            "complete": complete,
            "sample_uuid": sample_uuid,
            "sample_uuid2": sample_uuid2
        }
        
        query = """
            MERGE (s:SpectralRaw {uuid: $scan_uuid,
            path: $spectral_path,
            date_start: $datetime_start})
        """
        if datetime_end:
            query += " SET s.date_end = $datetime_end"
        if complete:
            query += " SET s.complete = $complete"       
        if sample_uuid:
            query = "MATCH (e:EduceLabID {uuid: $sample_uuid}) " + query + " MERGE (e)<-[:BELONGS_TO]-(s)"
        if sample_uuid2:
            query += " WITH s MATCH (e2:EduceLabID {uuid: $sample_uuid2}) MERGE (e2)<-[:BELONGS_TO]-(s)"
            
        self._run_query(query, **params)
        
        
################ For the image processing pipeline ################
    
    
    def add_image_processing_node(self, artifact_uuid, op_type, input_ds_path, output_ds_path,
                                  date_time, slurm_id, pipeline_id):
        """
        Creates an image processing node and attaches it to
        - input-dataset node
        - output-dataset node
        - pipeline node
        
        If pipline node does not exist, it creates one first.
        
        input:
        op_type: "PGS" | "SPEC" | "WEB"
        """
        
        if op_type == "PGS":
        
            query = """
            MATCH (:EduceLabID {uuid: $artifact_uuid})-[:BELONGS_TO]-(pgs:PGSRaw {path: $input_ds_path})
            MERGE (proc:Process {stage: "PGS",
            start_time: $date_t,
            slurm_id: $slurm_id,
            status: "submitted"})
            MERGE (pgs_proc:PGSProcessed {path: $output_ds_path})
            MERGE (pgs)-[:INPUT]->(proc)-[:OUTPUT]->(pgs_proc)
            MERGE (ppline:Pipeline {pipeline_id: $pipeline_id})
            MERGE (proc)-[:STAGE_OF]->(ppline)
            RETURN proc
            """

        elif op_type == "SPEC":

            query = """
            MATCH (:EduceLabID {uuid: $artifact_uuid})-[:BELONGS_TO]-(spectral:SpectralRaw {path: $input_ds_path})
            MERGE (proc:Process {stage: "SPEC",
            start_time: $date_t,
            slurm_id: $slurm_id,
            status: "submitted"})
            MERGE (spec_proc:SpectralProcessed {path: $output_ds_path})
            MERGE (spectral)-[:INPUT]->(proc)-[:OUTPUT]->(spec_proc)
            MERGE (ppline:Pipeline {pipeline_id: $pipeline_id})
            MERGE (proc)-[:STAGE_OF]->(ppline)
            RETURN proc
            """

        elif op_type == "WEB":
            # In this case, find the registered image node using the pipeline_id instead of EduceLabID(uuid)
            query = """
            MATCH (ppline:Pipeline {pipeline_id: $pipeline_id})--(:Process)--(reg:Registered {path: $input_ds_path})
            MERGE (proc:Process {stage: "WEB",
            start_time: $date_t,
            slurm_id: $slurm_id,
            status: "submitted"})
            MERGE (web:WebProcessed {path: $output_ds_path})
            MERGE (reg)-[:INPUT]->(proc)-[:OUTPUT]->(web)
            MERGE (proc)-[:STAGE_OF]->(ppline)
            RETURN proc
            """
            
        params = {
            "artifact_uuid": artifact_uuid,
            "input_ds_path": input_ds_path,
            "date_t": date_time,
            "slurm_id": slurm_id,
            "output_ds_path": output_ds_path,
            "pipeline_id": pipeline_id
        }
          
        proc_node = self._run_query(query, **params)
        
        return proc_node
        
    def add_registration_processing_node(self, artifact_uuid, date_time, slurm_id, input_pgs_path, input_spectral_path,
                                         registered_img_path, pipeline_id):
        query = """
        MATCH (:EduceLabID {uuid: $artifact_uuid})--(:PGSRaw)--(:Process)--(pg_proc:PGSProcessed {path: $input_pg_path})
        MATCH (:EduceLabID {uuid: $artifact_uuid})--(:SpectralRaw)--(:Process)--(spec_proc:SpectralProcessed {path: $input_spectral_path})
        MERGE (proc:Process {stage: "REG",
        start_time: $date_t,
        slurm_id: $slurm_id,
        status: "submitted"})
        MERGE (reg:Registered {path: $registered_img_path})
        MERGE (pg_proc)-[:INPUT]->(proc)<-[:INPUT]-(spec_proc)
        MERGE (proc)-[:OUTPUT]->(reg)
        WITH proc
        MATCH (ppline:Pipeline {pipeline_id: $pipeline_id})
        MERGE (proc)-[:STAGE_OF]->(ppline)
        RETURN proc
            """    
            
        params = {
            "artifact_uuid": artifact_uuid,
            "input_pg_path": input_pgs_path,
            "input_spectral_path": input_spectral_path,
            "date_t": date_time,
            "slurm_id": slurm_id,
            "registered_img_path": registered_img_path,
            "pipeline_id": pipeline_id
        }
          
        proc_node = self._run_query(query, **params)

        return proc_node

    def update_process_status(self, pipeline_id, stage, property_name, value):
        """
        Updates a property of a Process node identified by pipeline_id and slurm_id.

        Args:
            pipeline_id: The pipeline ID to identify the process
            stage: The process stage ("PGS", "SPEC", "WEB", or "REG")
            property_name: The name of the property to update (e.g., "status", "slurm_id")
            value: The new value for the property

        Returns:
            The updated process node
        """
        if property_name == "status" and value in ("completed", "failed"):
            query = f"""
            MATCH (ppline:Pipeline {{pipeline_id: $pipeline_id}})-[:STAGE_OF]-(proc:Process {{stage: $stage}})
            SET proc.{property_name} = $value, proc.end_time = $end_time
            RETURN proc
            """
            params = {
                "pipeline_id": pipeline_id,
                "stage": stage,
                "value": value,
                "end_time": datetime.now().isoformat()
            }
        else:
            query = f"""
            MATCH (ppline:Pipeline {{pipeline_id: $pipeline_id}})-[:STAGE_OF]-(proc:Process {{stage: $stage}})
            SET proc.{property_name} = $value
            RETURN proc
            """
            params = {
                "pipeline_id": pipeline_id,
                "stage": stage,
                "value": value
            }

        proc_node = self._run_query(query, **params)

        return proc_node
