import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Depends, Query, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from educelab import hercdb
from educelab.hercdb.db import DatasetType

# Load tokens from tokens file
TOKENS = {}
TOKEN_TO_USER = {}
try:
    
    tokens_path = Path.home() / '.tokens'
    with open(tokens_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and '=' in line:
                user, token = line.split('=', 1)
                user = user.strip()
                token = token.strip()
                TOKENS[user] = token
                TOKEN_TO_USER[token] = user
except FileNotFoundError:
    print("Warning: '.tokens' file not found. No authentication will work.")

# --- Setup logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-auth")

# --- App and Auth ---
app = FastAPI(
    title="EduceLab HercDB API",
    description="REST API for the Herculaneum Papyrus Scroll Database",
    version="0.1.0",
)
security = HTTPBearer()


# Initialize DB connection
hercdb.config._load_config()
db = hercdb.connect()
print(f"Connected to DB?: {db.verify_connection()}")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    user = TOKEN_TO_USER.get(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
    return user

@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    method = request.method
    path = request.url.path
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "") if "Bearer " in auth_header else None
    user = TOKEN_TO_USER.get(token, "unknown")
    logger.info(f"{method} {path} called by user: {user}")
    return response

@app.get("/check-token")
async def check_token(user: str = Depends(get_current_user)):
    """
    Endpoint to verify if the provided token is valid.
    Returns user information if token is valid, otherwise returns 401.
    """
    logger.info(f"Token check requested by user: {user}")
    return JSONResponse(
        status_code=200, 
        content={
            "valid": True, 
            "user": user,
            "message": "Token is valid"
        }
    )

@app.get("/artifacts")
async def get_artifact_by_name(
    pherc: str = Query(..., description="PHerc displayName (exact)"),
    cornice: Optional[str] = Query(None, description="Cornice displayName (exact)"),
    pezzo: Optional[str] = Query(None, description="Pezzo displayName (exact)"),
    user: str = Depends(get_current_user),
):
    """Get full detail for one artifact (PHerc / Cornice / Pezzo) by exact name.

    ``pherc`` is always required; add ``cornice`` and/or ``pezzo`` to address a
    subdivision. Names must be exact displayNames — resolve noisy input via
    ``/resolve`` first. Returns the artifact's own properties, attached metadata,
    the ``educelabids`` assigned to it, and child counts. Datasets are not
    included (use ``/all-datasets`` or ``/educelabid/{uuid}/datasets``).
    """
    logger.info(
        f"User {user} called /artifacts pherc={pherc!r} "
        f"cornice={cornice!r} pezzo={pezzo!r}"
    )
    info = db.get_artifact_info(pherc, cornice=cornice, pezzo=pezzo)
    if info is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No artifact found for pherc={pherc!r} "
                f"cornice={cornice!r} pezzo={pezzo!r}"
            ),
        )
    return JSONResponse(content=info, status_code=200)


@app.get("/pherc/{pherc_id}/subdivisions")
async def get_subdivisions(pherc_id: str, user: str = Depends(get_current_user)):
    """List all Cornici and Pezzi for a PHerc.

    Each node (the PHerc itself, every Cornice, every Pezzo) is returned as
    ``{displayName, aliases, educelabids}`` — the alternate name forms plus the
    UUID bridge, with no other physical characteristics (those live on the
    ``/artifacts`` detail view).
    """
    logger.info(f"User {user} called /pherc/{pherc_id}/subdivisions")
    result = db.list_cornici_and_pezzi_for_pherc(pherc_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No PHerc found with displayName '{pherc_id}'",
        )

    return JSONResponse(content=result, status_code=200)


@app.get("/home")
async def home(user: str = Depends(get_current_user)):
    """Welcome endpoint."""
    logger.info(f"User {user} called /home")
    return {"message": "Welcome to the Educelab Herculaneum Database"}


