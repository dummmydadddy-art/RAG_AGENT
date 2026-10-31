"""
tests/unit/test_stem_sft_dataset.py

Unit and integration tests for Milestone 1 (M1_STEM):
1. Alpaca format schema validation for STEM curriculum records.
2. Sequence token length bounding (<= 1024 tokens / <= 4096 characters).
3. SftDatasetBuilder retrieval and conversion from 'stem_curriculum' collection.
4. 3-tier Silver deduplication verification (Exact Hash, Lexical Jaccard, Semantic Collision).
5. Global table segregation and PHP 128MB RAM safeguard (material_chunks <= 500 rows).
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[2]
CURRICULUM_DATA_PATH = ROOT / "data" / "stem_curriculum_expanded.json"
INSTRUCT_DATA_PATH = ROOT / "data" / "stem_instruct_dataset.json"
DB_PATH = ROOT / "backend" / "storage" / "vectors.sqlite"

from scripts.ingest_stem_curriculum import (
    CurriculumBronzeStage,
    CurriculumGoldStage,
    CurriculumItem,
    CurriculumSilverStage,
    export_curriculum_instruct_dataset,
    load_curriculum_dataset,
)
from scripts.train_stem_model import SftDatasetBuilder


# ============================================================================
# 1. ALPACA FORMAT SCHEMA VALIDATION TESTS
# ============================================================================

class TestStemAlpacaSchemaValidation:
    """Verifies STEM curriculum conversion to Alpaca instruction format."""

    def test_exported_curriculum_instruct_dataset_schema(self):
        """Verify data/stem_instruct_dataset.json adheres to Alpaca instruction schema."""
        if not INSTRUCT_DATA_PATH.exists():
            export_curriculum_instruct_dataset(output_path=INSTRUCT_DATA_PATH)

        with open(INSTRUCT_DATA_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)

        assert isinstance(records, list), "Dataset root must be a list"
        assert len(records) == 52, f"Expected exactly 52 curriculum instruction records, found {len(records)}"

        expected_keys = {"instruction", "input", "output", "id", "domain", "tier", "grade_level"}
        for idx, rec in enumerate(records):
            missing = expected_keys - set(rec.keys())
            assert not missing, f"Record {idx} ({rec.get('id')}) missing required keys: {missing}"
            assert isinstance(rec["instruction"], str) and len(rec["instruction"]) > 0
            assert isinstance(rec["input"], str)  # Can be empty string or context
            assert isinstance(rec["output"], str) and len(rec["output"]) > 0
            assert rec["domain"] in {"maths", "physics"}
            assert rec["tier"] in {"elementary", "secondary", "higher_secondary", "sme"}

    def test_export_curriculum_instruct_dataset_in_memory(self):
        """Verify export_curriculum_instruct_dataset function produces valid Alpaca records."""
        items = load_curriculum_dataset(CURRICULUM_DATA_PATH)
        alpaca_records = export_curriculum_instruct_dataset(items=items, output_path=None)

        assert len(alpaca_records) == 52
        for r in alpaca_records:
            assert "Domain: " in r["instruction"]
            assert "Question / Challenge:" in r["instruction"]
            assert "Relevant Principles:" in r["input"]
            assert len(r["output"]) > 0


# ============================================================================
# 2. SEQUENCE TOKEN LENGTH TESTS (<= 1024 TOKENS / <= 4096 CHARS)
# ============================================================================

class TestStemSequenceLengthCutoff:
    """Verifies sequence lengths strictly adhere to the <= 1024 token cutoff."""

    def test_all_curriculum_samples_within_1024_tokens(self):
        """Verify character length of all 52 samples <= 4096 characters (1024 tokens)."""
        items = load_curriculum_dataset(CURRICULUM_DATA_PATH)
        alpaca_records = export_curriculum_instruct_dataset(items=items, output_path=None)

        max_len = 0
        min_len = 999999
        for r in alpaca_records:
            total_chars = len(r["instruction"]) + len(r["input"]) + len(r["output"])
            if total_chars > max_len:
                max_len = total_chars
            if total_chars < min_len:
                min_len = total_chars

            assert total_chars <= 4096, f"Record {r['id']} exceeds 4096 char cutoff: {total_chars} chars"

        # Empirical sanity bounds
        assert max_len <= 3500, f"Max characters {max_len} unexpectedly high"
        assert min_len >= 500, f"Min characters {min_len} unexpectedly low"

    def test_truncation_guard_on_oversized_record(self):
        """Verify truncation guard gracefully cuts oversized content when total_chars > 4096."""
        oversized_item = CurriculumItem(
            id="CURR-OVERSIZED-001",
            title="Extremely Long Analytical Derivation",
            domain="physics",
            tier="sme",
            grade_level="Graduate",
            concept="A" * 2000,
            example_problem="B" * 2000,
            solution_steps="C" * 2500,
            tags=["oversized"],
        )
        alpaca = export_curriculum_instruct_dataset(items=[oversized_item], output_path=None, max_tokens=1024)
        assert len(alpaca) == 1
        rec = alpaca[0]
        total_len = len(rec["instruction"]) + len(rec["input"]) + len(rec["output"])
        assert total_len <= 4096
        assert "[truncated for token budget]" in rec["output"] or "[truncated for token budget]" in rec["instruction"]


# ============================================================================
# 3. SFT DATASET BUILDER & SQLITE RETRIEVAL TESTS
# ============================================================================

class TestSftDatasetBuilderCurriculumIntegration:
    """Verifies SftDatasetBuilder integration with the 'stem_curriculum' collection."""

    def test_load_stem_records_retrieves_stem_curriculum_from_db(self):
        """Verify SftDatasetBuilder.load_stem_records() retrieves 52 curriculum modules."""
        if not DB_PATH.exists():
            pytest.skip("vectors.sqlite not available in this test environment")

        builder = SftDatasetBuilder(db_path=DB_PATH)
        records = builder.load_stem_records()

        collections = {r["collection"] for r in records}
        assert "stem_curriculum" in collections, "'stem_curriculum' collection must be queried"

        curriculum_records = [r for r in records if r["collection"] == "stem_curriculum"]
        assert len(curriculum_records) == 52, f"Expected 52 stem_curriculum records, got {len(curriculum_records)}"

        # Verify fields were unpacked from metadata
        for r in curriculum_records:
            assert len(r["concept"]) > 0, f"Record {r['id']} missing concept"
            assert len(r["example_problem"]) > 0, f"Record {r['id']} missing example_problem"
            assert len(r["solution_steps"]) > 0, f"Record {r['id']} missing solution_steps"

    def test_build_alpaca_dataset_with_stem_curriculum_records(self):
        """Verify SftDatasetBuilder.build_alpaca_dataset converts curriculum records."""
        items = load_curriculum_dataset(CURRICULUM_DATA_PATH)
        builder = SftDatasetBuilder()

        # Test with CurriculumItem DTOs
        alpaca_from_dtos = builder.build_alpaca_dataset(items)
        assert len(alpaca_from_dtos) == 52
        for s in alpaca_from_dtos:
            assert "instruction" in s and "input" in s and "output" in s
            assert len(s["instruction"]) > 0
            assert len(s["output"]) > 0

        # Test with raw record dicts matching DB output
        raw_dicts = [
            {
                "id": it.id,
                "collection": "stem_curriculum",
                "title": it.title,
                "domain": it.domain,
                "tier": it.tier,
                "grade_level": it.grade_level,
                "concept": it.concept,
                "example_problem": it.example_problem,
                "solution_steps": it.solution_steps,
            }
            for it in items
        ]
        alpaca_from_dicts = builder.build_alpaca_dataset(raw_dicts)
        assert len(alpaca_from_dicts) == 52
        for s in alpaca_from_dicts:
            assert "Domain: " in s["instruction"]
            assert len(s["output"]) > 0

    def test_build_sharegpt_dataset_with_curriculum_records(self):
        """Verify SftDatasetBuilder.build_sharegpt_dataset formats multi-turn conversations."""
        items = load_curriculum_dataset(CURRICULUM_DATA_PATH)[:5]
        builder = SftDatasetBuilder()
        sharegpt_samples = builder.build_sharegpt_dataset(items)

        assert len(sharegpt_samples) == 5
        for s in sharegpt_samples:
            assert "conversations" in s
            convs = s["conversations"]
            assert len(convs) == 3
            assert convs[0]["from"] == "system"
            assert convs[1]["from"] == "human"
            assert convs[2]["from"] == "gpt"


# ============================================================================
# 4. 3-TIER SILVER DEDUPLICATION TESTS
# ============================================================================

class TestSilverThreeTierDeduplication:
    """Verifies 3-tier Silver deduplication yields 0 duplicates across all 52 modules."""

    def test_curriculum_52_modules_zero_duplicates(self):
        """Verify all 52 curriculum modules pass 3-tier deduplication with 0 duplicates."""
        items = load_curriculum_dataset(CURRICULUM_DATA_PATH)
        silver = CurriculumSilverStage(fuzzy_jaccard_threshold=0.82)
        deduped, stats = silver.deduplicate(items)

        assert stats["total_input"] == 52
        assert stats["tier1_exact_duplicates"] == 0
        assert stats["tier2_fuzzy_duplicates"] == 0
        assert stats["tier3_semantic_duplicates"] == 0
        assert stats["retained"] == 52
        assert len(deduped) == 52

    def test_tier1_exact_duplicate_filter(self):
        """Verify Tier 1 exact hash deduplication catches and filters identical item."""
        items = load_curriculum_dataset(CURRICULUM_DATA_PATH)[:3]
        duplicate_item = CurriculumItem(
            id="CURR-CLONE-001",
            title=items[0].title,
            domain=items[0].domain,
            tier=items[0].tier,
            grade_level=items[0].grade_level,
            concept=items[0].concept,
            example_problem=items[0].example_problem,
            solution_steps=items[0].solution_steps,
        )
        silver = CurriculumSilverStage()
        deduped, stats = silver.deduplicate([*items, duplicate_item])

        assert stats["tier1_exact_duplicates"] == 1
        assert stats["retained"] == 3

    def test_tier2_fuzzy_duplicate_filter(self):
        """Verify Tier 2 lexical Jaccard catches shingle overlap >= 0.82."""
        items = load_curriculum_dataset(CURRICULUM_DATA_PATH)[:1]
        base = items[0]
        # Modify slightly (swap a couple of words) so exact hash differs, but shingles overlap > 82%
        fuzzy_clone = CurriculumItem(
            id="CURR-FUZZY-001",
            title=base.title + " Extra",
            domain=base.domain,
            tier=base.tier,
            grade_level=base.grade_level,
            concept=base.concept,
            example_problem=base.example_problem,
            solution_steps="Different solution but same core problem content.",
        )
        silver = CurriculumSilverStage(fuzzy_jaccard_threshold=0.82)
        deduped, stats = silver.deduplicate([base, fuzzy_clone])

        assert stats["tier2_fuzzy_duplicates"] == 1
        assert stats["retained"] == 1

    def test_tier3_semantic_collision_filter(self):
        """Verify Tier 3 semantic collision catches items with identical canonical key."""
        base = CurriculumItem(
            id="CURR-SEM-001",
            title="Newton Laws of Motion Acceleration",
            domain="physics",
            tier="secondary",
            grade_level="Class 9",
            concept="Detailed force and mass relationship description.",
            example_problem="Calculate the force given 10kg mass and 2m/s^2.",
            solution_steps="Step 1: F=ma.",
        )
        colliding = CurriculumItem(
            id="CURR-SEM-002",
            title="Newton Laws of Motion Acceleration",
            domain="physics",
            tier="secondary",
            grade_level="Class 9",
            concept="Completely different words used here for testing semantic topic key collision.",
            example_problem="A very different problem statement with different phrasing completely.",
            solution_steps="Step 1: Different solution steps altogether.",
        )
        silver = CurriculumSilverStage(fuzzy_jaccard_threshold=0.99)
        deduped, stats = silver.deduplicate([base, colliding])

        assert stats["tier3_semantic_duplicates"] == 1
        assert stats["retained"] == 1


# ============================================================================
# 5. TABLE SEGREGATION & PHP 128MB RAM SAFEGUARD TESTS
# ============================================================================

class TestTableSegregationAndPhpMemoryCeiling:
    """Verifies material_chunks global table count <= 500 rows and PHP RAM preservation."""

    def test_production_material_chunks_row_count_under_500(self):
        """Verify production vectors.sqlite material_chunks row count remains <= 500."""
        if not DB_PATH.exists():
            pytest.skip("vectors.sqlite not available in this test environment")

        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM material_chunks")
        total_chunks = cursor.fetchone()[0]
        conn.close()

        assert total_chunks <= 500, f"material_chunks row count {total_chunks} breaches 500 ceiling"
        # Current actual count is ~140 (105 stem_curriculum + 32 polyglot_curriculum + 3 others)
        assert total_chunks >= 100, f"Expected at least 100 material chunks, found {total_chunks}"

    def test_gold_stage_strictly_enforces_global_row_cap(self, tmp_path):
        """Verify CurriculumGoldStage enforces global material_chunks cap even with preexisting rows."""
        db_file = tmp_path / "test_ceiling.sqlite"
        conn = sqlite3.connect(str(db_file))
        conn.execute("""
            CREATE TABLE rag_documents (
                id TEXT NOT NULL,
                collection TEXT NOT NULL,
                text TEXT NOT NULL,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (collection, id)
            );
        """)
        conn.execute("""
            CREATE TABLE material_chunks (
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
        # Prepopulate with 8 existing chunks from another course
        for i in range(8):
            conn.execute(
                "INSERT INTO material_chunks (id, course_id, title) VALUES (?, ?, ?)",
                (f"existing_poly_{i}", "polyglot_curriculum", f"Polyglot Challenge {i}")
            )
        conn.commit()
        conn.close()

        gold = CurriculumGoldStage(
            db_path=db_file,
            max_material_chunks=10,  # Global ceiling is 10
            enable_ollama=False,
        )
        # Attempt to insert 6 new curriculum items
        new_items = [
            CurriculumItem(
                id=f"CURR-CAP-{i:03d}",
                title=f"Curriculum Topic {i}",
                domain="maths",
                tier="elementary",
                grade_level="Class 5",
                concept=f"Concept {i}",
                example_problem=f"Problem {i}",
                solution_steps=f"Solution {i}",
            )
            for i in range(6)
        ]
        stats = gold.persist(new_items, collection="stem_curriculum")

        # Since table had 8 rows and ceiling is 10, only 2 new chunks should be written
        assert stats["material_chunks_written"] == 2

        # Check total rows in material_chunks is strictly 10
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM material_chunks")
        final_count = cursor.fetchone()[0]
        conn.close()

        assert final_count == 10, f"Expected total 10 chunks, found {final_count}"
