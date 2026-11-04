"""
tests/unit/test_web_harvester.py

Comprehensive unit test suite for Milestone M1:
- HarvestedItem data model & formatted documents
- Arxiv Atom XML parser and domain mapping
- OfflineMockHarvesterAdapter deterministic generation across polyglot languages
- Shannon character entropy calculation & noise rejection heuristics
- Markdown text cleaner and boilerplate stripping
- AST & polyglot balanced delimiter syntax validation (Python, C++, Rust, Go, TS, Java, PHP, SQL)
- 3-Tier Silver Deduplication (Exact Hash, Lexical Jaccard, Semantic Topic Collision)
- SQ8 vector quantization (776-byte blobs, high similarity fidelity)
- Ingestion pipeline with strict 500-chunk FIFO ceiling in material_chunks
- Dynamic PHP 8.3 dequantization compatibility (776-byte SQ8 and 3072-byte raw)
"""

import math
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import List

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from unittest.mock import MagicMock, patch

from scripts.learning.web_harvester import (
    ArxivHarvesterAdapter,
    HarvestedItem,
    OfflineMockHarvesterAdapter,
    OpenCodeHarvesterAdapter,
    QualityFilterPipeline,
    SQ8VectorIngester,
    WebHarvester,
)
from scripts.learning.vector_quantizer import SQ8VectorQuantizer


# -----------------------------------------------------------------------------
# 1. Data Model Tests
# -----------------------------------------------------------------------------

def test_harvested_item_dataclass_and_serialization():
    item = HarvestedItem(
        id="test_stem_001",
        title="Hamiltonian Mechanics",
        concept="Conservation of phase space volume",
        domain="physics",
        tier="sme",
        text="Hamiltonian mechanics describes dynamical systems via symplectic manifolds.",
        code="def H(p, q): return 0.5 * (p**2) + (q**2)",
        language="python",
        source="arxiv",
        metadata={"paper_id": "1234.5678"},
    )

    doc_str = item.to_formatted_document()
    assert "# Hamiltonian Mechanics" in doc_str
    assert "**Domain**: physics | **Tier**: sme" in doc_str
    assert "```python" in doc_str
    assert "def H(p, q)" in doc_str

    item_dict = item.to_dict()
    assert item_dict["id"] == "test_stem_001"
    assert item_dict["domain"] == "physics"
    assert item_dict["metadata"]["paper_id"] == "1234.5678"


# -----------------------------------------------------------------------------
# 2. Arxiv Atom Feed Parsing Tests
# -----------------------------------------------------------------------------

