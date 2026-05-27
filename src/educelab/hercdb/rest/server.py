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

@app.get('/pherc/{pherc_id}')
async def get_pherc_by_id(pherc_id: str, user: str = Depends(get_current_user)):
    """Get a PHerc and all its directly attached nodes by display name."""
    logger.info(f"User {user} requested PHerc with ID: {pherc_id}")
    records,_,_ = db.get_directly_attached_nodes(node_type="PHerc", pherc_display_name=pherc_id)
    logger.debug(f"Found records: {records}")
    if records and len(records) > 0:
        record_json = db.records_to_label_json(records)
        return JSONResponse(record_json, status_code=200)
    else:
        return HTTPException(status_code=404, detail=f"No PHerc found with displayName '{pherc_id}'")

@app.get("/pherc/{pherc_id}/cornice/{cornice_id}")
async def get_cornice_by_id(pherc_id: str, cornice_id: str, user: str = Depends(get_current_user)):
    """Get a Cornice and all its directly attached nodes (excluding the parent PHerc)."""
    logger.info(f"User {user} called /pherc/{pherc_id}/cornice/{cornice_id}")
    records, _, _ = db.get_directly_attached_nodes(node_type="Cornice", pherc_display_name=pherc_id, cornice_display_name=cornice_id)
    if records and len(records) > 0:
        record_json = db.records_to_label_json(records)
        if isinstance(record_json, dict) and "PHerc" in record_json:
            record_json.pop("PHerc")
        return JSONResponse(content=record_json)
    else:
        raise HTTPException(status_code=404, detail=f"No Cornice found with displayName '{cornice_id}' in PHerc '{pherc_id}'")


@app.get("/pherc/{pherc_id}/cornice/{cornice_id}/pezzo/{pezzo_id}")
async def get_pezzo_by_pherc_cornice(pherc_id: str, cornice_id: str, pezzo_id: str, user: str = Depends(get_current_user)):
    """Get a Pezzo under a specific Cornice and all its directly attached nodes."""
    logger.info(f"User {user} called /pherc/{pherc_id}/cornice/{cornice_id}/pezzo/{pezzo_id}")
    records, _, _ = db.get_directly_attached_nodes(
        node_type="Pezzo",
        pherc_display_name=pherc_id,
        cornice_display_name=cornice_id,
        pezzo_display_name=pezzo_id
    )
    if records and len(records) > 0:
        record_json = db.records_to_label_json(records)
        if isinstance(record_json, dict):
            record_json.pop("PHerc", None)
            record_json.pop("Cornice", None)
        return JSONResponse(content=record_json)
    else:
        raise HTTPException(status_code=404, detail=f"No Pezzo found with displayName '{pezzo_id}' in Cornice '{cornice_id}' of PHerc '{pherc_id}'")


@app.get("/pherc/{pherc_id}/pezzo/{pezzo_id}")
async def get_pezzo_by_pherc(pherc_id, pezzo_id, user: str = Depends(get_current_user)):
    """Get a Pezzo directly under a PHerc and all its directly attached nodes."""
    logger.info(f"User {user} called /pherc/{pherc_id}/pezzo/{pezzo_id}")
    records,_,_ = db.get_directly_attached_nodes(node_type="Pezzo", pherc_display_name=pherc_id, pezzo_display_name=pezzo_id)
    if records and len(records) > 0:
        record_json = db.records_to_label_json(records)
        # Remove the "PHerc" key if present
        if isinstance(record_json, dict) and "PHerc" in record_json:
            record_json.pop("PHerc")
        return JSONResponse(content=record_json), 200
        
    else:
        raise HTTPException(status_code=404, detail=f"No Pezzo found with displayName '{pezzo_id}' in PHerc '{pherc_id}'")


