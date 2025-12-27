"""
Bull's Eye - Component Detector
Intelligent detection of code components in a repository
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict
import structlog

from config import settings

logger = structlog.get_logger()

# File extensions for each language
LANGUAGE_EXTENSIONS = {
    "python": {".py", ".pyx", ".pyi"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
    "typescript": {".ts", ".tsx"},
    "go": {".go"},
    "rust": {".rs"},
    "java": {".java"},
    "c": {".c", ".h"},
    "cpp": {".cpp", ".hpp", ".cc", ".cxx", ".hxx"},
    "ruby": {".rb"},
    "php": {".php"},
    "shell": {".sh", ".bash", ".zsh"},
    "yaml": {".yml", ".yaml"},
    "json": {".json"},
    "markdown": {".md", ".markdown"},
}

# Inverse mapping: extension to language
EXTENSION_TO_LANGUAGE = {}
for lang, exts in LANGUAGE_EXTENSIONS.items():
    for ext in exts:
        EXTENSION_TO_LANGUAGE[ext] = lang

# Directories to skip
SKIP_DIRECTORIES = {
    "node_modules", ".git", ".svn", ".hg", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".tox", ".nox", "venv", ".venv", "env", ".env",
    "dist", "build", "target", "vendor", ".cargo", ".rustup",
    "coverage", ".coverage", "htmlcov", ".nyc_output",
    ".idea", ".vscode", ".vs", ".DS_Store",
    "eggs", "*.egg-info", "site-packages",
}

# Component type markers
COMPONENT_MARKERS = {
    "service": ["main.py", "main.go", "main.rs", "index.ts", "index.js", "app.py", "server.py"],
    "library": ["__init__.py", "lib.rs", "mod.rs", "index.ts"],
    "config": ["config.py", "config.ts", "config.go", "settings.py", ".env.example"],
    "test": ["test_", "_test.py", "_test.go", ".test.ts", ".spec.ts", ".test.js", ".spec.js"],
    "api": ["api/", "routes/", "handlers/", "controllers/", "endpoints/"],
    "model": ["models/", "entities/", "schemas/", "types/"],
    "util": ["utils/", "helpers/", "common/", "shared/", "lib/"],
}


class ComponentDetector:
    """Detect logical components in a codebase."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path)
        self.logger = structlog.get_logger().bind(component="detector")
    
    def detect_components(self) -> List[Dict[str, Any]]:
        """
        Detect components in the repository.
        Returns list of component dictionaries.
        """
        components = []
        
        # First, identify the primary language
        language_counts = self._count_languages()
        primary_language = max(language_counts, key=language_counts.get) if language_counts else "unknown"
        
        self.logger.info(
            "Language detection complete",
            languages=language_counts,
            primary=primary_language
        )
        
        # Get top-level directories as potential components
        top_level_dirs = self._get_component_candidates()
        
        for dir_path in top_level_dirs:
            rel_path = dir_path.relative_to(self.repo_path)
            
            # Skip non-code directories
            if self._should_skip_directory(dir_path):
                continue
            
            # Analyze the directory
            component = self._analyze_directory(dir_path, rel_path)
            if component and component.get("file_count", 0) > 0:
                components.append(component)
        
        # If no components found, treat root as single component
        if not components:
            root_component = self._analyze_directory(self.repo_path, Path("."))
            if root_component:
                root_component["name"] = self.repo_path.name
                components.append(root_component)
        
        self.logger.info("Component detection complete", component_count=len(components))
        return components
    
    def _count_languages(self) -> Dict[str, int]:
        """Count files by programming language."""
        counts = defaultdict(int)
        
        for root, dirs, files in os.walk(self.repo_path):
            # Filter out skip directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES]
            
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in EXTENSION_TO_LANGUAGE:
                    counts[EXTENSION_TO_LANGUAGE[ext]] += 1
        
        return dict(counts)
    
    def _get_component_candidates(self) -> List[Path]:
        """Get candidate directories for components."""
        candidates = []
        
        # Check src/, lib/, packages/, apps/ first
        common_roots = ["src", "lib", "packages", "apps", "pkg", "cmd", "internal"]
        
        for root_name in common_roots:
            root_dir = self.repo_path / root_name
            if root_dir.is_dir():
                # Add subdirectories as components
                for subdir in root_dir.iterdir():
                    if subdir.is_dir() and not self._should_skip_directory(subdir):
                        candidates.append(subdir)
        
        # If no common roots, use top-level directories
        if not candidates:
            for item in self.repo_path.iterdir():
                if item.is_dir() and not self._should_skip_directory(item):
                    candidates.append(item)
        
        return candidates
    
    def _should_skip_directory(self, dir_path: Path) -> bool:
        """Check if a directory should be skipped."""
        dir_name = dir_path.name
        
        # Skip hidden directories
        if dir_name.startswith("."):
            return True
        
        # Skip known non-code directories
        if dir_name in SKIP_DIRECTORIES:
            return True
        
        # Skip if matches pattern
        for pattern in SKIP_DIRECTORIES:
            if "*" in pattern and dir_name.endswith(pattern.replace("*", "")):
                return True
        
        return False
    
    def _analyze_directory(self, dir_path: Path, rel_path: Path) -> Optional[Dict[str, Any]]:
        """Analyze a directory and create component info."""
        files = []
        language_counts = defaultdict(int)
        total_lines = 0
        
        for root, dirs, filenames in os.walk(dir_path):
            # Filter out skip directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES]
            
            for filename in filenames:
                file_path = Path(root) / filename
                ext = file_path.suffix.lower()
                
                if ext in EXTENSION_TO_LANGUAGE:
                    language = EXTENSION_TO_LANGUAGE[ext]
                    language_counts[language] += 1
                    
                    try:
                        stat = file_path.stat()
                        size_kb = stat.st_size / 1024
                        
                        # Skip files that are too large
                        if size_kb > settings.max_file_size_kb:
                            continue
                        
                        # Count lines
                        try:
                            line_count = sum(1 for _ in open(file_path, 'rb'))
                        except:
                            line_count = 0
                        
                        total_lines += line_count
                        
                        files.append({
                            "path": str(file_path.relative_to(self.repo_path)),
                            "language": language,
                            "size_bytes": stat.st_size,
                            "line_count": line_count,
                        })
                    except Exception as e:
                        self.logger.warning(f"Error processing file {file_path}: {e}")
        
        if not files:
            return None
        
        # Determine primary language
        primary_language = max(language_counts, key=language_counts.get) if language_counts else "unknown"
        
        # Determine component type
        component_type = self._determine_component_type(dir_path, files)
        
        return {
            "name": rel_path.name if rel_path.name != "." else dir_path.name,
            "path": str(rel_path),
            "full_path": str(dir_path),
            "component_type": component_type,
            "language": primary_language,
            "file_count": len(files),
            "line_count": total_lines,
            "files": files[:settings.max_files_per_component],  # Limit files
            "language_breakdown": dict(language_counts),
        }
    
    def _determine_component_type(self, dir_path: Path, files: List[Dict]) -> str:
        """Determine the type of component based on contents."""
        dir_name = dir_path.name.lower()
        
        # Check directory name first
        for comp_type, markers in COMPONENT_MARKERS.items():
            for marker in markers:
                if marker.endswith("/"):
                    if dir_name == marker.rstrip("/"):
                        return comp_type
        
        # Check for marker files
        file_names = {Path(f["path"]).name.lower() for f in files}
        
        for comp_type, markers in COMPONENT_MARKERS.items():
            for marker in markers:
                if not marker.endswith("/"):
                    # Check exact match or prefix match
                    for fn in file_names:
                        if fn == marker or fn.startswith(marker) or marker in fn:
                            return comp_type
        
        # Check for test files
        test_count = sum(1 for f in files if self._is_test_file(f["path"]))
        if test_count > len(files) * 0.5:
            return "test"
        
        return "module"
    
    def _is_test_file(self, file_path: str) -> bool:
        """Check if a file is a test file."""
        path = Path(file_path)
        name = path.stem.lower()
        
        test_patterns = ["test_", "_test", ".test", ".spec", "tests"]
        return any(p in name for p in test_patterns)
    
    def get_files_for_component(self, component: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get list of files for a component."""
        return component.get("files", [])
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """Read file content."""
        full_path = self.repo_path / file_path
        try:
            return full_path.read_text(errors='ignore')
        except Exception as e:
            self.logger.warning(f"Failed to read file {file_path}: {e}")
            return None