@app.get("/resolve")
async def resolve_name(
    name: str = Query(..., description="Approximate displayName to resolve"),
    label: str = Query("PHerc", description="One of 'PHerc', 'Cornice', 'Pezzo'"),
    parent_pherc: Optional[str] = Query(None, description="Fuzzy parent PHerc scope (for Cornice/Pezzo)"),
    parent_cornice: Optional[str] = Query(None, description="Fuzzy parent Cornice scope (for Pezzo)"),
    threshold: int = Query(75, ge=0, le=100, description="Minimum similarity score"),
    limit: int = Query(10, ge=1, description="Max ranked candidates to return"),
    user: str = Depends(get_current_user),
):
    """Fuzzy-resolve a noisy displayName to ranked PHerc/Cornice/Pezzo candidates.

    Returns a JSON list ordered by similarity score (desc). Exact matches
    (after whitespace-strip + lowercase) short-circuit to score 100. An
    empty result is returned as ``[]`` with HTTP 200, not 404 — this is a
    discovery endpoint, not a "fetch this thing" lookup.
    """
    logger.info(
        f"User {user} called /resolve name={name!r} label={label!r} "
        f"parent_pherc={parent_pherc!r} parent_cornice={parent_cornice!r}"
    )

    try:
        candidates = db.fuzzy_find_node(
            name=name, label=label,
            parent_pherc=parent_pherc, parent_cornice=parent_cornice,
            threshold=threshold, limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = []
    for c in candidates:
        node = c["node"]
        props = dict(node) if node is not None else {}
        result.append({
            "displayName": c["displayName"],
            "name": props.get("name"),
            "score": c["score"],
            "nodeID": node.element_id if node is not None else None,
            "parent_pherc": c["parent_pherc"],
            "parent_cornice": c["parent_cornice"],
        })

    return JSONResponse(content=result, status_code=200)


@app.get("/pherc/{pherc_id}/all-datasets")
async def get_all_datasets_for_pherc(
    pherc_id: str,
    dataset_type: Optional[str] = Query(None),
    newest_completed: bool = Query(False),
    user: str = Depends(get_current_user),
):
    """Get all datasets under a PHerc, grouped by EduceLabID.

    Traverses the full hierarchy (PHerc, Cornici, Pezzi) and returns all
    datasets nested by physical artifact.

    Optional query parameters:
    - dataset_type: One of "FlatbedScan", "PGSRaw", "SpectralRaw"
    - newest_completed: If true, return only the newest completed dataset per type per artifact
    """
    logger.info(f"User {user} called /pherc/{pherc_id}/all-datasets")

    ds_type = None
    if dataset_type:
        try:
            ds_type = DatasetType[dataset_type]
        except KeyError:
            valid_types = [t.name for t in DatasetType]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid dataset type '{dataset_type}'. Must be one of: {valid_types}",
            )

    artifacts = db.find_all_datasets_for_pherc(
        pherc_id, ds_type=ds_type, newest_completed=newest_completed
    )

    if not artifacts:
        raise HTTPException(
            status_code=404,
            detail=f"No datasets found under PHerc '{pherc_id}'",
        )

    return JSONResponse(
        content={"pherc": pherc_id, "artifacts": artifacts},
        status_code=200,
    )


@app.get("/artifacts/{uuid}")
async def get_artifact(uuid: str, user: str = Depends(get_current_user)):
    """Resolve a UUID to its physical artifact (the UUID -> artifact bridge).

    Returns the node's ``type`` and ``displayName``, its place in the hierarchy
    (``pherc``/``cornice``/``pezzo``), its immediate ``parent`` (PHerc/Casetta in
    most cases), and a composed ``location`` string. Lightweight — for full
    detail look the artifact up by name via ``GET /artifacts?pherc=...``.
    """
    logger.info(f"User {user} called /artifacts/{uuid}")
    location = db.find_artifact_location_by_uuid(uuid)
    if not location:
        raise HTTPException(status_code=404, detail=f"No artifact found for UUID '{uuid}'")
    location["uuid"] = uuid
    location["location"] = db._format_dataset_name(location)
    return JSONResponse(content=location, status_code=200)


@app.get("/educelabid/{uuid}/datasets")
async def get_datasets_for_educelabid(
    uuid: str,
    dataset_type: Optional[str] = Query(None),
    newest_completed: bool = Query(False),
    user: str = Depends(get_current_user),
):
    """Get all datasets for a specific EduceLabID.

    Datasets are pooled across the UUID's replacement (REPLACES) chain, and each
    carries ``belongs_to_uuid`` (the EduceLabID it actually belongs to) so scans
    sitting on a retired predecessor UUID are visible.
    """
    logger.info(f"User {user} called /educelabid/{uuid}/datasets")

    ds_type = None
    if dataset_type:
        try:
            ds_type = DatasetType[dataset_type]
        except KeyError:
            valid_types = [t.name for t in DatasetType]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid dataset type '{dataset_type}'. Must be one of: {valid_types}",
            )

    datasets = db.find_datasets_for_educelabid_with_predecessors(
        uuid, ds_type=ds_type, newest_completed=newest_completed
    )

    if not datasets:
        raise HTTPException(
            status_code=404,
            detail=f"No datasets found for EduceLabID '{uuid}'",
        )

    return JSONResponse(content=datasets, status_code=200)


