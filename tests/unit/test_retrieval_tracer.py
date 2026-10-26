"""
Unit tests for Retrieval Tracing & Lesson Utility Analyzer (Phase 4).
"""

import json
import pytest
from pathlib import Path
from scripts.retrieval_tracer import (
    audit_retrieval_traces,
    generate_retrieval_report,
)


@pytest.fixture
def tracer_env(tmp_path):
    traces_dir = tmp_path / "traces"
    reports_dir = tmp_path / "reports"
    traces_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Write a mock trace file
    sample_trace = {
        "timestamp": "2026-10-26T20:00:00Z",
        "task_id": "TASK-08-RETRIEVAL-SYMPLECTIC",
        "retrieval_calls": [
            {
                "tool": "rag_search",
                "collection": "knowledge",
                "query": "Stormer-Verlet integrator conventions",
                "results": ["stormer_verlet_integrator_conventions_v1"],
            },
            {
                "tool": "rag_search",
                "collection": "lessons",
                "query": "Kepler orbit energy conservation",
                "results": ["L-2026-10-0005"],
            },
        ],
        "citations": ["stormer_verlet_integrator_conventions_v1", "L-2026-10-0005"],
        "status": "PASS",
    }
    (traces_dir / "trace_task08.json").write_text(json.dumps(sample_trace, indent=2), encoding="utf-8")

    return traces_dir, reports_dir


def test_audit_retrieval_traces(tracer_env):
    traces_dir, _ = tracer_env
    stats = audit_retrieval_traces(traces_dir=traces_dir, retired_ids={"L-RETIRED-001"})

    assert stats["total_traces"] == 1
    assert stats["total_rag_searches"] == 2
    assert "stormer_verlet_integrator_conventions_v1" in stats["retrieved_docs"]
    assert "L-2026-10-0005" in stats["retrieved_lessons"]
    assert stats["retired_leak_count"] == 0
    assert stats["citation_count"] == 2


def test_retired_lessons_leak_detection(tracer_env):
    traces_dir, _ = tracer_env
    # Add a trace with a leaked retired lesson
    leak_trace = {
        "timestamp": "2026-10-26T20:01:00Z",
        "task_id": "TASK-01-CODE-LRU",
        "retrieval_calls": [
            {
                "tool": "rag_search",
                "collection": "lessons",
                "results": ["L-RETIRED-001"],
            }
        ],
        "citations": [],
    }
    (traces_dir / "trace_leak.json").write_text(json.dumps(leak_trace), encoding="utf-8")

    stats = audit_retrieval_traces(traces_dir=traces_dir, retired_ids={"L-RETIRED-001"})
    assert stats["retired_leak_count"] == 1
    assert "L-RETIRED-001" in stats["leaked_retired_lessons"]


def test_generate_retrieval_report(tracer_env):
    traces_dir, reports_dir = tracer_env
    stats = audit_retrieval_traces(traces_dir=traces_dir, retired_ids=set())
    report_file = generate_retrieval_report(stats=stats, output_dir=reports_dir)

    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "# Retrieval Tracing & Lesson Utility Report" in content
    assert "## 1. Retrieval Activity Summary" in content
    assert "## 2. Invariant Audits" in content
    assert "Total RAG Searches" in content
