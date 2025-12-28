"""
Bull's Eye - Lizard Scanner
Cyclomatic complexity analysis for risk prioritization
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

from config import settings
from .base import BaseScanner, ScannerFinding, ScannerType


class LizardScanner(BaseScanner):
    """Cyclomatic complexity scanner using lizard."""

    name = "lizard"
    scanner_type = ScannerType.LINT
    supported_languages = [
        "python",
        "go",
        "rust",
        "javascript",
        "typescript",
        "java",
        "c",
        "cpp",
    ]

    def is_available(self) -> bool:
        _, _, code = self._run_command(["lizard", "--version"])
        return code == 0

    def get_version(self) -> Optional[str]:
        stdout, _, code = self._run_command(["lizard", "--version"])
        if code == 0:
            return stdout.strip()
        return None

    def build_command(self, target_path: Optional[Path] = None) -> List[str]:
        target = str(target_path) if target_path else str(self.repo_path)
        return [
            "lizard",
            "-X",
            target,
        ]

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> List[ScannerFinding]:
        findings: List[ScannerFinding] = []

        if not stdout.strip():
            return findings

        try:
            root = ET.fromstring(stdout)
        except ET.ParseError as e:
            self.logger.warning("Failed to parse lizard output", error=str(e))
            return findings

        functions = root.findall(".//measure[@type='Function']/item")
        threshold = settings.complexity_threshold

        for func in functions:
            name_attr = func.get("name", "")
            values = [value.text for value in func.findall("value")]
            if len(values) < 3:
                continue
            try:
                nloc = int(values[1])
                complexity = int(values[2])
            except (TypeError, ValueError):
                continue

            if complexity <= threshold:
                continue

            func_name, file_path, line_start = self._parse_function_name(name_attr)
            if file_path and file_path.startswith(str(self.repo_path)):
                file_path = str(Path(file_path).relative_to(self.repo_path))

            severity = self._map_severity(complexity, threshold)
            description = self._format_description(nloc, complexity, threshold)

            findings.append(
                ScannerFinding(
                    title=f"High complexity function: {func_name}",
                    description=description,
                    severity=severity,
                    category="maintainability",
                    confidence=0.8,
                    file_path=file_path,
                    line_start=line_start,
                    line_end=line_start,
                    source=self.name,
                    rule_id="cyclomatic_complexity",
                    rule_name=func_name,
                    references=["https://github.com/terryyin/lizard"],
                    raw_output={
                        "name": name_attr,
                        "nloc": nloc,
                        "complexity": complexity,
                    },
                )
            )

        return findings

    def _map_severity(self, complexity: int, threshold: int) -> str:
        if complexity >= max(threshold + 15, threshold * 3):
            return "critical"
        if complexity >= max(threshold + 10, threshold * 2):
            return "high"
        if complexity >= threshold + 5:
            return "medium"
        return "low"

    def _format_description(self, nloc: int, complexity: int, threshold: int) -> str:
        return (
            f"Cyclomatic complexity {complexity} exceeds threshold {threshold}. "
            f"NLOC: {nloc}."
        )

    def _parse_function_name(self, name_attr: str) -> tuple[str, str, Optional[int]]:
        func_name = name_attr
        file_path = ""
        line_start = None

        if " at " in name_attr:
            func_part, location_part = name_attr.rsplit(" at ", 1)
            func_name = func_part.strip()
            if ":" in location_part:
                path_part, line_part = location_part.rsplit(":", 1)
                file_path = path_part
                try:
                    line_start = int(line_part)
                except ValueError:
                    line_start = None
            else:
                file_path = location_part

        return func_name or "unknown", file_path, line_start