@app.get("/pipelines/{pipeline_id}/stages")
async def get_pipeline_stages(pipeline_id: str, user: str = Depends(get_current_user)):
    """Get all process stages for a given pipeline."""
    logger.info(f"User {user} requested pipeline stages for: {pipeline_id}")
    result = db.get_pipeline_status(pipeline_id)
    if result:
        # Rename 'stage' -> 'proc_type' for the client API.
        # Internally and in the DB the property is called 'stage' (e.g. "PGS", "SPEC").
        # The client uses 'proc_type' to avoid ambiguity with pipeline stage ordering.
        for proc in result:
            proc['proc_type'] = proc.pop('stage')
        return JSONResponse(content=result, status_code=200)
    else:
        raise HTTPException(status_code=404, detail=f"No pipeline found with ID '{pipeline_id}'")


@app.get("/pipelines")
async def get_pipelines(user: str = Depends(get_current_user)):
    """Get all pipelines with their status summaries."""
    logger.info(f"User {user} requested all pipelines")
    result = db.get_all_pipeline_summaries()
    return JSONResponse(content=result, status_code=200)


# --- Pipeline CRUD models ---

class CreatePipelineRequest(BaseModel):
    pipeline_id: str
    artifact_uuid: str
    datetime: str

class CreateProcessRequest(BaseModel):
    proc_type: str
    input_dataset_paths: list[str]
    output_dataset_path: str
    slurm_id: str
    start_datetime: str

class UpdateProcessStatusRequest(BaseModel):
    status: str
    end_datetime: str


# --- Pipeline CRUD endpoints ---

@app.post("/pipelines")
async def initialize_pipeline(body: CreatePipelineRequest, user: str = Depends(get_current_user)):
    """Create a new pipeline linked to an EduceLabID."""
    logger.info(f"User {user} creating pipeline: {body.pipeline_id}")
    result = db.initialize_pipeline(body.pipeline_id, body.artifact_uuid, body.datetime)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"EduceLabID with uuid '{body.artifact_uuid}' not found",
        )
    return JSONResponse(content=result, status_code=201)


@app.post("/pipelines/{pipeline_id}/processes")
async def initialize_process(pipeline_id: str, body: CreateProcessRequest, user: str = Depends(get_current_user)):
    """Create a new process (stage) within a pipeline."""
    logger.info(f"User {user} creating process {body.proc_type} for pipeline {pipeline_id}")

    valid_stages = ("PGS", "SPEC", "REG", "WEB")
    if body.proc_type not in valid_stages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid proc_type '{body.proc_type}'. Must be one of: {valid_stages}",
        )

    result = db.initialize_process(
        pipeline_id=pipeline_id,
        proc_type=body.proc_type,
        input_dataset_paths=body.input_dataset_paths,
        output_dataset_path=body.output_dataset_path,
        slurm_id=body.slurm_id,
        start_datetime=body.start_datetime,
    )
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline '{pipeline_id}' not found or input dataset(s) not found",
        )

    # Rename stage -> proc_type for consistency with existing convention
    result['proc_type'] = result.pop('stage')
    return JSONResponse(content=result, status_code=201)


@app.put("/pipelines/{pipeline_id}/processes/{proc_type}/status")
async def update_process_status(
    pipeline_id: str, proc_type: str, body: UpdateProcessStatusRequest,
    user: str = Depends(get_current_user),
):
    """Update the status of a process in a pipeline."""
    logger.info(f"User {user} updating {proc_type} status to {body.status} for pipeline {pipeline_id}")

    valid_statuses = ("completed", "failed")
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Must be one of: {valid_statuses}",
        )

    # Map proc_type back to stage for the DB layer
    result = db.update_process_status(
        pipeline_id=pipeline_id,
        stage=proc_type,
        status=body.status,
        end_datetime=body.end_datetime,
    )
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Process '{proc_type}' not found in pipeline '{pipeline_id}'",
        )

    # Rename stage -> proc_type for consistency
    result['proc_type'] = result.pop('stage')
    return JSONResponse(content=result, status_code=200)


@app.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str, user: str = Depends(get_current_user)):
    """Delete a pipeline and all its processes and output datasets."""
    logger.info(f"User {user} deleting pipeline: {pipeline_id}")
    result = db.delete_pipeline(pipeline_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No pipeline found with ID '{pipeline_id}'")
    return JSONResponse(content=result, status_code=200)


@app.get("/pipelines/{pipeline_id}/confirmation")
async def get_pipeline_confirmation(pipeline_id: str, user: str = Depends(get_current_user)):
    """Get full pipeline summary with all stages."""
    logger.info(f"User {user} requested confirmation for pipeline: {pipeline_id}")
    result = db.get_pipeline_confirmation(pipeline_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No pipeline found with ID '{pipeline_id}'",
        )
    return JSONResponse(content=result, status_code=200)
