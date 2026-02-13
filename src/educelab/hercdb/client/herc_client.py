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

    # -- public API --------------------------------------------------------

    def check_token(self) -> dict:
        """Verify that the current token is valid."""
        return self._get("/check-token").json()

    def home(self) -> dict:
        """Call the welcome endpoint."""
        return self._get("/home").json()

    def get_pherc(self, pherc_id: str) -> dict:
        """Get a PHerc and all its directly attached nodes."""
        return self._get(f"/pherc/{pherc_id}").json()

    def get_cornice(self, pherc_id: str, cornice_id: str) -> dict:
        """Get a Cornice and its attached nodes."""
        return self._get(f"/pherc/{pherc_id}/cornice/{cornice_id}").json()

    def get_pezzo(self, pherc_id: str, pezzo_id: str, cornice_id: str = None) -> dict:
        """Get a Pezzo and its attached nodes.

        If *cornice_id* is provided the Pezzo is looked up under that Cornice;
        otherwise it is looked up directly under the PHerc.
        """
        if cornice_id:
            path = f"/pherc/{pherc_id}/cornice/{cornice_id}/pezzo/{pezzo_id}"
        else:
            path = f"/pherc/{pherc_id}/pezzo/{pezzo_id}"
        return self._get(path).json()

    def get_subdivisions(self, pherc_id: str) -> dict:
        """List all Cornici and Pezzi for a given PHerc."""
        return self._get(f"/pherc/{pherc_id}/subdivisions").json()

    def get_datasets(
        self,
        pherc_id: str,
        dataset_type: str,
        cornice: str = None,
        pezzo: str = None,
        newest_completed: bool = False,
    ) -> list[dict]:
        """Get imaging datasets for a PHerc.

        Args:
            pherc_id: PHerc display name.
            dataset_type: One of "FlatbedScan", "PGSRaw", "SpectralRaw".
            cornice: Optional Cornice display name filter.
            pezzo: Optional Pezzo display name filter.
            newest_completed: If True, return only the newest completed dataset.
        """
        params: dict = {}
        if cornice is not None:
            params["cornice"] = cornice
        if pezzo is not None:
            params["pezzo"] = pezzo
        if newest_completed:
            params["newest_completed"] = "true"
        resp = requests.get(
            f"{self._base_url}/pherc/{pherc_id}/datasets/{dataset_type}",
            headers=self._headers(),
            params=params,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json()

    def search(self, **criteria) -> dict:
        """Search for PHercs using multiple criteria.

        Keyword arguments are passed directly as the JSON body to ``POST /search``.
        """
        return self._post("/search", json=criteria).json()

    def get_pipelines(self) -> list[dict]:
        """Get all pipelines with their status summaries."""
        return self._get("/pipelines").json()

    def get_pipeline_stages(self, pipeline_id: str) -> list[dict]:
        """Get all process stages for a given pipeline."""
        return self._get(f"/pipelines/{pipeline_id}/stages").json()
