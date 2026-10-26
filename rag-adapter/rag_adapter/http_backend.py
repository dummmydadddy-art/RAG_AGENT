import json
import os
from typing import Any, Dict, List, Optional
import httpx
from rag_adapter.interface import RagAdapter
from rag_adapter.models import Doc, Hit, LessonStatus
from rag_adapter.sqlite_backend import LocalSqliteRagBackend


class HttpRagBackend(RagAdapter):
    """
    HTTP REST client adapter for the PHP RAG engine service,
    with automatic local SQLite fallback (disabled when strict_mode is True).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        sqlite_fallback: Optional[LocalSqliteRagBackend] = None,
        strict_mode: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("LMS_SERVICE_API_KEY") or os.getenv("RAG_API_KEY") or "YOUR_SERVICE_API_KEY"
        self.timeout = timeout
        self.fallback = sqlite_fallback or LocalSqliteRagBackend()
        self.strict_mode = strict_mode or (os.getenv("RAG_STRICT_MODE", "0").lower() in ("1", "true", "yes"))

    @property
    def backend_identity(self) -> str:
        if self.strict_mode:
            return f"http_rag_engine_strict ({self.base_url} PHP 8.3 + nomic-embed-text)"
        return f"http_rag_engine ({self.base_url} with sqlite_fallback)"

    @property
    def retrieval_mode(self) -> str:
        return "hybrid_rrf_dense_sparse"

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key
            headers["X-Service-Key"] = self.api_key
        return headers

    def search(
        self,
        query: str,
        collections: List[str],
        filters: Optional[Dict[str, Any]] = None,
        k: int = 5,
    ) -> List[Hit]:
        http_error: Optional[Exception] = None
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/api/rag/search",
                    json={"query": query, "limit": k, "collections": collections, "filters": filters or {}},
                    headers=self._get_headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    hits: List[Hit] = []
                    for r in results:
                        raw_meta = r.get("metadata")
                        if isinstance(raw_meta, str):
                            try:
                                parsed_meta = json.loads(raw_meta)
                            except Exception:
                                parsed_meta = {"raw": raw_meta}
                        elif isinstance(raw_meta, dict):
                            parsed_meta = raw_meta
                        else:
                            parsed_meta = {}

                        hits.append(
                            Hit(
                                doc_id=str(r.get("material_id") or r.get("id") or ""),
                                collection=str(r.get("collection") or "knowledge"),
                                text=str(r.get("content") or r.get("title") or ""),
                                metadata=parsed_meta,
                                score=float(r.get("similarity") or r.get("score") or 0.0),
                            )
                        )
                    if hits:
                        return hits
                else:
                    if self.strict_mode:
                        raise RuntimeError(f"HTTP search returned non-200 status {resp.status_code}: {resp.text}")
        except Exception as e:
            http_error = e
            if self.strict_mode:
                raise RuntimeError(f"HTTP search failed in strict mode: {e}") from e

        if self.strict_mode:
            raise RuntimeError(f"Strict mode active: HTTP search returned zero results or encountered error: {http_error}")

        return self.fallback.search(query, collections, filters, k)

    def upsert(
        self,
        collection: str,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Always maintain local store for lessons/status lifecycle
        self.fallback.upsert(collection, doc_id, text, metadata)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/api/rag/ingest",
                    json={
                        "material_id": doc_id,
                        "title": (metadata or {}).get("title", doc_id),
                        "content": text,
                        "collection": collection,
                        "metadata": metadata or {},
                    },
                    headers=self._get_headers(),
                )
                if self.strict_mode and resp.status_code >= 400:
                    raise RuntimeError(f"HTTP ingest returned error {resp.status_code}: {resp.text}")
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"HTTP ingest failed in strict mode: {e}") from e

    def get(self, collection: str, doc_id: str) -> Optional[Doc]:
        return self.fallback.get(collection, doc_id)

    def set_status(
        self,
        collection: str,
        doc_id: str,
        status: LessonStatus,
        reason: str = "",
    ) -> None:
        self.fallback.set_status(collection, doc_id, status, reason)

    def delete(self, collection: str, doc_id: str) -> None:
        self.fallback.delete(collection, doc_id)
