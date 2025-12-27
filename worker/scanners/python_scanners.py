"""
Bull's Eye - Python Scanners
Ruff, Bandit, pip-audit, mypy
"""

import json
from pathlib import Path
from typing import List, Optional

from .base import BaseScanner, ScannerFinding, ScannerType


class RuffScanner(BaseScanner):
    """Fast Python linter using ruff."""
    
    name = "ruff"
    scanner_type = ScannerType.LINT
    supported_languages = ["python"]
    
    def is_available(self) -> bool:
        _, _, code = self._run_command(["ruff", "--version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["ruff", "--version"])
        if code == 0:
            return stdout.strip()
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        target = str(target_path) if target_path else "."
        return [
            "ruff", "check",
            "--output-format", "json",
            "--ignore", "E501",  # Ignore line length
            target,
        ]
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []
        
        if not stdout.strip():
            return findings
        
        try:
            data = json.loads(stdout)
            
            for item in data:
                severity = self._map_severity(item.get("code", ""))
                category = self._map_category(item.get("code", ""))
                
                finding = ScannerFinding(
                    title=f"{item.get('code', 'UNKNOWN')}: {item.get('message', 'Unknown issue')}",
                    description=item.get("message", ""),
                    severity=severity,
                    category=category,
                    confidence=0.95,
                    file_path=item.get("filename", ""),
                    line_start=item.get("location", {}).get("row"),
                    line_end=item.get("end_location", {}).get("row"),
                    column_start=item.get("location", {}).get("column"),
                    column_end=item.get("end_location", {}).get("column"),
                    source=self.name,
                    rule_id=item.get("code"),
                    rule_name=item.get("code"),
                    references=[f"https://docs.astral.sh/ruff/rules/{item.get('code', '')}"],
                    raw_output=item,
                )
                findings.append(finding)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse ruff output", error=str(e))
        
        return findings
    
    def _map_severity(self, code: str) -> str:
        """Map ruff code to severity."""
        if code.startswith(("S", "B")):  # Security, bugbear
            return "high"
        elif code.startswith(("E", "W")):  # Errors, warnings
            return "medium"
        return "low"
    
    def _map_category(self, code: str) -> str:
        """Map ruff code to category."""
        if code.startswith("S"):
            return "security"
        elif code.startswith(("E", "F")):
            return "reliability"
        elif code.startswith("PERF"):
            return "performance"
        return "maintainability"


class BanditScanner(BaseScanner):
    """Python security linter using bandit."""
    
    name = "bandit"
    scanner_type = ScannerType.SECURITY
    supported_languages = ["python"]
    
    def is_available(self) -> bool:
        _, _, code = self._run_command(["bandit", "--version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["bandit", "--version"])
        if code == 0:
            return stdout.strip().split("\n")[0]
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        target = str(target_path) if target_path else "."
        return [
            "bandit",
            "-r",  # Recursive
            "-f", "json",
            "-x", ".venv,venv,node_modules,vendor",
            target,
        ]
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []
        
        if not stdout.strip():
            return findings
        
        try:
            data = json.loads(stdout)
            results = data.get("results", [])
            
            for item in results:
                severity = item.get("issue_severity", "LOW").lower()
                confidence = {"HIGH": 0.9, "MEDIUM": 0.7, "LOW": 0.5}.get(
                    item.get("issue_confidence", "MEDIUM"), 0.5
                )
                
                finding = ScannerFinding(
                    title=f"{item.get('test_id', 'B000')}: {item.get('issue_text', 'Unknown issue')}",
                    description=item.get("issue_text", ""),
                    severity=severity,
                    category="security",
                    confidence=confidence,
                    file_path=item.get("filename", ""),
                    line_start=item.get("line_number"),
                    line_end=item.get("line_number"),
                    code_snippet=item.get("code", ""),
                    source=self.name,
                    rule_id=item.get("test_id"),
                    rule_name=item.get("test_name"),
                    references=[f"https://bandit.readthedocs.io/en/latest/plugins/{item.get('test_id', '').lower()}.html"],
                    raw_output=item,
                )
                findings.append(finding)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse bandit output", error=str(e))
        
        return findings


class PipAuditScanner(BaseScanner):
    """Python dependency vulnerability scanner using pip-audit."""
    
    name = "pip-audit"
    scanner_type = ScannerType.DEPS
    supported_languages = ["python"]
    
    def is_available(self) -> bool:
        _, _, code = self._run_command(["pip-audit", "--version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["pip-audit", "--version"])
        if code == 0:
            return stdout.strip()
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        target = str(target_path) if target_path else str(self.repo_path)
        
        # Check for requirements.txt
        req_file = Path(target) / "requirements.txt"
        if req_file.exists():
            return [
                "pip-audit",
                "-r", str(req_file),
                "--format", "json",
            ]
        
        # Fall back to scanning the current environment
        return [
            "pip-audit",
            "--format", "json",
        ]
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []
        
        if not stdout.strip():
            return findings
        
        try:
            data = json.loads(stdout)
            
            for vuln in data.get("dependencies", []):
                for v in vuln.get("vulns", []):
                    severity = self._map_cvss_severity(v.get("fix_versions", []))
                    
                    finding = ScannerFinding(
                        title=f"Vulnerable dependency: {vuln.get('name', 'unknown')} ({v.get('id', 'unknown')})",
                        description=v.get("description", ""),
                        severity=severity,
                        category="security",
                        confidence=0.95,
                        file_path="requirements.txt",
                        source=self.name,
                        rule_id=v.get("id"),
                        rule_name=f"{vuln.get('name')}@{vuln.get('version')}",
                        references=v.get("aliases", []) + [f"https://pypi.org/project/{vuln.get('name')}/"],
                        raw_output={**vuln, **v},
                    )
                    findings.append(finding)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse pip-audit output", error=str(e))
        
        return findings
    
    def _map_cvss_severity(self, fix_versions: list) -> str:
        """Estimate severity based on whether fix is available."""
        if fix_versions:
            return "high"
        return "critical"


class MypyScanner(BaseScanner):
    """Python type checker using mypy."""
    
    name = "mypy"
    scanner_type = ScannerType.TYPE_CHECK
    supported_languages = ["python"]
    
    def is_available(self) -> bool:
        _, _, code = self._run_command(["mypy", "--version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["mypy", "--version"])
        if code == 0:
            return stdout.strip()
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        target = str(target_path) if target_path else "."
        return [
            "mypy",
            "--ignore-missing-imports",
            "--no-error-summary",
            "--output", "json",
            target,
        ]
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []
        
        # Mypy outputs one JSON object per line
        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            
            try:
                item = json.loads(line)
                severity = "medium" if item.get("severity") == "error" else "low"
                
                finding = ScannerFinding(
                    title=f"Type error: {item.get('message', 'Unknown')}",
                    description=item.get("message", ""),
                    severity=severity,
                    category="reliability",
                    confidence=0.9,
                    file_path=item.get("file", ""),
                    line_start=item.get("line"),
                    column_start=item.get("column"),
                    source=self.name,
                    rule_id=item.get("code"),
                    references=["https://mypy.readthedocs.io/"],
                    raw_output=item,
                )
                findings.append(finding)
            except json.JSONDecodeError:
                continue
        
        return findings
