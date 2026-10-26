from typing import Any, Dict, List, Optional
from rag_adapter.interface import RagAdapter
from rag_adapter.models import Doc, Hit, LessonStatus


class StubBackend(RagAdapter):
    """
    Thread-safe in-memory RAG backend stub for fast unit testing and contract parity checks.
    """

    def __init__(self) -> None:
        # structure: {collection_name: {doc_id: Doc}}
        self._collections: Dict[str, Dict[str, Doc]] = {
            "knowledge": {},
            "lessons": {},
            "traces": {},
        }

    def search(
        self,
        query: str,
        collections: List[str],
        filters: Optional[Dict[str, Any]] = None,
        k: int = 5,
    ) -> List[Hit]:
        hits: List[Hit] = []
        tokens = query.lower().split()

        for coll in collections:
            docs = self._collections.get(coll, {})
            for doc_id, doc in docs.items():
                # Apply filters if provided
                if filters:
                    match = True
                    for f_key, f_val in filters.items():
                        if doc.metadata.get(f_key) != f_val:
                            match = False
                            break
                    if not match:
                        continue

                # Exclude retired lessons by default if searching lessons
                if coll == "lessons" and doc.metadata.get("status") == LessonStatus.RETIRED:
                    continue

                text_lower = doc.text.lower()
                # Compute simple lexical overlap score
                score = sum(1.0 for t in tokens if t in text_lower)
                # Boost if exact phrase in text
                if query.lower() in text_lower:
                    score += 2.0

                if score > 0 or not tokens:
                    hits.append(
                        Hit(
                            doc_id=doc.doc_id,
                            collection=doc.collection,
                            text=doc.text,
                            metadata=doc.metadata,
                            score=float(score),
                        )
                    )

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def upsert(
        self,
        collection: str,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if collection not in self._collections:
            self._collections[collection] = {}

        self._collections[collection][doc_id] = Doc(
            doc_id=doc_id,
            collection=collection,
            text=text,
            metadata=metadata or {},
        )

    def get(self, collection: str, doc_id: str) -> Optional[Doc]:
        coll = self._collections.get(collection, {})
        return coll.get(doc_id)

    def set_status(
        self,
        collection: str,
        doc_id: str,
        status: LessonStatus,
        reason: str = "",
    ) -> None:
        doc = self.get(collection, doc_id)
        if not doc:
            raise KeyError(f"Document {doc_id} not found in collection {collection}")

        doc.metadata["status"] = status
        if reason:
            doc.metadata["status_reason"] = reason

    def delete(self, collection: str, doc_id: str) -> None:
        if collection in self._collections and doc_id in self._collections[collection]:
            del self._collections[collection][doc_id]
