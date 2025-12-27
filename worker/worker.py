"""
Bull's Eye - Celery Worker Configuration
"""

import asyncio
from celery import Celery
import structlog

from config import settings

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Create Celery app
celery_app = Celery(
    "bullseye",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.analysis_timeout,
    worker_prefetch_multiplier=1,
    worker_concurrency=settings.worker_concurrency,
)


@celery_app.task(bind=True, name="analyze_repository")
def analyze_repository(self, job_id: str):
    """Celery task to run repository analysis."""
    from database import DatabaseManager
    from analysis.engine import AnalysisEngine
    
    logger.info("Starting analysis task", job_id=job_id, task_id=self.request.id)
    
    # Get database manager
    db = DatabaseManager()
    
    try:
        # Create engine and run analysis
        engine = AnalysisEngine(db)
        
        # Run async analysis in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(engine.run_analysis(job_id))
        finally:
            loop.close()
        
        logger.info("Analysis task completed", job_id=job_id, success=result)
        return {"job_id": job_id, "success": result}
        
    except Exception as e:
        logger.error("Analysis task failed", job_id=job_id, error=str(e))
        raise
    finally:
        db.close()


@celery_app.task(name="health_check")
def health_check():
    """Simple health check task."""
    return {"status": "healthy"}
