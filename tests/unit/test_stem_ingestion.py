"""
Unit tests for STEM Knowledge Ingestion & Training Pipeline.

Verifies:
1. Medallion architecture (Bronze staging, Silver 3-tier dedup, Gold vector persistence).
2. 3-tier deduplication: exact hash, fuzzy Jaccard, semantic key collision.
3. Ollama 'search_document: ' prefix requirement for nomic-embed-text.
4. PHP 128M memory limit safeguard (material_chunks row capping).
5. Schema compatibility with vectors.sqlite (rag_documents and material_chunks).
6. Graceful offline fallback without crashing.
7. VRAM eviction, SFT dataset preparation, QLoRA config, and Modelfile generation.
"""

import json
import sqlite3
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.ingest_stem_knowledge import (
    CURATED_STEM_CORPUS,
    StemBronzeStage,
    StemGoldStage,
    StemKnowledgeItem,
    StemSilverStage,
    run_stem_ingestion_pipeline,
)
from scripts.train_stem_model import (
    QloraConfigGenerator,
    SftDatasetBuilder,
    VramEvictor,
    ZeroRedundancyPersister,
    run_stem_training_pipeline,
)


@pytest.fixture
def temp_db(tmp_path):
    """Provides a temporary SQLite database initialized with RAG schema."""
    db_file = tmp_path / "test_vectors.sqlite"
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
# 1. BRONZE STAGE TESTS
# ============================================================================

def test_bronze_curated_seed_corpus_coverage():
    """Verify built-in curated corpus covers Class 4 to SME across all 3 domains."""
    items = StemBronzeStage.load_seed_corpus()
    assert len(items) >= 20

    domains = {item["domain"] for item in items}
    tiers = {item["tier"] for item in items}

    assert {"maths", "physics", "coding"}.issubset(domains)
    assert {"elementary", "secondary", "higher_secondary", "sme"}.issubset(tiers)


def test_bronze_validation_and_staging():
    """Verify Bronze validation accepts valid records and skips malformed records."""
    raw_records = [
        {
            "id": "VALID-01",
            "title": "Valid Record",
            "domain": "maths",
            "tier": "elementary",
            "concept": "Valid mathematical concept",
            "example_problem": "Problem 1",
            "solution_steps": "Solution 1",
        },
        {
            # Missing concept
            "id": "INVALID-02",
            "title": "No Concept",
            "domain": "physics",
        },
        {
            # Missing title
            "id": "INVALID-03",
            "concept": "Has concept but no title",
            "domain": "coding",
        },
    ]

    staged = StemBronzeStage.validate_and_stage(raw_records)
    assert len(staged) == 1
    assert staged[0].id == "VALID-01"
    assert staged[0].title == "Valid Record"


def test_bronze_load_from_json(tmp_path):
    """Verify loading external Bronze records from JSON."""
    json_path = tmp_path / "external_stem.json"
    data = [
        {
            "id": "EXT-01",
            "title": "External Algebra",
            "domain": "maths",
            "concept": "External concept",
        }
    ]
    json_path.write_text(json.dumps(data), encoding="utf-8")

    loaded = StemBronzeStage.load_from_json(json_path)
    assert len(loaded) == 1
    assert loaded[0]["id"] == "EXT-01"

    with pytest.raises(FileNotFoundError):
        StemBronzeStage.load_from_json(tmp_path / "non_existent.json")


# ============================================================================
# 2. SILVER STAGE DEDUPLICATION TESTS
# ============================================================================

