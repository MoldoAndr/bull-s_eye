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
    {"id": "deepseek-r1:70b", "name": "DeepSeek R1 70B", "description": "Best for complex reasoning and analysis"},
    {"id": "deepseek-r1:32b", "name": "DeepSeek R1 32B", "description": "Fast reasoning model"},
    {"id": "deepseek-r1:14b", "name": "DeepSeek R1 14B", "description": "Lightweight reasoning model"},
    {"id": "deepseek-r1:8b", "name": "DeepSeek R1 8B", "description": "Fastest reasoning model"},
    {"id": "deepseek-r1:1.5b", "name": "DeepSeek R1 1.5B", "description": "Ultra-light reasoning"},
    {"id": "deepseek-v3:671b", "name": "DeepSeek V3 671B", "description": "Most powerful model"},
    {"id": "deepseek-v3.1:671b", "name": "DeepSeek V3.1 671B", "description": "Latest DeepSeek flagship"},
    {"id": "qwq:32b", "name": "QwQ 32B", "description": "Strong reasoning capabilities"},
    {"id": "llama3.3:70b", "name": "Llama 3.3 70B", "description": "Meta's latest large model"},
    {"id": "llama3.2:latest", "name": "Llama 3.2", "description": "Versatile general model"},
    {"id": "llama3.1:405b", "name": "Llama 3.1 405B", "description": "Largest Llama model"},
    {"id": "llama3.1:70b", "name": "Llama 3.1 70B", "description": "High-quality large model"},
    {"id": "gemma2:27b", "name": "Gemma 2 27B", "description": "Google's efficient model"},
    {"id": "gemma3:27b", "name": "Gemma 3 27B", "description": "Latest Google model"},
    {"id": "qwen2.5:72b", "name": "Qwen 2.5 72B", "description": "Alibaba's flagship model"},
    {"id": "qwen2.5-coder:32b", "name": "Qwen 2.5 Coder 32B", "description": "Specialized for code"},
    {"id": "mistral:7b", "name": "Mistral 7B", "description": "Fast and efficient"},
    {"id": "mixtral:8x7b", "name": "Mixtral 8x7B", "description": "MoE architecture"},
    {"id": "mixtral:8x22b", "name": "Mixtral 8x22B", "description": "Large MoE model"},
    {"id": "command-r:35b", "name": "Command R 35B", "description": "Cohere's RAG model"},
    {"id": "command-r-plus:104b", "name": "Command R+ 104B", "description": "Cohere's largest model"},
    {"id": "phi4:14b", "name": "Phi-4 14B", "description": "Microsoft's efficient model"},
    {"id": "wizardlm2:8x22b", "name": "WizardLM2 8x22B", "description": "Instruction-tuned MoE"},
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
        default="deepseek-r1:70b",
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
    api_key: Optional[str] = Field(
        default=None,
        description="Optional API key for authentication"
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
