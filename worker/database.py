"""
Bull's Eye - SQLite Database Manager
Lightweight database operations for analysis jobs
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import threading

from config import settings


class Database:
    """Thread-safe SQLite database manager."""
    
    _local = threading.local()
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.database_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database with schema."""
        schema_candidates = [
            Path(__file__).parent / "database" / "schema.sql",
            Path(__file__).parent.parent / "database" / "schema.sql",
        ]
        schema_path = next((path for path in schema_candidates if path.exists()), None)
        if schema_path:
            with self.get_connection() as conn:
                conn.executescript(schema_path.read_text())

        self._ensure_jobs_schema()
        
        # Migration: Add celery_task_id to jobs if it doesn't exist
        try:
            with self.get_connection() as conn:
                conn.execute("ALTER TABLE jobs ADD COLUMN celery_task_id TEXT")
                print("Added celery_task_id column to jobs table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                print(f"Migration error: {e}")

    def _ensure_jobs_schema(self):
        """Ensure jobs table supports the cancelled status and new columns."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'"
            ).fetchone()
            if not row or not row["sql"]:
                return

            create_sql = row["sql"]
            if "cancelled" in create_sql:
                return

            current_columns = [
                col["name"]
                for col in conn.execute("PRAGMA table_info(jobs)").fetchall()
            ]
            target_columns = [
                "id",
                "name",
                "repo_url",
                "branch",
                "commit_hash",
                "status",
                "status_message",
                "progress",
                "progress_total",
                "progress_detail",
                "model",
                "celery_task_id",
                "created_at",
                "started_at",
                "completed_at",
                "error_message",
                "config",
            ]
            common_columns = [col for col in target_columns if col in current_columns]

            conn.execute("DROP TABLE IF EXISTS jobs_new")
            conn.execute(
                """
                CREATE TABLE jobs_new (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    repo_url TEXT NOT NULL,
                    branch TEXT DEFAULT 'main',
                    commit_hash TEXT,
                    status TEXT DEFAULT 'pending' CHECK (
                        status IN (
                            'pending',
                            'cloning',
                            'detecting_components',
                            'scanning',
                            'analyzing',
                            'generating_report',
                            'completed',
                            'failed',
                            'cancelled'
                        )
                    ),
                    status_message TEXT,
                    progress INTEGER DEFAULT 0,
                    progress_total INTEGER DEFAULT 100,
                    progress_detail TEXT,
                    model TEXT NOT NULL,
                    celery_task_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    config TEXT
                )
                """
            )

            if common_columns:
                columns_csv = ", ".join(common_columns)
                conn.execute(
                    f"INSERT INTO jobs_new ({columns_csv}) SELECT {columns_csv} FROM jobs"
                )

            conn.execute("DROP TABLE jobs")
            conn.execute("ALTER TABLE jobs_new RENAME TO jobs")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC)")
            print("Migrated jobs table to include cancelled status")
    
    @contextmanager
    def get_connection(self):
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA foreign_keys=ON")
        
        try:
            yield self._local.connection
            self._local.connection.commit()
        except Exception:
            self._local.connection.rollback()
            raise
    
    def dict_from_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert sqlite Row to dictionary."""
        return dict(row) if row else None

    # ==================== JOB OPERATIONS ====================
    
    def create_job(
        self,
        repo_url: str,
        branch: str,
        model: str,
        name: Optional[str] = None,
        config: Optional[Dict] = None
    ) -> str:
        """Create a new analysis job."""
        job_id = str(uuid.uuid4())
        job_name = name or f"Analysis of {repo_url.split('/')[-1].replace('.git', '')}"
        
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO jobs (id, name, repo_url, branch, model, config, status, progress)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', 0)
            """, (job_id, job_name, repo_url, branch, model, json.dumps(config or {})))
        
        self.add_status_update(job_id, "created", f"Job created: {job_name}")
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row:
                job = self.dict_from_row(row)
                job['config'] = json.loads(job['config']) if job['config'] else {}
                return job
            return None
    
    def get_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """Get all jobs with optional filtering."""
        with self.get_connection() as conn:
            if status:
                rows = conn.execute("""
                    SELECT * FROM jobs WHERE status = ?
                    ORDER BY created_at DESC LIMIT ? OFFSET ?
                """, (status, limit, offset)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM jobs
                    ORDER BY created_at DESC LIMIT ? OFFSET ?
                """, (limit, offset)).fetchall()
            
            jobs = []
            for row in rows:
                job = self.dict_from_row(row)
                job['config'] = json.loads(job['config']) if job['config'] else {}
                jobs.append(job)
            return jobs
    
    def update_job_status(
        self,
        job_id: str,
        status: str,
        message: Optional[str] = None,
        progress: Optional[int] = None,
        progress_total: Optional[int] = None,
        progress_detail: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Update job status with detailed progress."""
        started_at = None
        completed_at = None
        if status == "cloning":
            started_at = datetime.utcnow().isoformat()
        elif status in ("completed", "failed"):
            completed_at = datetime.utcnow().isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET
                    status = ?,
                    status_message = ?,
                    progress = COALESCE(?, progress),
                    progress_total = COALESCE(?, progress_total),
                    progress_detail = COALESCE(?, progress_detail),
                    error_message = COALESCE(?, error_message),
                    started_at = COALESCE(?, started_at),
                    completed_at = COALESCE(?, completed_at)
                WHERE id = ?
                """,
                (
                    status,
                    message,
                    progress,
                    progress_total,
                    progress_detail,
                    error,
                    started_at,
                    completed_at,
                    job_id,
                ),
            )
        
        # Add status update entry
        self.add_status_update(job_id, status, message or status, progress, progress_detail)
    
    def set_job_commit(self, job_id: str, commit_hash: str):
        """Set the commit hash for a job."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET commit_hash = ? WHERE id = ?",
                (commit_hash, job_id)
            )

    def set_job_task_id(self, job_id: str, task_id: str):
        """Set the Celery task ID for a job."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET celery_task_id = ? WHERE id = ?",
                (task_id, job_id)
            )

    # ==================== STATUS UPDATES ====================
    
    def add_status_update(
        self,
        job_id: str,
        stage: str,
        message: str,
        progress: Optional[int] = None,
        details: Optional[str] = None
    ):
        """Add a detailed status update for progress tracking."""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO status_updates (job_id, stage, message, progress, details)
                VALUES (?, ?, ?, ?, ?)
            """, (job_id, stage, message, progress, details))
    
    def get_status_updates(self, job_id: str, limit: int = 100) -> List[Dict]:
        """Get status updates for a job."""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM status_updates 
                WHERE job_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (job_id, limit)).fetchall()
            return [self.dict_from_row(row) for row in rows]

    # ==================== COMPONENT OPERATIONS ====================
    
    def create_component(
        self,
        job_id: str,
        name: str,
        path: str,
        component_type: str,
        language: Optional[str] = None
    ) -> str:
        """Create a new component."""
        component_id = str(uuid.uuid4())
        
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO components (id, job_id, name, path, component_type, language)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (component_id, job_id, name, path, component_type, language))
        
        return component_id
    
    def get_components(self, job_id: str) -> List[Dict]:
        """Get all components for a job."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM components WHERE job_id = ? ORDER BY path",
                (job_id,)
            ).fetchall()
            return [self.dict_from_row(row) for row in rows]
    
    def update_component(
        self,
        component_id: str,
        status: Optional[str] = None,
        file_count: Optional[int] = None,
        line_count: Optional[int] = None,
        analysis_summary: Optional[str] = None,
        health_score: Optional[int] = None
    ):
        """Update component details."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE components
                SET
                    status = COALESCE(?, status),
                    file_count = COALESCE(?, file_count),
                    line_count = COALESCE(?, line_count),
                    analysis_summary = COALESCE(?, analysis_summary),
                    health_score = COALESCE(?, health_score)
                WHERE id = ?
                """,
                (status, file_count, line_count, analysis_summary, health_score, component_id),
            )

    # ==================== FILE OPERATIONS ====================
    
    def create_file(
        self,
        component_id: str,
        job_id: str,
        path: str,
        language: Optional[str] = None,
        line_count: int = 0,
        size_bytes: int = 0
    ) -> str:
        """Create a new file record."""
        file_id = str(uuid.uuid4())
        
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO files (id, component_id, job_id, path, language, line_count, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (file_id, component_id, job_id, path, language, line_count, size_bytes))
        
        return file_id
    
    def get_files(self, component_id: str) -> List[Dict]:
        """Get all files for a component."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM files WHERE component_id = ? ORDER BY path",
                (component_id,)
            ).fetchall()
            return [self.dict_from_row(row) for row in rows]
    
    def update_file(
        self,
        file_id: str,
        status: Optional[str] = None,
        analysis_summary: Optional[str] = None
    ):
        """Update file analysis status."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE files
                SET
                    status = COALESCE(?, status),
                    analysis_summary = COALESCE(?, analysis_summary)
                WHERE id = ?
                """,
                (status, analysis_summary, file_id),
            )

    # ==================== FINDING OPERATIONS ====================
    
    def create_finding(
        self,
        job_id: str,
        scanner: str,
        severity: str,
        title: str,
        description: Optional[str] = None,
        component_id: Optional[str] = None,
        file_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        category: Optional[str] = None,
        file_path: Optional[str] = None,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        code_snippet: Optional[str] = None,
        suggestion: Optional[str] = None,
        llm_explanation: Optional[str] = None,
        fingerprint: Optional[str] = None
    ) -> Optional[str]:
        """Create a new finding (with deduplication)."""
        finding_id = str(uuid.uuid4())
        
        # Generate fingerprint for deduplication if not provided
        if not fingerprint:
            fingerprint = f"{scanner}:{rule_id or title}:{file_path}:{line_start}"
        
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO findings (
                        id, job_id, component_id, file_id, scanner, rule_id,
                        severity, category, title, description, file_path,
                        line_start, line_end, code_snippet, suggestion,
                        llm_explanation, fingerprint
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    finding_id, job_id, component_id, file_id, scanner, rule_id,
                    severity, category, title, description, file_path,
                    line_start, line_end, code_snippet, suggestion,
                    llm_explanation, fingerprint
                ))
            return finding_id
        except sqlite3.IntegrityError:
            # Duplicate fingerprint - skip
            return None
    
    def get_findings(
        self,
        job_id: str,
        severity: Optional[str] = None,
        scanner: Optional[str] = None,
        component_id: Optional[str] = None
    ) -> List[Dict]:
        """Get findings with optional filtering."""
        query = "SELECT * FROM findings WHERE job_id = ?"
        params = [job_id]
        
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if scanner:
            query += " AND scanner = ?"
            params.append(scanner)
        if component_id:
            query += " AND component_id = ?"
            params.append(component_id)
        
        query += " ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5 END, created_at"
        
        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self.dict_from_row(row) for row in rows]
    
    def get_findings_summary(self, job_id: str) -> Dict[str, int]:
        """Get findings count by severity."""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT severity, COUNT(*) as count
                FROM findings WHERE job_id = ?
                GROUP BY severity
            """, (job_id,)).fetchall()
            
            summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "total": 0}
            for row in rows:
                summary[row["severity"]] = row["count"]
                summary["total"] += row["count"]
            return summary

    # ==================== SCANNER RESULTS ====================
    
    def create_scanner_result(
        self,
        job_id: str,
        scanner: str,
        component_id: Optional[str] = None
    ) -> str:
        """Create a scanner result record."""
        result_id = str(uuid.uuid4())
        
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO scanner_results (id, job_id, component_id, scanner, status, started_at)
                VALUES (?, ?, ?, ?, 'running', ?)
            """, (result_id, job_id, component_id, scanner, datetime.utcnow().isoformat()))
        
        return result_id
    
    def update_scanner_result(
        self,
        result_id: str,
        status: str,
        findings_count: int = 0,
        raw_output: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """Update scanner result."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE scanner_results
                SET status = ?, completed_at = ?, findings_count = ?, raw_output = ?, error_message = ?
                WHERE id = ?
            """, (status, datetime.utcnow().isoformat(), findings_count, raw_output, error_message, result_id))

    # ==================== REPORTS ====================
    
    def create_report(
        self,
        job_id: str,
        content: str,
        report_type: str = "full",
        format: str = "json"
    ) -> str:
        """Create a report."""
        report_id = str(uuid.uuid4())
        
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO reports (id, job_id, report_type, format, content)
                VALUES (?, ?, ?, ?, ?)
            """, (report_id, job_id, report_type, format, content))
        
        return report_id
    
    def get_report(self, job_id: str, report_type: str = "full") -> Optional[Dict]:
        """Get report for a job."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM reports WHERE job_id = ? AND report_type = ?",
                (job_id, report_type)
            ).fetchone()
            return self.dict_from_row(row)

    # ==================== STATS ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        with self.get_connection() as conn:
            stats = {}
            
            # Job counts
            row = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    COALESCE(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END), 0) as completed,
                    COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) as failed,
                    COALESCE(SUM(CASE WHEN status IN ('pending', 'cloning', 'scanning', 'analyzing') THEN 1 ELSE 0 END), 0) as running
                FROM jobs
            """).fetchone()
            stats['jobs'] = dict(row)
            
            # Findings counts
            row = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    COALESCE(SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END), 0) as critical,
                    COALESCE(SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END), 0) as high,
                    COALESCE(SUM(CASE WHEN severity = 'medium' THEN 1 ELSE 0 END), 0) as medium,
                    COALESCE(SUM(CASE WHEN severity = 'low' THEN 1 ELSE 0 END), 0) as low
                FROM findings
            """).fetchone()
            stats['findings'] = dict(row)
            
            return stats
    
    def delete_job(self, job_id: str):
        """Delete a job and all related data."""
        with self.get_connection() as conn:
            # Delete all related data in order due to foreign keys
            conn.execute("DELETE FROM status_updates WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM reports WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM scanner_results WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM findings WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM files WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM components WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))


# Global database instance
db = Database()
