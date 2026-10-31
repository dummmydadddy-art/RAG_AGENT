"""
src/web/app.py

Main FastAPI application for the ChatGPT-Style Web Interface Gateway:
- Configures CORS middleware for local frontend development
- Mounts API routers under /api: /chat, /execute, /lessons, /conversations, /health
- Manages startup lifecycle (chat_history.sqlite table initialization)
- Serves static SPA frontend from src/web/static if directory exists
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.web.config import get_config
from src.web.database import init_chat_db
from src.web.routes.chat import router as chat_router
from src.web.routes.conversations import router as conversations_router
from src.web.routes.execute import router as execute_router
from src.web.routes.health import router as health_router
from src.web.routes.learning import router as learning_router
from src.web.routes.lessons import router as lessons_router

logger = logging.getLogger("web.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Initializes SQLite chat store and verifies database connectivity on startup.
    """
    logger.info("Initializing ChatGPT Web Interface API Gateway...")
    init_chat_db()
    yield
    logger.info("Shutting down API Gateway.")


def create_app() -> FastAPI:
    """Factory creating and configuring the FastAPI instance."""
    cfg = get_config()

    app = FastAPI(
        title="RAG Agent ChatGPT Interface API Gateway",
        description="FastAPI gateway with SSE chat streaming, polyglot Win32 sandbox, and RAG/PhysMath telemetry.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 1. CORS Configuration (allow all origins for local dev)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Mount API Routes under /api
    app.include_router(chat_router, prefix="/api")
    app.include_router(execute_router, prefix="/api")
    app.include_router(lessons_router, prefix="/api")
    app.include_router(conversations_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(learning_router, prefix="/api")

    # 3. Mount Static Files for Frontend SPA
    static_path = cfg.static_dir
    static_path.mkdir(parents=True, exist_ok=True)

    # If an index.html does not yet exist, create a clean placeholder until Frontend Worker finishes
    index_file = static_path / "index.html"
    if not index_file.exists():
        placeholder_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>RAG Agent - ChatGPT Interface</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .card { background: #1e293b; padding: 2rem; border-radius: 0.75rem; border: 1px solid #334155; text-align: center; max-width: 480px; }
        h1 { font-size: 1.5rem; margin-bottom: 0.5rem; color: #38bdf8; }
        p { color: #94a3b8; font-size: 0.95rem; }
        .badge { display: inline-block; background: #0369a1; color: #e0f2fe; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; margin-top: 1rem; }
    </style>
</head>
<body>
    <div class="card">
        <h1>STEM Coder Expert Gateway</h1>
        <p>FastAPI backend gateway is operational. Static SPA assets will be populated by Frontend Worker.</p>
        <span class="badge">API Gateway Port: 8080 Active</span>
    </div>
</body>
</html>"""
        index_file.write_text(placeholder_html, encoding="utf-8")

    # Mount static assets explicitly under /static
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static_assets")
    # Mount root for SPA index.html and root fallbacks
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static_root")

    return app


# Default app instance for ASGI servers (uvicorn src.web.app:app)
app = create_app()
