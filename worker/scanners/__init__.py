"""
Bull's Eye - Scanner implementations
"""

from typing import List
from pathlib import Path
from .base import BaseScanner, ScannerFinding, ScannerResult, ScannerType
from .gitleaks import GitleaksScanner
from .semgrep import SemgrepScanner
from .python_scanners import RuffScanner, BanditScanner, PipAuditScanner
from .go_scanners import GolangciLintScanner, GosecScanner
from .rust_scanners import ClippyScanner, CargoAuditScanner
from .js_scanners import EslintScanner, NpmAuditScanner
from .trivy import TrivyScanner


def get_universal_scanners(repo_path: Path) -> List[BaseScanner]:
    """Get scanners that run on the whole repository."""
    return [
        GitleaksScanner(repo_path),
        SemgrepScanner(repo_path),
        TrivyScanner(repo_path),
    ]


def get_scanner_for_language(language: str, repo_path: Path) -> List[BaseScanner]:
    """Get language-specific scanners."""
    scanners = {
        "python": [RuffScanner(repo_path), BanditScanner(repo_path)],
        "javascript": [EslintScanner(repo_path)],
        "typescript": [EslintScanner(repo_path)],
        "go": [GolangciLintScanner(repo_path), GosecScanner(repo_path)],
        "rust": [ClippyScanner(repo_path)],
    }
    return scanners.get(language.lower(), [])


__all__ = [
    "BaseScanner",
    "ScannerFinding",
    "ScannerResult",
    "ScannerType",
    "GitleaksScanner",
    "SemgrepScanner",
    "RuffScanner",
    "BanditScanner",
    "PipAuditScanner",
    "GolangciLintScanner",
    "GosecScanner",
    "ClippyScanner",
    "CargoAuditScanner",
    "EslintScanner",
    "NpmAuditScanner",
    "TrivyScanner",
    "get_universal_scanners",
    "get_scanner_for_language",
]
