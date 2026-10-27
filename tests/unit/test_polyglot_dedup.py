"""
Unit tests for Polyglot Multi-Language Dataset Ingestion & 3-Tier Deduplication.

Verifies:
1. Multi-language coverage across 8 Tier-1 languages (Python, TypeScript, C++, Java, Rust, Go, PHP, SQL)
   and 4 difficulty tiers (Elementary, Intermediate, Systems, Competitive).
2. 3-Tier Silver Deduplication:
   - Tier 1: Exact Hash (comment-stripped, whitespace-collapsed SHA-256)
   - Tier 2: Lexical Jaccard (shingle token overlap at threshold 0.82)
   - Tier 3: Semantic Collision (cosine similarity threshold 0.92 with test-coverage arbitration)
3. Zero-duplicate guarantee before vectorization.
4. SQLite vector store persistence with dual-table segregation:
   - Full corpus in rag_documents under 'polyglot_coding'
   - material_chunks row capping (<= 500 rows) protecting PHP 128 MB memory limit
5. Ollama nomic-embed-text 'search_document: ' prefix requirement.
6. Offline fallback to deterministic 768-d unit vectors.
7. Instruction fine-tuning dataset export (Alpaca format) bounded to <= 1024 tokens.
"""

import json
import sqlite3
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.ingest_polyglot import (
    CURATED_POLYGLOT_CORPUS,
    DIFFICULTY_TIERS,
    TIER_1_LANGUAGES,
    PolyglotBronzeStage,
    PolyglotChallenge,
    PolyglotGoldStage,
    PolyglotSilverStage,
    export_polyglot_instruct_dataset,
    run_polyglot_ingestion_pipeline,
)
from scripts.ingest_stem_knowledge import (
    CURATED_POLYGLOT_CORPUS as STEM_REEXPORT_CORPUS,
    PolyglotChallenge as StemReexportChallenge,
    run_polyglot_ingestion_pipeline as stem_reexport_pipeline,
)


@pytest.fixture
def temp_polyglot_db(tmp_path):
    """Provides a temporary SQLite database initialized with vector store schema."""
    db_file = tmp_path / "polyglot_vectors.sqlite"
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
# 1. DATASET CURATION & BRONZE STAGE TESTS
# ============================================================================

def test_polyglot_corpus_coverage():
    """Verify built-in curated corpus covers all 8 Tier-1 languages and all 4 tiers."""
    corpus = PolyglotBronzeStage.load_seed_corpus()
    assert len(corpus) >= 32

    languages = {item["language"] for item in corpus}
    tiers = {item["tier"] for item in corpus}

    assert TIER_1_LANGUAGES.issubset(languages)
    assert DIFFICULTY_TIERS.issubset(tiers)

    # Verify every language has at least one challenge in each tier
    for lang in TIER_1_LANGUAGES:
        for tier in DIFFICULTY_TIERS:
            matching = [c for c in corpus if c["language"] == lang and c["tier"] == tier]
            assert len(matching) >= 1, f"Missing challenge for language '{lang}' in tier '{tier}'"


def test_bronze_validation_valid_and_malformed():
    """Verify Bronze stage accepts compliant challenges and filters invalid/malformed records."""
    raw_records = [
        {
            "id": "POLY-TEST-001",
            "language": "python",
            "tier": "elementary",
            "title": "Valid Python Challenge",
            "problem_statement": "Implement binary search.",
            "starter_code": "def search(): pass",
            "reference_solution": "def search(): return 0",
            "unit_test_suite": "assert search() == 0",
        },
        {
            # Missing solution
            "id": "POLY-INVALID-002",
            "language": "rust",
            "tier": "systems",
            "title": "Missing Solution",
            "problem_statement": "Implement lock-free queue.",
        },
        {
            # Unsupported language
            "id": "POLY-INVALID-003",
            "language": "brainfuck",
            "tier": "elementary",
            "title": "Unsupported Language",
            "problem_statement": "Run code.",
            "reference_solution": "++++",
        },
        {
            # Unsupported tier
            "id": "POLY-INVALID-004",
            "language": "go",
            "tier": "legendary",
            "title": "Bad Tier",
            "problem_statement": "Do something.",
            "reference_solution": "package main",
        },
    ]

    staged = PolyglotBronzeStage.validate_and_stage(raw_records)
    assert len(staged) == 1
    assert staged[0].id == "POLY-TEST-001"
    assert staged[0].language == "python"
    assert staged[0].tier == "elementary"


