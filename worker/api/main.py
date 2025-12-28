"""
Bull's Eye - FastAPI Application
REST API for the analysis service with detailed status tracking
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import structlog
import asyncio
import secrets

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json

from config import settings, get_available_models
from database import db
from worker import analyze_repository, celery_app

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()


def require_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    api_key: Optional[str] = Query(None, description="API key (use headers when possible)")
) -> None:
    """Require a valid API key for protected endpoints."""
    expected = (settings.api_key or "").strip()
    if not expected:
        # Misconfiguration: refuse unauthenticated operation
        raise HTTPException(status_code=500, detail="Server API key is not configured")

    token = (x_api_key or api_key or "").strip()
    if not token and authorization:
        auth = authorization.strip()
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()

    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")

# Create FastAPI app
app = FastAPI(
    title="Bull's Eye API",
    description="Intelligent Codebase Analysis API",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== PYDANTIC MODELS ====================

class ModelInfo(BaseModel):
    """Available LLM model information."""
    id: str
    name: str
    description: str


class JobCreate(BaseModel):
    """Request to create a new analysis job."""
    repo_url: str = Field(..., description="Git repository URL")
    branch: str = Field(default="main", description="Branch to analyze")
    name: Optional[str] = Field(None, description="Job name (auto-generated if not provided)")
    model: str = Field(default="deepseek-v3.2:cloud", description="Ollama model to use for analysis")
    ollama_api_key: Optional[str] = Field(None, description="Optional per-job Ollama Cloud API key")
    ollama_api_keys: Optional[List[str]] = Field(None, description="Optional list of per-job Ollama Cloud API keys")


class JobStatus(BaseModel):
    """Detailed job status."""
    id: str
    name: str
    repo_url: str
    branch: str
    model: str
    status: str
    status_message: Optional[str]
    progress: int
    progress_total: int
    progress_detail: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    celery_task_id: Optional[str] = None


class JobSummary(BaseModel):
    """Brief job summary for list view."""
    id: str
    name: str
    repo_url: str
    status: str
    progress: int
    created_at: str
    findings_count: Dict[str, int]


class StatusUpdate(BaseModel):
    """Status update entry."""
    timestamp: str
    stage: str
    message: str
    progress: Optional[int]
    details: Optional[str]


class ComponentInfo(BaseModel):
    """Component information."""
    id: str
    name: str
    path: str
    component_type: str
    language: Optional[str]
    file_count: int
    line_count: int
    health_score: Optional[int]
    analysis_summary: Optional[str]


class FindingInfo(BaseModel):
    """Finding information."""
    id: str
    scanner: str
    severity: str
    category: Optional[str]
    title: str
    description: Optional[str]
    file_path: Optional[str]
    line_start: Optional[int]
    suggestion: Optional[str]
    llm_explanation: Optional[str]


class StatsResponse(BaseModel):
    """Overall statistics."""
    jobs: Dict[str, int]
    findings: Dict[str, int]


# ==================== STARTUP/SHUTDOWN ====================

@app.on_event("startup")
async def startup():
    """Initialize application."""
    logger.info("Starting Bull's Eye API")
    if not (settings.api_key or "").strip():
        logger.error("API_KEY is required; refusing to start without authentication")
        raise RuntimeError("API_KEY must be set (non-empty)")
    # Ensure data directory exists
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.repos_dir.mkdir(parents=True, exist_ok=True)


# ==================== MODEL ENDPOINTS ====================

@app.get(
    "/api/models",
    response_model=List[ModelInfo],
    tags=["Models"],
    dependencies=[Depends(require_api_key)],
)
async def get_models():
    """Get list of available Ollama cloud models."""
    return get_available_models()


# ==================== JOB ENDPOINTS ====================

@app.post(
    "/api/jobs",
    response_model=JobStatus,
    tags=["Jobs"],
    dependencies=[Depends(require_api_key)],
)
async def create_job(job_data: JobCreate, background_tasks: BackgroundTasks):
    """
    Create a new analysis job.
    
    The job will be queued and executed in the background.
    Use the status endpoint to track progress.
    """
    # Create job in database
    config = {}
    if job_data.ollama_api_key:
        config["ollama_api_key"] = job_data.ollama_api_key.strip()
    if job_data.ollama_api_keys:
        normalized_keys = []
        seen = set()
        for key in job_data.ollama_api_keys:
            if not key:
                continue
            trimmed = key.strip()
            if trimmed and trimmed not in seen:
                normalized_keys.append(trimmed)
                seen.add(trimmed)
        if normalized_keys:
            config["ollama_api_keys"] = normalized_keys

    job_id = db.create_job(
        repo_url=job_data.repo_url,
        branch=job_data.branch,
        model=job_data.model,
        name=job_data.name,
        config=config if config else None,
    )
    
    logger.info(
        "Job created",
        job_id=job_id[:8],
        repo=job_data.repo_url,
        model=job_data.model
    )
    
    # Start analysis via Celery
    task = analyze_repository.delay(job_id, job_data.model)
    db.set_job_task_id(job_id, task.id)
    
    # Return job status
    job = db.get_job(job_id)
    return _format_job_status(job)


@app.get(
    "/api/jobs",
    response_model=List[JobSummary],
    tags=["Jobs"],
    dependencies=[Depends(require_api_key)],
)
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get list of all jobs."""
    jobs = db.get_jobs(status=status, limit=limit, offset=offset)
    
    result = []
    for job in jobs:
        findings_summary = db.get_findings_summary(job["id"])
        result.append({
            "id": job["id"],
            "name": job["name"],
            "repo_url": job["repo_url"],
            "status": job["status"],
            "progress": job["progress"],
            "created_at": job["created_at"],
            "findings_count": findings_summary,
        })
    
    return result


