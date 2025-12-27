"""
Bull's Eye - Gitleaks Scanner
Detects secrets and sensitive data in code
"""

import json
from pathlib import Path
from typing import List, Optional

from .base import BaseScanner, ScannerFinding, ScannerType


class GitleaksScanner(BaseScanner):
    """Scanner for detecting secrets using gitleaks."""
    
    name = "gitleaks"
    scanner_type = ScannerType.SECRETS
    supported_languages = ["*"]  # All languages
    
    def is_available(self) -> bool:
        stdout, _, code = self._run_command(["gitleaks", "version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["gitleaks", "version"])
        if code == 0:
            return stdout.strip()
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        target = str(target_path) if target_path else str(self.repo_path)
        return [
            "gitleaks",
            "detect",
            "--source", target,
            "--report-format", "json",
            "--report-path", "/dev/stdout",
            "--no-git",  # Scan files, not git history
            "--exit-code", "0",  # Don't fail on findings
        ]
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []
        
        if not stdout.strip():
            return findings
        
        try:
            data = json.loads(stdout)
            if not isinstance(data, list):
                return findings
            
            for item in data:
                severity = self._map_severity(item.get("Rule", {}).get("Entropy", 0))
                
                finding = ScannerFinding(
                    title=f"Secret detected: {item.get('Description', 'Unknown secret')}",
                    description=f"Potential secret or sensitive data found. Rule: {item.get('RuleID', 'unknown')}",
                    severity=severity,
                    category="security",
                    confidence=0.9,
                    file_path=item.get("File", ""),
                    line_start=item.get("StartLine"),
                    line_end=item.get("EndLine"),
                    column_start=item.get("StartColumn"),
                    column_end=item.get("EndColumn"),
                    code_snippet=item.get("Secret", "")[:100] + "..." if len(item.get("Secret", "")) > 100 else item.get("Secret", ""),
                    source=self.name,
                    rule_id=item.get("RuleID"),
                    rule_name=item.get("Description"),
                    references=["https://github.com/gitleaks/gitleaks"],
                    raw_output=item,
                )
                findings.append(finding)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse gitleaks output", error=str(e))
        
        return findings
    
    def _map_severity(self, entropy: float) -> str:
        """Map entropy/confidence to severity."""
        if entropy > 4.5:
            return "critical"
        elif entropy > 4.0:
            return "high"
        elif entropy > 3.5:
            return "medium"
        return "low"
