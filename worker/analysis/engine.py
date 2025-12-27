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
import structlog
from git import Repo, GitCommandError

from config import settings
from database import db
from llm.ollama_client import OllamaCloudClient, get_ollama_client
from .component_detector import ComponentDetector
from scanners import get_scanner_for_language, get_universal_scanners

logger = structlog.get_logger()


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
            api_key_override = (job.get("config") or {}).get("ollama_api_key")
            self.ollama = get_ollama_client(model=self.model, api_key=api_key_override)
            
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
        
        # Get universal scanners (gitleaks, semgrep, trivy)
        universal_scanners = get_universal_scanners()
        
        # Run universal scanners on whole repo
        scanner_count = len(universal_scanners)
        for i, scanner in enumerate(universal_scanners):
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
                self.status.log_step(f"{scanner_name}: {len(findings)} findings")
                
            except Exception as e:
                self.logger.warning(f"Scanner {scanner_name} failed: {e}")
                db.update_scanner_result(result_id, "failed", error_message=str(e))
        
        # Run language-specific scanners per component
        for comp_idx, comp in enumerate(components):
            language = comp.get("language", "unknown")
            scanners = get_scanner_for_language(language)
            
            if not scanners:
                continue
            
            comp_path = self.repo_path / comp["path"]
            
            for scanner in scanners:
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
        """Run LLM analysis on files and components (SEQUENTIAL - no parallel)."""
        total_files = sum(len(c.get("files", [])) for c in components)
        analyzed_files = 0
        
        for comp_idx, comp in enumerate(components):
            comp_name = comp["name"]
            files = comp.get("files", [])
            
            self.status.update(
                "analyzing",
                f"Analyzing component: {comp_name}",
                progress=50 + int((comp_idx / len(components)) * 35),
                detail=f"Component {comp_idx+1}/{len(components)}, {len(files)} files"
            )
            
            file_summaries = []
            
            # Analyze each file SEQUENTIALLY
            for file_idx, file_info in enumerate(files):
                file_path = file_info["path"]
                
                self.status.log_step(
                    f"Analyzing file: {file_path}",
                    detail=f"File {analyzed_files+1}/{total_files}"
                )
                
                # Read file content
                content = detector.get_file_content(file_path)
                if not content:
                    continue
                
                # Skip very small files
                if len(content.strip()) < 50:
                    continue
                
                try:
                    # LLM analysis (sequential, one at a time)
                    analysis = await self.ollama.analyze_code(
                        code=content,
                        file_path=file_path,
                        language=file_info.get("language", "unknown")
                    )
                    
                    file_summaries.append({
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
                
                analyzed_files += 1
            
            # Summarize component (after all files analyzed)
            if file_summaries:
                try:
                    self.status.log_step(f"Generating summary for {comp_name}")
                    
                    comp_summary = await self.ollama.summarize_component(
                        component_name=comp_name,
                        component_path=comp["path"],
                        file_summaries=file_summaries,
                        language=comp.get("language", "unknown")
                    )
                    
                    db.update_component(
                        comp.get("db_id"),
                        status="completed",
                        analysis_summary=comp_summary.get("summary", ""),
                        health_score=comp_summary.get("health_score", 50)
                    )
                    
                except Exception as e:
                    self.logger.warning(f"Component summary failed for {comp_name}: {e}")
                    db.update_component(comp.get("db_id"), status="completed")
    
    async def _generate_report(self, components: List[Dict]):
        """Generate the final analysis report."""
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