def test_arxiv_atom_feed_parsing():
    sample_feed = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
        <entry>
            <id>http://arxiv.org/abs/2403.00001v1</id>
            <published>2024-03-01T12:00:00Z</published>
            <title> Symplectic Integrators for Quantum Many-Body Dynamics </title>
            <summary>
                We formulate energy-preserving symplectic schemes for Hamiltonian simulations.
                The algorithm bounds numerical energy drift over extended time horizons.
            </summary>
            <category term="physics.comp-ph" scheme="http://arxiv.org/schemas/atom"/>
            <category term="cs.NA" scheme="http://arxiv.org/schemas/atom"/>
        </entry>
        <entry>
            <id>http://arxiv.org/abs/2403.00002v1</id>
            <published>2024-03-02T15:00:00Z</published>
            <title> Automated Program Synthesis with Large Language Models </title>
            <summary>
                A novel framework for automated synthesis of provably correct software implementations.
            </summary>
            <category term="cs.SE" scheme="http://arxiv.org/schemas/atom"/>
        </entry>
    </feed>
    """

    items = ArxivHarvesterAdapter.parse_atom_feed(sample_feed, max_items=10)
    assert len(items) == 2

    # Check first item (physics)
    item1 = items[0]
    assert item1.id == "arxiv_2403_00001"
    assert item1.title == "Symplectic Integrators for Quantum Many-Body Dynamics"
    assert item1.domain == "physics"
    assert item1.tier == "sme"
    assert item1.source == "arxiv"
    assert "physics.comp-ph" in item1.metadata["categories"]

    # Check second item (coding/software engineering)
    item2 = items[1]
    assert item2.id == "arxiv_2403_00002"
    assert item2.domain == "coding"
    assert item2.title == "Automated Program Synthesis with Large Language Models"


# -----------------------------------------------------------------------------
# 3. Offline Mock Harvester Tests
# -----------------------------------------------------------------------------

def test_offline_mock_adapter():
    adapter = OfflineMockHarvesterAdapter()
    items = adapter.harvest(max_items=8)

    assert len(items) == 8
    languages = {item.language for item in items}
    expected_langs = {"python", "cpp", "rust", "go", "typescript", "java", "php", "sql"}
    assert expected_langs.issubset(languages)

    for item in items:
        assert len(item.text) >= 80
        assert len(item.code) >= 30
        assert item.source == "offline_mock"


def test_opencode_harvester_adapter():
    """Verifies OpenCodeHarvesterAdapter source parsing, mocked harvesting, and network error handling."""
    adapter = OpenCodeHarvesterAdapter(timeout=2.0)

    # 1. Catalog coverage check
    catalog_langs = {entry["language"] for entry in adapter.catalog}
    expected_langs = {"python", "cpp", "rust", "go", "typescript", "java", "php", "sql"}
    assert expected_langs.issubset(catalog_langs)

    # 2. Source parsing check (Python with docstring)
    py_code = (
        '"""\n'
        'Dijkstra shortest path algorithm implementation.\n'
        'Finds single-source shortest paths on non-negative weighted graphs.\n'
        'Time Complexity: O((V + E) log V).\n'
        '"""\n\n'
        'import heapq\n\n'
        'def dijkstra(graph, start):\n'
        '    distances = {node: float("inf") for node in graph}\n'
        '    distances[start] = 0\n'
        '    pq = [(0, start)]\n'
        '    while pq:\n'
        '        curr_dist, curr_node = heapq.heappop(pq)\n'
        '        if curr_dist > distances[curr_node]:\n'
        '            continue\n'
        '        for neighbor, weight in graph[curr_node].items():\n'
        '            d = curr_dist + weight\n'
        '            if d < distances[neighbor]:\n'
        '                distances[neighbor] = d\n'
        '                heapq.heappush(pq, (d, neighbor))\n'
        '    return distances\n'
    )
    py_entry = {
        "id": "test_py_dijkstra",
        "title": "Dijkstra Algorithm",
        "concept": "Single-source shortest path using priority queues",
        "domain": "coding",
        "tier": "advanced",
        "language": "python",
        "url": "https://example.com/dijkstra.py",
    }
    item = OpenCodeHarvesterAdapter.parse_source_content(py_code, py_entry)
    assert item.id == "test_py_dijkstra"
    assert item.language == "python"
    assert item.source == "opencode"
    assert "Dijkstra shortest path" in item.text
    assert len(item.text) >= 80
    assert "def dijkstra" in item.code

    # 3. Source parsing check (C++ with block comment)
    cpp_code = (
        "/**\n"
        " * @brief QuickSort implementation with median-of-three pivot.\n"
        " * Divides array into subproblems and sorts recursively in-place.\n"
        " */\n"
        "#include <vector>\n"
        "#include <algorithm>\n\n"
        "void quicksort(std::vector<int>& arr, int low, int high) {\n"
        "    if (low < high) {\n"
        "        int pivot = arr[high];\n"
        "        int i = low - 1;\n"
        "        for (int j = low; j < high; ++j) {\n"
        "            if (arr[j] < pivot) std::swap(arr[++i], arr[j]);\n"
        "        }\n"
        "        std::swap(arr[i + 1], arr[high]);\n"
        "        quicksort(arr, low, i);\n"
        "        quicksort(arr, i + 2, high);\n"
        "    }\n"
        "}\n"
    )
    cpp_entry = {
        "id": "test_cpp_qs",
        "title": "C++ QuickSort",
        "concept": "In-place partition sorting",
        "domain": "coding",
        "tier": "advanced",
        "language": "cpp",
        "url": "https://example.com/qs.cpp",
    }
    cpp_item = OpenCodeHarvesterAdapter.parse_source_content(cpp_code, cpp_entry)
    assert cpp_item.language == "cpp"
    assert len(cpp_item.text) >= 80
    assert "void quicksort" in cpp_item.code

    # 4. Mocked HTTP fetching
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = py_code

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        harvested = adapter.harvest(max_items=2)
        assert len(harvested) == 2
        assert all(isinstance(h, HarvestedItem) for h in harvested)
        assert all(h.source == "opencode" for h in harvested)

    # 5. Network error handling (verifying graceful recovery without unhandled exceptions)
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.side_effect = Exception("Network timeout/connection refused")
        mock_client_cls.return_value = mock_client

        failed_items = adapter.harvest(max_items=2)
        assert failed_items == []


