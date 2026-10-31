"""
tests/unit/test_expanded_stem_curriculum.py

Unit tests for Expanded STEM Curriculum Ingestion & Verification.
Enforces:
1. Coverage across all 4 educational tiers:
   - Elementary (Class 4-5)
   - Secondary (Class 6-10)
   - Higher Secondary (Class 11-12)
   - Subject Matter Expert (SME / Research / Olympiad)
2. Domain coverage across Mathematics and Physics.
3. Strict schema validation for all curriculum records.
4. Silver 3-tier deduplication (Exact Hash, Lexical Jaccard, Semantic Collision).
5. Pint unit and physical dimension consistency via physmath-mcp sandbox.
6. Gold stage persistence and PHP 128M row capping safeguard.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "stem_curriculum_expanded.json"

try:
    from scripts.ingest_stem_curriculum import (
        CurriculumBronzeStage,
        CurriculumGoldStage,
        CurriculumItem,
        CurriculumSilverStage,
        load_curriculum_dataset,
        run_curriculum_ingestion_pipeline,
    )
except ImportError:
    CurriculumBronzeStage = None
    CurriculumGoldStage = None
    CurriculumItem = None
    CurriculumSilverStage = None
    load_curriculum_dataset = None
    run_curriculum_ingestion_pipeline = None


@pytest.fixture
def temp_curriculum_db(tmp_path):
    """Provides a temporary SQLite database initialized with vector store schema."""
    db_file = tmp_path / "test_curriculum_vectors.sqlite"
    conn = sqlite3.connect(str(db_file))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rag_documents (
            id TEXT NOT NULL,
            collection TEXT NOT NULL,
            text TEXT NOT NULL,
            metadata TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (collection, id)
        );
    """)
    conn.execute("""
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
    conn.commit()
    conn.close()
    return db_file


# ============================================================================
# 1. CURRICULUM DATASET & SCHEMA TESTS
# ============================================================================

def test_curriculum_dataset_file_exists():
    """Verify data/stem_curriculum_expanded.json exists and is valid JSON."""
    assert DATA_PATH.exists(), f"Curriculum dataset missing at: {DATA_PATH}"
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list), "Curriculum dataset must be a list of records"
    assert len(data) >= 30, f"Expected at least 30 curriculum items, found {len(data)}"


def test_curriculum_schema_and_required_fields():
    """Verify all items contain mandatory fields with non-empty string contents."""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    required_keys = {
        "id", "title", "domain", "tier", "grade_level",
        "concept", "example_problem", "solution_steps", "tags"
    }

    valid_domains = {"maths", "physics"}
    valid_tiers = {"elementary", "secondary", "higher_secondary", "sme"}

    for idx, item in enumerate(records):
        missing = required_keys - set(item.keys())
        assert not missing, f"Item index {idx} ({item.get('id', 'NO_ID')}) missing keys: {missing}"
        assert item["domain"] in valid_domains, f"Invalid domain '{item['domain']}' in item {item['id']}"
        assert item["tier"] in valid_tiers, f"Invalid tier '{item['tier']}' in item {item['id']}"
        assert isinstance(item["tags"], list) and len(item["tags"]) > 0, f"Empty tags in item {item['id']}"
        assert len(item["concept"].strip()) > 30, f"Concept too short in item {item['id']}"
        assert len(item["example_problem"].strip()) > 15, f"Problem too short in item {item['id']}"
        assert len(item["solution_steps"].strip()) > 30, f"Solution too short in item {item['id']}"


def test_four_tier_coverage():
    """Verify comprehensive coverage across Elementary, Secondary, Higher Secondary, and SME."""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    tier_counts = {"elementary": 0, "secondary": 0, "higher_secondary": 0, "sme": 0}
    domain_counts = {"maths": 0, "physics": 0}

    for item in records:
        tier_counts[item["tier"]] += 1
        domain_counts[item["domain"]] += 1

    for tier, count in tier_counts.items():
        assert count >= 6, f"Tier '{tier}' has insufficient coverage: {count} items (minimum 6 required)"

    for domain, count in domain_counts.items():
        assert count >= 12, f"Domain '{domain}' has insufficient coverage: {count} items (minimum 12 required)"


# ============================================================================
# 2. SILVER STAGE DEDUPLICATION TESTS
# ============================================================================

def test_silver_deduplication_exact_and_fuzzy():
    """Verify CurriculumSilverStage filters exact and near-duplicate items."""
    assert CurriculumSilverStage is not None, "CurriculumSilverStage not implemented"

    item1 = CurriculumItem(
        id="TEST-001",
        title="Archimedes Principle of Buoyancy",
        domain="physics",
        tier="elementary",
        grade_level="Class 4-5",
        concept="Any object fully or partially immersed in a fluid is buoyed up by a force equal to weight of displaced fluid.",
        example_problem="Why does a steel ship float while a steel bolt sinks?",
        solution_steps="A hollow hull displaces a large volume of water creating a buoyant force equal to total ship weight.",
        tags=["buoyancy", "fluids", "density"],
    )

    # Exact duplicate with different ID and spacing
    item2 = CurriculumItem(
        id="TEST-002",
        title="  Archimedes  Principle   of  Buoyancy ",
        domain="physics",
        tier="elementary",
        grade_level="Class 4-5",
        concept="Any object fully or partially immersed in a fluid is buoyed up by a force equal to weight of displaced fluid. ",
        example_problem="Why does a steel ship float while a steel bolt sinks?",
        solution_steps="A hollow hull displaces a large volume of water creating a buoyant force equal to total ship weight.",
        tags=["buoyancy"],
    )

    # Distinct item
    item3 = CurriculumItem(
        id="TEST-003",
        title="Stokes Law of Viscous Drag",
        domain="physics",
        tier="higher_secondary",
        grade_level="Class 11-12",
        concept="The drag force on a spherical particle moving through a viscous fluid is F = 6*pi*eta*r*v.",
        example_problem="Find terminal velocity of a falling raindrop.",
        solution_steps="Equate gravitational weight minus buoyancy with Stokes viscous drag force.",
        tags=["viscosity", "stokes_law", "fluids"],
    )

    silver = CurriculumSilverStage(fuzzy_jaccard_threshold=0.82)
    deduped, stats = silver.deduplicate([item1, item2, item3])

    assert len(deduped) == 2
    assert {d.id for d in deduped} == {"TEST-001", "TEST-003"}
    assert stats["tier1_exact_duplicates"] == 1
    assert stats["retained"] == 2


# ============================================================================
# 3. PHYSMATH & DIMENSIONAL CONSISTENCY TESTS
# ============================================================================

def test_physmath_dimensional_consistency():
    """Verify physical formulas adhere to Pint unit consistency in physmath_mcp."""
    from physmath_mcp.server import units_check

    # 1. Potential Energy = m * g * h -> Joules
    res1 = units_check(
        expression="m * g * h",
        symbol_units={"m": "kilogram", "g": "meter / second**2", "h": "meter"},
        target_unit="joule",
    )
    assert res1.get("valid") is True
    assert res1.get("compatible_with_target") is True

    # 2. Kinetic Energy = 0.5 * m * v**2 -> Joules
    res2 = units_check(
        expression="0.5 * m * v**2",
        symbol_units={"m": "kilogram", "v": "meter / second"},
        target_unit="joule",
    )
    assert res2.get("valid") is True
    assert res2.get("compatible_with_target") is True

    # 3. Stokes Drag Force = 6 * pi * eta * r * v -> Newtons
    res3 = units_check(
        expression="6 * pi * eta * r * v",
        symbol_units={
            "pi": "dimensionless",
            "eta": "pascal * second",
            "r": "meter",
            "v": "meter / second",
        },
        target_unit="newton",
    )
    assert res3.get("valid") is True
    assert res3.get("compatible_with_target") is True


# ============================================================================
# 4. GOLD STAGE PERSISTENCE & PHP 128M MEMORY SAFEGUARD TESTS
# ============================================================================

def test_curriculum_gold_stage_persistence(temp_curriculum_db):
    """Verify Gold stage persists into rag_documents and caps material_chunks to protect PHP RAM."""
    assert CurriculumGoldStage is not None, "CurriculumGoldStage not implemented"

    gold = CurriculumGoldStage(
        db_path=temp_curriculum_db,
        max_material_chunks=10,
        enable_ollama=False,  # Test fallback embedding generation
    )

    items = [
        CurriculumItem(
            id=f"CURR-TEST-{i:03d}",
            title=f"Curriculum Topic {i}",
            domain="maths" if i % 2 == 0 else "physics",
            tier="elementary" if i < 3 else "secondary",
            grade_level="Class 5" if i < 3 else "Class 9",
            concept=f"Comprehensive concept explanation for topic {i}.",
            example_problem=f"Example problem statement {i}.",
            solution_steps=f"Step 1: Compute value {i}. Step 2: Conclude.",
            tags=[f"tag_{i}"],
        )
        for i in range(15)
    ]

    stats = gold.persist(items, collection="stem_curriculum")

    assert stats["rag_documents_written"] == 15
    assert stats["material_chunks_written"] == 10  # Capped at max_material_chunks=10

    # Verify directly in SQLite
    conn = sqlite3.connect(str(temp_curriculum_db))
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM rag_documents WHERE collection = 'stem_curriculum'")
    assert c.fetchone()[0] == 15

    c.execute("SELECT COUNT(*) FROM material_chunks WHERE course_id = 'stem_curriculum'")
    assert c.fetchone()[0] == 10
    conn.close()