def test_bronze_load_from_json(tmp_path):
    """Verify external JSON file loading in Bronze stage."""
    json_file = tmp_path / "custom_challenges.json"
    data = [
        {
            "id": "EXT-01",
            "language": "rust",
            "tier": "systems",
            "title": "Custom Rust Challenge",
            "problem_statement": "Statement",
            "reference_solution": "pub fn test() {}",
            "unit_test_suite": "#[test] fn t() {}",
        }
    ]
    json_file.write_text(json.dumps(data), encoding="utf-8")

    loaded = PolyglotBronzeStage.load_from_json(json_file)
    assert len(loaded) == 1
    staged = PolyglotBronzeStage.validate_and_stage(loaded)
    assert len(staged) == 1
    assert staged[0].id == "EXT-01"


# ============================================================================
# 2. 3-TIER SILVER DEDUPLICATION TESTS
# ============================================================================

def test_tier1_exact_hash_deduplication():
    """Verify Tier 1 exact SHA-256 hash collision eliminates identical solutions."""
    c1 = PolyglotChallenge(
        id="POLY-PY-1",
        language="python",
        tier="elementary",
        title="Two Sum Problem",
        tags=["hash-map"],
        problem_statement="Find two indices.",
        starter_code="def two_sum(): pass",
        reference_solution="def two_sum(nums, target):\n    # Hash map lookup\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen: return [seen[target - n], i]\n        seen[n] = i\n    return []",
        unit_test_suite="assert two_sum([2, 7], 9) == [0, 1]",
    )
    # Exact duplicate with different ID, whitespace mutations, and extra comments
    c2 = PolyglotChallenge(
        id="POLY-PY-2",
        language="python",
        tier="elementary",
        title="  Two   Sum   Problem  ",
        tags=["hash-map"],
        problem_statement="Find two indices.",
        starter_code="def two_sum(): pass",
        reference_solution="def two_sum(nums, target):\n    # Different comment here\n    # Another comment\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen: return [seen[target - n], i]\n        seen[n] = i\n    return []",
        unit_test_suite="assert two_sum([2, 7], 9) == [0, 1]",
    )

    silver = PolyglotSilverStage()
    deduped, stats = silver.deduplicate([c1, c2])

    assert len(deduped) == 1
    assert deduped[0].id == "POLY-PY-1"
    assert stats["tier1_exact_duplicates"] == 1
    assert stats["retained"] == 1


def test_tier1_comment_stripping_per_language():
    """Verify comment stripping for Python/SQL vs C/C++/Java/Rust/Go/TS/PHP."""
    py_code = "# Comment line\nnum = 42 # inline comment\n'''docstring'''"
    c_code = "// Single line\nint x = 42; /* Block comment */"
    sql_code = "-- SQL comment\nSELECT * FROM users;"

    assert "comment" not in PolyglotSilverStage.normalize_code(py_code, "python")
    assert "comment" not in PolyglotSilverStage.normalize_code(c_code, "cpp")
    assert "comment" not in PolyglotSilverStage.normalize_code(sql_code, "sql")


def test_tier2_lexical_jaccard_deduplication():
    """Verify Tier 2 near-duplicate elimination at threshold 0.82."""
    c1 = PolyglotChallenge(
        id="POLY-TS-1",
        language="typescript",
        tier="intermediate",
        title="EventEmitter Implementation",
        tags=["events"],
        problem_statement="Create a fully type safe generic event emitter supporting on off and emit methods.",
        starter_code="class Emitter {}",
        reference_solution="export class TypedEventEmitter {\n    private listeners: Map<string, Function[]> = new Map();\n    on(event: string, fn: Function) { this.listeners.get(event)?.push(fn); }\n    emit(event: string, data: any) { this.listeners.get(event)?.forEach(f => f(data)); }\n}",
        unit_test_suite="expect(1).toBe(1);",
    )
    # Paraphrased version with >0.82 token overlap (just renaming data to payload)
    c2 = PolyglotChallenge(
        id="POLY-TS-2",
        language="typescript",
        tier="intermediate",
        title="EventEmitter Implementation",
        tags=["events"],
        problem_statement="Create a fully type safe generic event emitter supporting on off and emit methods.",
        starter_code="class Emitter {}",
        reference_solution="export class TypedEventEmitter {\n    private listeners: Map<string, Function[]> = new Map();\n    on(event: string, fn: Function) { this.listeners.get(event)?.push(fn); }\n    emit(event: string, payload: any) { this.listeners.get(event)?.forEach(f => f(payload)); }\n}",
        unit_test_suite="expect(1).toBe(1);",
    )

    silver = PolyglotSilverStage(fuzzy_jaccard_threshold=0.82)
    deduped, stats = silver.deduplicate([c1, c2])

    assert len(deduped) == 1
    assert deduped[0].id == "POLY-TS-1"
    assert stats["tier2_fuzzy_duplicates"] == 1


