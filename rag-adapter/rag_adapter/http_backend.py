import os
from typing import Any, Dict, List, Optional
import httpx
from rag_adapter.interface import RagAdapter
from rag_adapter.models import Doc, Hit, LessonStatus
from rag_adapter.sqlite_backend import LocalSqliteRagBackend


class HttpRagBackend(RagAdapter):
    """
    HTTP REST client adapter for the PHP RAG engine service,
    with automatic local SQLite fallback if the remote/local HTTP daemon is unavailable.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 10.0,
        sqlite_fallback: Optional[LocalSqliteRagBackend] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("LMS_SERVICE_API_KEY") or os.getenv("RAG_API_KEY") or ""
        self.timeout = timeout
        self.fallback = sqlite_fallback or LocalSqliteRagBackend()

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key
        return headers

    def search(
        self,
        query: str,
        collections: List[str],
        filters: Optional[Dict[str, Any]] = None,
        k: int = 5,
    ) -> List[Hit]:
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
                        hits.append(
                            Hit(
                                doc_id=str(r.get("id") or r.get("material_id") or ""),
                                collection=str(r.get("collection") or "knowledge"),
                                text=str(r.get("content") or r.get("title") or ""),
                                metadata=r.get("metadata") or {},
                                score=float(r.get("similarity") or r.get("score") or 0.0),
                            )
                        )
                    if hits:
                        return hits
        except Exception:
            # Fall back to local SQLite on network or connection errors
            pass

        return self.fallback.search(query, collections, filters, k)

    def upsert(
        self,
        collection: str,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Always update local sqlite storage
        self.fallback.upsert(collection, doc_id, text, metadata)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                client.post(
                    f"{self.base_url}/api/rag/ingest",
                    json={
                        "material_id": doc_id,
                        "collection": collection,
                        "content": text,
                        "metadata": metadata or {},
                    },
                    headers=self._get_headers(),
                )
        except Exception:
            pass

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
