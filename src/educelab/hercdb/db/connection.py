import logging
from collections import OrderedDict, defaultdict
from enum import Enum

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired
from rapidfuzz import fuzz

# Driver-level errors that mean "couldn't reach Neo4j" (e.g. the server is down
# for its nightly backup), as opposed to a query that ran and matched nothing.
# execute_query already retries these internally for up to
# max_transaction_retry_time (~30s) before giving up and raising.
_UNAVAILABLE_ERRORS = (ServiceUnavailable, SessionExpired)


class DatabaseUnavailableError(Exception):
    """The Neo4j server could not be reached.

    Raised by :meth:`GraphDBConnection._run_query` when the driver reports the
    database is unavailable (down, restarting, connection lost). Callers should
    treat this as a transient/retryable infrastructure failure — distinct from a
    query that executed successfully and returned no rows. The REST layer maps it
    to HTTP 503 so clients can retry rather than misread it as a 404.
    """


class DatasetType(Enum):
    FlatbedScan = 'FlatbedScanDataset'
    PGSRaw = 'PGSRaw'
    SpectralRaw = 'SpectralRaw'

    def __str__(self):
        return f'{self.value}'


# Cypher predicate for "a dataset is fully complete": the `complete` flag is
# "True" AND it has no missing / zero-byte / short / bad-format files. This is
# the Cypher twin of cli/scan_completeness.py `_is_fully_complete` — keep the two
# in sync. `coalesce(..., 0)` preserves the flag-only behaviour for legacy nodes
# loaded before the count columns existed (their missing counts read as 0, i.e.
# clean), exactly as the Python rule defaults those counts to 0. Assumes the
# dataset is bound to `d`.
_FULLY_COMPLETE_CYPHER = (
    'AND d.complete = "True" '
    'AND coalesce(d.missing_files, 0) = 0 '
    'AND coalesce(d.zero_byte_files, 0) = 0 '
    'AND coalesce(d.short_files, 0) = 0 '
    'AND coalesce(d.bad_format_files, 0) = 0'
)

# The raw dataset label each proc_type's work-list scans. Neo4j cannot
# parameterize a label, so the query interpolates one -- looked up here rather
# than accepted from the caller, which makes injection structurally impossible.
_CANDIDATE_LABELS = {'SPEC': 'SpectralRaw', 'PGS': 'PGSRaw'}