@app.get(
    "/api/jobs/{job_id}",
    response_model=JobStatus,
    tags=["Jobs"],
    dependencies=[Depends(require_api_key)],
)
async def get_job(job_id: str):
    """Get detailed job status."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return _format_job_status(job)


@app.post(
    "/api/jobs/{job_id}/stop",
    tags=["Jobs"],
    dependencies=[Depends(require_api_key)],
)
async def stop_job(job_id: str):
    """Stop a running job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Job is not running")
    
    # Stop Celery task if it exists
    if job.get("celery_task_id"):
        try:
            celery_app.control.revoke(job["celery_task_id"], terminate=True, signal="SIGTERM")
            logger.info(f"Revoked Celery task {job['celery_task_id']} for job {job_id}")
        except Exception as e:
            logger.warning(
                "Failed to revoke Celery task",
                job_id=job_id,
                task_id=job.get("celery_task_id"),
                error=str(e),
            )
    
    # Update job status to cancelled
    try:
        db.update_job_status(
            job_id=job_id,
            status="cancelled",
            message="Job stopped by user",
            progress=job["progress"],
            error="Job was cancelled by user"
        )
    except Exception as e:
        logger.error("Failed to mark job as cancelled", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to stop job")
    
    logger.info(f"Job {job_id} stopped by user")
    
    return {"message": "Job stopped successfully"}


@app.delete(
    "/api/jobs/{job_id}",
    tags=["Jobs"],
    dependencies=[Depends(require_api_key)],
)
async def delete_job(job_id: str):
    """Delete a job and all its data."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] in ["pending", "cloning", "detecting_components", "scanning", "analyzing", "generating_report"]:
        raise HTTPException(status_code=400, detail="Cannot delete running job. Stop it first.")
    
    # Delete job and all related data
    db.delete_job(job_id)
    
    logger.info(f"Job {job_id} deleted by user")
    
    return {"message": "Job deleted successfully"}


@app.get(
    "/api/jobs/{job_id}/status",
    tags=["Jobs"],
    dependencies=[Depends(require_api_key)],
)
async def get_job_status_updates(
    job_id: str,
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get detailed status updates for a job.
    
    Returns chronological list of all status changes.
    """
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    updates = db.get_status_updates(job_id, limit=limit)
    
    return {
        "job_id": job_id,
        "current_status": job["status"],
        "current_progress": job["progress"],
        "current_message": job["status_message"],
        "updates": [
            {
                "timestamp": u["timestamp"],
                "stage": u["stage"],
                "message": u["message"],
                "progress": u["progress"],
                "details": u["details"],
            }
            for u in updates
        ]
    }


@app.get(
    "/api/jobs/{job_id}/stream",
    tags=["Jobs"],
    dependencies=[Depends(require_api_key)],
)
async def stream_job_status(job_id: str):
    """
    Stream job status updates via Server-Sent Events.
    
    Connect to this endpoint to receive real-time status updates.
    """
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    async def event_generator():
        last_progress = -1
        last_status = ""
        
        while True:
            job = db.get_job(job_id)
            if not job:
                break
            
            # Send update if changed
            if job["progress"] != last_progress or job["status"] != last_status:
                data = {
                    "status": job["status"],
                    "progress": job["progress"],
                    "progress_total": job["progress_total"],
                    "message": job["status_message"],
                    "detail": job["progress_detail"],
                }
                yield f"data: {json.dumps(data)}\n\n"
                last_progress = job["progress"]
                last_status = job["status"]
            
            # Stop if completed or failed
            if job["status"] in ("completed", "failed"):
                break
            
            await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ==================== COMPONENT ENDPOINTS ====================

@app.get(
    "/api/jobs/{job_id}/components",
    response_model=List[ComponentInfo],
    tags=["Components"],
    dependencies=[Depends(require_api_key)],
)
async def get_job_components(job_id: str):
    """Get all components for a job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    components = db.get_components(job_id)
    return [_format_component(c) for c in components]


# ==================== FINDING ENDPOINTS ====================

@app.get(
    "/api/jobs/{job_id}/findings",
    response_model=List[FindingInfo],
    tags=["Findings"],
    dependencies=[Depends(require_api_key)],
)
async def get_job_findings(
    job_id: str,
    severity: Optional[str] = Query(None, description="Filter by severity"),
    scanner: Optional[str] = Query(None, description="Filter by scanner"),
    component_id: Optional[str] = Query(None, description="Filter by component"),
):
    """Get all findings for a job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    findings = db.get_findings(
        job_id=job_id,
        severity=severity,
        scanner=scanner,
        component_id=component_id,
    )
    
    return [_format_finding(f) for f in findings]


@app.get(
    "/api/jobs/{job_id}/findings/summary",
    tags=["Findings"],
    dependencies=[Depends(require_api_key)],
)
async def get_findings_summary(job_id: str):
    """Get findings summary by severity."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return db.get_findings_summary(job_id)


# ==================== REPORT ENDPOINTS ====================

@app.get(
    "/api/jobs/{job_id}/report",
    tags=["Reports"],
    dependencies=[Depends(require_api_key)],
)
async def get_job_report(job_id: str):
    """Get the full analysis report."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    report = db.get_report(job_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not ready")
    
    return json.loads(report["content"])


