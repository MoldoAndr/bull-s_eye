"""
Bull's Eye - JavaScript/TypeScript Scanners
ESLint, npm audit
"""

import json
from pathlib import Path
from typing import List, Optional

from .base import BaseScanner, ScannerFinding, ScannerType


class EslintScanner(BaseScanner):
    """JavaScript/TypeScript linter using ESLint."""
    
    name = "eslint"
    scanner_type = ScannerType.LINT
    supported_languages = ["javascript", "typescript", "react"]
    
    def is_available(self) -> bool:
        _, _, code = self._run_command(["eslint", "--version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["eslint", "--version"])
        if code == 0:
            return stdout.strip()
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        target = str(target_path) if target_path else "."
        return [
            "eslint",
            "--format", "json",
            "--ext", ".js,.jsx,.ts,.tsx",
            "--no-error-on-unmatched-pattern",
            target,
        ]
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []
        
        if not stdout.strip():
            return findings
        
        try:
            data = json.loads(stdout)
            
            for file_result in data:
                file_path = file_result.get("filePath", "")
                
                for msg in file_result.get("messages", []):
                    severity = "high" if msg.get("severity") == 2 else "medium"
                    
                    finding = ScannerFinding(
                        title=f"[{msg.get('ruleId', 'unknown')}] {msg.get('message', 'Unknown')[:100]}",
                        description=msg.get("message", ""),
                        severity=severity,
                        category=self._map_category(msg.get("ruleId", "")),
                        confidence=0.85,
                        file_path=file_path,
                        line_start=msg.get("line"),
                        line_end=msg.get("endLine"),
                        column_start=msg.get("column"),
                        column_end=msg.get("endColumn"),
                        source=self.name,
                        rule_id=msg.get("ruleId"),
                        rule_name=msg.get("ruleId"),
                        references=[f"https://eslint.org/docs/rules/{msg.get('ruleId', '')}"],
                        raw_output=msg,
                    )
                    findings.append(finding)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse eslint output", error=str(e))
        
        return findings
    
    def _map_category(self, rule_id: str) -> str:
        """Map ESLint rule to category."""
        if not rule_id:
            return "maintainability"
        
        # Security-related rules
        security_rules = ["no-eval", "no-implied-eval", "no-new-func", "no-script-url"]
        if any(r in rule_id for r in security_rules):
            return "security"
        
        # Reliability rules
        reliability_rules = ["no-undef", "no-unused-vars", "no-unreachable", "no-constant-condition"]
        if any(r in rule_id for r in reliability_rules):
            return "reliability"
        
        return "maintainability"


class NpmAuditScanner(BaseScanner):
    """JavaScript dependency vulnerability scanner using npm audit."""
    
    name = "npm-audit"
    scanner_type = ScannerType.DEPS
    supported_languages = ["javascript", "typescript", "react"]
    
    def is_available(self) -> bool:
        _, _, code = self._run_command(["npm", "--version"])
        return code == 0
    
    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["npm", "--version"])
        if code == 0:
            return f"npm {stdout.strip()}"
        return None
    
    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        return [
            "npm", "audit",
            "--json",
        ]
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []
        
        if not stdout.strip():
            return findings
        
        try:
            data = json.loads(stdout)
            vulnerabilities = data.get("vulnerabilities", {})
            
            for pkg_name, vuln in vulnerabilities.items():
                severity = vuln.get("severity", "moderate").lower()
                severity = {"critical": "critical", "high": "high", "moderate": "medium", "low": "low"}.get(severity, "medium")
                
                via = vuln.get("via", [])
                description = ""
                references = []
                rule_id = None
                
                for v in via:
                    if isinstance(v, dict):
                        description = v.get("title", "")
                        rule_id = v.get("cwe", [None])[0] if v.get("cwe") else None
                        if v.get("url"):
                            references.append(v["url"])
                        break
                    elif isinstance(v, str):
                        description = f"Dependency of vulnerable package: {v}"
                
                finding = ScannerFinding(
                    title=f"Vulnerable package: {pkg_name} ({severity})",
                    description=description,
                    severity=severity,
                    category="security",
                    confidence=0.9,
                    file_path="package.json",
                    source=self.name,
                    rule_id=rule_id,
                    rule_name=pkg_name,
                    references=references or [f"https://www.npmjs.com/package/{pkg_name}"],
                    raw_output=vuln,
                )
                findings.append(finding)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse npm audit output", error=str(e))
        
        return findings