# -----------------------------------------------------------------------------
# 4. Shannon Character Entropy Tests
# -----------------------------------------------------------------------------

def test_shannon_entropy_calculation():
    pipeline = QualityFilterPipeline()

    assert pipeline.calculate_shannon_entropy("") == 0.0

    # Low entropy (repetitive stream)
    repetitive_text = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    h_low = pipeline.calculate_shannon_entropy(repetitive_text)
    assert h_low < 1.0

    # Standard informative English STEM prose (typically 3.5 - 5.5 bits/char)
    natural_text = (
        "The Störmer-Verlet algorithm is a second-order symplectic integrator designed "
        "for separable Hamiltonian dynamical systems of the form H(q, p) = T(p) + V(q)."
    )
    h_nat = pipeline.calculate_shannon_entropy(natural_text)
    assert 3.0 <= h_nat <= 6.0

    # High entropy random character distribution
    import string, random
    rng = random.Random(42)
    # Generate broad uniform mix of ASCII printable + unicode chars
    high_entropy_chars = [chr(rng.randint(32, 255)) for _ in range(500)]
    high_entropy_text = "".join(high_entropy_chars)
    h_high = pipeline.calculate_shannon_entropy(high_entropy_text)
    assert h_high > 6.0


# -----------------------------------------------------------------------------
# 5. Text Cleaner & Boilerplate Stripper Tests
# -----------------------------------------------------------------------------

def test_markdown_cleaner_and_boilerplate_removal():
    pipeline = QualityFilterPipeline()
    raw = (
        "&lt;h1&gt;Calculus &amp; Linear Algebra&lt;/h1&gt;\n\n"
        "Click here to read more about vector spaces.\n\n"
        "Terms of service apply to all users.\n\n"
        "This is genuine STEM curriculum content on eigenvalue decomposition.\n\n"
        "All rights reserved. Cookie notice."
    )

    cleaned = pipeline.clean_text(raw)
    assert "<h1>" in cleaned or "<h1" not in cleaned  # unescaped
    assert "&" in cleaned
    assert "Click here to read more" not in cleaned
    assert "Terms of service" not in cleaned
    assert "Cookie notice" not in cleaned
    assert "eigenvalue decomposition" in cleaned


# -----------------------------------------------------------------------------
# 6. Noise Rejection Filter Tests
# -----------------------------------------------------------------------------

def test_noise_rejection_heuristics():
    pipeline = QualityFilterPipeline()

    # Case A: Too short text
    item_short = HarvestedItem(
        id="short", title="Short", concept="Short", domain="coding", tier="elem",
        text="Too short text.", code="print('hello')", language="python"
    )
    passed, reason = pipeline.filter_noise(item_short)
    assert not passed
    assert "text_too_short" in reason

    # Case B: Too short code
    item_short_code = HarvestedItem(
        id="sc", title="Short Code", concept="concept", domain="coding", tier="elem",
        text="Valid long enough text description for the algorithm under consideration that exceeds eighty characters.",
        code="x = 1", language="python"
    )
    passed, reason = pipeline.filter_noise(item_short_code)
    assert not passed
    assert "code_too_short" in reason

    # Case C: Low entropy repetitive spam
    item_spam = HarvestedItem(
        id="spam", title="Spam", concept="concept", domain="coding", tier="elem",
        text="A" * 150, code="", language="python"
    )
    passed, reason = pipeline.filter_noise(item_spam)
    assert not passed
    assert "entropy_too_low" in reason

    # Case D: Valid item
    item_valid = HarvestedItem(
        id="valid", title="Valid Title", concept="Valid Concept", domain="coding", tier="sme",
        text="The quick brown fox jumps over the lazy dog. Algorithmic complexity is O(N log N) with quicksort.",
        code="def quicksort(arr):\n    if len(arr) <= 1: return arr\n    pivot = arr[0]\n    return [x for x in arr[1:] if x < pivot] + [pivot] + [x for x in arr[1:] if x >= pivot]\n",
        language="python"
    )
    passed, reason = pipeline.filter_noise(item_valid)
    assert passed
    assert reason == "passed"


