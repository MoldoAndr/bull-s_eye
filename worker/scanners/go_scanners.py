"""
Bull's Eye - Go Scanners
golangci-lint, gosec, govulncheck
"""

import json
from pathlib import Path
from typing import List, Optional

from .base import BaseScanner, ScannerFinding, ScannerType


class GolangciLintScanner(BaseScanner):
    """Go linter aggregator using golangci-lint."""
    
    name = "golangci-lint"
    scanner_type = ScannerType.LINT
    supported_languages = ["go"]
    
    def is_available(self) -> bool:
        _, _, code = self._run_command(["golangci-lint", "--version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["golangci-lint", "--version"])
        if code == 0:
            return stdout.strip().split("\n")[0]
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        return [
            "golangci-lint", "run",
            "--out-format", "json",
            "--timeout", "5m",
            "./...",
        ]
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []
        
        if not stdout.strip():
            return findings
        
        try:
            data = json.loads(stdout)
            issues = data.get("Issues", [])
            
            for item in issues:
                severity = self._map_severity(item.get("Severity", "warning"))
                category = self._map_category(item.get("FromLinter", ""))
                
                pos = item.get("Pos", {})
                
                finding = ScannerFinding(
                    title=f"[{item.get('FromLinter', 'unknown')}] {item.get('Text', 'Unknown issue')[:100]}",
                    description=item.get("Text", ""),
                    severity=severity,
                    category=category,
                    confidence=0.85,
                    file_path=pos.get("Filename", ""),
                    line_start=pos.get("Line"),
                    column_start=pos.get("Column"),
                    source=self.name,
                    rule_id=item.get("FromLinter"),
                    rule_name=item.get("FromLinter"),
                    references=[f"https://golangci-lint.run/usage/linters/#{item.get('FromLinter', '')}"],
                    raw_output=item,
                )
                findings.append(finding)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse golangci-lint output", error=str(e))
        
        return findings
    
    def _map_severity(self, severity: str) -> str:
        mapping = {
            "error": "high",
            "warning": "medium",
            "info": "low",
        }
        return mapping.get(severity.lower(), "low")
    
    def _map_category(self, linter: str) -> str:
        security_linters = ["gosec", "gocritic"]
        perf_linters = ["prealloc", "bodyclose"]
        
        if linter in security_linters:
            return "security"
        elif linter in perf_linters:
            return "performance"
        return "maintainability"


class GosecScanner(BaseScanner):
    """Go security scanner using gosec."""
    
    name = "gosec"
    scanner_type = ScannerType.SECURITY
    supported_languages = ["go"]
    
    def is_available(self) -> bool:
        _, _, code = self._run_command(["gosec", "-version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["gosec", "-version"])
        if code == 0:
            return stdout.strip()
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        return [
            "gosec",
            "-fmt", "json",
            "-severity", "low",
            "-confidence", "low",
            "./...",
        ]
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []
        
        if not stdout.strip():
            return findings
        
        try:
            data = json.loads(stdout)
            issues = data.get("Issues", [])
            
            for item in issues:
                severity = item.get("severity", "MEDIUM").lower()
                confidence = {"HIGH": 0.9, "MEDIUM": 0.7, "LOW": 0.5}.get(
                    item.get("confidence", "MEDIUM"), 0.5
                )
                
                finding = ScannerFinding(
                    title=f"{item.get('rule_id', 'G000')}: {item.get('details', 'Unknown issue')[:100]}",
                    description=item.get("details", ""),
                    severity=severity,
                    category="security",
                    confidence=confidence,
                    file_path=item.get("file", ""),
                    line_start=int(item.get("line", 0)) if item.get("line") else None,
                    column_start=int(item.get("column", 0)) if item.get("column") else None,
                    code_snippet=item.get("code", ""),
                    source=self.name,
                    rule_id=item.get("rule_id"),
                    rule_name=item.get("rule_id"),
                    references=[
                        item.get("cwe", {}).get("url", ""),
                        "https://securego.io/docs/rules/",
                    ],
                    raw_output=item,
                )
                findings.append(finding)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse gosec output", error=str(e))
        
        return findings


class GovulncheckScanner(BaseScanner):
    """Go vulnerability scanner using govulncheck."""
    
    name = "govulncheck"
    scanner_type = ScannerType.DEPS
    supported_languages = ["go"]
    
    def is_available(self) -> bool:
        _, _, code = self._run_command(["govulncheck", "-version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["govulncheck", "-version"])
        if code == 0:
            return stdout.strip()
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        return [
            "govulncheck",
            "-json",
            "./...",
        ]
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []
        
        # govulncheck outputs newline-delimited JSON
        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            
            try:
                data = json.loads(line)
                
                # Look for vulnerability entries
                if "finding" not in data:
                    continue
                
                finding_data = data["finding"]
                osv = finding_data.get("osv", "")
                
                finding = ScannerFinding(
                    title=f"Vulnerable dependency: {osv}",
                    description=finding_data.get("trace", [{}])[0].get("function", ""),
                    severity="high",
                    category="security",
                    confidence=0.95,
                    file_path="go.mod",
                    source=self.name,
                    rule_id=osv,
                    references=[f"https://pkg.go.dev/vuln/{osv}"],
                    raw_output=data,
                )
                findings.append(finding)
            except json.JSONDecodeError:
                continue
        
        return findings