@app.get("/pherc/{pherc_id}/datasets/{dataset_type}")
async def get_datasets(
    pherc_id: str,
    dataset_type: str,
    cornice: Optional[str] = Query(None),
    pezzo: Optional[str] = Query(None),
    newest_completed: bool = Query(False),
    user: str = Depends(get_current_user),
):
    """Get imaging datasets for a PHerc, optionally filtered by Cornice or Pezzo.

    Valid dataset types: FlatbedScan, PGSRaw, SpectralRaw.
    """
    logger.info(f"User {user} called /pherc/{pherc_id}/datasets/{dataset_type}")

    # Validate dataset_type against the DatasetType enum
    try:
        ds_type = DatasetType[dataset_type]
    except KeyError:
        valid_types = [t.name for t in DatasetType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dataset type '{dataset_type}'. Must be one of: {valid_types}",
        )

    datasets = db.find_datasets(
        ds_type, pherc_id, cornice=cornice, pezzo=pezzo,
        newest_completed=newest_completed, properties_only=True,
    )

    if not datasets:
        raise HTTPException(
            status_code=404,
            detail=f"No {dataset_type} datasets found for PHerc '{pherc_id}'",
        )

    # Convert any non-serializable values (e.g. Neo4j DateTime) to strings
    for dataset in datasets:
        for key, value in dataset.items():
            if not isinstance(value, (str, int, float, bool, type(None), list, dict)):
                dataset[key] = str(value)

    return JSONResponse(content=datasets, status_code=200)


@app.get("/pherc/{pherc_id}/subdivisions")
async def get_subdivisions(pherc_id: str, user: str = Depends(get_current_user)):
    """List all Cornici and Pezzi for a given PHerc."""
    logger.info(f"User {user} called /pherc/{pherc_id}/subdivisions")
    records = db.list_cornici_and_pezzi_for_pherc(pherc_id)

    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"No PHerc found with displayName '{pherc_id}'",
        )

    record = records[0].data()
    result = {
        "pherc": dict(record["ph"]) if record["ph"] else {},
        "cornici": [
            {"name": c.get("name"), "displayName": c.get("displayName")}
            for c in record.get("cr", [])
        ],
        "pezzi": [
            {"name": p.get("name"), "displayName": p.get("displayName")}
            for p in record.get("pz", [])
        ],
    }
    return JSONResponse(content=result, status_code=200)


@app.get("/home")
async def home(user: str = Depends(get_current_user)):
    """Welcome endpoint."""
    logger.info(f"User {user} called /home")
    return {"message": "Welcome to the Educelab Herculaneum Database"}