def test_tier3_semantic_collision_with_arbitration():
    """Verify Tier 3 semantic collision (> 0.92) triggers test-coverage arbitration."""
    # Item 1: Lower test coverage
    c1 = PolyglotChallenge(
        id="POLY-RUST-LOW",
        language="rust",
        tier="systems",
        title="Ring Buffer Implementation",
        tags=["rust", "concurrency"],
        problem_statement="Bounded SPSC ring buffer in Rust without mutexes.",
        starter_code="pub struct RB {}",
        reference_solution="pub struct RingBuffer { cap: usize }",
        unit_test_suite="assert!(true);",
        explanation_steps=["Step 1"],
    )
    # Item 2: Higher test coverage and better explanation (different solution to pass Tier 1)
    c2 = PolyglotChallenge(
        id="POLY-RUST-HIGH",
        language="rust",
        tier="systems",
        title="Ring Buffer Implementation",
        tags=["rust", "concurrency"],
        problem_statement="Bounded SPSC ring buffer in Rust without mutexes.",
        starter_code="pub struct RB {}",
        reference_solution="pub struct RingBuffer { capacity: usize }",
        unit_test_suite=(
            "#[test]\nfn test_push_pop() { assert!(rb.push(1).is_ok()); assert_eq!(rb.pop(), Some(1)); }\n"
            "#[test]\nfn test_overflow() { assert!(rb.push(2).is_err()); }\n"
            "#[test]\nfn test_concurrency() { assert!(true); }"
        ),
        explanation_steps=["Step 1", "Step 2", "Step 3", "Step 4"],
    )

    silver = PolyglotSilverStage(fuzzy_jaccard_threshold=0.99, semantic_threshold=0.90)

    # Identical embedding to simulate semantic collision >= 0.92
    mock_vec = [0.1] * 768
    deduped, stats = silver.deduplicate([c1, c2], embed_fn=lambda _: mock_vec)

    assert len(deduped) == 1
    # Candidate c2 has higher quality score and should win arbitration
    assert deduped[0].id == "POLY-RUST-HIGH"
    assert stats["tier3_semantic_duplicates"] == 1
    assert stats["arbitration_replacements"] == 1



def test_zero_duplicate_guarantee_on_curated_corpus():
    """Verify built-in curated corpus has strictly 0 duplicates across all 3 tiers."""
    corpus = PolyglotBronzeStage.load_seed_corpus()
    staged = PolyglotBronzeStage.validate_and_stage(corpus)

    silver = PolyglotSilverStage(fuzzy_jaccard_threshold=0.82, semantic_threshold=0.92)
    deduped, stats = silver.deduplicate(staged)

    assert len(deduped) == len(staged)
    assert stats["tier1_exact_duplicates"] == 0
    assert stats["tier2_fuzzy_duplicates"] == 0
    assert stats["tier3_semantic_duplicates"] == 0


# ============================================================================
# 3. GOLD PERSISTENCE & PHP 128 MB SAFEGUARD TESTS
# ============================================================================

def test_gold_persistence_and_php_memory_guard(temp_polyglot_db):
    """
    Verify full corpus writes to rag_documents while material_chunks is strictly
    capped at max_material_chunks to protect PHP's 128 MB memory ceiling.
    """
    corpus = PolyglotBronzeStage.load_seed_corpus()[:20]
    staged = PolyglotBronzeStage.validate_and_stage(corpus)

    # Cap chunks at 5 to verify enforcement
    gold = PolyglotGoldStage(
        db_path=temp_polyglot_db,
        max_material_chunks=5,
        enable_ollama=False,
    )
    stats = gold.persist(staged)

    assert stats["rag_documents_written"] == 20
    assert stats["material_chunks_written"] == 5

    conn = sqlite3.connect(str(temp_polyglot_db))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM rag_documents WHERE collection = 'polyglot_coding'")
    assert cur.fetchone()[0] == 20

    cur.execute("SELECT COUNT(*) FROM material_chunks")
    assert cur.fetchone()[0] == 5

    # Verify vector binary BLOB packaging matches 768 float32 values (3072 bytes)
    cur.execute("SELECT embedding FROM material_chunks LIMIT 1")
    blob = cur.fetchone()[0]
    assert len(blob) == 768 * 4
    unpacked = struct.unpack("768f", blob)
    assert len(unpacked) == 768
    conn.close()


