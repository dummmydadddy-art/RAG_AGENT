from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from rag_adapter.models import Doc, Hit, LessonStatus


class RagAdapter(ABC):
    """
    Backend-agnostic RAG adapter interface.
    Exposes unified search, upsert, get, status management, and delete across collections.
    """

    @abstractmethod
    def search(
        self,
        query: str,
        collections: List[str],
        filters: Optional[Dict[str, Any]] = None,
        k: int = 5,
    ) -> List[Hit]:
        """
        Search for documents across specified collections matching optional filters.
        """
        pass

    @abstractmethod
    def upsert(
        self,
        collection: str,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Insert or update a document in the target collection.
        """
        pass

    @abstractmethod
    def get(self, collection: str, doc_id: str) -> Optional[Doc]:
        """
        Retrieve a single document by collection and ID.
        """
        pass

    @abstractmethod
    def set_status(
        self,
        collection: str,
        doc_id: str,
        status: LessonStatus,
        reason: str = "",
    ) -> None:
        """
        Update the lifecycle status of a document (e.g. lesson).
        """
        pass

    @abstractmethod
    def delete(self, collection: str, doc_id: str) -> None:
        """
        Remove a document from the collection.
        """
        pass
