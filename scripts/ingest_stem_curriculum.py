#!/usr/bin/env python3
"""
scripts/ingest_stem_curriculum.py

Medallion Ingestion & Deduplication Pipeline for Expanded STEM Curriculum.
Ingests Class 4 to SME foundational and advanced science & math curricula into
the SQLite Vector RAG store.

Pipeline Stages:
- Bronze: Schema validation & normalization of raw curriculum items.
- Silver: 3-tier deduplication (Exact SHA-256, Fuzzy Jaccard, Semantic Collision).
- Gold: Persistence into SQLite vector store (rag_documents and material_chunks)
        with 'search_document: ' prefix for Ollama nomic-embed-text and row
        capping to safeguard PHP 128MB memory limit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import re
import struct
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "rag-adapter"))

from rag_adapter.sqlite_backend import LocalSqliteRagBackend

logger = logging.getLogger("ingest_stem_curriculum")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_CURRICULUM_PATH = ROOT / "data" / "stem_curriculum_expanded.json"
DEFAULT_DB_PATH = ROOT / "backend" / "storage" / "vectors.sqlite"


@dataclass
class CurriculumItem:
    """Core STEM Curriculum Item DTO."""
    id: str
    title: str
    domain: str  # maths, physics
    tier: str    # elementary, secondary, higher_secondary, sme
    grade_level: str
    concept: str
    example_problem: str
    solution_steps: str
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_formatted_document(self) -> str:
        """Render comprehensive readable text representation for vector indexing."""
        tags_str = ", ".join(self.tags)
        return (
            f"Title: {self.title}\n"
            f"Domain: {self.domain} | Tier: {self.tier} ({self.grade_level})\n"
            f"Tags: {tags_str}\n\n"
            f"Core Concept & Principles:\n{self.concept}\n\n"
            f"Problem Statement / Challenge:\n{self.example_problem}\n\n"
            f"Detailed Solution & Analytical Reasoning:\n{self.solution_steps}"
        )


# ============================================================================
# 1. BRONZE STAGE: VALIDATION & NORMALIZATION
# ============================================================================

class CurriculumBronzeStage:
    """Bronze Stage: Ingests raw JSON records, validates fields, and stages DTOs."""

    REQUIRED_FIELDS = {
        "id", "title", "domain", "tier", "grade_level",
        "concept", "example_problem", "solution_steps"
    }

    VALID_DOMAINS = {"maths", "physics"}
    VALID_TIERS = {"elementary", "secondary", "higher_secondary", "sme"}

    @classmethod
    def load_from_json(cls, file_path: Path) -> List[Dict[str, Any]]:
        """Loads raw JSON records from disk."""
        if not file_path.exists():
            raise FileNotFoundError(f"Curriculum file not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Curriculum JSON root must be a list of objects")
        return data

    @classmethod
    def validate_and_stage(cls, records: List[Dict[str, Any]]) -> List[CurriculumItem]:
        """Validates schema conformance and transforms raw dicts into CurriculumItem DTOs."""
        staged: List[CurriculumItem] = []
        for idx, rec in enumerate(records):
            missing = cls.REQUIRED_FIELDS - set(rec.keys())
            if missing:
                logger.warning("Bronze: Skipping record %d (ID: %s) missing keys: %s", idx, rec.get("id"), missing)
                continue

            domain = str(rec.get("domain", "")).strip().lower()
            tier = str(rec.get("tier", "")).strip().lower()

            if domain not in cls.VALID_DOMAINS:
                logger.warning("Bronze: Invalid domain '%s' in record %s", domain, rec.get("id"))
                continue
            if tier not in cls.VALID_TIERS:
                logger.warning("Bronze: Invalid tier '%s' in record %s", tier, rec.get("id"))
                continue

            item = CurriculumItem(
                id=str(rec["id"]).strip(),
                title=str(rec["title"]).strip(),
                domain=domain,
                tier=tier,
                grade_level=str(rec.get("grade_level", "")).strip(),
                concept=str(rec["concept"]).strip(),
                example_problem=str(rec["example_problem"]).strip(),
                solution_steps=str(rec["solution_steps"]).strip(),
                tags=[str(t).strip() for t in rec.get("tags", []) if str(t).strip()],
                metadata=rec.get("metadata", {}),
            )
            staged.append(item)

        logger.info("Bronze: Validated and staged %d of %d raw curriculum records", len(staged), len(records))
        return staged


def load_curriculum_dataset(path: Optional[Path] = None) -> List[CurriculumItem]:
    """Convenience loader for Bronze stage."""
    file_path = path or DEFAULT_CURRICULUM_PATH
    raw = CurriculumBronzeStage.load_from_json(file_path)
    return CurriculumBronzeStage.validate_and_stage(raw)


# ============================================================================
# 2. SILVER STAGE: 3-TIER DEDUPLICATION
# ============================================================================

class CurriculumSilverStage:
    """
    Silver Stage: 3-tier Deduplication Pipeline
    Tier 1: Exact Hash Deduplication (SHA-256 of normalized text)
    Tier 2: Fuzzy Jaccard Shingle Deduplication (>= threshold, default 0.82)
    Tier 3: Semantic Topic Key Collision (Domain + Tier + Normalized Title Key)
    """

    def __init__(
        self,
        fuzzy_jaccard_threshold: float = 0.82,
        shingle_size: int = 3,
    ) -> None:
        self.fuzzy_threshold = fuzzy_jaccard_threshold
        self.shingle_size = shingle_size

    @staticmethod
    def normalize_text(text: str) -> str:
        """Lowercases, strips punctuation, and collapses multiple whitespaces."""
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        return " ".join(cleaned.split())

    @classmethod
    def compute_exact_hash(cls, item: CurriculumItem) -> str:
        """SHA-256 fingerprint computed across core normalized fields."""
        norm_title = cls.normalize_text(item.title)
        norm_concept = cls.normalize_text(item.concept)
        norm_problem = cls.normalize_text(item.example_problem)
        combined = f"{norm_title}||{norm_concept}||{norm_problem}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def generate_shingles(self, text: str) -> Set[str]:
        """Creates word-level n-gram shingles for lexical Jaccard similarity."""
        words = self.normalize_text(text).split()
        if len(words) < self.shingle_size:
            return {" ".join(words)} if words else set()
        return {
            " ".join(words[i:i + self.shingle_size])
            for i in range(len(words) - self.shingle_size + 1)
        }

    @staticmethod
    def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
        """Computes Jaccard index between two shingle sets."""
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return intersection / union if union > 0 else 0.0

    @classmethod
    def compute_semantic_key(cls, item: CurriculumItem) -> str:
        """Canonical semantic key: domain + tier + alphanumeric title tokens."""
        norm_title = cls.normalize_text(item.title)
        tokens = sorted([w for w in norm_title.split() if len(w) > 3])
        title_key = "_".join(tokens[:5])
        return f"{item.domain}:{item.tier}:{title_key}"

    def deduplicate(self, items: List[CurriculumItem]) -> Tuple[List[CurriculumItem], Dict[str, int]]:
        """
        Executes sequential 3-tier deduplication.
        Returns:
            retained: List of unique CurriculumItems.
            stats: Dictionary of deduplication metrics.
        """
        retained: List[CurriculumItem] = []
        seen_exact_hashes: Set[str] = set()
        retained_shingles: List[Tuple[CurriculumItem, Set[str]]] = []
        seen_semantic_keys: Set[str] = set()

        stats = {
            "total_input": len(items),
            "tier1_exact_duplicates": 0,
            "tier2_fuzzy_duplicates": 0,
            "tier3_semantic_duplicates": 0,
            "retained": 0,
        }

        for item in items:
            # Tier 1: Exact Hash Deduplication
            item_hash = self.compute_exact_hash(item)
            if item_hash in seen_exact_hashes:
                stats["tier1_exact_duplicates"] += 1
                logger.debug("Silver: Tier 1 exact duplicate filtered: %s (%s)", item.id, item.title)
                continue

            # Tier 2: Fuzzy Jaccard Shingle Deduplication
            content_for_shingling = f"{item.title} {item.concept} {item.example_problem}"
            item_shingles = self.generate_shingles(content_for_shingling)
            is_fuzzy_dup = False

            for existing_item, existing_shingles in retained_shingles:
                if existing_item.domain == item.domain and existing_item.tier == item.tier:
                    sim = self.jaccard_similarity(item_shingles, existing_shingles)
                    if sim >= self.fuzzy_threshold:
                        is_fuzzy_dup = True
                        stats["tier2_fuzzy_duplicates"] += 1
                        logger.debug(
                            "Silver: Tier 2 fuzzy duplicate filtered: %s vs %s (sim: %.3f)",
                            item.id, existing_item.id, sim
                        )
                        break

            if is_fuzzy_dup:
                continue

            # Tier 3: Semantic Topic Key Collision
            sem_key = self.compute_semantic_key(item)
            if sem_key in seen_semantic_keys:
                stats["tier3_semantic_duplicates"] += 1
                logger.debug("Silver: Tier 3 semantic collision filtered: %s (%s)", item.id, sem_key)
                continue

            # If all tiers pass, retain item
            seen_exact_hashes.add(item_hash)
            retained_shingles.append((item, item_shingles))
            seen_semantic_keys.add(sem_key)
            retained.append(item)

        stats["retained"] = len(retained)
        logger.info(
            "Silver: Deduplication complete: %d input -> %d retained (exact=%d, fuzzy=%d, semantic=%d)",
            stats["total_input"], stats["retained"],
            stats["tier1_exact_duplicates"], stats["tier2_fuzzy_duplicates"], stats["tier3_semantic_duplicates"]
        )
        return retained, stats


# ============================================================================
# 3. GOLD STAGE: VECTOR DATABASE PERSISTENCE & MEMORY SAFEGUARDS
# ============================================================================

class CurriculumGoldStage:
    """
    Gold Stage: Production Vector Store persistence.
    - Stores all documents in 'rag_documents' under collection 'stem_curriculum'.
    - Stores representative summary chunks in 'material_chunks'.
    - Capping rows in 'material_chunks' at max_material_chunks strictly safeguards
      the PHP 128M memory_limit in backend/rag_service.php.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        ollama_base_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
        max_material_chunks: int = 500,
        enable_ollama: bool = True,
    ) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.embed_model = embed_model
        self.max_material_chunks = max_material_chunks
        self.enable_ollama = enable_ollama
        self.backend = LocalSqliteRagBackend(str(self.db_path))

    def _get_ollama_embedding(self, text: str) -> Optional[List[float]]:
        """
        Requests 768-dim embedding from Ollama with mandatory 'search_document: ' prefix
        for nomic-embed-text.
        """
        if not self.enable_ollama:
            return None

        prefixed_input = f"search_document: {text.strip()}"
        url = f"{self.ollama_base_url}/api/embed"
        payload = {
            "model": self.embed_model,
            "input": prefixed_input,
            "keep_alive": "5m",
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    embeddings = data.get("embeddings")
                    if embeddings and len(embeddings) > 0:
                        return embeddings[0]
        except Exception as e:
            logger.debug("Gold: Ollama embedding failed: %s", e)
            return None
        return None

    @staticmethod
    def pack_float_vector(vec: List[float]) -> bytes:
        """Packs a float list into binary BLOB matching PHP pack('f*', ...)."""
        return struct.pack(f"{len(vec)}f", *vec)

    @staticmethod
    def generate_fallback_vector(seed_text: str, dim: int = 768) -> List[float]:
        """Deterministic unit vector fallback when Ollama is offline."""
        h = hashlib.sha256(seed_text.encode("utf-8")).digest()
        raw = [float(h[i % len(h)]) - 128.0 for i in range(dim)]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    def persist(
        self,
        items: List[CurriculumItem],
        collection: str = "stem_curriculum",
    ) -> Dict[str, int]:
        """
        Persists curriculum items into SQLite database:
        1. Ingests all items into rag_documents under specified collection.
        2. Ingests representative chunks into material_chunks respecting max_material_chunks cap.
        """
        stats = {
            "rag_documents_written": 0,
            "material_chunks_written": 0,
            "embeddings_computed": 0,
            "fallback_embeddings_used": 0,
        }

        with self.backend._get_connection() as conn:
            cursor = conn.cursor()

            # Ensure material_chunks exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS material_chunks (
                    id TEXT PRIMARY KEY,
                    material_id TEXT,
                    course_id TEXT,
                    batch_id TEXT,
                    chunk_index INTEGER,
                    title TEXT,
                    content TEXT,
                    metadata TEXT,
                    embedding BLOB,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 1. Ingest into rag_documents
            for item in items:
                formatted_text = item.to_formatted_document()
                meta = {
                    "title": item.title,
                    "domain": item.domain,
                    "tier": item.tier,
                    "grade_level": item.grade_level,
                    "tags": item.tags,
                    "concept": item.concept,
                    "example_problem": item.example_problem,
                    "solution_steps": item.solution_steps,
                    "source": "stem_curriculum_expanded",
                    "updated_at": datetime.now().isoformat(),
                    **item.metadata,
                }
                self.backend.upsert(
                    collection=collection,
                    doc_id=item.id,
                    text=formatted_text,
                    metadata=meta,
                )
                stats["rag_documents_written"] += 1

            # 2. Ingest into material_chunks respecting ceiling
            cursor.execute("SELECT COUNT(*) FROM material_chunks WHERE course_id = 'stem_curriculum'")
            current_count = cursor.fetchone()[0]

            available_slots = max(0, self.max_material_chunks - current_count)

            for idx, item in enumerate(items[:available_slots]):
                chunk_id = f"stem_curr_{item.id}_{idx:03d}"
                summary = (
                    f"{item.title} ({item.grade_level} - {item.domain.upper()}):\n"
                    f"{item.concept}\n\n"
                    f"Problem: {item.example_problem}\n"
                    f"Solution: {item.solution_steps}"
                )

                vec = self._get_ollama_embedding(summary)
                if vec is not None:
                    stats["embeddings_computed"] += 1
                else:
                    vec = self.generate_fallback_vector(summary)
                    stats["fallback_embeddings_used"] += 1

                packed_blob = self.pack_float_vector(vec)
                meta_json = json.dumps({
                    "title": item.title,
                    "domain": item.domain,
                    "tier": item.tier,
                    "grade_level": item.grade_level,
                    "source_id": item.id,
                })

                cursor.execute("""
                    INSERT OR REPLACE INTO material_chunks (
                        id, material_id, course_id, batch_id, chunk_index, title, content, metadata, embedding
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chunk_id,
                    f"curr_{item.domain}",
                    "stem_curriculum",
                    f"batch_{item.tier}",
                    idx,
                    item.title,
                    summary,
                    meta_json,
                    packed_blob,
                ))
                stats["material_chunks_written"] += 1

            conn.commit()

        logger.info(
            "Gold: Persistence complete. rag_documents: %d, material_chunks: %d (limit: %d), embeddings: %d (live), %d (fallback)",
            stats["rag_documents_written"], stats["material_chunks_written"],
            self.max_material_chunks, stats["embeddings_computed"], stats["fallback_embeddings_used"]
        )
        return stats


# ============================================================================
# 4. PIPELINE RUNNER & CLI
# ============================================================================

def run_curriculum_ingestion_pipeline(
    input_file: Optional[Path] = None,
    db_path: Optional[Path] = None,
    ollama_url: str = "http://localhost:11434",
    embed_model: str = "nomic-embed-text",
    max_material_chunks: int = 500,
    enable_ollama: bool = True,
    fuzzy_threshold: float = 0.82,
) -> Dict[str, Any]:
    """Executes the complete Bronze -> Silver -> Gold Curriculum Ingestion Pipeline."""
    logger.info("=== Starting STEM Curriculum Ingestion Pipeline ===")

    # 1. Bronze Stage
    file_path = input_file or DEFAULT_CURRICULUM_PATH
    raw = CurriculumBronzeStage.load_from_json(file_path)
    staged = CurriculumBronzeStage.validate_and_stage(raw)

    # 2. Silver Stage
    silver = CurriculumSilverStage(fuzzy_jaccard_threshold=fuzzy_threshold)
    deduped, silver_stats = silver.deduplicate(staged)

    # 3. Gold Stage
    gold = CurriculumGoldStage(
        db_path=db_path or DEFAULT_DB_PATH,
        ollama_base_url=ollama_url,
        embed_model=embed_model,
        max_material_chunks=max_material_chunks,
        enable_ollama=enable_ollama,
    )
    gold_stats = gold.persist(deduped, collection="stem_curriculum")

    summary = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "bronze_count": len(staged),
        "silver_retained": len(deduped),
        "silver_stats": silver_stats,
        "gold_stats": gold_stats,
    }
    logger.info("=== Curriculum Pipeline Summary: %s ===", json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description="Ingest and deduplicate expanded STEM curriculum into SQLite vector store.")
    parser.add_argument("--input", type=Path, default=DEFAULT_CURRICULUM_PATH, help="Input curriculum JSON file.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help="Path to vectors.sqlite database.")
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434", help="Ollama API URL.")
    parser.add_argument("--embed-model", type=str, default="nomic-embed-text", help="Embedding model tag.")
    parser.add_argument("--max-chunks", type=int, default=500, help="Max rows for material_chunks to protect PHP RAM.")
    parser.add_argument("--no-ollama", action="store_true", help="Disable Ollama embedding and use deterministic fallback.")
    parser.add_argument("--fuzzy-threshold", type=float, default=0.82, help="Jaccard fuzzy deduplication threshold.")

    args = parser.parse_args()
    run_curriculum_ingestion_pipeline(
        input_file=args.input,
        db_path=args.db_path,
        ollama_url=args.ollama_url,
        embed_model=args.embed_model,
        max_material_chunks=args.max_chunks,
        enable_ollama=not args.no_ollama,
        fuzzy_threshold=args.fuzzy_threshold,
    )


if __name__ == "__main__":
    main()
