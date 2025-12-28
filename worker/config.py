"""
Bull's Eye - Codebase Analysis Worker
Configuration settings using Pydantic
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
from pathlib import Path
import json


# Available Ollama Cloud Models
OLLAMA_CLOUD_MODELS = [
    {"id": "deepseek-v3.2:cloud", "name": "DeepSeek V3.2 Cloud", "description": "Latest DeepSeek model for strong reasoning"},
    {"id": "gpt-oss:120b-cloud", "name": "GPT-OSS 120B Cloud", "description": "Powerful open-source model for complex analysis"},
    {"id": "kimi-k2-thinking:cloud", "name": "Kimi K2 Thinking Cloud", "description": "Long-form reasoning and deep analysis"},
]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # SQLite Database
    database_path: Path = Field(
        default=Path("/app/data/bullseye.db"),
        description="SQLite database file path"
    )
    
    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    
    # Ollama Cloud API
    ollama_api_url: str = Field(
        default="https://ollama.com/api/chat",
        description="Ollama Cloud API URL"
    )
    ollama_api_key: str = Field(
        default="",
        description="Ollama Cloud API key (Bearer token)"
    )
    ollama_model: str = Field(
        default="deepseek-v3.2:cloud",
        description="Default Ollama model for analysis"
    )
    ollama_models: Optional[str] = Field(
        default=None,
        description="Override model list for UI (comma-separated or JSON array)"
    )
    ollama_timeout: int = Field(
        default=300,
        description="Timeout for Ollama API calls in seconds"
    )
    
    # Worker settings
    worker_concurrency: int = Field(
        default=2,
        description="Number of concurrent analysis tasks"
    )
    max_file_size_kb: int = Field(
        default=500,
        description="Maximum file size to analyze in KB"
    )
    max_repo_size_mb: int = Field(
        default=500,
        description="Maximum repository size to clone in MB"
    )
    
    # Paths
    repos_dir: Path = Field(
        default=Path("/app/repos"),
        description="Directory to store cloned repositories"
    )
    data_dir: Path = Field(
        default=Path("/app/data"),
        description="Directory for SQLite database and cache"
    )
    reports_dir: Path = Field(
        default=Path("/app/data/reports"),
        description="Directory for generated reports"
    )
    
    # Analysis settings
    analysis_timeout: int = Field(
        default=3600,
        description="Maximum time for a single job in seconds"
    )
    llm_request_delay: float = Field(
        default=1.0,
        description="Delay between sequential LLM requests (no parallel)"
    )
    enable_caching: bool = Field(
        default=True,
        description="Enable file/component caching"
    )
    max_files_per_component: int = Field(
        default=50,
        description="Maximum files per component for analysis"
    )
    enable_context_aware_analysis: bool = Field(
        default=False,
        description="Enable enhanced context-aware analysis with cross-file relationships"
    )
    max_context_files: int = Field(
        default=10,
        description="Maximum related files to include in context"
    )
    
    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # API settings
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_workers: int = Field(default=4)
    
    # Security
    api_key: str = Field(
        ...,
        description="API key required for authenticating requests to the Bull's Eye API"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()


def get_available_models() -> List[dict]:
    """Get list of available Ollama cloud models."""
    if settings.ollama_models:
        raw = settings.ollama_models.strip()
        if raw:
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list) and all(isinstance(item, dict) and "id" in item for item in parsed):
                        return parsed
                except json.JSONDecodeError:
                    pass

            model_ids = [item.strip() for item in raw.replace("\n", ",").split(",") if item.strip()]
            if model_ids:
                return [
                    {"id": model_id, "name": model_id, "description": "Custom model"}
                    for model_id in model_ids
                ]

    return OLLAMA_CLOUD_MODELS
