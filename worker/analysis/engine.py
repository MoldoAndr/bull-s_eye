"""
Bull's Eye - Analysis Engine
Core orchestration for codebase analysis with detailed status tracking
"""

import asyncio
import shutil
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import structlog
from git import Repo, GitCommandError

from config import settings
from database import db
from llm.ollama_client import OllamaCloudClient, get_ollama_client
from .component_detector import ComponentDetector
from .context_aware_analysis import ContextAwareAnalyzer
from scanners import get_scanner_for_language, get_universal_scanners

logger = structlog.get_logger()

class AnalysisCancelled(Exception):
    """Raised when a job is cancelled by the user."""


class StatusTracker:
    """Tracks and reports detailed analysis status."""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.current_stage = ""
        self.current_step = ""
        self.progress = 0
        self.total_steps = 0
        self.completed_steps = 0
    
    def update(
        self,
        stage: str,
        message: str,
        progress: int,
        progress_total: int = 100,
        detail: Optional[str] = None
    ):
        """Update job status in database."""
        self.current_stage = stage
        self.progress = progress
        
        db.update_job_status(
            job_id=self.job_id,
            status=stage,
            message=message,
            progress=progress,
            progress_total=progress_total,
            progress_detail=detail
        )
        
        logger.info(
            "Status update",
            job_id=self.job_id[:8],
            stage=stage,
            message=message,
            progress=f"{progress}/{progress_total}"
        )
    
    def log_step(self, message: str, detail: Optional[str] = None):
        """Log a step without changing main progress."""
        db.add_status_update(
            job_id=self.job_id,
            stage=self.current_stage,
            message=message,
            progress=self.progress,
            details=detail
        )


