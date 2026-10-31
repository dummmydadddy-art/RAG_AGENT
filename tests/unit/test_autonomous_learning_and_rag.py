"""
tests/unit/test_autonomous_learning_and_rag.py

TDD Acceptance Tests for Milestone 4: Autonomous Closed-Loop Self-Learning & Scalable RAG.
Verifies:
1. SQ8 Scalar Vector Quantization & Two-Stage SQLite Filtering:
   - Compresses 768-d float32 vectors to <= 776 bytes (>74% memory reduction).
   - Quantized cosine similarity achieves >= 99% fidelity (error < 0.01) against uncompressed vectors.
   - Two-stage retrieval pre-filters top K <= 50 candidates, bounding memory <= 38 MB.
2. APERL (Automated Post-Execution Reflection Loop):
   - Automatically distills error/fix pairs into canonical lessons: When <situation>, do <action>, because <reason>.
   - Upserts candidate lessons into RAG database.
3. Ebbinghaus Memory Consolidation Engine:
   - Computes retention decay R(t) = exp(-delta_t / S).
   - Retires or demotes stale unreinforced lessons.
   - Flags semantic contradictions between candidate and existing lessons.
4. Active Synthetic Challenge Generator (ASCG):
   - Generates polyglot coding challenges with verifiable test assertions.
   - Validates challenge execution through AST guard and sandbox.
"""

import pytest
import math
import numpy as np
from pathlib import Path
from scripts.learning.vector_quantizer import (
    SQ8VectorQuantizer,
    TwoStageRetriever,
)
from scripts.learning.aperl import (
    APERLEngine,
    ExecutionTrace,
    DistilledLesson,
)
from scripts.learning.memory_consolidation import (
    EbbinghausConsolidator,
    LessonConsolidationRecord,
)
from scripts.learning.synthetic_challenge_generator import (
    SyntheticChallengeGenerator,
    SyntheticChallenge,
)


class TestSQ8VectorQuantizerAndTwoStageFilter:
    """Verifies scalar quantization and 2-stage SQLite retrieval memory bounds."""

    def test_sq8_quantization_compression_ratio(self):
        """768-d float32 vector (3,072 bytes) compresses to <= 776 bytes."""
        quantizer = SQ8VectorQuantizer(dim=768)
        vec = np.random.randn(768).astype(np.float32)
        raw_bytes_len = len(vec.tobytes())
        assert raw_bytes_len == 3072

        quantized_blob = quantizer.quantize(vec)
        assert len(quantized_blob) <= 776
        compression_ratio = 1.0 - (len(quantized_blob) / raw_bytes_len)
        assert compression_ratio >= 0.74, f"Expected >=74% compression, got {compression_ratio:.2%}"

    def test_sq8_cosine_similarity_fidelity(self):
        """Quantized cosine similarity matches uncompressed float32 similarity within <0.01."""
        quantizer = SQ8VectorQuantizer(dim=768)
        v1 = np.random.randn(768).astype(np.float32)
        v2 = np.random.randn(768).astype(np.float32)

        # Uncompressed cosine similarity
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        sim_uncompressed = float(np.dot(v1, v2) / (norm_v1 * norm_v2))

        # Quantized cosine similarity
        q1 = quantizer.quantize(v1)
        q2 = quantizer.quantize(v2)
        sim_quantized = quantizer.quantized_similarity(q1, q2)

        error = abs(sim_uncompressed - sim_quantized)
        assert error < 0.01, f"Quantization error too large: {error} >= 0.01"

    def test_two_stage_candidate_prefilter_bounds_memory(self):
        """TwoStageRetriever filters top 50 candidates from 1,000 corpus items within <= 38MB peak memory."""
        retriever = TwoStageRetriever(dim=768)
        # Populate corpus with 1000 items
        corpus = []
        for i in range(1000):
            corpus.append({
                "id": f"chunk_{i:04d}",
                "text": f"STEM concept item {i} discussing differential calculus and physics equations.",
                "keywords": ["calculus", "physics"] if i % 20 == 0 else ["generic", "topic"],
                "embedding": np.random.randn(768).astype(np.float32),
            })
        retriever.index_corpus(corpus)

        results = retriever.search(
            query="differential calculus in physics",
            top_k=10,
            stage1_candidates_cap=50,
        )
        assert len(results) <= 10
        assert retriever.get_peak_memory_mb() <= 38.0


