"""
Bull's Eye - Opengrep Scanner
Multi-language static analysis security scanner
"""

import json
from pathlib import Path
from typing import List, Optional

from .base import BaseScanner, ScannerFinding, ScannerType


class OpengrepScanner(BaseScanner):
    """Scanner for static analysis using opengrep."""
    
    name = "opengrep"
    scanner_type = ScannerType.SECURITY
    supported_languages = ["python", "go", "rust", "javascript", "typescript"]
    
    def is_available(self) -> bool:
        stdout, _, code = self._run_command(["opengrep", "--version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["opengrep", "--version"])
        if code == 0:
            return stdout.strip()
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        target = str(target_path) if target_path else str(self.repo_path)
        return [
            "opengrep",
            "scan",
            "--config", "auto",  # Use recommended rules
            "--json",
            "--no-git-ignore",  # Scan everything
            "--timeout", "300",
            "--max-target-bytes", "5000000",  # 5MB max file
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
                extra = item.get("extra", {})
                metadata = extra.get("metadata", {})
                
                severity = self._map_severity(extra.get("severity", "INFO"))
                category = self._map_category(metadata)
                
                finding = ScannerFinding(
                    title=metadata.get("message", item.get("check_id", "Unknown issue")),
                    description=extra.get("message", ""),
                    severity=severity,
                    category=category,
                    confidence=self._map_confidence(metadata.get("confidence", "MEDIUM")),
                    file_path=item.get("path", ""),
                    line_start=item.get("start", {}).get("line"),
                    line_end=item.get("end", {}).get("line"),
                    column_start=item.get("start", {}).get("col"),
                    column_end=item.get("end", {}).get("col"),
                    code_snippet=extra.get("lines", ""),
                    source=self.name,
                    rule_id=item.get("check_id"),
                    rule_name=metadata.get("shortlink", item.get("check_id")),
                    references=self._extract_references(metadata),
                    raw_output=item,
                )
                findings.append(finding)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse opengrep output", error=str(e))
        
        return findings
    
    def _map_severity(self, severity: str) -> str:
        """Map opengrep severity to standard severity."""
        mapping = {
            "ERROR": "high",
            "WARNING": "medium",
            "INFO": "low",
        }
        return mapping.get(severity.upper(), "info")
    
    def _map_category(self, metadata: dict) -> str:
        """Map opengrep category to standard category."""
        category = metadata.get("category", "").lower()
        if "security" in category:
            return "security"
        elif "performance" in category:
            return "performance"
        elif "correctness" in category or "bug" in category:
            return "reliability"
        elif "maintainability" in category or "style" in category:
            return "maintainability"
        return "best_practice"
    
    def _map_confidence(self, confidence: str) -> float:
        """Map opengrep confidence to float."""
        mapping = {
            "HIGH": 0.9,
            "MEDIUM": 0.7,
            "LOW": 0.5,
        }
        return mapping.get(confidence.upper(), 0.5)
    
    def _extract_references(self, metadata: dict) -> List[str]:
        """Extract references from metadata."""
        refs = []
        if metadata.get("cwe"):
            cwe = metadata["cwe"]
            if isinstance(cwe, list):
                refs.extend([f"https://cwe.mitre.org/data/definitions/{c.split('-')[-1]}.html" for c in cwe])
            else:
                refs.append(f"https://cwe.mitre.org/data/definitions/{cwe.split('-')[-1]}.html")
        if metadata.get("owasp"):
            refs.append(f"https://owasp.org/Top10/{metadata['owasp']}")
        if metadata.get("shortlink"):
            refs.append(metadata["shortlink"])
        return refs
