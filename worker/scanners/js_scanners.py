"""
Bull's Eye - JavaScript/TypeScript Scanners
Biome, ESLint, npm audit
"""

import json
from pathlib import Path
from typing import List, Optional

from .base import BaseScanner, ScannerFinding, ScannerType


class BiomeScanner(BaseScanner):
    """JavaScript/TypeScript linter using Biome."""

    name = "biome"
    scanner_type = ScannerType.LINT
    supported_languages = ["javascript", "typescript", "react"]

    def is_available(self) -> bool:
        _, _, code = self._run_command(["biome", "--version"])
        return code == 0

    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["biome", "--version"])
        if code == 0:
            return stdout.strip()
        return None

    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        target = str(target_path) if target_path else "."
        return [
            "biome",
            "lint",
            "--reporter=json",
            "--no-errors-on-unmatched",
            target,
        ]

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings = []

        if not stdout.strip():
            return findings

        raw = stdout.strip()
        if not raw:
            return findings

        payload = self._extract_json_payload(raw)
        if not payload:
            return findings

        try:
            data, _ = json.JSONDecoder().raw_decode(payload)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse biome output", error=str(e))
            return findings

        diagnostics = self._collect_diagnostics(data)

        for diag in diagnostics:
            message = self._format_message(diag.get("message")) or diag.get("description") or "Unknown issue"
            category = diag.get("category", "")
            rule_name = self._extract_rule_name(category)
            severity = self._map_severity(diag.get("severity", "warning"))
            file_path, line_start, line_end, column_start, column_end = self._extract_location(diag)

            finding = ScannerFinding(
                title=self._format_title(rule_name, message),
                description=message,
                severity=severity,
                category=self._map_category(category),
                confidence=0.85,
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                column_start=column_start,
                column_end=column_end,
                source=self.name,
                rule_id=category or None,
                rule_name=rule_name or None,
                references=self._build_references(rule_name),
                raw_output=diag,
            )
            findings.append(finding)

        return findings

    def _collect_diagnostics(self, data: object) -> List[dict]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if "diagnostics" in data:
                return data.get("diagnostics", [])
            if "files" in data:
                diagnostics = []
                for file_entry in data.get("files", []):
                    diagnostics.extend(file_entry.get("diagnostics", []))
                return diagnostics
        return []

    def _extract_json_payload(self, raw: str) -> str:
        if raw.startswith("{") or raw.startswith("["):
            return raw

        candidates = []
        for marker in ("{", "["):
            idx = raw.find(marker)
            if idx >= 0:
                candidates.append(idx)
        if not candidates:
            return ""
        start = min(candidates)
        return raw[start:]

    def _format_message(self, message: object) -> str:
        if isinstance(message, str):
            return message
        if isinstance(message, list):
            parts = []
            for segment in message:
                if isinstance(segment, dict):
                    content = segment.get("content")
                    if content:
                        parts.append(content)
            return "".join(parts)
        return ""

    def _extract_location(self, diag: dict) -> tuple[str, Optional[int], Optional[int], Optional[int], Optional[int]]:
        location = diag.get("location", {}) or {}
        path_value = location.get("path") or diag.get("path") or diag.get("filePath")
        if isinstance(path_value, dict):
            file_path = path_value.get("file") or path_value.get("path") or ""
        else:
            file_path = path_value or ""

        span = location.get("span") or diag.get("span") or {}
        if isinstance(span, list) and len(span) >= 2:
            line_start, column_start = self._offset_to_line_col(
                location.get("sourceCode") or "",
                span[0],
            )
            line_end, column_end = self._offset_to_line_col(
                location.get("sourceCode") or "",
                span[1],
            )
        else:
            start = span.get("start", {}) or {}
            end = span.get("end", {}) or {}

            line_start = start.get("line") or start.get("row") or location.get("line")
            line_end = end.get("line") or end.get("row") or location.get("line")
            column_start = start.get("column") or start.get("col") or location.get("column")
            column_end = end.get("column") or end.get("col") or location.get("column")

        return file_path, line_start, line_end, column_start, column_end

    def _extract_rule_name(self, category: str) -> str:
        if not category:
            return ""
        return category.split("/")[-1]

    def _format_title(self, rule_name: str, message: str) -> str:
        if rule_name:
            return f"[{rule_name}] {message[:100]}"
        return message[:100]

    def _map_severity(self, severity: str) -> str:
        mapping = {
            "error": "high",
            "warning": "medium",
            "warn": "medium",
            "info": "low",
            "hint": "info",
        }
        return mapping.get(str(severity).lower(), "low")

    def _map_category(self, category: str) -> str:
        category_lower = category.lower()
        if "security" in category_lower:
            return "security"
        if "performance" in category_lower:
            return "performance"
        if "correctness" in category_lower or "suspicious" in category_lower or "bug" in category_lower:
            return "reliability"
        return "maintainability"

    def _build_references(self, rule_name: str) -> List[str]:
        if not rule_name:
            return []
        return [f"https://biomejs.dev/linter/rules/{rule_name}/"]

    def _offset_to_line_col(self, source: str, offset: int) -> tuple[Optional[int], Optional[int]]:
        if not source or offset is None:
            return None, None
        if offset < 0:
            return None, None
        if offset > len(source):
            offset = len(source)
        line = source.count("\n", 0, offset) + 1
        last_newline = source.rfind("\n", 0, offset)
        column = offset + 1 if last_newline == -1 else offset - last_newline
        return line, column


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