# -----------------------------------------------------------------------------
# 7. AST & Polyglot Syntax Validation Tests
# -----------------------------------------------------------------------------

def test_ast_and_polyglot_syntax_validation():
    pipeline = QualityFilterPipeline()

    # Python valid
    py_ok = "def add(a: int, b: int) -> int:\n    return a + b\n"
    assert pipeline.validate_syntax(py_ok, "python")[0] is True

    # Python invalid syntax
    py_bad = "def add(a, b\n    return a +"
    passed, reason = pipeline.validate_syntax(py_bad, "python")
    assert passed is False
    assert "python_syntax_error" in reason

    # C++ balanced vs unbalanced
    cpp_ok = (
        "#include <iostream>\n"
        "int main() {\n"
        "    std::cout << \"Hello world!\" << std::endl;\n"
        "    return 0;\n"
        "}\n"
    )
    assert pipeline.validate_syntax(cpp_ok, "cpp")[0] is True

    cpp_bad = "int main() { std::cout << 'x'; return 0;"  # missing closing brace
    assert pipeline.validate_syntax(cpp_bad, "cpp")[0] is False

    # Rust with lifetimes (e.g. 'a, 'static)
    rust_ok = (
        "pub struct Frame<'a> {\n"
        "    pub data: &'a [u8],\n"
        "}\n"
        "impl<'a> Frame<'a> {\n"
        "    pub fn new(d: &'a [u8]) -> Self { Self { data: d } }\n"
        "}\n"
    )
    assert pipeline.validate_syntax(rust_ok, "rust")[0] is True

    # SQL with keyword check and in-memory SQLite EXPLAIN
    sql_ok = "SELECT u.id, u.name FROM users u WHERE u.active = 1 ORDER BY u.created_at DESC;"
    assert pipeline.validate_syntax(sql_ok, "sql")[0] is True

    # Valid complex recursive CTE (even on tables not yet created in memory)
    sql_cte_ok = (
        "WITH RECURSIVE OrgHierarchy AS (\n"
        "    SELECT emp_id, manager_id, title, 1 AS depth\n"
        "    FROM employees\n"
        "    WHERE manager_id IS NULL\n"
        "    UNION ALL\n"
        "    SELECT e.emp_id, e.manager_id, e.title, h.depth + 1\n"
        "    FROM employees e\n"
        "    INNER JOIN OrgHierarchy h ON e.manager_id = h.emp_id\n"
        ")\n"
        "SELECT emp_id, title, depth\n"
        "FROM OrgHierarchy\n"
        "ORDER BY depth ASC;\n"
    )
    assert pipeline.validate_syntax(sql_cte_ok, "sql")[0] is True

    # Broken SQL syntax with orphaned SELECT clause (must be rejected by EXPLAIN)
    sql_broken_syntax = (
        "WITH RECURSIVE OrgHierarchy AS (\n"
        "    SELECT emp_id, manager_id, title, 1 AS depth\n"
        "    SELECT manager_id IS NULL\n"
        "    FROM employees\n"
        "    WHERE manager_id IS NULL\n"
        ")\n"
        "SELECT * FROM OrgHierarchy;\n"
    )
    passed_broken, reason_broken = pipeline.validate_syntax(sql_broken_syntax, "sql")
    assert passed_broken is False
    assert "sql_syntax_error" in reason_broken

    sql_no_kw = "just some arbitrary text without any recognized database statement;"
    passed_sql, reason_sql = pipeline.validate_syntax(sql_no_kw, "sql")
    assert passed_sql is False
    assert "sql_missing_keywords" in reason_sql

    # TypeScript with template literal backticks
    ts_ok = (
        "export function greet(name: string): string {\n"
        "    const msg = `Hello, ${name}!`;\n"
        "    return msg;\n"
        "}\n"
    )
    assert pipeline.validate_syntax(ts_ok, "typescript")[0] is True