def test_silver_exact_hash_deduplication():
    """Verify Tier 1 exact duplicate hash elimination."""
    item1 = StemKnowledgeItem(
        id="STEM-001",
        title="Newton's First Law",
        domain="physics",
        tier="secondary",
        grade_level="Class 9",
        concept="An object at rest stays at rest unless acted on by external force.",
        example_problem="Why does a passenger jerk forward when brakes are applied?",
        solution_steps="Inertia of motion causes the passenger to maintain forward velocity.",
    )
    # Exact duplicate with different ID and whitespace differences
    item2 = StemKnowledgeItem(
        id="STEM-002",
        title="  Newton's   First  Law  ",
        domain="physics",
        tier="secondary",
        grade_level="Class 9",
        concept="An object at rest stays at rest unless acted on by external force.  ",
        example_problem="Why does a passenger jerk forward when brakes are applied?",
        solution_steps="Inertia of motion causes the passenger to maintain forward velocity.",
    )

    silver = StemSilverStage()
    deduped, stats = silver.deduplicate([item1, item2])

    assert len(deduped) == 1
    assert deduped[0].id == "STEM-001"
    assert stats["tier1_exact_duplicates"] == 1
    assert stats["retained"] == 1


def test_silver_fuzzy_jaccard_deduplication():
    """Verify Tier 2 near-duplicate Jaccard shingle elimination."""
    item1 = StemKnowledgeItem(
        id="STEM-FUZZY-1",
        title="Binary Search Algorithm",
        domain="coding",
        tier="secondary",
        grade_level="Class 10",
        concept="Binary search finds the position of a target value within a sorted array by comparing against the middle element repeatedly.",
        example_problem="Search target 42 in sorted array.",
        solution_steps="Divide search interval in half each iteration in O(log n).",
    )
    # Highly overlapping paraphrased version
    item2 = StemKnowledgeItem(
        id="STEM-FUZZY-2",
        title="Binary Search In Sorted Arrays",
        domain="coding",
        tier="secondary",
        grade_level="Class 10",
        concept="Binary search locates the position of a target value within a sorted array by comparing against the middle element continuously.",
        example_problem="Search target in sorted array.",
        solution_steps="Divide interval in half each step.",
    )

    silver = StemSilverStage(fuzzy_jaccard_threshold=0.60)
    deduped, stats = silver.deduplicate([item1, item2])

    assert len(deduped) == 1
    assert deduped[0].id == "STEM-FUZZY-1"
    assert stats["tier2_fuzzy_duplicates"] == 1


def test_silver_semantic_key_collision():
    """Verify Tier 3 semantic topic key collision elimination."""
    item1 = StemKnowledgeItem(
        id="STEM-SEM-1",
        title="Euler Lagrange Equations",
        domain="physics",
        tier="sme",
        grade_level="SME / Research",
        concept="Stationary action principle δS = 0 yields Euler-Lagrange equations.",
        example_problem="Derive for simple pendulum.",
        solution_steps="Compute derivatives.",
    )
    item2 = StemKnowledgeItem(
        id="STEM-SEM-2",
        title="Euler Lagrange Equations",  # Same domain, tier, title
        domain="physics",
        tier="sme",
        grade_level="SME / Research",
        concept="Alternative presentation of Lagrangian mechanics.",
        example_problem="Derive for double pendulum.",
        solution_steps="Compute Lagrangian L = T - V.",
    )

    silver = StemSilverStage(fuzzy_jaccard_threshold=0.99)
    deduped, stats = silver.deduplicate([item1, item2])

    assert len(deduped) == 1
    assert stats["tier3_semantic_duplicates"] == 1


# ============================================================================
# 3. GOLD STAGE & PHP 128M MEMORY LIMIT SAFEGUARD TESTS
# ============================================================================

