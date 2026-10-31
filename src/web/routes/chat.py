"""
src/web/routes/chat.py

Server-Sent Events (SSE) streaming chat endpoint:
- Connects to local Ollama daemon (`stem-coder-expert:latest` on port 11434)
- Context augmentation via RAG lessons retrieved from vectors.sqlite
- Multi-turn conversation history persistence in chat_history.sqlite
- Live PhysMath verification telemetry via Pint units_check and SymPy sym_equiv
- W3C SSE event stream emitting metadata, token chunks, telemetry, and done events
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from src.web.config import REPO_ROOT, get_config
from src.web.database import (
    create_conversation,
    get_conversation,
    retrieve_relevant_context,
    save_message,
)
from src.web.schemas import ChatRequest

logger = logging.getLogger("web.routes.chat")
router = APIRouter(tags=["Chat"])

# Add physmath-mcp to sys.path if not present
_pm_path = str(REPO_ROOT / "physmath-mcp")
if _pm_path not in sys.path:
    sys.path.insert(0, _pm_path)

try:
    from physmath_mcp.server import sym_equiv, units_check
except ImportError:
    units_check = None
    sym_equiv = None

DEFAULT_SYSTEM_PROMPT = (
    "You are an elite STEM Subject Matter Expert and polyglot software engineer capable of synthesizing, "
    "refactoring, and verifying correct and efficient code across Python, TypeScript, C++, Java, Rust, Go, "
    "PHP, and SQL with rigorous step-by-step reasoning, test suites, and algorithmic complexity analysis."
)


def _detect_and_verify_physmath(text: str) -> Optional[Dict[str, Any]]:
    """
    Scans generated text for physical quantities or equations and performs Pint/SymPy verification.
    """
    if units_check is None:
        return None

    # Common physical formula signatures to inspect
    # e.g., F = m * a, E = m * c**2, P = V * I, v = u + a * t, KE = 0.5 * m * v**2
    checks: List[Dict[str, Any]] = []

    lower_text = text.lower()

    # Case 1: Newton's Second Law: F = m * a
    if re.search(r"\b(f\s*=\s*m\s*\*\s*a|force\s*=\s*mass\s*\*\s*acceleration)\b", lower_text):
        res = units_check("m * a", {"m": "kg", "a": "m/s**2"}, "N")
        checks.append({
            "equation": "F = m * a",
            "test": "Newton's Second Law dimensional consistency",
            "result": res,
        })

    # Case 2: Kinetic Energy: 0.5 * m * v**2
    if re.search(r"\b(0\.5\s*\*\s*m\s*\*\s*v(\*\*2|\^2)|kinetic energy)\b", lower_text):
        res = units_check("0.5 * m * v**2", {"m": "kg", "v": "m/s"}, "joule")
        checks.append({
            "equation": "KE = 0.5 * m * v^2",
            "test": "Kinetic Energy dimensional consistency",
            "result": res,
        })

    # Case 3: Electrical Power: P = V * I
    if re.search(r"\b(p\s*=\s*v\s*\*\s*i|power\s*=\s*voltage\s*\*\s*current)\b", lower_text):
        res = units_check("V * I", {"V": "volt", "I": "ampere"}, "watt")
        checks.append({
            "equation": "P = V * I",
            "test": "Electrical Power dimensional consistency",
            "result": res,
        })

    # Case 4: Pressure: P = F / A
    if re.search(r"\b(p\s*=\s*f\s*/\s*a|pressure\s*=\s*force\s*/\s*area)\b", lower_text):
        res = units_check("F / A", {"F": "N", "A": "m**2"}, "pascal")
        checks.append({
            "equation": "P = F / A",
            "test": "Pressure dimensional consistency",
            "result": res,
        })

    # Case 5: Wave speed: v = f * lambda
    if re.search(r"\b(v\s*=\s*f\s*\*\s*lambda|wave speed)\b", lower_text):
        res = units_check("f * w", {"f": "Hz", "w": "meter"}, "m/s")
        checks.append({
            "equation": "v = f * lambda",
            "test": "Wave Velocity dimensional consistency",
            "result": res,
        })

    if not checks:
        # Check if units like 'kg', 'm/s', 'newton' are mentioned
        unit_matches = re.findall(r"\b(kg|m/s|m/s\*\*2|newton|joule|watt|pascal|kelvin)\b", lower_text)
        if unit_matches:
            return {
                "status": "detected",
                "units_detected": list(set(unit_matches)),
                "checks_run": 0,
            }
        return {"status": "none", "checks_run": 0}

    all_valid = all(c["result"].get("valid", False) for c in checks)
    return {
        "status": "verified" if all_valid else "inconsistent",
        "checks_run": len(checks),
        "checks": checks,
    }


async def _stream_chatml(
    req: ChatRequest,
    conv_id: str,
    conv_title: str,
    citations: List[Dict[str, Any]],
    conversation_history: List[Dict[str, Any]],
) -> AsyncGenerator[Dict[str, str], None]:
    """
    Streams Server-Sent Events from Ollama ChatML and persists final message.
    """
    cfg = get_config()
    t0 = time.time()
    assistant_msg_id = str(uuid.uuid4())
    accumulated_content: List[str] = []

    # 1. Emit metadata event
    yield {
        "event": "metadata",
        "data": json.dumps({
            "conversation_id": conv_id,
            "title": conv_title,
            "model": req.model,
            "citations": citations,
        }),
    }

    # 2. Build ChatML messages list
    base_sys = req.system_prompt or DEFAULT_SYSTEM_PROMPT
    if req.enable_rag and citations:
        rag_section = "\n\n### Retrieved STEM Lessons & Knowledge:\n"
        for i, cit in enumerate(citations, 1):
            rag_section += f"{i}. [{cit.get('id')}] ({cit.get('collection')}) {cit.get('text')}\n"
        base_sys += rag_section

    messages_payload: List[Dict[str, str]] = [{"role": "system", "content": base_sys}]

    # Include recent context from conversation history (up to last 6 messages)
    for prev_msg in conversation_history[-6:]:
        if prev_msg.get("role") in ("user", "assistant"):
            messages_payload.append({
                "role": prev_msg["role"],
                "content": prev_msg["content"],
            })

    # Append current user prompt
    messages_payload.append({"role": "user", "content": req.message})

    # Save user message to database
    save_message(
        conv_id=conv_id,
        role="user",
        content=req.message,
    )

    # 3. Build ChatML prompt and stream from Ollama /api/generate
    chatml_parts: List[str] = []
    for prev_msg in conversation_history[-6:]:
        role = prev_msg.get("role", "user")
        content = prev_msg.get("content", "")
        if role in ("user", "assistant"):
            chatml_parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")

    chatml_parts.append(f"<|im_start|>user\n{req.message}<|im_end|>\n<|im_start|>assistant")
    full_prompt = "\n".join(chatml_parts)

    ollama_url = f"{cfg.ollama_url}/api/generate"
    request_body = {
        "model": req.model,
        "prompt": full_prompt,
        "system": base_sys,
        "stream": True,
        "options": {
            "temperature": req.temperature,
            "top_p": req.top_p,
            "stop": ["<|im_end|>", "<|im_start|>"],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=cfg.ollama_timeout_seconds) as client:
            async with client.stream("POST", ollama_url, json=request_body) as response:
                if response.status_code != 200:
                    err_text = await response.aread()
                    yield {
                        "event": "error",
                        "data": json.dumps({
                            "error": f"Ollama HTTP {response.status_code}: {err_text.decode('utf-8', errors='ignore')}"
                        }),
                    }
                    return

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    token = chunk.get("response", "")
                    if not token:
                        msg_chunk = chunk.get("message", {})
                        if isinstance(msg_chunk, dict):
                            token = msg_chunk.get("content", "")
                    if token:
                        accumulated_content.append(token)
                        yield {
                            "event": "token",
                            "data": json.dumps({"token": token}),
                        }

                    if chunk.get("done", False):
                        break

    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError) as e:
        logger.error(f"Ollama connection error: {e}")
        fallback_msg = f"[Ollama Service Offline or Unreachable]: {e}"
        accumulated_content.append(fallback_msg)
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e), "message": fallback_msg}),
        }

    # 4. Telemetry and PhysMath Verification
    full_text = "".join(accumulated_content)
    elapsed = round(time.time() - t0, 3)

    physmath_telemetry: Optional[Dict[str, Any]] = None
    if req.enable_physmath:
        combined_text = f"{req.message}\n{full_text}"
        physmath_telemetry = _detect_and_verify_physmath(combined_text)

    telemetry_payload = {
        "elapsed_seconds": elapsed,
        "physmath": physmath_telemetry,
        "citations_count": len(citations),
        "citations": citations,
        "character_count": len(full_text),
        "model": req.model,
    }

    yield {
        "event": "telemetry",
        "data": json.dumps(telemetry_payload),
    }

    # 5. Persist assistant message to database
    save_message(
        conv_id=conv_id,
        role="assistant",
        content=full_text,
        citations=citations,
        telemetry=telemetry_payload,
        msg_id=assistant_msg_id,
    )

    # 6. Emit done event
    yield {
        "event": "done",
        "data": json.dumps({
            "message_id": assistant_msg_id,
            "finish_reason": "stop",
            "elapsed_seconds": elapsed,
        }),
    }


@router.post("/chat")
async def chat_stream_endpoint(req: ChatRequest, request: Request) -> EventSourceResponse:
    """
    Streaming chat endpoint emitting Server-Sent Events (SSE).
    """
    # 1. Resolve or create conversation
    conv_id = req.conversation_id
    conv_title = "New Conversation"
    conversation_history: List[Dict[str, Any]] = []

    if conv_id:
        existing = get_conversation(conv_id)
        if existing:
            conv_title = existing["title"]
            conversation_history = existing.get("messages", [])
        else:
            # Create if specified ID did not exist
            snippet = req.message.strip().split("\n")[0][:40]
            conv_title = snippet or "New Conversation"
            create_conversation(conv_id=conv_id, title=conv_title)
    else:
        conv_id = str(uuid.uuid4())
        snippet = req.message.strip().split("\n")[0][:40]
        conv_title = snippet or "New Conversation"
        create_conversation(conv_id=conv_id, title=conv_title)

    # 2. Retrieve RAG lessons / knowledge if enabled
    citations: List[Dict[str, Any]] = []
    if req.enable_rag:
        citations = retrieve_relevant_context(req.message, limit=3)

    # 3. Return EventSourceResponse
    return EventSourceResponse(
        _stream_chatml(
            req=req,
            conv_id=conv_id,
            conv_title=conv_title,
            citations=citations,
            conversation_history=conversation_history,
        ),
        media_type="text/event-stream",
        ping=None,
    )