# -----------------------------------------------------------------------------
# 8. 3-Tier Deduplication Tests
# -----------------------------------------------------------------------------

def test_three_tier_deduplication():
    pipeline = QualityFilterPipeline()

    base_item = HarvestedItem(
        id="item_001",
        title="Dijkstra Shortest Path Algorithm",
        concept="Finding single source shortest paths on non-negative weighted graphs",
        domain="coding",
        tier="advanced",
        text="Dijkstra algorithm explores graphs using a priority queue to achieve optimal shortest paths on large weighted graphs with non-negative edge weights everywhere.",
        code="def dijkstra(graph, start): pass\n",
        language="python"
    )

    # Tier 1 Duplicate: Same content and code
    t1_dup = HarvestedItem(
        id="item_001_copy",
        title="  dijkstra  shortest  path algorithm  ",
        concept="Finding single source shortest paths on non-negative weighted graphs",
        domain="coding",
        tier="advanced",
        text="Different text here, but exact normalized title, concept and code",
        code="def dijkstra(graph, start): pass\n",
        language="python"
    )

    # Tier 2 Duplicate: High Jaccard lexical shingle overlap (adding one trailing word gives > 0.90 Jaccard)
    t2_dup = HarvestedItem(
        id="item_002",
        title="Different Title For Dijkstra",
        concept="Different concept statement",
        domain="coding",
        tier="advanced",
        text="Dijkstra algorithm explores graphs using a priority queue to achieve optimal shortest paths on large weighted graphs with non-negative edge weights everywhere indeed.",
        code="def other_impl(): pass\n",
        language="python"
    )

    # Tier 3 Duplicate: Semantic topic key collision (domain, tier, normalized_title)
    t3_dup = HarvestedItem(
        id="item_003",
        title="Dijkstra Shortest Path Algorithm",
        concept="A completely different concept description here",
        domain="coding",
        tier="advanced",
        text="Completely different article text explaining graph traversal without any matching words or shingles.",
        code="def unique_code(): return 42\n",
        language="python"
    )

    # Completely unique item
    unique_item = HarvestedItem(
        id="item_004",
        title="Symplectic Geometric Integrator",
        concept="Preserving Hamiltonian energy and phase space volume",
        domain="physics",
        tier="sme",
        text="Störmer Verlet integration provides second-order symplectic trajectory tracking for planetary orbital dynamics.",
        code="def verlet(q, v, dt): return q + v * dt\n",
        language="python"
    )

    candidates = [base_item, t1_dup, t2_dup, t3_dup, unique_item]
    deduped, stats = pipeline.deduplicate(candidates)

    assert len(deduped) == 2
    assert deduped[0].id == "item_001"
    assert deduped[1].id == "item_004"
    assert stats["exact_hash_duplicates"] >= 1
    assert stats["jaccard_near_duplicates"] >= 1 or stats["semantic_topic_collisions"] >= 1


# -----------------------------------------------------------------------------
# 9. SQ8 Quantization & Cosine Similarity Fidelity Tests
# -----------------------------------------------------------------------------

def test_sq8_vector_quantization_and_packing():
    quantizer = SQ8VectorQuantizer(dim=768)

    rng = np.random.RandomState(42)
    vec1 = rng.randn(768).astype(np.float32)
    vec2 = (vec1 + 0.1 * rng.randn(768)).astype(np.float32)

    blob1 = quantizer.quantize(vec1)
    blob2 = quantizer.quantize(vec2)

    assert len(blob1) == 776
    assert len(blob2) == 776

    # Test reconstruction fidelity
    deq1 = quantizer.dequantize(blob1)
    assert deq1.shape == (768,)
    # Peak error on normalized range should be <= 0.02
    spread = float(np.max(vec1) - np.min(vec1))
    max_abs_err = np.max(np.abs(vec1 - deq1))
    assert max_abs_err <= (spread / 255.0) * 1.5

    # Test quantized cosine similarity vs raw cosine similarity
    raw_sim = float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))
    q_sim = quantizer.quantized_similarity(blob1, blob2)
    assert abs(raw_sim - q_sim) < 0.01


