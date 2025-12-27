"""
Bull's Eye - Rust Scanners
clippy, cargo-audit
"""

import json
from pathlib import Path
from typing import List, Optional

from .base import BaseScanner, ScannerFinding, ScannerType


class ClippyScanner(BaseScanner):
    """Rust linter using cargo clippy."""
    
    name = "clippy"
    scanner_type = ScannerType.LINT
    supported_languages = ["rust"]
    
    def is_available(self) -> bool:
        _, _, code = self._run_command(["cargo", "clippy", "--version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["cargo", "clippy", "--version"])
        if code == 0:
            return stdout.strip()
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        return [
            "cargo", "clippy",
            "--message-format", "json",
            "--all-targets",
            "--all-features",
            "--", "-D", "warnings",
        ]
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []
        
        # Clippy outputs newline-delimited JSON
        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            
            try:
                data = json.loads(line)
                
                # Only process compiler messages
                if data.get("reason") != "compiler-message":
                    continue
                
                message = data.get("message", {})
                level = message.get("level", "warning")
                
                if level not in ["warning", "error"]:
                    continue
                
                spans = message.get("spans", [])
                primary_span = next((s for s in spans if s.get("is_primary")), spans[0] if spans else {})
                
                severity = "high" if level == "error" else "medium"
                code = message.get("code", {})
                
                finding = ScannerFinding(
                    title=f"[{code.get('code', 'unknown')}] {message.get('message', 'Unknown')[:100]}",
                    description=message.get("message", ""),
                    severity=severity,
                    category=self._map_category(code.get("code", "")),
                    confidence=0.9,
                    file_path=primary_span.get("file_name", ""),
                    line_start=primary_span.get("line_start"),
                    line_end=primary_span.get("line_end"),
                    column_start=primary_span.get("column_start"),
                    column_end=primary_span.get("column_end"),
                    code_snippet=primary_span.get("text", [{}])[0].get("text", "") if primary_span.get("text") else "",
                    source=self.name,
                    rule_id=code.get("code"),
                    rule_name=code.get("code"),
                    references=[code.get("explanation")] if code.get("explanation") else [],
                    raw_output=data,
                )
                findings.append(finding)
            except json.JSONDecodeError:
                continue
        
        return findings
    
    def _map_category(self, code: str) -> str:
        """Map clippy lint code to category."""
        if "unsafe" in code.lower() or "security" in code.lower():
            return "security"
        elif "perf" in code.lower():
            return "performance"
        elif "correctness" in code.lower() or "suspicious" in code.lower():
            return "reliability"
        return "maintainability"


class CargoAuditScanner(BaseScanner):
    """Rust dependency vulnerability scanner using cargo-audit."""
    
    name = "cargo-audit"
    scanner_type = ScannerType.DEPS
    supported_languages = ["rust"]
    
    def is_available(self) -> bool:
        _, _, code = self._run_command(["cargo", "audit", "--version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["cargo", "audit", "--version"])
        if code == 0:
            return stdout.strip()
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        return [
            "cargo", "audit",
            "--json",
        ]
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []
        
        if not stdout.strip():
            return findings
        
        try:
            data = json.loads(stdout)
            vulnerabilities = data.get("vulnerabilities", {}).get("list", [])
            
            for vuln in vulnerabilities:
                advisory = vuln.get("advisory", {})
                package = vuln.get("package", {})
                
                severity = self._map_cvss_severity(advisory.get("cvss"))
                
                finding = ScannerFinding(
                    title=f"Vulnerable crate: {package.get('name', 'unknown')} - {advisory.get('id', 'unknown')}",
                    description=advisory.get("description", ""),
                    severity=severity,
                    category="security",
                    confidence=0.95,
                    file_path="Cargo.toml",
                    source=self.name,
                    rule_id=advisory.get("id"),
                    rule_name=f"{package.get('name')}@{package.get('version')}",
                    references=[
                        advisory.get("url", ""),
                        f"https://rustsec.org/advisories/{advisory.get('id', '')}.html",
                    ],
                    raw_output=vuln,
                )
                findings.append(finding)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse cargo-audit output", error=str(e))
        
        return findings
    
    def _map_cvss_severity(self, cvss: Optional[str]) -> str:
        """Map CVSS score to severity."""
        if not cvss:
            return "medium"
        
        try:
            score = float(cvss.split("/")[0]) if "/" in cvss else float(cvss)
            if score >= 9.0:
                return "critical"
            elif score >= 7.0:
                return "high"
            elif score >= 4.0:
                return "medium"
            return "low"
        except (ValueError, IndexError):
            return "medium"
