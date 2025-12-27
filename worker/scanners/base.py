"""
Bull's Eye - Scanner Base
Abstract base class for all code scanners
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
from enum import Enum
import subprocess
import json
import time
import structlog

logger = structlog.get_logger()


class ScannerType(str, Enum):
    SECURITY = "security"
    LINT = "lint"
    DEPS = "deps"
    SECRETS = "secrets"
    TYPE_CHECK = "type_check"


@dataclass
class ScannerFinding:
    """Standardized finding from any scanner."""
    title: str
    description: str
    severity: str  # info, low, medium, high, critical
    category: str  # security, reliability, performance, maintainability, best_practice
    confidence: float  # 0.0 to 1.0
    
    # Location
    file_path: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    column_start: Optional[int] = None
    column_end: Optional[int] = None
    code_snippet: Optional[str] = None
    
    # Source info
    source: str = ""
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    
    # References
    references: List[str] = field(default_factory=list)
    
    # Raw tool output
    raw_output: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "category": self.category,
            "confidence": self.confidence,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "column_start": self.column_start,
            "column_end": self.column_end,
            "code_snippet": self.code_snippet,
            "source": self.source,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "references": self.references,
        }


@dataclass
class ScannerResult:
    """Result from running a scanner."""
    scanner_name: str
    scanner_version: Optional[str]
    success: bool
    findings: List[ScannerFinding]
    
    # Execution info
    command: str
    exit_code: int
    duration_ms: int
    
    # Raw output
    stdout: str
    stderr: str
    
    # Stats
    errors_count: int = 0
    warnings_count: int = 0


class BaseScanner(ABC):
    """Abstract base class for all scanners."""
    
    name: str = "base"
    scanner_type: ScannerType = ScannerType.LINT
    supported_languages: List[str] = []
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.logger = structlog.get_logger().bind(scanner=self.name)
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the scanner is installed and available."""
        pass
    
    @abstractmethod
    def get_version(self) -> Optional[str]:
        """Get the scanner version."""
        pass
    
    @abstractmethod
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        """Build the command to run the scanner."""
        pass
    
    @abstractmethod
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        """Parse scanner output into standardized findings."""
        pass
    
    def run(self, target_path: Optional[Path] = None) -> ScannerResult:
        """Run the scanner and return results."""
        if not self.is_available():
            self.logger.warning("Scanner not available", scanner=self.name)
            return ScannerResult(
                scanner_name=self.name,
                scanner_version=None,
                success=False,
                findings=[],
                command="",
                exit_code=-1,
                duration_ms=0,
                stdout="",
                stderr=f"Scanner {self.name} is not available",
                errors_count=1,
            )
        
        command = self.build_command(target_path)
        command_str = " ".join(command)
        
        self.logger.info("Running scanner", command=command_str)
        
        start_time = time.time()
        try:
            result = subprocess.run(
                command,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )
            exit_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.TimeoutExpired:
            self.logger.error("Scanner timeout", scanner=self.name)
            return ScannerResult(
                scanner_name=self.name,
                scanner_version=self.get_version(),
                success=False,
                findings=[],
                command=command_str,
                exit_code=-1,
                duration_ms=600000,
                stdout="",
                stderr="Scanner timed out after 10 minutes",
                errors_count=1,
            )
        except Exception as e:
            self.logger.error("Scanner error", scanner=self.name, error=str(e))
            return ScannerResult(
                scanner_name=self.name,
                scanner_version=self.get_version(),
                success=False,
                findings=[],
                command=command_str,
                exit_code=-1,
                duration_ms=0,
                stdout="",
                stderr=str(e),
                errors_count=1,
            )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        findings = self.parse_output(stdout, stderr, exit_code)
        
        self.logger.info(
            "Scanner completed",
            scanner=self.name,
            findings_count=len(findings),
            duration_ms=duration_ms,
            exit_code=exit_code,
        )
        
        return ScannerResult(
            scanner_name=self.name,
            scanner_version=self.get_version(),
            success=exit_code in [0, 1],  # Many linters exit 1 when findings exist
            findings=findings,
            command=command_str,
            exit_code=exit_code,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
        )
    
    def _run_command(self, command: List[str]) -> tuple[str, str, int]:
        """Helper to run a command and get output."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout, result.stderr, result.returncode
        except Exception:
            return "", "", -1