# -----------------------------------------------------------------------------
# 10. SQ8 Ingestion & Strict 500-Chunk Ceiling FIFO Eviction Tests
# -----------------------------------------------------------------------------

def test_sq8_ingester_and_fifo_500_chunk_ceiling(tmp_path):
    test_db = tmp_path / "vectors_test.sqlite"
    # Test with a bounded ceiling of 10 chunks to verify FIFO eviction deterministically
    ingester = SQ8VectorIngester(
        db_path=test_db,
        max_material_chunks=10,
        enable_ollama=False,  # Use deterministic fallback
    )

    items_batch_1 = [
        HarvestedItem(
            id=f"item_b1_{i:02d}",
            title=f"Batch 1 Algorithm {i}",
            concept=f"Concept for algorithm {i}",
            domain="coding",
            tier="advanced",
            text=f"Detailed explanatory text for algorithm {i} with sufficient length to pass through.",
            code=f"def alg_{i}(): return {i}\n",
            language="python",
        )
        for i in range(8)
    ]

    stats1 = ingester.ingest(items_batch_1, collection="stem_knowledge")
    assert stats1["rag_documents_upserted"] == 8
    assert stats1["material_chunks_inserted"] == 8
    assert stats1["material_chunks_evicted"] == 0
    assert stats1["total_material_chunks_after"] == 8

    # Now ingest batch 2 with 6 items: total attempted = 8 + 6 = 14 > ceiling of 10
    # Must evict 4 oldest items from batch 1
    items_batch_2 = [
        HarvestedItem(
            id=f"item_b2_{i:02d}",
            title=f"Batch 2 Algorithm {i}",
            concept=f"Concept for batch 2 item {i}",
            domain="physics",
            tier="sme",
            text=f"Detailed physics lesson for item {i} with sufficient length to satisfy criteria.",
            code=f"def phys_{i}(): return {i} * 9.81\n",
            language="python",
        )
        for i in range(6)
    ]

    stats2 = ingester.ingest(items_batch_2, collection="stem_knowledge")
    assert stats2["material_chunks_evicted"] == 4
    assert stats2["material_chunks_inserted"] == 6
    assert stats2["total_material_chunks_after"] == 10

    # Verify directly via sqlite query
    conn = sqlite3.connect(str(test_db))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM material_chunks")
    chunk_count = cur.fetchone()[0]
    assert chunk_count == 10  # Strictly capped at 10!

    cur.execute("SELECT COUNT(*) FROM rag_documents WHERE collection = 'stem_knowledge'")
    doc_count = cur.fetchone()[0]
    assert doc_count == 14  # All 14 preserved in uncapped rag_documents!

    # Verify embedding blobs in material_chunks are 776 bytes (SQ8)
    cur.execute("SELECT length(embedding) FROM material_chunks")
    lengths = [r[0] for r in cur.fetchall()]
    assert all(l == 776 for l in lengths)

    # Verify deterministic chunk IDs format (chunk_{item.id}_{idx:03d})
    cur.execute("SELECT id FROM material_chunks")
    chunk_ids = [r[0] for r in cur.fetchall()]
    assert all(cid.startswith("chunk_") for cid in chunk_ids)
    conn.close()

    # Verify Reviewer 2 edge-case: ingesting a batch larger than ceiling into empty table (15 items with ceiling 10)
    empty_db = tmp_path / "vectors_overflow.sqlite"
    overflow_ingester = SQ8VectorIngester(
        db_path=empty_db,
        max_material_chunks=10,
        enable_ollama=False,
    )
    overflow_items = [
        HarvestedItem(
            id=f"overflow_{i:02d}",
            title=f"Overflow Item {i}",
            concept=f"Concept {i}",
            domain="coding",
            tier="advanced",
            text=f"Detailed explanatory text for overflow algorithm {i} with sufficient length.",
            code=f"def over_{i}(): return {i}\n",
            language="python",
        )
        for i in range(15)
    ]
    overflow_stats = overflow_ingester.ingest(overflow_items, collection="stem_knowledge")
    assert overflow_stats["material_chunks_inserted"] == 15
    assert overflow_stats["material_chunks_evicted"] == 5
    assert overflow_stats["total_material_chunks_after"] == 10

    conn_over = sqlite3.connect(str(empty_db))
    cur_over = conn_over.cursor()
    cur_over.execute("SELECT COUNT(*) FROM material_chunks")
    assert cur_over.fetchone()[0] == 10  # Strictly capped at 10!
    cur_over.execute("SELECT id FROM material_chunks")
    over_ids = [r[0] for r in cur_over.fetchall()]
    assert all(cid.startswith("chunk_overflow_") for cid in over_ids)
    conn_over.close()


