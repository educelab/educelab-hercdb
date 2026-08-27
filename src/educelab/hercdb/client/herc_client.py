import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HercClient:
    """Lightweight REST API client for the EduceLab HercDB API.

    Only requires the ``requests`` library. No Neo4j or server-side
    dependencies are needed.

    Requests carry a default ``timeout`` and are retried automatically on
    transient failures (connection errors, read timeouts, and 502/503/504) with
    an exponential backoff. This rides over the brief nightly Neo4j backup
    window, during which the server returns ``503`` (see the REST API's error
    docs). Because every hercdb write is idempotent (``MERGE``-based), retrying
    is safe for **all** HTTP verbs, not just reads.

    With the defaults the client keeps retrying for ~108s total (sleeps of
    ``0, 4, 8, 16, 20, 20, 20, 20`` seconds between the 8 attempts, the tail
    capped at ``backoff_max``), comfortably longer than the ~1-min backup window
    while still recovering within ~20s of the database coming back.

    Args:
        host: Hostname or IP of the API server.
        token: Bearer token for authentication.
        port: Port number (default 8000).
        scheme: URL scheme (default "http").
        timeout: Per-request timeout in seconds (default 10). A request with no
            response within this window is retried like any other transient
            failure.
        retries: Max retry attempts for transient failures (default 8).
        backoff_factor: Exponential backoff base in seconds (default 2).
        backoff_max: Cap on any single backoff sleep in seconds (default 20), so
            the tail polls at a steady interval instead of ballooning.
    """

    def __init__(self, host: str, token: str, port: int = 8000, scheme: str = "http",
                 timeout: float = 10, retries: int = 8, backoff_factor: float = 2,
                 backoff_max: float = 20):
        self._base_url = f"{scheme}://{host}:{port}"
        self._token = token
        self._timeout = timeout
        self._session = requests.Session()
        # Retry connection errors, read timeouts, and the retryable 5xx statuses.
        # allowed_methods=None disables the method allowlist so POST/PUT/DELETE are
        # retried too — safe here because hercdb writes are idempotent (MERGE).
        # respect_retry_after_header=False so we use our own bounded backoff rather
        # than sleeping the server's advisory `Retry-After: 60` flat on each attempt.
        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            status=retries,
            status_forcelist=(502, 503, 504),
            allowed_methods=None,
            backoff_factor=backoff_factor,
            backoff_max=backoff_max,
            respect_retry_after_header=False,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    # -- internal helpers --------------------------------------------------

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def _request(self, method: str, path: str, tolerate_404: bool = False,
                 **kwargs) -> requests.Response:
        url = f"{self._base_url}{path}"
        kwargs.setdefault("timeout", self._timeout)
        resp = self._session.request(method, url, headers=self._headers(), **kwargs)
        # Some callers treat 404 as an empty result rather than an error; let them
        # inspect the response instead of raising.
        if tolerate_404 and resp.status_code == 404:
            return resp
        resp.raise_for_status()
        return resp

    def _get(self, path: str, **kwargs) -> requests.Response:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs) -> requests.Response:
        return self._request("POST", path, **kwargs)

    def _put(self, path: str, **kwargs) -> requests.Response:
        return self._request("PUT", path, **kwargs)

    # -- public API --------------------------------------------------------

    def check_token(self) -> dict:
        """Verify that the current token is valid."""
        return self._get("/check-token").json()

    def home(self) -> dict:
        """Call the welcome endpoint."""
        return self._get("/home").json()

    def get_artifact_by_name(
        self,
        pherc: str,
        cornice: str = None,
        pezzo: str = None,
    ) -> dict:
        """Get full detail for one artifact (PHerc / Cornice / Pezzo) by name.

        ``pherc`` is required; add *cornice* and/or *pezzo* to address a
        subdivision. Names must be exact displayNames — resolve noisy input
        with :meth:`resolve` first. Returns the artifact's own properties,
        attached metadata, assigned ``educelabids``, and child counts.
        Datasets are not included (use the dataset methods).
        """
        params: dict = {"pherc": pherc}
        if cornice is not None:
            params["cornice"] = cornice
        if pezzo is not None:
            params["pezzo"] = pezzo
        return self._get("/artifacts", params=params).json()

    def get_subdivisions(self, pherc_id: str) -> dict:
        """List all Cornici and Pezzi for a PHerc.

        Returns ``{pherc, cornici, pezzi}`` where each node is
        ``{displayName, aliases, educelabids, parent}``. ``parent`` is
        ``{type, displayName}`` (a nested Pezzo's parent Cornice, or the PHerc
        for a directly-attached node) or ``None`` for the PHerc itself.
        """
        return self._get(f"/pherc/{pherc_id}/subdivisions").json()

    def get_all_datasets_for_pherc(
        self,
        pherc_id: str,
        dataset_type: str = None,
        newest_completed: bool = False,
    ) -> dict:
        """Get all datasets under a PHerc, grouped by EduceLabID.

        Traverses the full hierarchy (PHerc, Cornici, Pezzi) and returns
        all datasets nested by physical artifact.

        Args:
            pherc_id: PHerc display name.
            dataset_type: Optional filter. One of "FlatbedScan", "PGSRaw", "SpectralRaw".
            newest_completed: If True, return only the newest completed dataset
                per type per artifact.
        """
        params: dict = {}
        if dataset_type is not None:
            params["dataset_type"] = dataset_type
        if newest_completed:
            params["newest_completed"] = "true"
        resp = self._get(
            f"/pherc/{pherc_id}/all-datasets", params=params, tolerate_404=True,
        )
        if resp.status_code == 404:
            return {"pherc": pherc_id, "artifacts": []}
        return resp.json()

    def get_artifact(self, uuid: str) -> dict:
        """Resolve a UUID to its physical artifact (the UUID -> artifact bridge).

        Returns ``{uuid, type, displayName, pherc, cornice, pezzo, parent,
        location}``. Lightweight — for full detail look the artifact up by name
        via :meth:`get_artifact_by_name`.
        """
        return self._get(f"/artifacts/{uuid}").json()

    def get_datasets_for_educelabid(
        self,
        uuid: str,
        dataset_type: str = None,
        newest_completed: bool = False,
    ) -> list[dict]:
        """Get all datasets for a specific EduceLabID.

        Datasets are pooled across the UUID's replacement (REPLACES) chain; each
        carries ``belongs_to_uuid`` (the EduceLabID it actually belongs to) so a
        scan on a retired predecessor UUID is visible.

        Args:
            uuid: The EduceLabID UUID.
            dataset_type: Optional filter. One of "FlatbedScan", "PGSRaw", "SpectralRaw".
            newest_completed: If True, return only the newest completed dataset per type.
        """
        params: dict = {}
        if dataset_type is not None:
            params["dataset_type"] = dataset_type
        if newest_completed:
            params["newest_completed"] = "true"
        resp = self._get(
            f"/educelabid/{uuid}/datasets", params=params, tolerate_404=True,
        )
        if resp.status_code == 404:
            return []
        return resp.json()

    def resolve(
        self,
        name: str,
        label: str = "PHerc",
        parent_pherc: str = None,
        parent_cornice: str = None,
        threshold: int = 75,
        limit: int = 10,
    ) -> list[dict]:
        """Fuzzy-resolve a noisy displayName to ranked PHerc/Cornice/Pezzo candidates.

        Use this when you don't know the exact displayName but have a
        noisy version. Pick a candidate from the returned list, then use
        its UUID / EduceLabID with the other client methods for any
        downstream lookup.

        Args:
            name: Approximate displayName to look up.
            label: One of ``"PHerc"``, ``"Cornice"``, ``"Pezzo"``.
            parent_pherc: Optional (fuzzy) PHerc scope for Cornice/Pezzo
                lookups.
            parent_cornice: Optional (fuzzy) Cornice scope for Pezzo
                lookups.
            threshold: Minimum similarity score 0-100 (default 75).
            limit: Max ranked candidates to return (default 10).

        Returns:
            List of dicts ordered by ``score`` desc:
            ``{"displayName", "score", "node": {<flattened properties>},
            "parent_pherc": {"displayName", "score"} | None,
            "parent_cornice": {"displayName", "score"} | None}``.
            Exact (whitespace-stripped, lowercased) matches score 100.
        """
        params = {
            "name": name,
            "label": label,
            "threshold": threshold,
            "limit": limit,
        }
        if parent_pherc is not None:
            params["parent_pherc"] = parent_pherc
        if parent_cornice is not None:
            params["parent_cornice"] = parent_cornice
        return self._get("/resolve", params=params).json()

    def get_pipelines(self) -> list[dict]:
        """Get all pipelines with their status summaries."""
        return self._get("/pipelines").json()

    def get_pipeline_stages(self, pipeline_id: str) -> list[dict]:
        """Get all process stages for a given pipeline."""
        return self._get(f"/pipelines/{pipeline_id}/stages").json()

    def initialize_pipeline(self, pipeline_id: str, artifact_uuid: str, datetime: str) -> dict:
        """Create a new pipeline linked to an EduceLabID.

        Args:
            pipeline_id: Unique identifier for the pipeline.
            artifact_uuid: UUID of the EduceLabID to link to.
            datetime: ISO datetime string (e.g. 2026-02-18T12:18:21.726912).
        """
        return self._post("/pipelines", json={
            "pipeline_id": pipeline_id,
            "artifact_uuid": artifact_uuid,
            "datetime": datetime,
        }).json()

    def initialize_process(
        self,
        pipeline_id: str,
        proc_type: str,
        input_dataset_paths: list[str],
        output_dataset_path: str,
        slurm_id: str,
        start_datetime: str,
    ) -> dict:
        """Create a new process (stage) within a pipeline.

        Args:
            pipeline_id: Pipeline to attach the process to.
            proc_type: One of PGS, SPEC, REG, WEB.
            input_dataset_paths: List of input dataset paths.
            output_dataset_path: Path for the output dataset.
            slurm_id: Slurm job ID.
            start_datetime: ISO datetime string for start time.
        """
        return self._post(f"/pipelines/{pipeline_id}/processes", json={
            "proc_type": proc_type,
            "input_dataset_paths": input_dataset_paths,
            "output_dataset_path": output_dataset_path,
            "slurm_id": slurm_id,
            "start_datetime": start_datetime,
        }).json()

    def update_process_status(
        self,
        pipeline_id: str,
        proc_type: str,
        status: str,
        end_datetime: str,
        notes: str | None = None,
    ) -> dict:
        """Update the status of a process in a pipeline.

        Args:
            pipeline_id: The pipeline ID.
            proc_type: The process type (PGS, SPEC, REG, WEB).
            status: New status (completed or failed).
            end_datetime: ISO datetime string for end time.
            notes: Free text saying where a multi-job stage failed. Sent only
                when given, so this cannot blank a note another job just wrote.
                Requires a 0.3.2 server — an older one ignores the field
                silently rather than erroring.
        """
        body = {"status": status, "end_datetime": end_datetime}
        if notes is not None:
            body["notes"] = notes
        return self._put(
            f"/pipelines/{pipeline_id}/processes/{proc_type}/status", json=body).json()

    def get_unprocessed_datasets(self, proc_type: str) -> list[dict]:
        """Raw scans awaiting `proc_type`: one row per artifact, newest scan.

        The work-list for an unattended dispatcher. Each row carries the dataset
        to process plus the artifact fields an output directory is named from.
        An empty list means nothing is left to process.

        Args:
            proc_type: 'SPEC' or 'PGS'. Anything else returns 400.
        """
        return self._get(f"/datasets/{proc_type}/unprocessed").json()

    def get_ambiguous_datasets(self, proc_type: str) -> list[dict]:
        """Complete raw scans the `proc_type` dispatcher skips, and why."""
        return self._get(f"/datasets/{proc_type}/ambiguous").json()

    # Kept for 0.3.2 callers, and deliberately still on the literal
    # /datasets/spectral/... routes: a 0.3.3 client then also works against a
    # server that has not been upgraded yet.

    def get_unprocessed_spectral_datasets(self) -> list[dict]:
        """The SPEC work-list. See `get_unprocessed_datasets`."""
        return self._get("/datasets/spectral/unprocessed").json()

    def get_ambiguous_spectral_datasets(self) -> list[dict]:
        """Complete spectral scans the dispatcher skips, and why."""
        return self._get("/datasets/spectral/ambiguous").json()

    def delete_pipeline(self, pipeline_id: str) -> dict:
        """Delete a pipeline and all its processes and output datasets.

        Args:
            pipeline_id: The pipeline ID to delete.
        """
        return self._request("DELETE", f"/pipelines/{pipeline_id}").json()

    def get_pipeline_confirmation(self, pipeline_id: str) -> dict:
        """Get full pipeline summary with all stages.

        Args:
            pipeline_id: The pipeline ID.
        """
        return self._get(f"/pipelines/{pipeline_id}/confirmation").json()
