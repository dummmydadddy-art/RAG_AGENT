"""
src/web/config.py

Configuration settings for the ChatGPT-style Web Interface API Gateway.
Supports environment variable overrides and resolves absolute repository paths.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# Root repository anchor: d:\RAG-Agent
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class WebConfig:
    """Runtime configuration for FastAPI Gateway and associated subsystems."""

    host: str = os.getenv("WEB_HOST", "127.0.0.1")
    port: int = int(os.getenv("WEB_PORT", "8080"))

    # Ollama Local LLM Daemon
    ollama_url: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    model: str = os.getenv("OLLAMA_MODEL", "stem-coder-expert:latest")
    ollama_timeout_seconds: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60.0"))

    # SQLite Databases
    vectors_db_path: Path = Path(
        os.getenv("VECTORS_DB_PATH", str(REPO_ROOT / "backend" / "storage" / "vectors.sqlite"))
    )
    chat_history_db_path: Path = Path(
        os.getenv("CHAT_HISTORY_DB_PATH", str(REPO_ROOT / "backend" / "storage" / "chat_history.sqlite"))
    )

    # Win32 Sandbox Constraints
    max_memory_mb: int = int(os.getenv("SANDBOX_MAX_MEMORY_MB", "256"))
    sandbox_timeout_seconds: float = float(os.getenv("SANDBOX_TIMEOUT_SECONDS", "5.0"))

    # Static UI Files
    static_dir: Path = Path(
        os.getenv("STATIC_DIR", str(REPO_ROOT / "src" / "web" / "static"))
    )

    # Hardware Budget Ceilings
    vram_budget_gb: float = 4.0
    ram_budget_gb: float = 15.0
    php_memory_limit_mb: int = 128


# Global default configuration instance
_CONFIG = WebConfig()


def get_config() -> WebConfig:
    """Returns the singleton WebConfig instance."""
    return _CONFIG