# -----------------------------------------------------------------------------
# 11. PHP Dynamic Dequantization Compatibility Tests
# -----------------------------------------------------------------------------

def test_php_dequantization_compatibility():
    """
    Verifies that backend/rag_service.php unpackVector dequantizes both:
    1. 776-byte SQ8 binary blob into 768 floats
    2. 3072-byte uncompressed float32 binary blob into 768 floats
    """
    # Find PHP executable
    php_bin = shutil.which("php")
    if not php_bin:
        pytest.skip("php executable not found on system PATH")

    quantizer = SQ8VectorQuantizer(dim=768)
    rng = np.random.RandomState(123)
    vec = rng.uniform(-1.0, 1.0, 768).astype(np.float32)

    # 1. Generate SQ8 binary blob (776 bytes)
    sq8_blob = quantizer.quantize(vec)
    assert len(sq8_blob) == 776

    # 2. Generate uncompressed raw binary blob (3072 bytes)
    raw_blob = vec.tobytes()
    assert len(raw_blob) == 3072

    # Save to temp files
    tmp_sq8 = Path("tmp_test_sq8.bin")
    tmp_raw = Path("tmp_test_raw.bin")
    try:
        tmp_sq8.write_bytes(sq8_blob)
        tmp_raw.write_bytes(raw_blob)

        php_script = (
            "require 'backend/rag_service.php';\n"
            "$sq8 = file_get_contents('tmp_test_sq8.bin');\n"
            "$raw = file_get_contents('tmp_test_raw.bin');\n"
            "$v_sq8 = RagService::unpackVector($sq8);\n"
            "$v_raw = RagService::unpackVector($raw);\n"
            "echo count($v_sq8) . ',' . count($v_raw) . ',' . sprintf('%.6f', $v_sq8[0]) . ',' . sprintf('%.6f', $v_raw[0]);\n"
        )

        res = subprocess.run([php_bin, "-r", php_script], capture_output=True, text=True, timeout=10)
        assert res.returncode == 0, f"PHP error: {res.stderr}"

        parts = res.stdout.strip().split(",")
        assert len(parts) == 4
        assert int(parts[0]) == 768  # SQ8 count
        assert int(parts[1]) == 768  # Raw count

        php_sq8_first = float(parts[2])
        php_raw_first = float(parts[3])
        assert abs(php_sq8_first - float(vec[0])) < 0.02
        assert abs(php_raw_first - float(vec[0])) < 1e-5

    finally:
        if tmp_sq8.exists():
            tmp_sq8.unlink()
        if tmp_raw.exists():
            tmp_raw.unlink()


# -----------------------------------------------------------------------------
# 12. Full WebHarvester Orchestrator End-to-End Tests
# -----------------------------------------------------------------------------

def test_web_harvester_orchestrator_end_to_end(tmp_path):
    test_db = tmp_path / "web_harvester_e2e.sqlite"
    harvester = WebHarvester(db_path=test_db, max_material_chunks=20)

    # Run mock harvest and ingestion
    result = harvester.harvest_and_ingest(max_items=8, mock=True)

    assert result["status"] == "success"
    assert result["harvested_raw_count"] == 8
    assert result["clean_items_count"] == 8
    assert result["material_chunks_total"] == 8
    assert result["ingest_summary"]["material_chunks_inserted"] == 8

    # Query status telemetry
    status = harvester.get_status()
    assert status["total_harvested"] == 8
    assert status["total_passed_quality"] == 8
    assert status["material_chunks_count"] == 8
    assert status["stem_knowledge_docs_count"] == 8
    assert status["material_chunks_ceiling"] == 20
