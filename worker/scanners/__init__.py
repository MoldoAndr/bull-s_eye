"""
Bull's Eye - Scanner implementations
"""

from typing import List
from .base import BaseScanner, ScannerFinding, ScannerResult, ScannerType
from .gitleaks import GitleaksScanner
from .semgrep import SemgrepScanner
from .python_scanners import RuffScanner, BanditScanner, PipAuditScanner
from .go_scanners import GolangciLintScanner, GosecScanner
from .rust_scanners import ClippyScanner, CargoAuditScanner
from .js_scanners import EslintScanner, NpmAuditScanner
from .trivy import TrivyScanner


def get_universal_scanners() -> List[BaseScanner]:
    """Get scanners that run on the whole repository."""
    return [
        GitleaksScanner(),
        SemgrepScanner(),
        TrivyScanner(),
    ]


def get_scanner_for_language(language: str) -> List[BaseScanner]:
    """Get language-specific scanners."""
    scanners = {
        "python": [RuffScanner(), BanditScanner()],
        "javascript": [EslintScanner()],
        "typescript": [EslintScanner()],
        "go": [GolangciLintScanner(), GosecScanner()],
        "rust": [ClippyScanner()],
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
