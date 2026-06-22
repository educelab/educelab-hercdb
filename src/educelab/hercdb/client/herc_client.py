import requests


class HercClient:
    """Lightweight REST API client for the EduceLab HercDB API.

    Only requires the ``requests`` library. No Neo4j or server-side
    dependencies are needed.

    Args:
        host: Hostname or IP of the API server.
        token: Bearer token for authentication.
        port: Port number (default 8000).
        scheme: URL scheme (default "http").
    """

    def __init__(self, host: str, token: str, port: int = 8000, scheme: str = "http"):
        self._base_url = f"{scheme}://{host}:{port}"
        self._token = token

    # -- internal helpers --------------------------------------------------

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self._base_url}{path}"
        resp = requests.request(method, url, headers=self._headers(), **kwargs)
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
        resp = requests.get(
            f"{self._base_url}/pherc/{pherc_id}/all-datasets",
            headers=self._headers(),
            params=params,
        )
        if resp.status_code == 404:
            return {"pherc": pherc_id, "artifacts": []}
        resp.raise_for_status()
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
        resp = requests.get(
            f"{self._base_url}/educelabid/{uuid}/datasets",
            headers=self._headers(),
            params=params,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
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
    ) -> dict:
        """Update the status of a process in a pipeline.

        Args:
            pipeline_id: The pipeline ID.
            proc_type: The process type (PGS, SPEC, REG, WEB).
            status: New status (completed or failed).
            end_datetime: ISO datetime string for end time.
        """
        return self._put(f"/pipelines/{pipeline_id}/processes/{proc_type}/status", json={
            "status": status,
            "end_datetime": end_datetime,
        }).json()

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