def test_gold_php_memory_guard_and_persistence(temp_db):
    """
    Verify that Gold stage stores all items in rag_documents while strictly
    capping material_chunks rows to protect PHP 128M memory limit.
    """
    items = [
        StemKnowledgeItem(
            id=f"ITEM-{i:03d}",
            title=f"STEM Concept {i}",
            domain="maths",
            tier="secondary",
            grade_level="Class 8",
            concept=f"Concept explanation {i}",
            example_problem=f"Problem {i}",
            solution_steps=f"Solution {i}",
        )
        for i in range(15)
    ]

    # Set strict cap of 5 chunks in material_chunks to verify enforcement
    gold = StemGoldStage(
        db_path=temp_db,
        max_material_chunks=5,
        enable_ollama=False,
    )
    stats = gold.persist(items)

    assert stats["rag_documents_written"] == 15
    assert stats["material_chunks_written"] == 5

    conn = sqlite3.connect(str(temp_db))
    rag_doc_count = conn.execute("SELECT COUNT(*) FROM rag_documents WHERE collection = 'stem_knowledge'").fetchone()[0]
    mat_chunk_count = conn.execute("SELECT COUNT(*) FROM material_chunks").fetchone()[0]

    assert rag_doc_count == 15
    assert mat_chunk_count == 5

    # Verify vector packing format matches PHP float32 binary unpack
    blob = conn.execute("SELECT embedding FROM material_chunks LIMIT 1").fetchone()[0]
    unpacked_vec = struct.unpack("768f", blob)
    assert len(unpacked_vec) == 768
    conn.close()


def test_gold_ollama_search_document_prefix():
    """
    Verify that Ollama embedding requests strictly prepend 'search_document: '
    as required by nomic-embed-text.
    """
    gold = StemGoldStage(enable_ollama=True)

    with patch("httpx.Client.post") as mock_post:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {"embeddings": [[0.1] * 768]}
        mock_post.return_value = mock_res

        vec = gold._get_ollama_embedding("Newton's second law F = ma")
        assert vec is not None
        assert len(vec) == 768

        # Check call arguments
        mock_post.assert_called_once()
        sent_json = mock_post.call_args[1]["json"]
        assert sent_json["input"].startswith("search_document: ")
        assert "Newton's second law F = ma" in sent_json["input"]


def test_gold_offline_ollama_fallback(temp_db):
    """Verify Gold stage operates resiliently with offline Ollama without crashing."""
    gold = StemGoldStage(
        db_path=temp_db,
        ollama_base_url="http://localhost:9999",  # non-existent port
        enable_ollama=True,
    )
    # Should fallback to deterministic unit vector
    vec = gold._get_ollama_embedding("Offline test")
    assert vec is None

    fb_vec = gold.generate_fallback_vector("Offline test")
    assert len(fb_vec) == 768
    # Norm should be ~1.0
    norm = sum(x * x for x in fb_vec) ** 0.5
    assert abs(norm - 1.0) < 1e-4


def test_full_ingestion_pipeline_end_to_end(temp_db):
    """Verify complete end-to-end execution of run_stem_ingestion_pipeline."""
    summary = run_stem_ingestion_pipeline(
        db_path=temp_db,
        max_material_chunks=10,
        enable_ollama=False,
    )

    assert summary["status"] == "success"
    assert summary["bronze_count"] >= 20
    assert summary["silver_retained"] >= 20
    assert summary["gold_stats"]["rag_documents_written"] >= 20
    assert summary["gold_stats"]["material_chunks_written"] == 10


# ============================================================================
# 4. TRAINING PIPELINE TESTS
# ============================================================================

def test_vram_evictor_ollama_and_torch():
    """Verify pre-flight VRAM eviction unloads running Ollama models."""
    evictor = VramEvictor()

    with patch("httpx.Client.get") as mock_get, patch("httpx.Client.post") as mock_post:
        mock_res_get = MagicMock()
        mock_res_get.status_code = 200
        mock_res_get.json.return_value = {
            "models": [{"name": "nomic-embed-text:latest"}, {"name": "llama3.2:latest"}]
        }
        mock_get.return_value = mock_res_get

        mock_res_post = MagicMock()
        mock_res_post.status_code = 200
        mock_post.return_value = mock_res_post

        unloaded = evictor.evict_ollama_models()
        assert "nomic-embed-text:latest" in unloaded
        assert "llama3.2:latest" in unloaded
        assert mock_post.call_count == 2


