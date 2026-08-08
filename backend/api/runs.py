import hashlib
import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from auth.middleware import require_auth
from core.validators import validate_model_url, validate_run_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Optimization Runs"])

class OptimizeRequest(BaseModel):
    model_url: str = Field(..., description="HuggingFace model ID or HTTPS .gguf URL")
    target_clouds: list = Field(default=["graviton4"], description="Target cloud providers")
    quantization_target: str = Field(default="INT4", description="Target quantization level")
    sla_spec: dict = Field(default={"max_p99_latency_ms": 500.0, "min_tps": 30.0})
    quality_floor: float = Field(default=0.98, ge=0.5, le=1.0)

@router.post("/optimize", status_code=202)
async def start_optimization(
    req: OptimizeRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_auth),
):
    """Start an asynchronous model optimization run."""
    import uuid
    from core.config import settings

    # Validate model URL for SSRF and format
    validated_url = validate_model_url(req.model_url)

    # Validate clouds
    allowed_clouds = {"graviton4", "cobalt100", "axion"}
    invalid = set(req.target_clouds) - allowed_clouds
    if invalid:
        raise HTTPException(400, f"Invalid clouds: {invalid}. Allowed: {allowed_clouds}")

    run_id = str(uuid.uuid4())
    model_hash = hashlib.sha256(validated_url.encode()).hexdigest()

    # Persist run to DB
    try:
        from db.runs_repository import RunsRepository
        await RunsRepository.create_run(
            run_id=run_id,
            model_url=validated_url,
            model_hash=model_hash,
            sla_spec=req.sla_spec,
            target_clouds=req.target_clouds,
            quality_floor=req.quality_floor,
            org_id=user.get("org_id"),
            user_id=user.get("user_id"),
        )
    except Exception as e:
        logger.error(f"Failed to persist run to DB: {e}")
        raise HTTPException(500, f"Failed to create optimization run: {str(e)}")

    # Enqueue to Redis worker queue
    try:
        from cache.redis_client import get_redis
        redis = await get_redis()
        await redis.rpush("inferav22:optimization:queue", run_id)
        logger.info(f"Enqueued run {run_id} to worker queue")
    except Exception as e:
        logger.error(f"Failed to enqueue run {run_id}: {e}")
        # Don't fail the request — worker will retry from DB

    return {
        "run_id": run_id,
        "status": "queued",
        "model_url": validated_url,
        "target_clouds": req.target_clouds,
        "websocket_url": f"/ws/{run_id}",
        "message": "Optimization run queued. Connect to websocket_url for real-time progress.",
    }

@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    user: dict = Depends(require_auth),
):
    """Get the current status and results of an optimization run."""
    validate_run_id(run_id)
    from db.runs_repository import RunsRepository
    from auth.rbac import require_run_access
    run = await require_run_access(run_id, user)
    return run

@router.get("/runs")
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_auth),
):
    """List optimization runs for the authenticated user's organization."""
    from db.runs_repository import RunsRepository
    runs = await RunsRepository.list_runs(
        org_id=user.get("org_id"),
        limit=limit,
        offset=offset,
    )
    return {"runs": runs, "limit": limit, "offset": offset}

@router.get("/runs/{run_id}/helm-chart")
async def download_helm_chart(
    run_id: str,
    user: dict = Depends(require_auth),
):
    """Download the optimized Helm chart (.tgz) for a completed run."""
    from fastapi.responses import Response
    from db.runs_repository import RunsRepository
    from auth.rbac import require_run_access
    from services.helm_generator import HelmGenerator

    validate_run_id(run_id)
    run = await require_run_access(run_id, user)

    if run.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Helm chart is only available for completed runs")

    model_url = run.get("model_url", "meta-llama/Llama-3.2-3B-Instruct")
    # For a real implementation, you'd extract quant_level from the optimal_config in the cert
    quant_level = "INT4" 
    
    # Generate the actual .tgz bytes
    tgz_bytes = HelmGenerator.generate_helm_tgz(model_url, quant_level)

    return Response(
        content=tgz_bytes,
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="inferav22-{run_id[:8]}.tgz"'
        }
    )
