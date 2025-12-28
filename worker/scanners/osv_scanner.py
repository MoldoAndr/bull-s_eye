"""
Bull's Eye - OSV Scanner
Dependency vulnerability scanner using osv-scanner
"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Iterable

from .base import BaseScanner, ScannerFinding, ScannerType


class OSVScanner(BaseScanner):
    """Dependency vulnerability scanner using osv-scanner."""

    name = "osv-scanner"
    scanner_type = ScannerType.DEPS
    supported_languages = ["python", "go", "javascript", "typescript", "rust"]

    def is_available(self) -> bool:
        _, _, code = self._run_command(["osv-scanner", "--version"])
        return code == 0

    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["osv-scanner", "--version"])
        if code == 0:
            return stdout.strip()
        return None

    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        target = str(target_path) if target_path else str(self.repo_path)
        return [
            "osv-scanner",
            "--format", "json",
            "--recursive",
            target,
        ]

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings: List[ScannerFinding] = []

        if not stdout.strip():
            return findings

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse osv-scanner output", error=str(e))
            return findings

        results = data.get("results", [])
        seen: set[tuple[str, str, str, str]] = set()

        for result in results:
            source = result.get("source", {}) or {}
            source_path = source.get("path", "")

            package_entries = self._extract_packages(result.get("packages", []))
            for pkg in result.get("packages", []):
                pkg_info = self._normalize_package(pkg)
                for vuln in pkg.get("vulnerabilities", []) or []:
                    self._add_vuln_finding(
                        findings,
                        seen,
                        vuln,
                        pkg_info,
                        source_path,
                    )

            for vuln in result.get("vulnerabilities", []) or []:
                vuln_packages = self._packages_for_vuln(vuln, package_entries)
                for pkg_info in vuln_packages:
                    self._add_vuln_finding(
                        findings,
                        seen,
                        vuln,
                        pkg_info,
                        source_path,
                    )

        return findings

    def _extract_packages(self, packages: Iterable[Dict[str, Any]]) -> List[Dict[str, Optional[str]]]:
        extracted = []
        for pkg in packages:
            extracted.append(self._normalize_package(pkg))
        return extracted

    def _normalize_package(self, pkg: Dict[str, Any]) -> Dict[str, Optional[str]]:
        pkg_info = pkg.get("package", {}) or {}
        return {
            "name": pkg_info.get("name") or pkg.get("name") or "",
            "version": pkg.get("version"),
            "ecosystem": pkg_info.get("ecosystem") or pkg.get("ecosystem"),
        }

    def _packages_for_vuln(
        self,
        vuln: Dict[str, Any],
        fallback_packages: List[Dict[str, Optional[str]]],
    ) -> List[Dict[str, Optional[str]]]:
        packages: List[Dict[str, Optional[str]]] = []

        for affected in vuln.get("affected", []) or []:
            pkg_info = affected.get("package", {}) or {}
            name = pkg_info.get("name")
            if name:
                packages.append(
                    {
                        "name": name,
                        "version": None,
                        "ecosystem": pkg_info.get("ecosystem"),
                    }
                )

        if not packages:
            packages = fallback_packages or [{"name": "", "version": None, "ecosystem": None}]

        return packages

    def _add_vuln_finding(
        self,
        findings: List[ScannerFinding],
        seen: set[tuple[str, str, str, str]],
        vuln: Dict[str, Any],
        pkg_info: Dict[str, Optional[str]],
        source_path: str,
    ) -> None:
        vuln_id = vuln.get("id", "unknown")
        package_name = pkg_info.get("name") or "unknown"
        version = pkg_info.get("version") or ""

        key = (vuln_id, package_name, version, source_path)
        if key in seen:
            return
        seen.add(key)

        severity = self._map_severity(vuln)
        description = vuln.get("details") or vuln.get("summary") or ""
        version_details = self._format_affected_versions(vuln.get("affected", []))
        if version_details:
            description = f"{description}\nAffected versions: {version_details}".strip()

        rule_name = package_name
        if version:
            rule_name = f"{package_name}@{version}"

        finding = ScannerFinding(
            title=f"Vulnerable dependency: {package_name} ({vuln_id})",
            description=description,
            severity=severity,
            category="security",
            confidence=0.9,
            file_path=source_path or "dependency manifest",
            source=self.name,
            rule_id=vuln_id,
            rule_name=rule_name,
            references=self._extract_references(vuln, vuln_id),
            raw_output={**vuln, "package": pkg_info},
        )
        findings.append(finding)

    def _map_severity(self, vuln: Dict[str, Any]) -> str:
        scores = []
        for severity in vuln.get("severity", []) or []:
            score = severity.get("score")
            if score is None:
                continue
            try:
                scores.append(float(score))
            except (TypeError, ValueError):
                continue

        if scores:
            max_score = max(scores)
            if max_score >= 9.0:
                return "critical"
            if max_score >= 7.0:
                return "high"
            if max_score >= 4.0:
                return "medium"
            if max_score > 0.0:
                return "low"

        db_severity = (vuln.get("database_specific", {}) or {}).get("severity")
        if isinstance(db_severity, str):
            normalized = db_severity.lower()
            return {
                "critical": "critical",
                "high": "high",
                "moderate": "medium",
                "medium": "medium",
                "low": "low",
                "info": "info",
            }.get(normalized, "medium")

        return "medium"

    def _extract_references(self, vuln: Dict[str, Any], vuln_id: str) -> List[str]:
        refs = []
        for ref in vuln.get("references", []) or []:
            url = ref.get("url")
            if url:
                refs.append(url)

        aliases = vuln.get("aliases", []) or []
        refs.extend([f"https://osv.dev/vulnerability/{alias}" for alias in aliases])
        refs.append(f"https://osv.dev/vulnerability/{vuln_id}")
        return list(dict.fromkeys(refs))

    def _format_affected_versions(self, affected: List[Dict[str, Any]]) -> str:
        ranges = []
        versions = []

        for entry in affected or []:
            versions.extend(entry.get("versions", []) or [])
            for rng in entry.get("ranges", []) or []:
                events = []
                for event in rng.get("events", []) or []:
                    if "introduced" in event:
                        events.append(f"introduced {event['introduced']}")
                    if "fixed" in event:
                        events.append(f"fixed {event['fixed']}")
                    if "last_affected" in event:
                        events.append(f"last affected {event['last_affected']}")
                if events:
                    ranges.append(" -> ".join(events))

        parts = []
        if ranges:
            parts.append("; ".join(ranges))
        if versions:
            parts.append(", ".join(versions))

        return " | ".join(parts)