def test_sft_dataset_builder_alpaca_and_sharegpt(tmp_path):
    """Verify SFT dataset generation in Alpaca and ShareGPT formats with list/str domains."""
    builder = SftDatasetBuilder()
    records = [
        {
            "id": "SFT-001",
            "title": "Quantum Spin 1/2",
            "domain": ["physics", "quantum"],  # list domain test
            "grade_level": "SME / Research",
            "concept": "Pauli matrices σx, σy, σz satisfy SU(2) algebra.",
            "example_problem": "Compute the eigenvalues of Pauli matrix σz.",
            "solution_steps": "det(σz - λI) = 0 => λ = ±1.",
        },
        {
            "id": "SFT-002",
            "title": "Fraction Addition",
            "domain": "maths",  # string domain test
            "grade_level": "Class 4",
            "concept": "Add fractions with like denominators.",
            "example_problem": "Compute 1/5 + 2/5.",
            "solution_steps": "(1+2)/5 = 3/5.",
        },
    ]

    alpaca = builder.build_alpaca_dataset(records)
    assert len(alpaca) == 2
    assert "PHYSICS/QUANTUM" in alpaca[0]["instruction"]
    assert "MATHS" in alpaca[1]["instruction"]
    assert "input" in alpaca[0]
    assert "output" in alpaca[0]

    sharegpt = builder.build_sharegpt_dataset(records)
    assert len(sharegpt) == 2
    assert len(sharegpt[0]["conversations"]) == 3
    assert sharegpt[0]["conversations"][0]["from"] == "system"


def test_qlora_config_and_modelfile_generation():
    """Verify low-VRAM 4-bit QLoRA configs and Modelfile generation."""
    config_yaml = QloraConfigGenerator.generate_llama_factory_config(
        base_model="Qwen/Qwen2.5-Coder-1.5B-Instruct",
        dataset_name="sft_stem_dataset",
        output_dir="models/lora_adapters/stem_expert",
    )
    assert "quantization_bit: 4" in config_yaml
    assert "quantization_type: nf4" in config_yaml
    assert "lora_rank: 8" in config_yaml
    assert "optim: paged_adamw_8bit" in config_yaml
    assert "gradient_checkpointing: true" in config_yaml

    modelfile = QloraConfigGenerator.generate_modelfile(
        gguf_path="./stem-expert-q4_k_m.gguf",
        model_name="stem-expert",
    )
    assert "FROM ./stem-expert-q4_k_m.gguf" in modelfile
    assert "PARAMETER temperature 0.2" in modelfile
    assert "STEM Subject Matter Expert" in modelfile


def test_zero_redundancy_persister_and_cleanup(tmp_path):
    """Verify intermediate weights cleanup to protect 20GB SSD budget."""
    persister = ZeroRedundancyPersister(workspace_root=tmp_path)

    # Create dummy intermediate weight files
    checkpoint_dir = tmp_path / "temp_checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    (checkpoint_dir / "weights.bin").write_bytes(b"0" * 1024 * 1024)  # 1MB dummy

    freed = persister.clean_intermediate_weights([checkpoint_dir])
    assert freed >= 1024 * 1024
    assert not checkpoint_dir.exists()


def test_training_pipeline_dry_run(tmp_path):
    """Verify end-to-end dry run of run_stem_training_pipeline."""
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "models"

    summary = run_stem_training_pipeline(
        base_model="Qwen/Qwen2.5-Coder-1.5B-Instruct",
        data_dir=data_dir,
        output_dir=output_dir,
        target_model_name="test-stem-expert",
        dry_run=True,
    )

    assert summary["status"] == "success"
    assert summary["dry_run"] is True
    assert (data_dir / "sft_stem_dataset.json").exists()
    assert (output_dir / "llama_factory_stem_qlora.yaml").exists()
    assert (output_dir / "Modelfile").exists()
    assert (output_dir / "merge_cpu.py").exists()