class AnalysisEngine:
    """Main analysis engine that orchestrates the entire analysis pipeline."""
    
    def __init__(self, job_id: str, model: Optional[str] = None):
        self.job_id = job_id
        self.model = model
        self.logger = structlog.get_logger().bind(job_id=job_id[:8])
        self.status = StatusTracker(job_id)
        self.ollama: Optional[OllamaCloudClient] = None
        self.ollama_clients: List[OllamaCloudClient] = []
        self.repo_path: Optional[Path] = None
    
    async def run(self) -> bool:
        """Run the full analysis pipeline."""
        try:
            # Get job info
            job = db.get_job(self.job_id)
            if not job:
                self.logger.error("Job not found")
                return False

            # Initialize LLM client
            self._init_llm_clients(job)
            self._ensure_not_cancelled()
            
            self.logger.info("Starting analysis", repo=job["repo_url"], model=self.model)
            
            # ========== STAGE 1: CLONE REPOSITORY ==========
            self.status.update(
                "cloning",
                f"Cloning repository from {job['repo_url']}",
                progress=0,
                progress_total=100,
                detail="Initializing git clone..."
            )
            
            self.repo_path = await self._clone_repository(
                job["repo_url"],
                job["branch"]
            )
            
            if not self.repo_path:
                raise Exception("Failed to clone repository")

            self._ensure_not_cancelled()
            
            self.status.update(
                "cloning",
                "Repository cloned successfully",
                progress=5,
                detail=f"Cloned to {self.repo_path}"
            )
            
            # ========== STAGE 2: DETECT COMPONENTS ==========
            self.status.update(
                "detecting_components",
                "Analyzing repository structure...",
                progress=8,
                detail="Scanning directories and files"
            )
            
            detector = ComponentDetector(self.repo_path)
            components = detector.detect_components()

            self._ensure_not_cancelled()
            
            self.status.update(
                "detecting_components",
                f"Detected {len(components)} components",
                progress=10,
                detail=", ".join([c["name"] for c in components[:5]])
            )
            
            # Save components to database
            component_ids = []
            total_files = 0
            for comp in components:
                comp_id = db.create_component(
                    job_id=self.job_id,
                    name=comp["name"],
                    path=comp["path"],
                    component_type=comp["component_type"],
                    language=comp["language"]
                )
                component_ids.append(comp_id)
                comp["db_id"] = comp_id
                
                # Save files
                for file_info in comp.get("files", []):
                    db.create_file(
                        component_id=comp_id,
                        job_id=self.job_id,
                        path=file_info["path"],
                        language=file_info.get("language"),
                        line_count=file_info.get("line_count", 0),
                        size_bytes=file_info.get("size_bytes", 0)
                    )
                    total_files += 1
                
                db.update_component(
                    comp_id,
                    file_count=len(comp.get("files", [])),
                    line_count=comp.get("line_count", 0)
                )
            
            self.status.log_step(
                f"Saved {len(components)} components with {total_files} files"
            )
            
            # ========== STAGE 3: RUN SCANNERS ==========
            self.status.update(
                "scanning",
                "Running security scanners...",
                progress=15,
                detail="Initializing scanners"
            )
            
            all_findings = await self._run_all_scanners(components, detector)

            self._ensure_not_cancelled()
            
            self.status.update(
                "scanning",
                f"Scanners complete: {len(all_findings)} findings",
                progress=45,
                detail=f"Found {len(all_findings)} potential issues"
            )
            
            # ========== STAGE 4: LLM ANALYSIS ==========
            self.status.update(
                "analyzing",
                "Starting AI-powered code analysis...",
                progress=50,
                detail=f"Using model: {self.model or settings.ollama_model}"
            )
            
            await self._run_llm_analysis(components, detector, all_findings)

            self._ensure_not_cancelled()
            
            # ========== STAGE 5: GENERATE REPORT ==========
            self.status.update(
                "generating_report",
                "Generating analysis report...",
                progress=90,
                detail="Compiling findings and recommendations"
            )
            
            await self._generate_report(components)

            # ========== COMPLETE ==========
            findings_summary = db.get_findings_summary(self.job_id)
            
            self.status.update(
                "completed",
                "Analysis completed successfully",
                progress=100,
                detail=f"Critical: {findings_summary['critical']}, High: {findings_summary['high']}, Medium: {findings_summary['medium']}, Low: {findings_summary['low']}"
            )
            
            self.logger.info(
                "Analysis completed",
                total_findings=findings_summary["total"],
                critical=findings_summary["critical"],
                high=findings_summary["high"]
            )
            
            return True
            
        except AnalysisCancelled:
            self.logger.info("Analysis cancelled by user")
            try:
                db.update_job_status(
                    self.job_id,
                    status="cancelled",
                    message="Job stopped by user",
                    progress=self.status.progress,
                    error="Job was cancelled by user"
                )
            except Exception as e:
                self.logger.warning("Failed to update cancelled status", error=str(e))
            return False
        except Exception as e:
            self.logger.exception("Analysis failed", error=str(e))
            self.status.update(
                "failed",
                f"Analysis failed: {str(e)}",
                progress=self.status.progress,
                detail=str(e)
            )
            db.update_job_status(
                self.job_id,
                status="failed",
                error=str(e)
            )
            return False
        
        finally:
            # Cleanup
            if self.repo_path and self.repo_path.exists():
                try:
                    shutil.rmtree(self.repo_path)
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup repo: {e}")

    def _normalize_api_keys(self, job: Dict[str, Any]) -> List[str]:
        """Normalize API keys from job config or settings."""
        config = job.get("config") or {}
        keys: List[str] = []

        raw_keys = config.get("ollama_api_keys")
        if isinstance(raw_keys, str):
            keys.extend(item.strip() for item in raw_keys.replace("\n", ",").split(","))
        elif isinstance(raw_keys, list):
            for item in raw_keys:
                if item is None:
                    continue
                keys.append(str(item))

        single_key = config.get("ollama_api_key")
        if single_key:
            keys.append(single_key)

        normalized = []
        seen = set()
        for key in keys:
            trimmed = str(key).strip()
            if trimmed and trimmed not in seen:
                normalized.append(trimmed)
                seen.add(trimmed)

        if normalized:
            return normalized

        fallback = (settings.ollama_api_key or "").strip()
        return [fallback] if fallback else []

    def _init_llm_clients(self, job: Dict[str, Any]) -> None:
        """Initialize LLM clients for parallel analysis."""
        api_keys = self._normalize_api_keys(job)
        if api_keys:
            self.ollama_clients = [
                get_ollama_client(model=self.model, api_key=key)
                for key in api_keys
            ]
        else:
            self.ollama_clients = [get_ollama_client(model=self.model)]

        self.ollama = self.ollama_clients[0]
        self.logger.info("Initialized LLM clients", workers=len(self.ollama_clients))

    def _is_cancelled(self) -> bool:
        """Check whether the job has been cancelled."""
        job = db.get_job(self.job_id)
        return bool(job and job.get("status") == "cancelled")

    def _ensure_not_cancelled(self) -> None:
        """Raise if the job has been cancelled."""
        if self._is_cancelled():
            raise AnalysisCancelled()

    async def _filter_security_irrelevant_files(self, file_paths: List[str]) -> List[str]:
        """Use LLM to skip files unlikely to contain security-relevant logic."""
        if not file_paths or not self.ollama:
            return []

        chunk_size = 200
        skipped = set()

        self.status.log_step(
            "LLM file triage: selecting low-signal files by name",
            detail=f"{len(file_paths)} candidates"
        )

        for start in range(0, len(file_paths), chunk_size):
            chunk = file_paths[start:start + chunk_size]
            try:
                skip_list = await self.ollama.filter_security_irrelevant_files(chunk)
            except Exception as e:
                self.logger.warning("File triage chunk failed", error=str(e))
                continue

            allowed = set(chunk)
            for path in skip_list:
                if path in allowed:
                    skipped.add(path)

        return list(skipped)
    
    async def _clone_repository(self, repo_url: str, branch: str) -> Optional[Path]:
        """Clone the repository."""
        repo_dir = settings.repos_dir / f"repo_{self.job_id[:8]}"
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self.status.log_step(f"Cloning {repo_url} (branch: {branch})")
            
            # Clone with depth limit for speed
            repo = Repo.clone_from(
                repo_url,
                str(repo_dir),
                branch=branch,
                depth=1,
                single_branch=True
            )
            
            # Store commit hash
            commit_hash = repo.head.commit.hexsha
            db.set_job_commit(self.job_id, commit_hash)
            
            self.status.log_step(f"Cloned at commit {commit_hash[:8]}")
            
            return repo_dir
            
        except GitCommandError as e:
            self.logger.error("Git clone failed", error=str(e))
            return None
        except Exception as e:
            self.logger.error("Clone failed", error=str(e))
            return None
    
    async def _run_all_scanners(
        self,
        components: List[Dict],
        detector: ComponentDetector
    ) -> List[Dict]:
        """Run all applicable scanners on the repository."""
        all_findings = []
        self._ensure_not_cancelled()
        
        # Get universal scanners (gitleaks, opengrep, osv-scanner, lizard, trivy)
        universal_scanners = get_universal_scanners(self.repo_path)
        
        # Run universal scanners on whole repo
        scanner_count = len(universal_scanners)
        for i, scanner in enumerate(universal_scanners):
            self._ensure_not_cancelled()
            scanner_name = scanner.get_tool_name()
            progress = 15 + int((i / scanner_count) * 15)
            
            self.status.update(
                "scanning",
                f"Running {scanner_name}...",
                progress=progress,
                detail=f"Scanner {i+1}/{scanner_count}"
            )
            
            result_id = db.create_scanner_result(self.job_id, scanner_name)
            
            try:
                findings = await scanner.scan(str(self.repo_path), self.job_id)
                
                for finding in findings:
                    db.create_finding(
                        job_id=self.job_id,
                        scanner=scanner_name,
                        severity=finding.get("severity", "info"),
                        title=finding.get("title", "Untitled"),
                        description=finding.get("description"),
                        rule_id=finding.get("rule_id"),
                        category=finding.get("category"),
                        file_path=finding.get("file_path"),
                        line_start=finding.get("line_start"),
                        line_end=finding.get("line_end"),
                        code_snippet=finding.get("code_snippet"),
                        suggestion=finding.get("suggestion"),
                    )
                    all_findings.append(finding)
                
                db.update_scanner_result(result_id, "completed", len(findings))
                self.status.log_step( f"{scanner_name}: {len(findings)} findings")
                
            except Exception as e:
                self.logger.warning(f"Scanner {scanner_name} failed: {e}")
                db.update_scanner_result(result_id, "failed", error_message=str(e))
        
        # Run language-specific scanners per component
        for comp_idx, comp in enumerate(components):
            self._ensure_not_cancelled()
            language = comp.get("language", "unknown")
            scanners = get_scanner_for_language(language, self.repo_path)
            
            if not scanners:
                continue
            
            comp_path = self.repo_path / comp["path"]
            
            for scanner in scanners:
                self._ensure_not_cancelled()
                scanner_name = scanner.get_tool_name()
                progress = 30 + int((comp_idx / len(components)) * 15)
                
                self.status.update(
                    "scanning",
                    f"Running {scanner_name} on {comp['name']}",
                    progress=progress,
                    detail=f"Component {comp_idx+1}/{len(components)}"
                )
                
                result_id = db.create_scanner_result(
                    self.job_id,
                    scanner_name,
                    component_id=comp.get("db_id")
                )
                
                try:
                    findings = await scanner.scan(
                        str(comp_path),
                        self.job_id,
                        component_id=comp.get("db_id")
                    )
                    
                    for finding in findings:
                        db.create_finding(
                            job_id=self.job_id,
                            component_id=comp.get("db_id"),
                            scanner=scanner_name,
                            severity=finding.get("severity", "info"),
                            title=finding.get("title", "Untitled"),
                            description=finding.get("description"),
                            rule_id=finding.get("rule_id"),
                            category=finding.get("category"),
                            file_path=finding.get("file_path"),
                            line_start=finding.get("line_start"),
                            line_end=finding.get("line_end"),
                            code_snippet=finding.get("code_snippet"),
                            suggestion=finding.get("suggestion"),
                        )
                        all_findings.append(finding)
                    
                    db.update_scanner_result(result_id, "completed", len(findings))
                    
                except Exception as e:
                    self.logger.warning(f"Scanner {scanner_name} failed on {comp['name']}: {e}")
                    db.update_scanner_result(result_id, "failed", error_message=str(e))
        
        return all_findings
    
    async def _run_llm_analysis(
        self,
        components: List[Dict],
        detector: ComponentDetector,
        scanner_findings: List[Dict]
    ):
        """Run LLM analysis on code files with parallel workers per API key."""
        self._ensure_not_cancelled()
        file_jobs = []
        total_files = sum(len(c.get("files", [])) for c in components)

        for comp in components:
            files = comp.get("files", [])
            code_files = [f for f in files if detector.should_analyze_with_llm(f["path"])]
            for file_info in code_files:
                file_jobs.append({
                    "component": comp,
                    "file_info": file_info,
                })

        total_code_files = len(file_jobs)
        skipped_files = total_files - total_code_files

        self.status.log_step(
            f"LLM Analysis: Found {total_code_files} code files to analyze (skipping {skipped_files} docs/configs)"
        )

        if total_code_files == 0:
            return

        candidate_paths = [job["file_info"]["path"] for job in file_jobs]
        llm_skipped = await self._filter_security_irrelevant_files(candidate_paths)
        skip_set = set(llm_skipped)
        if skip_set:
            keep_jobs = [job for job in file_jobs if job["file_info"]["path"] not in skip_set]
            skip_jobs = [job for job in file_jobs if job["file_info"]["path"] in skip_set]
            file_jobs = keep_jobs + skip_jobs
            self.status.log_step(
                f"LLM file triage flagged {len(skip_set)} low-signal files based on names"
            )

        total_llm_files = len(file_jobs)
        if total_llm_files == 0:
            self.status.log_step("LLM Analysis: No files left after triage")
            return

        worker_count = max(1, min(len(self.ollama_clients), total_llm_files))
        detail_parts = [f"Skipping {skipped_files} non-code files"]
        if llm_skipped:
            detail_parts.append(f"{len(llm_skipped)} name-filtered")

        self.status.update(
            "analyzing",
            f"Analyzing {total_llm_files} code files with {worker_count} parallel LLM workers",
            progress=50,
            detail=", ".join(detail_parts)
        )

        queue: asyncio.Queue = asyncio.Queue()
        for job in file_jobs:
            queue.put_nowait(job)
        for _ in range(worker_count):
            queue.put_nowait(None)

        file_summaries_by_component: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        processed_files = 0
        last_progress = 50
        progress_lock = asyncio.Lock()

        async def worker(client: OllamaCloudClient, worker_id: int):
            nonlocal processed_files, last_progress

            while True:
                job = await queue.get()
                if job is None:
                    queue.task_done()
                    break
                if self._is_cancelled():
                    queue.task_done()
                    while True:
                        try:
                            queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                        queue.task_done()
                    break

                comp = job["component"]
                file_info = job["file_info"]
                file_path = file_info["path"]

                self.status.log_step(
                    f"Analyzing code file: {file_path}",
                    detail=f"Worker {worker_id + 1}/{worker_count}"
                )

                try:
                    content = detector.get_file_content(file_path)
                    if content and len(content.strip()) >= 50:
                        analysis = await client.analyze_code(
                            code=content,
                            file_path=file_path,
                            language=file_info.get("language", "unknown")
                        )

                        comp_id = comp.get("db_id")
                        if comp_id:
                            file_summaries_by_component[comp_id].append({
                                "path": file_path,
                                "summary": analysis.get("summary", ""),
                                "complexity": analysis.get("complexity", "unknown"),
                            })

                        # Create findings from LLM analysis
                        for issue in analysis.get("security_issues", []):
                            db.create_finding(
                                job_id=self.job_id,
                                component_id=comp.get("db_id"),
                                scanner="llm",
                                severity=issue.get("severity", "medium"),
                                title=issue.get("title", "Security Issue"),
                                description=issue.get("description"),
                                category="security",
                                file_path=file_path,
                                suggestion=issue.get("recommendation"),
                            )

                        for issue in analysis.get("quality_issues", []):
                            db.create_finding(
                                job_id=self.job_id,
                                component_id=comp.get("db_id"),
                                scanner="llm",
                                severity=issue.get("severity", "low"),
                                title=issue.get("title", "Quality Issue"),
                                description=issue.get("description"),
                                category="quality",
                                file_path=file_path,
                                suggestion=issue.get("recommendation"),
                            )

                except Exception as e:
                    self.logger.warning(f"LLM analysis failed for {file_path}: {e}")

                finally:
                    async with progress_lock:
                        processed_files += 1
                        progress = 50 + int((processed_files / total_llm_files) * 35)
                        if progress > last_progress:
                            last_progress = progress
                            self.status.update(
                                "analyzing",
                                "Analyzing code files...",
                                progress=progress,
                                detail=f"{processed_files}/{total_llm_files} files analyzed"
                            )
                    queue.task_done()

        workers = []
        for idx in range(worker_count):
            client = self.ollama_clients[idx % len(self.ollama_clients)]
            workers.append(asyncio.create_task(worker(client, idx)))

        await queue.join()
        for worker_task in workers:
            await worker_task

        self.status.log_step(
            f"LLM Analysis complete: {processed_files}/{total_llm_files} files analyzed"
        )

        # Summarize components (after all files analyzed)
        for comp in components:
            self._ensure_not_cancelled()
            comp_id = comp.get("db_id")
            file_summaries = file_summaries_by_component.get(comp_id, [])
            if not file_summaries:
                continue

            try:
                self.status.log_step(f"Generating summary for {comp['name']}")

                comp_summary = await self.ollama.summarize_component(
                    component_name=comp["name"],
                    component_path=comp["path"],
                    file_summaries=file_summaries,
                    language=comp.get("language", "unknown")
                )

                if comp_id:
                    db.update_component(
                        comp_id,
                        status="completed",
                        analysis_summary=comp_summary.get("summary", ""),
                        health_score=comp_summary.get("health_score", 50)
                    )

            except Exception as e:
                self.logger.warning(f"Component summary failed for {comp['name']}: {e}")
                if comp_id:
                    db.update_component(comp_id, status="completed")
    
    async def _generate_report(self, components: List[Dict]):
        """Generate the final analysis report."""
        self._ensure_not_cancelled()
        # Get all data
        job = db.get_job(self.job_id)
        findings = db.get_findings(self.job_id)
        findings_summary = db.get_findings_summary(self.job_id)
        db_components = db.get_components(self.job_id)
        
        # Generate executive summary with LLM
        self.status.log_step("Generating executive summary...")
        
        try:
            executive_summary = await self.ollama.generate_executive_summary(
                job_name=job["name"],
                repo_url=job["repo_url"],
                findings_summary=findings_summary,
                component_summaries=[
                    {"name": c["name"], "summary": c.get("analysis_summary", "")}
                    for c in db_components
                ]
            )
        except Exception as e:
            self.logger.warning(f"Executive summary generation failed: {e}")
            executive_summary = "Executive summary generation failed."
        
        # Build full report
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "job": {
                "id": self.job_id,
                "name": job["name"],
                "repo_url": job["repo_url"],
                "branch": job["branch"],
                "commit": job.get("commit_hash"),
                "model": job["model"],
            },
            "executive_summary": executive_summary,
            "summary": findings_summary,
            "components": [
                {
                    "name": c["name"],
                    "path": c["path"],
                    "type": c["component_type"],
                    "language": c["language"],
                    "health_score": c.get("health_score"),
                    "summary": c.get("analysis_summary"),
                    "files": c["file_count"],
                    "lines": c["line_count"],
                }
                for c in db_components
            ],
            "findings": [
                {
                    "id": f["id"],
                    "severity": f["severity"],
                    "title": f["title"],
                    "description": f["description"],
                    "scanner": f["scanner"],
                    "file": f["file_path"],
                    "line": f["line_start"],
                    "suggestion": f["suggestion"],
                }
                for f in findings
            ],
        }
        
        # Save report
        db.create_report(
            job_id=self.job_id,
            content=json.dumps(report, indent=2),
            report_type="full",
            format="json"
        )
        
        self.status.log_step(f"Report generated with {len(findings)} findings")


async def run_analysis(job_id: str, model: Optional[str] = None) -> bool:
    """Entry point for running an analysis job."""
    engine = AnalysisEngine(job_id, model)
    return await engine.run()