@app.post("/search")
async def search_pherc(request: Request, user: str = Depends(get_current_user)):
    """Search for PHercs using multiple criteria. Results are the intersection of all provided filters."""
    data =await request.json()
    logger.info(f"User {user} called /search with data: {data}")
    logger.debug(f"Search parameters: {data}")

    result_sets = []

    # Handle all numeric property searches in a loop
    numeric_fields = [
        ("diameter", "diameter_operator", "diameter_value"),
        ("height", "height_operator", "height_value"),
        ("width", "width_operator", "width_value"),
        ("weight", "weight_operator", "weight_value"),
    ]
    for prop, op_key, val_key in numeric_fields:
        operator = data.get(op_key)
        value = data.get(val_key)
        if value:
            records, _, _ = db.find_pherc_by_numeric_property(prop, operator, value)
            if not records:
                return JSONResponse(status_code=404, content={"PHercs": []})
            result_sets.append(set(record['ph']['displayName'] for record in records))

    # Handle unrolled year search
    operator = data.get("unrolled_year_operator")
    value = data.get("unrolled_year_value")
    if value:
        records, _, _ = db.find_pherc_by_unrolled_year(operator, value)
        if not records:
            return JSONResponse(status_code=404, content={"PHercs": []})
        result_sets.append(set(record['ph']['displayName'] for record in records))

    print(f"Result sets: {result_sets}")

    # Map parameter names to (function, argument)
    param_map = [
        ("uuid", db.find_pherc_by_uuid, None),
        ("display-name", db.find_pherc_by_display_name, None),
        ("author", db.find_pherc_by_author, None),
        ("language", db.find_pherc_by_language, None),
        ("unrolling-status", db.find_pherc_by_property_value, "unrolling_status"),
        ("scorze", db.find_pherc_by_property_value, "scorze"),
        ("unrolling-method", db.find_pherc_by_unrolling_method, None),
        ("unroller", db.find_pherc_by_unroller_name, None),
        ("literary-work", db.find_pherc_by_property_value, "literary_work"),
        ("editions", db.find_pherc_by_property_value, "editions"),
        ("subscriptio", db.find_pherc_by_property_value, "subscriptio"),
        ("instituion", db.find_pherc_by_custodial_institution, None),
        ("initial-end-title", db.find_pherc_by_property_value, "initial_end_title"),
        ("recto-verso-title", db.find_pherc_by_property_value, "recto_verso_title"),
        ("multiple-hands", db.find_pherc_by_property_value, "multiple_hands"),
        ("neapolitan-drawings", db.find_pherc_by_property_value, "neapolitan_drawings"),
        ("oxonian-drawings", db.find_pherc_by_property_value, "oxonian_drawings"),
        ("cavallo-scribal-style", db.find_pherc_by_cavallo_scribal_style, None),
    ]
    
    for key, func, prop in param_map:
        value = data.get(key)
        
        if key in ("editions", "literary-work", "neapolitan-drawings", "oxonian-drawings") and value == "ALL":
            records, _, _ = db.find_pherc_with_any_property_value(prop)
            if not records:
                return JSONResponse(status_code=404, content={"PHercs": []})
            result_sets.append(set(record['ph']['displayName'] for record in records))
        elif value:
            if func == db.find_pherc_by_property_value:
                records, _, _ = func(prop, value)
            elif func == db.find_pherc_by_display_name:
                records, _, _ = func(value)
            elif func == db.find_pherc_by_author:
                records, _, _ = func(value)
            elif func == db.find_pherc_by_uuid:
                records, _, _ = func(value)
            elif func == db.find_pherc_by_language:
                records, _, _ = func(value)
            elif func == db.find_pherc_by_unroller_name:
                records, _, _ = func(value)
            elif func == db.find_pherc_by_unrolling_method:
                records, _, _ = func(value)
            elif func == db.find_pherc_by_custodial_institution:
                records, _, _ = func(value)
            elif func == db.find_pherc_by_cavallo_scribal_style:
                records, _, _ = func(value)
            else:
                continue  # skip if function mapping is not handled

            if not records:
                return JSONResponse(status_code=404, content={"PHercs": []})
                
            result_sets.append(set(record['ph']['displayName'] for record in records))

    # Fuzzy display-name lookup (kept separate from the strict "display-name"
    # param above so existing callers see no change). Resolves the noisy
    # input to a set of PHerc displayNames via fuzzy_find_node, then feeds
    # them into the same intersection logic as every other filter.
    fuzzy_name = data.get("display-name-fuzzy")
    if fuzzy_name:
        fuzzy_threshold = data.get("display-name-fuzzy-threshold", 75)
        try:
            fuzzy_hits = db.fuzzy_find_node(
                fuzzy_name, label="PHerc", threshold=fuzzy_threshold,
            )
        except ValueError as e:
            return JSONResponse(status_code=400, content={"detail": str(e)})
        if not fuzzy_hits:
            return JSONResponse(status_code=404, content={"PHercs": []})
        result_sets.append({c["displayName"] for c in fuzzy_hits})

    if result_sets:
        matching_names = set.intersection(*result_sets)
    else:
        matching_names = set()

    return JSONResponse(status_code=200, content={"PHercs": list(matching_names)})


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
        # Flatten the Neo4j Node to its properties dict so it's JSON-serializable.
        props = dict(c["node"]) if c["node"] is not None else {}
        result.append({
            "displayName": c["displayName"],
            "score": c["score"],
            "node": props,
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


@app.get("/pherc/{pherc_id}/educelabids")
async def get_educelabids_for_pherc(
    pherc_id: str,
    user: str = Depends(get_current_user),
):
    """List all EduceLabIDs under a PHerc umbrella."""
    logger.info(f"User {user} called /pherc/{pherc_id}/educelabids")

    educelabids = db.find_educelabids_for_pherc(pherc_id)

    if not educelabids:
        raise HTTPException(
            status_code=404,
            detail=f"No EduceLabIDs found under PHerc '{pherc_id}'",
        )

    return JSONResponse(content=educelabids, status_code=200)


@app.get("/artifacts/{uuid}")
async def get_artifact(uuid: str, user: str = Depends(get_current_user)):
    """Get the display name for an artifact by its UUID."""
    logger.info(f"User {user} called /artifacts/{uuid}")
    artifact_info = db.find_artifact_name_by_uuid(uuid)
    if not artifact_info:
        raise HTTPException(status_code=404, detail=f"No artifact found for UUID '{uuid}'")
    display_name = db._format_dataset_name(artifact_info)
    return {"display_name": display_name}


@app.get("/educelabid/{uuid}/datasets")
async def get_datasets_for_educelabid(
    uuid: str,
    dataset_type: Optional[str] = Query(None),
    newest_completed: bool = Query(False),
    user: str = Depends(get_current_user),
):
    """Get all datasets for a specific EduceLabID."""
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

    datasets = db.find_datasets_for_educelabid(
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