def _newer(a, b) -> bool:
    """Whether `a` is a later timestamp than `b`, tolerating missing values.

    Neo4j hands back DateTime objects, which compare directly; a null sorts
    oldest so a scan with no date_end never displaces one that has it.
    """
    if a is None:
        return False
    if b is None:
        return True
    return a > b


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
        except _UNAVAILABLE_ERRORS as e:
            # Neo4j is unreachable (e.g. down for backup). Propagate as a distinct
            # error so the REST layer returns 503, not a misleading 404 that a
            # swallowed None would produce.
            self.logger.error("Neo4j unavailable for query: %s",
                              query.strip().replace('\n', ' '), exc_info=e)
            raise DatabaseUnavailableError(str(e)) from e
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

    # Structural / dataset labels that are NOT "metadata" about an artifact.
    # Anything attached to a PHerc/Cornice/Pezzo whose label is outside this set
    # (Author, Language, Unroller, CustodialInstitution, Disegni, ...) is treated
    # as metadata by get_artifact_info.
    _STRUCTURAL_LABELS = [
        'PHerc', 'Casetta', 'Cornice', 'Pezzo', 'EduceLabID',
        'FlatbedScanDataset', 'PGSRaw', 'SpectralRaw',
    ]

    @staticmethod
    def _primary_label(labels, prefer=('PHerc', 'Casetta', 'Cornice', 'Pezzo')) -> str | None:
        """Pick the most relevant label from a node's label set.

        PHerc nodes may also carry :Casetta; ``prefer`` decides which wins.
        Defaults to reporting such a node as 'PHerc'; pass a Casetta-first
        order when a Casetta parent should surface as 'Casetta'.
        """
        if not labels:
            return None
        for p in prefer:
            if p in labels:
                return p
        return labels[0]

    def get_artifact_info(self, pherc, cornice=None, pezzo=None) -> dict | None:
        """Full detail for a single artifact (PHerc / Cornice / Pezzo) resolved
        by exact displayName. Backs ``GET /artifacts?pherc=...``.

        Returns the node's own properties (displayName, aliases, backing, ...)
        plus its attached metadata nodes, the EduceLabID uuid(s) assigned to it,
        and child counts. Datasets are intentionally excluded (they hang off the
        EduceLabID; use the dataset endpoints). Children are summarized as counts,
        not expanded (use ``/subdivisions`` or a child lookup for detail).

        Returns ``None`` when no such node exists.
        """
        if pezzo:
            node_type = "Pezzo"
        elif cornice:
            node_type = "Cornice"
        else:
            node_type = "PHerc"

        node_id = self._get_node_id(node_type, pherc, cornice, pezzo)
        if node_id is None:
            return None

        records, _, _ = self._run_query("""
            MATCH (n) WHERE elementId(n) = $node_id
            OPTIONAL MATCH (n)<-[:ASSIGNED_TO]-(eid:EduceLabID)
            OPTIONAL MATCH (n)-[:HAS]->(child)
            WHERE child:Cornice OR child:Pezzo
            OPTIONAL MATCH (n)--(meta)
            WHERE NONE(l IN labels(meta) WHERE l IN $structural)
            WITH n,
                 collect(DISTINCT eid.uuid) AS educelabids,
                 collect(DISTINCT child) AS children,
                 collect(DISTINCT meta) AS metas
            RETURN n, educelabids,
                   size([c IN children WHERE 'Cornice' IN labels(c)]) AS cornici_count,
                   size([c IN children WHERE 'Pezzo' IN labels(c)]) AS pezzi_count,
                   metas
            """, node_id=node_id, structural=self._STRUCTURAL_LABELS)

        if not records:
            return None

        record = records[0]
        result = self._jsonify_props(dict(record['n']))
        result['type'] = node_type
        result['educelabids'] = [u for u in record['educelabids'] if u]

        metadata = {}
        for meta in record['metas']:
            if meta is None:
                continue
            label = next(iter(meta.labels))
            props = self._jsonify_props(dict(meta))
            if label in metadata:
                if isinstance(metadata[label], list):
                    metadata[label].append(props)
                else:
                    metadata[label] = [metadata[label], props]
            else:
                metadata[label] = props
        result['metadata'] = metadata

        if node_type == "PHerc":
            result['cornici_count'] = record['cornici_count']
            result['pezzi_count'] = record['pezzi_count']
        elif node_type == "Cornice":
            result['pezzi_count'] = record['pezzi_count']

        return result

    @staticmethod
    def _jsonify_props(props: dict) -> dict:
        """Convert any non-JSON-safe values (e.g. Neo4j DateTime) to strings."""
        for key, value in list(props.items()):
            if not isinstance(value, (str, int, float, bool, type(None), list, dict)):
                props[key] = str(value)
        return props


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

    def find_artifact_location_by_uuid(self, uuid: str) -> dict | None:
        """Lightweight UUID -> artifact bridge. Backs ``GET /artifacts/{uuid}``.

        Returns the type and displayName of the node the UUID is assigned to,
        the PHerc/Cornice/Pezzo names in its hierarchy, and its immediate
        ``HAS``-parent (with a Casetta parent surfaced as such). Deliberately
        lighter than ``get_artifact_info`` (no metadata/counts); a caller who
        needs full detail re-queries by name. Returns ``None`` if the UUID is
        not assigned to any artifact.
        """
        records, _, _ = self._run_query("""
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
            RETURN labels(n) AS node_labels,
                   n.displayName AS display_name,
                   pherc.displayName AS pherc_name,
                   cornice.displayName AS cornice_name,
                   pezzo.displayName AS pezzo_name,
                   labels(parent1) AS parent_labels,
                   parent1.displayName AS parent_name
            """, uuid=uuid)

        if not records:
            return None

        r = records[0]
        parent = None
        if r['parent_name'] is not None:
            parent = {
                'type': self._primary_label(
                    r['parent_labels'],
                    prefer=('Casetta', 'PHerc', 'Cornice', 'Pezzo'),
                ),
                'displayName': r['parent_name'],
            }
        return {
            'type': self._primary_label(r['node_labels']),
            'displayName': r['display_name'],
            'pherc': r['pherc_name'],
            'cornice': r['cornice_name'],
            'pezzo': r['pezzo_name'],
            'parent': parent,
        }

    def list_all_pherc_display_names(self) -> list[dict]:
        """List every PHerc node, flagging which are also labeled :Casetta.

        Returns:
            List of dicts with keys 'display_name' (str) and 'is_casetta' (bool),
            ordered by displayName.

        Falls back to `name` / first alias when `displayName` is null so the
        scan-completeness walk never emits a nameless PHerc row (post-migration
        every node has a displayName; this guards any residual/un-migrated data).
        """
        records, _, _ = self._run_query("""
            MATCH (ph:PHerc)
            WITH ph, coalesce(ph.displayName, ph.name, head(coalesce(ph.aliases, []))) AS display_name
            RETURN display_name,
                   'Casetta' IN labels(ph) AS is_casetta
            ORDER BY display_name
            """)
        if not records:
            return []
        return [
            {'display_name': r['display_name'], 'is_casetta': r['is_casetta']}
            for r in records
        ]

    def list_cornici_and_pezzi_for_pherc(self, pherc_display_name) -> dict | None:
        """Full Cornici + Pezzi listing for a PHerc. Backs ``GET /subdivisions``.

        Each node (the PHerc itself, every Cornice, every Pezzo) is reported as
        ``{displayName, aliases, educelabids, parent}`` — the resolution surface,
        the UUID bridge, and the node's immediate parent (so a nested Pezzo can be
        shown under its Cornice). ``parent`` is ``{type, displayName}`` (e.g. a
        Pezzo nested under a Cornice carries ``{'type': 'Cornice', ...}``, a Pezzo
        directly under the PHerc carries ``{'type': 'PHerc', ...}``) or ``None`` for
        the PHerc itself. No other physical characteristics are included (those live
        on the ``/artifacts`` detail view). Returns ``None`` if the PHerc doesn't exist.
        """
        records, _, _ = self._run_query("""
            MATCH (ph:PHerc {displayName:$pherc_display_name})
            OPTIONAL MATCH (ph)<-[:ASSIGNED_TO]-(pe:EduceLabID)
            WITH ph, collect(DISTINCT pe.uuid) AS ph_uuids
            OPTIONAL MATCH (ph)-[:HAS*1..2]->(node)
            WHERE node:Cornice OR node:Pezzo
            OPTIONAL MATCH (parent)-[:HAS]->(node)
            OPTIONAL MATCH (node)<-[:ASSIGNED_TO]-(eid:EduceLabID)
            RETURN ph.displayName AS ph_display,
                   ph.aliases AS ph_aliases,
                   ph_uuids,
                   node.displayName AS node_display,
                   node.aliases AS node_aliases,
                   labels(node) AS node_labels,
                   parent.displayName AS parent_display,
                   labels(parent) AS parent_labels,
                   collect(DISTINCT eid.uuid) AS educelabids
            ORDER BY node_display
            """, pherc_display_name=pherc_display_name)

        if not records:
            return None

        first = records[0]
        result = {
            'pherc': {
                'displayName': first['ph_display'],
                'aliases': first['ph_aliases'] or [],
                'educelabids': [u for u in (first['ph_uuids'] or []) if u],
                'parent': None,
            },
            'cornici': [],
            'pezzi': [],
        }
        for r in records:
            if r['node_display'] is None:
                continue  # PHerc exists but this row carried no child
            parent = None
            if r['parent_display'] is not None:
                parent = {
                    'type': self._primary_label(r['parent_labels']),
                    'displayName': r['parent_display'],
                }
            entry = {
                'displayName': r['node_display'],
                'aliases': r['node_aliases'] or [],
                'educelabids': [u for u in r['educelabids'] if u],
                'parent': parent,
            }
            if 'Cornice' in r['node_labels']:
                result['cornici'].append(entry)
            elif 'Pezzo' in r['node_labels']:
                result['pezzi'].append(entry)
        return result

    def fuzzy_find_node(
        self,
        name: str,
        label: str = "PHerc",
        parent_pherc: str | None = None,
        parent_cornice: str | None = None,
        threshold: int = 75,
        limit: int = 10,
    ) -> list[dict]:
        """Fuzzy lookup of PHerc / Cornice / Pezzo nodes by displayName.

        A standalone primitive: callers use the returned candidates to pick
        a node, then read its UUID / EduceLabID and use the existing
        ``find_*`` methods for everything else. Do not bake fuzzy matching
        into other endpoints; compose with this method instead.

        Args:
            name: The (potentially noisy) displayName to look up.
            label: One of ``"PHerc"``, ``"Cornice"``, ``"Pezzo"``.
            parent_pherc: Optional (fuzzy) PHerc displayName scoping
                ``Cornice`` / ``Pezzo`` lookups.
            parent_cornice: Optional (fuzzy) Cornice displayName scoping
                ``Pezzo`` lookups (forces the via-Cornice path; direct-
                under-PHerc Pezzi are excluded when this is set).
            threshold: 0-100 minimum similarity score (``rapidfuzz.fuzz.ratio``
                on whitespace-stripped lowercased displayNames) for a
                candidate to survive filtering.
            limit: Maximum number of ranked candidates to return.

        Returns:
            List of dicts ordered by ``score`` desc:
            ``{"node", "displayName", "score",
            "parent_pherc": {"displayName", "score"} | None,
            "parent_cornice": {"displayName", "score"} | None}``.
            Exact (after-normalize) matches short-circuit to score 100
            (all candidates sharing that normalized name are returned).
            When a parent name was not supplied, ``parent_*.score`` is
            ``None`` (the parent is contextual, not matched).
        """
        valid_labels = {"PHerc", "Cornice", "Pezzo"}
        if label not in valid_labels:
            raise ValueError(
                f"label must be one of {sorted(valid_labels)}, got {label!r}"
            )

        def _norm(s):
            return "".join((s or "").split()).lower()

        def _forms(node, dn):
            """All raw name forms to match a candidate against: its displayName
            plus every alias. Display still uses displayName; aliases only widen
            the match surface (uuid-sheet names, Casetta synonyms, variants)."""
            forms = [dn] if dn else []
            forms += [a for a in (node.get("aliases") or []) if a]
            return forms or [dn]

        query_norm = _norm(name)
        if not query_norm:
            return []

        # parent_*_matches: {displayName: score} for parents the caller
        # asked us to fuzzy-resolve. Stays None when the caller didn't
        # supply that parent name (parent info is then contextual only).
        parent_pherc_matches: dict | None = None
        parent_cornice_matches: dict | None = None

        # candidates: list of (node, displayName, parent_pherc_dn, parent_cornice_dn)
        candidates: list = []

        if label == "PHerc":
            records, _, _ = self._run_query(
                "MATCH (ph:PHerc) RETURN ph, ph.displayName AS dn"
            )
            candidates = [
                (r["ph"], r["dn"], None, None) for r in (records or [])
            ]

        elif label == "Cornice":
            if parent_pherc is not None:
                parent_hits = self.fuzzy_find_node(
                    parent_pherc, label="PHerc",
                    threshold=threshold, limit=limit,
                )
                if not parent_hits:
                    return []
                parent_pherc_matches = {
                    p["displayName"]: p["score"] for p in parent_hits
                }
                records, _, _ = self._run_query(
                    """
                    MATCH (ph:PHerc)-[:HAS]->(c:Cornice)
                    WHERE ph.displayName IN $parent_names
                    RETURN c, c.displayName AS dn, ph.displayName AS ph_dn
                    """,
                    parent_names=list(parent_pherc_matches.keys()),
                )
            else:
                records, _, _ = self._run_query(
                    """
                    MATCH (ph:PHerc)-[:HAS]->(c:Cornice)
                    RETURN c, c.displayName AS dn, ph.displayName AS ph_dn
                    """
                )
            candidates = [
                (r["c"], r["dn"], r["ph_dn"], None) for r in (records or [])
            ]

        else:  # Pezzo
            ph_names: list | None = None
            if parent_pherc is not None:
                parent_hits = self.fuzzy_find_node(
                    parent_pherc, label="PHerc",
                    threshold=threshold, limit=limit,
                )
                if not parent_hits:
                    return []
                parent_pherc_matches = {
                    p["displayName"]: p["score"] for p in parent_hits
                }
                ph_names = list(parent_pherc_matches.keys())

            if parent_cornice is not None:
                cor_hits = self.fuzzy_find_node(
                    parent_cornice, label="Cornice",
                    parent_pherc=parent_pherc,
                    threshold=threshold, limit=limit,
                )
                if not cor_hits:
                    return []
                # (pherc_dn, cornice_dn) pairs — same cornice name can
                # exist under different PHercs, so we filter by pair.
                parent_cornice_matches = {
                    c["displayName"]: c["score"] for c in cor_hits
                }
                pairs = [
                    [c["parent_pherc"]["displayName"], c["displayName"]]
                    for c in cor_hits
                ]
                records, _, _ = self._run_query(
                    """
                    MATCH (ph:PHerc)-[:HAS]->(c:Cornice)-[:HAS]->(p:Pezzo)
                    WHERE [ph.displayName, c.displayName] IN $pairs
                    RETURN p, p.displayName AS dn,
                           ph.displayName AS ph_dn,
                           c.displayName  AS c_dn
                    """,
                    pairs=pairs,
                )
                candidates = [
                    (r["p"], r["dn"], r["ph_dn"], r["c_dn"])
                    for r in (records or [])
                ]
            else:
                # both direct-under-PHerc and via-Cornice Pezzi
                params: dict = {}
                where = ""
                if ph_names is not None:
                    where = " WHERE ph.displayName IN $ph_names"
                    params["ph_names"] = ph_names
                direct_recs, _, _ = self._run_query(
                    "MATCH (ph:PHerc)-[:HAS]->(p:Pezzo)" + where +
                    " RETURN p, p.displayName AS dn, ph.displayName AS ph_dn",
                    **params,
                )
                nested_recs, _, _ = self._run_query(
                    "MATCH (ph:PHerc)-[:HAS]->(c:Cornice)-[:HAS]->(p:Pezzo)" + where +
                    " RETURN p, p.displayName AS dn,"
                    " ph.displayName AS ph_dn, c.displayName AS c_dn",
                    **params,
                )
                candidates = [
                    (r["p"], r["dn"], r["ph_dn"], None)
                    for r in (direct_recs or [])
                ] + [
                    (r["p"], r["dn"], r["ph_dn"], r["c_dn"])
                    for r in (nested_recs or [])
                ]

        if not candidates:
            return []

        def _parent_info(dn, matches):
            if dn is None:
                return None
            return {
                "displayName": dn,
                "score": matches[dn] if matches is not None else None,
            }

        # Exact-match short-circuit: same normalized name can map to
        # multiple Cornici/Pezzi under different parents — return all of
        # them at score 100. Matches against displayName OR any alias.
        exact = [
            (node, dn, ph_dn, c_dn)
            for node, dn, ph_dn, c_dn in candidates
            if any(_norm(s) == query_norm for s in _forms(node, dn))
        ]
        if exact:
            return [
                {
                    "node": node,
                    "displayName": dn,
                    "score": 100,
                    "parent_pherc": _parent_info(ph_dn, parent_pherc_matches),
                    "parent_cornice": _parent_info(c_dn, parent_cornice_matches),
                }
                for node, dn, ph_dn, c_dn in exact
            ][:limit]

        scored = []
        for node, dn, ph_dn, c_dn in candidates:
            # Score against the best-matching form (displayName or any alias).
            score = max(
                (int(round(fuzz.ratio(query_norm, _norm(s)))) for s in _forms(node, dn)),
                default=0,
            )
            if score < threshold:
                continue
            scored.append({
                "node": node,
                "displayName": dn,
                "score": score,
                "parent_pherc": _parent_info(ph_dn, parent_pherc_matches),
                "parent_cornice": _parent_info(c_dn, parent_cornice_matches),
            })

        # Primary: score desc. Secondary: substring matches first (query
        # appears verbatim in any form), so e.g. "118a"/"1180" rank above
        # "1168" when searching "118", and "Cass."/"Cassetta" rank above
        # unrelated names when searching "cass". Tertiary: alphabetical.
        scored.sort(key=lambda r: (
            -r["score"],
            not any(query_norm in _norm(s) for s in _forms(r["node"], r["displayName"])),
            r["displayName"] or "",
        ))
        return scored[:limit]

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
            OPTIONAL MATCH (input)-[:INPUT]->(proc)
            OPTIONAL MATCH (proc)-[:OUTPUT]->(output)
            RETURN proc,
                   collect(DISTINCT input.path)  AS input_dataset_paths,
                   collect(DISTINCT output.path) AS output_dataset_paths
            ORDER BY proc.start_time
            """, pipeline_id=pipeline_id)

        if not records:
            return None

        processes = []
        for record in records:
            proc = record['proc']
            end_time = proc.get('end_time')
            output_paths = record['output_dataset_paths']
            processes.append({
                'start_time': str(proc.get('start_time', '')),
                'stage': proc.get('stage', ''),
                'status': proc.get('status', ''),
                'slurm_id': str(proc.get('slurm_id', '')),
                'end_time': str(end_time) if end_time else None,
                'input_dataset_paths': record['input_dataset_paths'],           # list[str]
                'output_dataset_path': output_paths[0] if output_paths else None,  # str | None
                # Where a multi-job stage failed. None on any process written
                # before 0.3.2, and on every one that simply succeeded.
                'notes': proc.get('notes'),
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

    def find_predecessor_uuid_map(self) -> dict:
        """Map every EduceLabID uuid to its full REPLACES chain (itself plus
        all predecessors reachable via [:REPLACES*0..]).

        Lets a caller pool scans across the chain: a scan whose `sample uuid`
        is a retired predecessor still counts toward the active artifact's
        UUID. Read-only. Returns {uuid: set(chain_uuids)}.
        """
        records, _, _ = self._run_query("""
            MATCH (e:EduceLabID)-[:REPLACES*0..]->(p:EduceLabID)
            RETURN e.uuid AS uuid, collect(DISTINCT p.uuid) AS chain
        """)
        return {r["uuid"]: set(r["chain"]) for r in (records or []) if r["uuid"]}

    def find_unassigned_educelabids(self) -> list[dict]:
        """EduceLabIDs that exist (loaded from the uuid file) but are linked to
        no artifact, and are neither deliberately retired nor superseded by a
        successor. These are source gaps: a UUID with no artifact name.

        Read-only. Returns [{'uuid': str}, ...].
        """
        records, _, _ = self._run_query("""
            MATCH (e:EduceLabID)
            WHERE NOT (e)-[:ASSIGNED_TO]->()
              AND NOT (e)<-[:REPLACES]-(:EduceLabID)
              AND coalesce(e.retired, false) = false
            RETURN e.uuid AS uuid
            ORDER BY uuid
        """)
        return [{"uuid": r["uuid"]} for r in (records or [])]

    def find_all_artifacts_and_educelabids_for_pherc(self, pherc_display_name: str) -> list[dict]:
        """For one PHerc, return one record per (artifact, UUID) pair, plus a
        sentinel record for any artifact in the hierarchy that has no UUID.

        Uses OPTIONAL MATCH on the EduceLabID, so Cornici/Pezzi (and the
        PHerc itself) without an assigned UUID still surface. Suppresses the
        PHerc-itself row when
        the PHerc has Cornici/Pezzi children but no UUID directly assigned —
        in that case the children rows carry the scan information and a
        PHerc-level "unscanned" row would be misleading.

        Each record has keys: 'uuid' (str | None), 'pherc' (str),
        'cornice' (str | None), 'pezzo' (str | None).
        """
        records, _, _ = self._run_query("""
            MATCH (ph:PHerc {displayName: $pherc_display_name})
            OPTIONAL MATCH (ph)-[:HAS]->(child)
            WHERE child:Cornice OR child:Pezzo
            WITH ph, count(DISTINCT child) AS num_children
            MATCH (ph)-[:HAS*0..2]->(artifact)
            WHERE artifact:PHerc OR artifact:Cornice OR artifact:Pezzo
            OPTIONAL MATCH (eid:EduceLabID)-[:ASSIGNED_TO]->(artifact)
            OPTIONAL MATCH (artifact)<-[:HAS]-(parent1)
            OPTIONAL MATCH (parent1)<-[:HAS]-(parent2)
            WITH num_children, eid, artifact, parent1, parent2,
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
            WHERE NOT (
                'PHerc' IN labels(artifact)
                AND eid IS NULL
                AND num_children > 0
            )
            RETURN DISTINCT eid.uuid AS uuid,
                   pherc_node.displayName AS pherc_name,
                   cornice_node.displayName AS cornice_name,
                   pezzo_node.displayName AS pezzo_name
            ORDER BY pherc_name, cornice_name, pezzo_name
            """, pherc_display_name=pherc_display_name)

        return [
            {
                'uuid': r['uuid'],
                'pherc': r['pherc_name'],
                'cornice': r['cornice_name'],
                'pezzo': r['pezzo_name'],
            }
            for r in records
        ]

    def find_datasets_for_educelabid(self, uuid: str, ds_type: DatasetType = None, newest_completed: bool = False) -> list[dict]:
        """Find all datasets for a specific EduceLabID."""
        dataset_labels = ['FlatbedScanDataset', 'PGSRaw', 'SpectralRaw']
        type_filter = "AND $data_t IN LABELS(d)" if ds_type else ""
        completed_filter = _FULLY_COMPLETE_CYPHER if newest_completed else ""

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

    def find_datasets_for_educelabid_with_predecessors(self, uuid: str, ds_type: DatasetType = None, newest_completed: bool = False) -> list[dict]:
        """Like find_datasets_for_educelabid, but also returns datasets
        BELONGING_TO any predecessor UUID reached by walking [:REPLACES*0..]
        from the given UUID.

        Pools scans across a UUID-replacement chain: an artifact whose UUID was
        replaced still surfaces its pre-replacement scans (which still BELONG_TO
        the original EduceLabID and were never reattached). Each returned dataset
        carries ``belongs_to_uuid`` — the EduceLabID it actually belongs to — so
        scans sitting on a retired predecessor UUID are obvious. Backs both
        ``GET /educelabid/{uuid}/datasets`` and the scan-completeness report.
        """
        dataset_labels = ['FlatbedScanDataset', 'PGSRaw', 'SpectralRaw']
        type_filter = "AND $data_t IN LABELS(d)" if ds_type else ""
        completed_filter = _FULLY_COMPLETE_CYPHER if newest_completed else ""

        grouping = """
            ORDER BY datetime(d.date_end) DESC
            WITH ds_type, collect({d: d, belongs_to_uuid: belongs_to_uuid})[0] AS top
            RETURN top.d AS d, ds_type, top.belongs_to_uuid AS belongs_to_uuid
        """ if newest_completed else "RETURN d, ds_type, belongs_to_uuid"

        query = f"""
            MATCH (e:EduceLabID {{uuid: $uuid}})-[:REPLACES*0..]->(predecessor:EduceLabID)
            MATCH (predecessor)<-[:BELONGS_TO]-(d)
            WHERE (d:FlatbedScanDataset OR d:PGSRaw OR d:SpectralRaw)
            {completed_filter}
            {type_filter}
            WITH DISTINCT d,
                 predecessor.uuid AS belongs_to_uuid,
                 [l IN labels(d) WHERE l IN $dataset_labels][0] AS ds_type
            {grouping}
        """

        params = {"uuid": uuid, "dataset_labels": dataset_labels}
        if ds_type:
            params["data_t"] = str(ds_type)

        records, _, _ = self._run_query(query, **params)

        if not records:
            return []

        results = []
        for record in records:
            ds = self._serialize_dataset(record)
            ds['belongs_to_uuid'] = record['belongs_to_uuid']
            results.append(ds)
        return results

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
                pherc, cornice, pezzo, datasets. Datasets are pooled across each
                artifact's UUID-replacement (REPLACES) chain and each carries
                ``belongs_to_uuid`` (the EduceLabID it actually belongs to);
                grouping is by the active/assigned UUID.
        """
        dataset_labels = ['FlatbedScanDataset', 'PGSRaw', 'SpectralRaw']
        type_filter = "AND $data_t IN LABELS(d)" if ds_type else ""
        completed_filter = _FULLY_COMPLETE_CYPHER if newest_completed else ""

        query = f"""
            MATCH (ph:PHerc {{displayName: $pherc_display_name}})
            MATCH (ph)-[:HAS*0..2]->(artifact)
            WHERE artifact:PHerc OR artifact:Cornice OR artifact:Pezzo
            MATCH (eid:EduceLabID)-[:ASSIGNED_TO]->(artifact)
            MATCH (eid)-[:REPLACES*0..]->(pred:EduceLabID)
            MATCH (pred)<-[:BELONGS_TO]-(d)
            WHERE (d:FlatbedScanDataset OR d:PGSRaw OR d:SpectralRaw)
            {type_filter}
            {completed_filter}
            OPTIONAL MATCH (artifact)<-[:HAS]-(parent1)
            OPTIONAL MATCH (parent1)<-[:HAS]-(parent2)
            WITH eid, pred, d, artifact, parent1, parent2,
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
            RETURN DISTINCT eid.uuid AS uuid,
                   pherc_node.displayName AS pherc_name,
                   cornice_node.displayName AS cornice_name,
                   pezzo_node.displayName AS pezzo_name,
                   d AS dataset,
                   ds_type AS dataset_type,
                   pred.uuid AS belongs_to_uuid
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
            ds['belongs_to_uuid'] = record['belongs_to_uuid']
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

    def _raw_candidate_rows(self, proc_type: str) -> list[dict]:
        """One row per (complete raw dataset, artifact it resolves to).

        The raw material for the two work-list queries below. Deliberately does
        no grouping: a scan can resolve to several artifacts (a tray holding
        fragments of more than one P.Herc.), and which of those rows to keep is
        policy, expressed in Python where it can be read.

        `attempts` / `last_status` / `last_notes` describe Processes of
        `proc_type` recorded against the *dataset*, so they are the same on every
        row of a given scan.
        """
        try:
            label = _CANDIDATE_LABELS[proc_type]
        except KeyError:
            raise ValueError(
                f"no work-list for proc_type {proc_type!r}; expected one of "
                f"{', '.join(sorted(_CANDIDATE_LABELS))}") from None

        records, _, _ = self._run_query(f"""
            MATCH (d:{label})-[:BELONGS_TO]->(e:EduceLabID)
            WHERE d.path IS NOT NULL AND d.path <> ''
              {_FULLY_COMPLETE_CYPHER}
            // The EduceLabID a Pipeline attaches to is the one bearing the
            // artifact, which may be a successor of the one the scan belongs to
            // -- the same REPLACES walk the dataset read path does.
            MATCH (active:EduceLabID)-[:REPLACES*0..]->(e)
            MATCH (active)-[:ASSIGNED_TO]->(artifact)
            WHERE artifact:PHerc OR artifact:Cornice OR artifact:Pezzo
            OPTIONAL MATCH (artifact)<-[:HAS]-(parent1)
            OPTIONAL MATCH (parent1)<-[:HAS]-(parent2)
            OPTIONAL MATCH (d)-[:INPUT]->(proc:Process {{stage: "{proc_type}"}})
            WITH d, active, artifact, parent1, parent2, proc
            ORDER BY proc.start_time DESC
            WITH d, active, artifact,
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
                 END AS pezzo_node,
                 collect(proc) AS procs
            RETURN d.path AS path,
                   d.date_end AS date_end,
                   active.uuid AS uuid,
                   elementId(artifact) AS artifact_id,
                   pherc_node.displayName AS pherc,
                   cornice_node.displayName AS cornice,
                   pezzo_node.displayName AS pezzo,
                   size(procs) AS attempts,
                   head(procs).status AS last_status,
                   head(procs).notes AS last_notes,
                   any(p IN procs WHERE p.status = "completed") AS processed
            """)

        return [
            {
                'uuid': r['uuid'],
                'pherc': r['pherc'],
                'cornice': r['cornice'],
                'pezzo': r['pezzo'],
                'path': r['path'],
                'date_end': r['date_end'],
                'artifact_id': r['artifact_id'],
                'attempts': r['attempts'],
                'last_status': r['last_status'],
                'last_notes': r['last_notes'],
                'processed': bool(r['processed']),
            }
            for r in (records or [])
        ]

    @staticmethod
    def _artifact_specificity(row) -> int:
        """Pezzo beats Cornice beats bare PHerc, for picking among an ID's artifacts."""
        if row['pezzo']:
            return 2
        if row['cornice']:
            return 1
        return 0

    @staticmethod
    def _candidate_rows_by_scan(rows) -> dict:
        """Group candidate rows by dataset path (one scan, one or more artifacts)."""
        by_path = defaultdict(list)
        for row in rows:
            by_path[row['path']].append(row)
        return by_path

    def find_unprocessed_datasets(self, proc_type: str) -> list[dict]:
        """Raw scans awaiting `proc_type`: one row per artifact, newest scan.

        Backs an unattended dispatcher, which needs a work-list it can act on
        without a human: each row carries both the dataset to process and the
        artifact fields the caller names its output directory from.

        Three selection rules, and **the order they are applied in matters**:

        1. *Skip multi-object trays.* A scan whose EduceLabID is assigned to more
           than one P.Herc. covers fragments of several objects, and its output
           could only be published under one of them. There is no non-arbitrary
           way to choose, so it is left for a human;
           `find_ambiguous_datasets` lists them.
        2. *One row per artifact, newest scan.* An artifact scanned repeatedly is
           processed once, from its newest scan by ``date_end`` -- the same
           choice the interactive submitter makes. Where one EduceLabID is
           assigned to both an artifact and its parent, the more specific
           artifact wins.
        3. *Then* drop anything already carrying a ``completed`` Process of this
           `proc_type`.

        Doing 3 before 2 looks equivalent and is not: once an artifact's newest
        scan is processed, the next-newest would become "newest of the
        unprocessed" and be queued, then the one after that, and the work-list
        would never empty.

        Scans whose EduceLabID resolves to no artifact are absent by
        construction -- the ``ASSIGNED_TO`` match is required, not optional --
        because they carry no P.Herc. number to name an output directory with.

        Args:
            proc_type: 'SPEC' or 'PGS'. Raises ValueError on anything else.

        Returns:
            List of dicts with keys 'uuid' (the *assigned* EduceLabID, which is
            what a Pipeline links to), 'pherc', 'cornice', 'pezzo', 'path'
            (exactly as recorded), 'date_end', 'attempts' (Processes of this
            proc_type so far, for a retry cap), 'last_status' and 'last_notes'.
        """
        by_path = self._candidate_rows_by_scan(
            self._raw_candidate_rows(proc_type))

        newest_per_artifact = {}
        for group in by_path.values():
            if len({r['pherc'] for r in group}) > 1:
                continue                                    # rule 1
            row = max(group, key=self._artifact_specificity)
            current = newest_per_artifact.get(row['artifact_id'])
            if current is None or _newer(row['date_end'], current['date_end']):
                newest_per_artifact[row['artifact_id']] = row  # rule 2

        return sorted(
            (self._public_candidate_row(r)
             for r in newest_per_artifact.values() if not r['processed']),  # rule 3
            key=lambda r: (r['pherc'] or '', r['cornice'] or '', r['pezzo'] or ''),
        )

    def find_ambiguous_datasets(self, proc_type: str) -> list[dict]:
        """Complete raw scans the `proc_type` dispatcher skips, and why.

        Currently one reason: the scan's EduceLabID is assigned to more than one
        P.Herc., so its output has no single object directory to belong to. These
        need a human to say where the result should land, and this is what stops
        them being silently dropped from the campaign.

        Returns one row per skipped *scan* (not per artifact), each with the
        artifacts it spans under 'artifacts'.
        """
        by_path = self._candidate_rows_by_scan(
            self._raw_candidate_rows(proc_type))

        skipped = []
        for path, group in by_path.items():
            if len({r['pherc'] for r in group}) <= 1:
                continue
            first = group[0]
            skipped.append({
                'path': path,
                'uuid': first['uuid'],
                'date_end': str(first['date_end']) if first['date_end'] else None,
                'reason': 'assigned to more than one P.Herc.',
                'processed': first['processed'],
                'artifacts': sorted(
                    ({'pherc': r['pherc'], 'cornice': r['cornice'],
                      'pezzo': r['pezzo']} for r in group),
                    key=lambda a: (a['pherc'] or '', a['cornice'] or '',
                                   a['pezzo'] or ''),
                ),
            })
        return sorted(skipped, key=lambda r: r['path'])

    def find_unprocessed_spectral_datasets(self) -> list[dict]:
        """`find_unprocessed_datasets('SPEC')`. Kept for 0.3.2 callers."""
        return self.find_unprocessed_datasets('SPEC')

    def find_ambiguous_spectral_datasets(self) -> list[dict]:
        """`find_ambiguous_datasets('SPEC')`. Kept for 0.3.2 callers."""
        return self.find_ambiguous_datasets('SPEC')

    @staticmethod
    def _public_candidate_row(row) -> dict:
        """Drop the internal grouping keys and make the row JSON-safe."""
        return {
            'uuid': row['uuid'],
            'pherc': row['pherc'],
            'cornice': row['cornice'],
            'pezzo': row['pezzo'],
            'path': row['path'],
            'date_end': str(row['date_end']) if row['date_end'] else None,
            'attempts': row['attempts'],
            'last_status': row['last_status'],
            'last_notes': row['last_notes'],
        }

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

        For PGS/SPEC the raw input dataset is matched across the pipeline
        EduceLabID's REPLACES chain (``[:REPLACES*0..]``), mirroring the read
        path (``find_datasets_for_educelabid_with_predecessors``): a pre-
        replacement scan still BELONGS_TO a predecessor UUID, so the raw node
        need not hang off the active UUID directly. REG/WEB match the upstream
        output nodes (PGSProcessed/SpectralProcessed/Registered) this pipeline
        produced, so they are unaffected.

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
            MATCH (e)-[:REPLACES*0..]->(:EduceLabID)<-[:BELONGS_TO]-(input:PGSRaw {path: $input_path})
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
            MATCH (e)-[:REPLACES*0..]->(:EduceLabID)<-[:BELONGS_TO]-(input:SpectralRaw {path: $input_path})
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

    def update_process_status(self, pipeline_id: str, stage: str, status: str,
                              end_datetime: str, notes: str = None) -> dict | None:
        """Update the status, end_time and optionally the notes of a process.

        Args:
            pipeline_id: The pipeline ID.
            stage: The process stage (PGS, SPEC, REG, WEB).
            status: New status (completed or failed).
            end_datetime: ISO datetime string for end time.
            notes: Free text saying *where* a stage failed, for a pipeline whose
                stage is split across several jobs and where only the job that
                died knows which one it was. Written only when given, so a caller
                that passes nothing cannot blank a note another job just wrote.

        Returns:
            Dict with updated process info, or None on failure.
        """
        set_clause = 'SET proc.status = $status, proc.end_time = $end_datetime'
        if notes is not None:
            set_clause += ', proc.notes = $notes'

        records, _, _ = self._run_query(f"""
            MATCH (ppline:Pipeline {{pipeline_id: $pipeline_id}})<-[:STAGE_OF]-(proc:Process {{stage: $stage}})
            {set_clause}
            RETURN proc
            """, pipeline_id=pipeline_id, stage=stage, status=status,
            end_datetime=end_datetime, notes=notes)

        if not records:
            return None
        proc = dict(records[0]['proc'])
        return {
            'stage': proc.get('stage', ''),
            'slurm_id': str(proc.get('slurm_id', '')),
            'start_time': str(proc.get('start_time', '')),
            'end_time': str(proc.get('end_time', '')) if proc.get('end_time') else None,
            'status': proc.get('status', ''),
            'notes': proc.get('notes'),
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
