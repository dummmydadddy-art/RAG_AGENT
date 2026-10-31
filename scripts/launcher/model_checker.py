"""
scripts/launcher/model_checker.py

Ollama daemon and model availability verification for RAG-Agent:
- Probes Ollama HTTP API (port 11434)
- Automatically spawns 'ollama serve' in background if offline
- Ensures custom fine-tuned model 'stem-coder-expert:latest' is registered
- Automatically builds 'stem-coder-expert:latest' from Modelfile and GGUF weights if needed
- Handles fallback to 'qwen2.5-coder:1.5b' and ensures 'nomic-embed-text:latest' embedding model
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from scripts.launcher.preflight import detect_ollama

PRIMARY_CODER_MODEL = "stem-coder-expert:latest"
FALLBACK_CODER_MODEL = "qwen2.5-coder:1.5b"
EMBEDDING_MODEL = "nomic-embed-text:latest"


@dataclass
class ModelCheckResult:
    """Outcome of Ollama daemon and model availability verification."""

    online: bool
    models: List[str] = field(default_factory=list)
    active_coder_model: Optional[str] = None
    has_embedding_model: bool = False
    started_by_us: bool = False
    process: Optional[subprocess.Popen] = None
    error_message: Optional[str] = None


def probe_ollama_daemon(
    host: str = "127.0.0.1", port: int = 11434, timeout: float = 2.0
) -> bool:
    """Probes the Ollama daemon HTTP endpoint to determine if it is responsive."""
    url = f"http://{host}:{port}/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RAG-Agent-Launcher"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def fetch_ollama_models(
    host: str = "127.0.0.1", port: int = 11434, timeout: float = 3.0
) -> List[str]:
    """Fetches list of registered model tags from Ollama daemon."""
    url = f"http://{host}:{port}/api/tags"
    req = urllib.request.Request(url, headers={"User-Agent": "RAG-Agent-Launcher"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = []
            for item in data.get("models", []):
                name = item.get("name") or item.get("model")
                if name:
                    models.append(name)
            return models
    except Exception:
        return []


def _has_model(models: List[str], target: str) -> bool:
    """Helper checking if target or target:latest is in model list."""
    target_base = target.split(":")[0]
    for m in models:
        if m == target or m == f"{target}:latest" or m.startswith(f"{target_base}:"):
            return True
    return False


def ensure_ollama_and_models(
    workspace_root: Path,
    ollama_path: Optional[Path] = None,
    host: str = "127.0.0.1",
    port: int = 11434,
) -> ModelCheckResult:
    """
    Ensures Ollama daemon is running and required models are available.
    """
    resolved_ollama = ollama_path
    if not resolved_ollama:
        detected = detect_ollama()
        resolved_ollama = detected.path or Path("ollama")

    started_by_us = False
    spawned_proc: Optional[subprocess.Popen] = None

    # 1. Probe daemon
    if not probe_ollama_daemon(host, port):
        print(f"[*] Ollama daemon is offline on port {port}. Launching 'ollama serve'...")
        cmd = [str(resolved_ollama), "serve"]
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            spawned_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            started_by_us = True
        except Exception as e:
            return ModelCheckResult(
                online=False,
                error_message=f"Failed to launch 'ollama serve': {e}",
            )

        # Poll until online (up to 15s)
        ready = False
        for _ in range(30):
            time.sleep(0.5)
            if probe_ollama_daemon(host, port):
                ready = True
                break

        if not ready:
            return ModelCheckResult(
                online=False,
                started_by_us=started_by_us,
                process=spawned_proc,
                error_message=f"Ollama daemon did not respond on port {port} after 15 seconds.",
            )
        print("[+] Ollama daemon is now online.")
    else:
        print(f"[+] Ollama daemon is online on port {port}.")

    # 2. Check models
    models = fetch_ollama_models(host, port)
    models_dir = workspace_root / "models"
    gguf_path = models_dir / "stem-coder-expert-q4_k_m.gguf"
    modelfile_path = models_dir / "Modelfile"

    # Check primary model
    if not _has_model(models, PRIMARY_CODER_MODEL):
        if gguf_path.exists() and modelfile_path.exists():
            print(f"[*] Creating '{PRIMARY_CODER_MODEL}' from {modelfile_path.name}...")
            create_res = subprocess.run(
                [str(resolved_ollama), "create", PRIMARY_CODER_MODEL, "-f", str(modelfile_path)],
                cwd=str(models_dir),
                capture_output=True,
                text=True,
                timeout=180,
            )
            if create_res.returncode == 0:
                print(f"[+] Model '{PRIMARY_CODER_MODEL}' registered successfully.")
                models = fetch_ollama_models(host, port)
            else:
                print(f"[!] Warning: 'ollama create' returned non-zero:\n{create_res.stderr}")
        else:
            # Fall back to pulling fallback model
            if not _has_model(models, FALLBACK_CODER_MODEL):
                print(f"[*] Pulling fallback coder model '{FALLBACK_CODER_MODEL}'...")
                subprocess.run(
                    [str(resolved_ollama), "pull", FALLBACK_CODER_MODEL],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                models = fetch_ollama_models(host, port)

    # Check embedding model
    if not _has_model(models, EMBEDDING_MODEL):
        print(f"[*] Pulling embedding model '{EMBEDDING_MODEL}'...")
        subprocess.run(
            [str(resolved_ollama), "pull", "nomic-embed-text"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        models = fetch_ollama_models(host, port)

    # Determine active coder model
    active_model: Optional[str] = None
    if _has_model(models, PRIMARY_CODER_MODEL):
        active_model = PRIMARY_CODER_MODEL
    elif _has_model(models, FALLBACK_CODER_MODEL):
        active_model = FALLBACK_CODER_MODEL
    elif models:
        active_model = models[0]

    has_embedding = _has_model(models, EMBEDDING_MODEL)

    return ModelCheckResult(
        online=True,
        models=models,
        active_coder_model=active_model,
        has_embedding_model=has_embedding,
        started_by_us=started_by_us,
        process=spawned_proc,
    )