class TestAPERLReflectionLoop:
    """Verifies automated post-execution reflection and lesson distillation."""

    def test_distill_lesson_from_failure_and_fix(self):
        """Distills canonical lesson from error traceback and resolved patch."""
        aperl = APERLEngine()
        trace = ExecutionTrace(
            task_id="task_calc_degc",
            language="python",
            error_type="OffsetUnitCalculusError",
            error_message="Ambiguous operation with offset unit (degree_Celsius). Use Quantity constructor instead.",
            failed_code="T = 1.0 * ureg('degC')",
            fixed_code="T = ureg.Quantity(1.0, 'degC')",
            test_output="PASSED: temperature offset conversion",
        )

        lesson = aperl.distill_lesson(trace)
        assert isinstance(lesson, DistilledLesson)
        assert "degC" in lesson.situation or "OffsetUnitCalculusError" in lesson.situation
        assert "ureg.Quantity" in lesson.action
        assert "offset" in lesson.reason.lower()
        
        canonical_str = lesson.to_canonical_format()
        assert canonical_str.startswith("When ")
        assert ", do " in canonical_str
        assert ", because " in canonical_str

    def test_aperl_persists_canonical_lesson_to_rag(self, tmp_path: Path):
        """Persists distilled lesson into RAG database collection 'lessons'."""
        db_path = tmp_path / "test_vectors.sqlite"
        aperl = APERLEngine(db_path=db_path)
        trace = ExecutionTrace(
            task_id="task_sym_01",
            language="python",
            error_type="AssertionError",
            error_message="A*B - B*A must not equal 0 for non-commutative operators",
            failed_code="e1 = parse_expr('A*B - B*A')",
            fixed_code="e1 = parse_expr('A*B - B*A', local_dict={'A': Symbol('A', commutative=False), 'B': Symbol('B', commutative=False)})",
            test_output="PASSED: non-commutative operator algebra",
        )
        lesson_id = aperl.process_and_save(trace)
        assert lesson_id is not None
        assert lesson_id.startswith("lesson_")


class TestEbbinghausMemoryConsolidation:
    """Verifies retention decay, stale demotion, and contradiction detection."""

    def test_retention_decay_calculation(self):
        """Verifies exponential retention decay R(t) = exp(-delta_t / S)."""
        consolidator = EbbinghausConsolidator()
        
        # Immediate retention (delta_t = 0) is 1.0
        r0 = consolidator.calculate_retention(elapsed_days=0.0, strength=10.0)
        assert math.isclose(r0, 1.0, abs_tol=1e-5)

        # Retention after 10 days with strength 10: exp(-1) ~= 0.3678
        r1 = consolidator.calculate_retention(elapsed_days=10.0, strength=10.0)
        assert math.isclose(r1, math.exp(-1.0), abs_tol=1e-3)

        # Higher strength resists decay: strength 30 -> exp(-10/30) ~= 0.7165
        r2 = consolidator.calculate_retention(elapsed_days=10.0, strength=30.0)
        assert r2 > r1

    def test_consolidation_demotes_stale_lessons(self):
        """Lessons with retention < 0.2 and 0 recent usages are marked for demotion/retirement."""
        consolidator = EbbinghausConsolidator()
        records = [
            LessonConsolidationRecord(
                lesson_id="L1",
                content="When using Pint, do ureg.Quantity.",
                elapsed_days=45.0,
                strength=5.0,  # exp(-45/5) = exp(-9) ~= 0.0001
                usage_count=0,
                status="candidate",
            ),
            LessonConsolidationRecord(
                lesson_id="L2",
                content="When handling ODEs, do sym_ode_solve.",
                elapsed_days=2.0,
                strength=20.0,  # exp(-2/20) ~= 0.9048
                usage_count=12,
                status="verified",
            ),
        ]
        actions = consolidator.consolidate(records)
        assert "L1" in actions["retire"]
        assert "L2" not in actions["retire"]

    def test_contradiction_detection_flags_conflicts(self):
        """Detects direct contradictions between competing lessons."""
        consolidator = EbbinghausConsolidator()
        l_existing = "When computing temperature differences, do convert degC to kelvin with Quantity, because Pint offsets fail on subtraction."
        l_conflict = "When computing temperature differences, do not convert degC to kelvin, because Pint offsets work automatically."

        conflict = consolidator.detect_contradiction(l_conflict, l_existing)
        assert conflict["has_conflict"] is True
        assert conflict["conflict_score"] > 0.6


class TestActiveSyntheticChallengeGenerator:
    """Verifies background autonomous coding challenge synthesis."""

    def test_generate_synthetic_challenge_structure(self):
        """Synthesizes structured challenge with prompt, starter code, and test suite."""
        ascg = SyntheticChallengeGenerator()
        ch = ascg.generate_challenge(domain="physics", language="python", difficulty="intermediate")
        assert isinstance(ch, SyntheticChallenge)
        assert len(ch.prompt) > 20
        assert len(ch.test_suite) > 20
        assert ch.language == "python"

    def test_challenge_executes_in_sandbox(self):
        """Verifies synthetic challenge code runs safely through the sandboxed verifier."""
        ascg = SyntheticChallengeGenerator()
        sample_code = "def compute_kinetic_energy(m: float, v: float) -> float:\n    return 0.5 * m * v**2\n"
        sample_test = "assert abs(compute_kinetic_energy(2.0, 3.0) - 9.0) < 1e-6\n"
        
        result = ascg.verify_challenge_solution(
            solution_code=sample_code,
            test_code=sample_test,
            language="python",
        )
        assert result["success"] is True
        assert result["sandboxed"] is True
