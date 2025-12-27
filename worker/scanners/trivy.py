"""
Bull's Eye - Trivy Scanner
Comprehensive vulnerability scanner for containers, filesystems, git repos
"""

import json
from pathlib import Path
from typing import List, Optional

from .base import BaseScanner, ScannerFinding, ScannerType


class TrivyScanner(BaseScanner):
    """Comprehensive scanner using Trivy."""
    
    name = "trivy"
    scanner_type = ScannerType.SECURITY
    supported_languages = ["*"]
    
    def is_available(self) -> bool:
        _, _, code = self._run_command(["trivy", "version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["trivy", "version"])
        if code == 0:
            for line in stdout.split("\n"):
                if "Version:" in line:
                    return line.split(":")[-1].strip()
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        target = str(target_path) if target_path else str(self.repo_path)
        return [
            "trivy", "fs",
            "--format", "json",
            "--scanners", "vuln,secret,misconfig",
            "--severity", "UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL",
            target,
        ]
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []
        
        if not stdout.strip():
            return findings
        
        try:
            data = json.loads(stdout)
            results = data.get("Results", [])
            
            for result in results:
                target = result.get("Target", "")
                
                # Parse vulnerabilities
                for vuln in result.get("Vulnerabilities", []):
                    severity = vuln.get("Severity", "MEDIUM").lower()
                    
                    finding = ScannerFinding(
                        title=f"Vulnerability: {vuln.get('VulnerabilityID', 'unknown')} in {vuln.get('PkgName', 'unknown')}",
                        description=vuln.get("Description", vuln.get("Title", "")),
                        severity=severity,
                        category="security",
                        confidence=0.95,
                        file_path=target,
                        source=self.name,
                        rule_id=vuln.get("VulnerabilityID"),
                        rule_name=f"{vuln.get('PkgName')}@{vuln.get('InstalledVersion')}",
                        references=vuln.get("References", [])[:5],
                        raw_output=vuln,
                    )
                    findings.append(finding)
                
                # Parse secrets
                for secret in result.get("Secrets", []):
                    finding = ScannerFinding(
                        title=f"Secret detected: {secret.get('Title', 'Unknown secret')}",
                        description=secret.get("Match", ""),
                        severity="high",
                        category="security",
                        confidence=0.9,
                        file_path=target,
                        line_start=secret.get("StartLine"),
                        line_end=secret.get("EndLine"),
                        source=f"{self.name}-secret",
                        rule_id=secret.get("RuleID"),
                        rule_name=secret.get("Category"),
                        raw_output=secret,
                    )
                    findings.append(finding)
                
                # Parse misconfigurations
                for misconfig in result.get("Misconfigurations", []):
                    severity = misconfig.get("Severity", "MEDIUM").lower()
                    
                    finding = ScannerFinding(
                        title=f"Misconfiguration: {misconfig.get('Title', 'Unknown')}",
                        description=misconfig.get("Description", ""),
                        severity=severity,
                        category="security",
                        confidence=0.85,
                        file_path=target,
                        line_start=misconfig.get("CauseMetadata", {}).get("StartLine"),
                        line_end=misconfig.get("CauseMetadata", {}).get("EndLine"),
                        code_snippet=misconfig.get("CauseMetadata", {}).get("Code", {}).get("Lines", [{}])[0].get("Content", ""),
                        source=f"{self.name}-misconfig",
                        rule_id=misconfig.get("ID"),
                        rule_name=misconfig.get("Type"),
                        references=misconfig.get("References", [])[:5],
                        raw_output=misconfig,
                    )
                    findings.append(finding)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse trivy output", error=str(e))
        
        return findings
