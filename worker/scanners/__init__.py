"""
Bull's Eye - Scanner implementations
"""

from typing import List
from pathlib import Path
from .base import BaseScanner, ScannerFinding, ScannerResult, ScannerType
from .gitleaks import GitleaksScanner
from .opengrep import OpengrepScanner
from .osv_scanner import OSVScanner
from .lizard import LizardScanner
from .python_scanners import RuffScanner, BanditScanner, PipAuditScanner
from .go_scanners import GolangciLintScanner, GosecScanner
from .rust_scanners import ClippyScanner, CargoAuditScanner
from .js_scanners import BiomeScanner, EslintScanner, NpmAuditScanner
from .trivy import TrivyScanner
from config import settings


def get_universal_scanners(repo_path: Path) -> List[BaseScanner]:
    """Get scanners that run on the whole repository."""
    scanners: List[BaseScanner] = [GitleaksScanner(repo_path), TrivyScanner(repo_path)]

    if settings.enable_opengrep:
        scanners.append(OpengrepScanner(repo_path))
    if settings.enable_osv_scanner:
        scanners.append(OSVScanner(repo_path))
    if settings.enable_lizard:
        scanners.append(LizardScanner(repo_path))

    return scanners


def get_scanner_for_language(language: str, repo_path: Path) -> List[BaseScanner]:
    """Get language-specific scanners."""
    scanners = {
        "python": [RuffScanner(repo_path), BanditScanner(repo_path)],
        "javascript": [BiomeScanner(repo_path)] if settings.enable_biome else [],
        "typescript": [BiomeScanner(repo_path)] if settings.enable_biome else [],
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
    "OpengrepScanner",
    "OSVScanner",
    "LizardScanner",
    "RuffScanner",
    "BanditScanner",
    "PipAuditScanner",
    "GolangciLintScanner",
    "GosecScanner",
    "ClippyScanner",
    "CargoAuditScanner",
    "BiomeScanner",
    "EslintScanner",
    "NpmAuditScanner",
    "TrivyScanner",
    "get_universal_scanners",
    "get_scanner_for_language",
]