# ==================== STATS ENDPOINTS ====================

@app.get(
    "/api/stats",
    response_model=StatsResponse,
    tags=["Stats"],
    dependencies=[Depends(require_api_key)],
)
async def get_stats():
    """Get overall statistics."""
    return db.get_stats()


# ==================== WEBHOOK ENDPOINTS ====================

@app.post(
    "/webhook/analyze",
    tags=["Webhooks"],
    dependencies=[Depends(require_api_key)],
)
async def webhook_analyze(
    repo_url: str,
    branch: str = "main",
    model: str = "deepseek-v3.2:cloud",
    name: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
):
    """
    Webhook endpoint for triggering analysis.
    
    Can be used by n8n workflows or CI/CD pipelines.
    """
    job_id = db.create_job(
        repo_url=repo_url,
        branch=branch,
        model=model,
        name=name,
    )
    
    analyze_repository.delay(job_id, model)
    
    return {
        "status": "queued",
        "job_id": job_id,
        "message": f"Analysis queued for {repo_url}",
    }


# ==================== HEALTH ENDPOINTS ====================

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


# ==================== HELPER FUNCTIONS ====================

def _format_job_status(job: Dict) -> Dict:
    """Format job for API response."""
    return {
        "id": job["id"],
        "name": job["name"],
        "repo_url": job["repo_url"],
        "branch": job["branch"],
        "model": job["model"],
        "status": job["status"],
        "status_message": job.get("status_message"),
        "progress": job["progress"],
        "progress_total": job.get("progress_total", 100),
        "progress_detail": job.get("progress_detail"),
        "created_at": job["created_at"],
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "error_message": job.get("error_message"),
        "celery_task_id": job.get("celery_task_id"),
    }


def _format_component(comp: Dict) -> Dict:
    """Format component for API response."""
    return {
        "id": comp["id"],
        "name": comp["name"],
        "path": comp["path"],
        "component_type": comp.get("component_type", "module"),
        "language": comp.get("language"),
        "file_count": comp.get("file_count", 0),
        "line_count": comp.get("line_count", 0),
        "health_score": comp.get("health_score"),
        "analysis_summary": comp.get("analysis_summary"),
    }


def _format_finding(finding: Dict) -> Dict:
    """Format finding for API response."""
    return {
        "id": finding["id"],
        "scanner": finding["scanner"],
        "severity": finding["severity"],
        "category": finding.get("category"),
        "title": finding["title"],
        "description": finding.get("description"),
        "file_path": finding.get("file_path"),
        "line_start": finding.get("line_start"),
        "suggestion": finding.get("suggestion"),
        "llm_explanation": finding.get("llm_explanation"),
    }


# Run with: uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