def test_gold_ollama_search_document_prefix():
    """Verify Ollama embed call strictly prepends 'search_document: '."""
    gold = PolyglotGoldStage(enable_ollama=True)

    with patch("httpx.Client.post") as mock_post:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {"embeddings": [[0.05] * 768]}
        mock_post.return_value = mock_res

        vec = gold.get_embedding("fn main() { println!(\"Hello\"); }")
        assert vec is not None
        assert len(vec) == 768

        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        assert payload["input"].startswith("search_document: ")
        assert "fn main()" in payload["input"]


def test_gold_offline_fallback_vectors(temp_polyglot_db):
    """Verify deterministic unit vector fallback when Ollama is unreachable."""
    gold = PolyglotGoldStage(
        db_path=temp_polyglot_db,
        ollama_base_url="http://localhost:59999",  # unreachable port
        enable_ollama=True,
    )
    vec = gold.get_embedding("offline text")
    assert vec is None

    fb_vec = gold.generate_fallback_vector("offline text")
    assert len(fb_vec) == 768
    norm = sum(x * x for x in fb_vec) ** 0.5
    assert abs(norm - 1.0) < 1e-4


# ============================================================================
# 4. INSTRUCTION DATASET EXPORT & TOKEN CUTOFF TESTS
# ============================================================================

def test_export_polyglot_instruct_dataset_schema(tmp_path):
    """Verify Alpaca instruction format export and schema compliance."""
    corpus = PolyglotBronzeStage.load_seed_corpus()
    staged = PolyglotBronzeStage.validate_and_stage(corpus)
    out_file = tmp_path / "instruct_dataset.json"

    records = export_polyglot_instruct_dataset(staged, out_file, max_tokens=1024)
    assert len(records) == len(staged)
    assert out_file.exists()

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == len(staged)
    for rec in data:
        assert "instruction" in rec and len(rec["instruction"]) > 0
        assert "input" in rec
        assert "output" in rec and len(rec["output"]) > 0
        assert "language" in rec and rec["language"] in TIER_1_LANGUAGES
        assert "tier" in rec and rec["tier"] in DIFFICULTY_TIERS


def test_token_cutoff_enforcement(tmp_path):
    """Verify that oversized challenges are bounded to <= 1024 tokens (~3584 characters)."""
    oversized = PolyglotChallenge(
        id="POLY-OVERSIZED",
        language="python",
        tier="competitive",
        title="Oversized Challenge",
        tags=["long"],
        problem_statement="Problem " * 500,
        starter_code="def code(): pass",
        reference_solution="def code():\n    return 42",
        unit_test_suite="assert code() == 42\n" * 200,
        explanation_steps=["Explanation line " * 50] * 10,
    )
    out_file = tmp_path / "oversized_export.json"
    records = export_polyglot_instruct_dataset([oversized], out_file, max_tokens=1024)

    assert len(records) == 1
    rec = records[0]
    total_chars = len(rec["instruction"]) + len(rec["input"]) + len(rec["output"])
    assert total_chars <= int(1024 * 3.5) + 100


# ============================================================================
# 5. INTEGRATION & RE-EXPORT TESTS
# ============================================================================

def test_ingest_stem_knowledge_polyglot_reexports():
    """Verify scripts/ingest_stem_knowledge.py cleanly re-exports polyglot components."""
    assert len(STEM_REEXPORT_CORPUS) >= 32
    assert StemReexportChallenge is not None
    assert callable(stem_reexport_pipeline)


def test_full_polyglot_pipeline_end_to_end(temp_polyglot_db, tmp_path):
    """Verify complete end-to-end execution of run_polyglot_ingestion_pipeline."""
    export_json = tmp_path / "polyglot_test_export.json"
    summary = run_polyglot_ingestion_pipeline(
        db_path=temp_polyglot_db,
        output_dataset=export_json,
        max_material_chunks=15,
        enable_ollama=False,
    )

    assert summary["status"] == "success"
    assert summary["bronze_count"] >= 32
    assert summary["silver_retained"] >= 32
    assert summary["gold_stats"]["rag_documents_written"] >= 32
    assert summary["gold_stats"]["material_chunks_written"] == 15
    assert summary["exported_count"] >= 32
    assert export_json.exists()
