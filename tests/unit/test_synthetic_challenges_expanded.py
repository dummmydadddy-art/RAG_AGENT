"""
tests/unit/test_synthetic_challenges_expanded.py

Unit and integration tests for Expanded Synthetic Challenge Generator (scripts/learning/synthetic_challenge_generator.py).
Verifies:
1. SyntheticChallenge 9-field schema and backward compatibility with 6 positional arguments.
2. High-difficulty challenges across 4 domains (DP, Graphs, Concurrency, Numerical Physics).
3. 4-tier automated test harness verification (Smoke, Boundary, Scale Stress, Invariants).
4. Physical invariants (Hamiltonian energy drift < 1e-4, angular momentum drift < 1e-10, monotonic dissipation).
5. Algorithmic invariants (Flow conservation, Min-Cut duality, Held-Karp cycle, Capacity bounds).
6. AST security compliance for all reference solutions.
7. Autonomous model solver (solve_challenge) offline fallback, Ollama probe, extraction, and mock tests.
8. End-to-end integration: solve_challenge -> execute_sandboxed_code -> assert success.
"""

import ast
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from scripts.learning.synthetic_challenge_generator import (
    SyntheticChallenge,
    SyntheticChallengeGenerator,
    extract_runnable_code,
    is_ollama_available,
    solve_challenge,
)
from src.sandbox.win32_job import check_ast_safety, execute_sandboxed_code


class TestSyntheticChallengeSchema:
    """Verifies SyntheticChallenge schema and backward compatibility."""

    def test_dataclass_9_fields_and_defaults(self):
        ch = SyntheticChallenge(
            challenge_id="syn_1234",
            domain="dynamic_programming",
            language="python",
            prompt="Solve knapsack",
            starter_code="def solve(): pass",
            test_suite="assert True",
            difficulty="advanced",
            reference_solution="def solve(): return 1",
            invariants=["capacity_bounded"],
        )
        assert ch.challenge_id == "syn_1234"
        assert ch.domain == "dynamic_programming"
        assert ch.language == "python"
        assert ch.difficulty == "advanced"
        assert ch.reference_solution == "def solve(): return 1"
        assert ch.invariants == ["capacity_bounded"]

    def test_backward_compatible_6_args(self):
        ch = SyntheticChallenge(
            "syn_legacy",
            "physics",
            "python",
            "compute energy",
            "def e(): pass",
            "assert True",
        )
        assert ch.challenge_id == "syn_legacy"
        assert ch.difficulty == "intermediate"
        assert ch.reference_solution == ""
        assert ch.invariants == []


class TestDynamicProgrammingChallenges:
    """Verifies Dynamic Programming challenges and 4-tier harnesses."""

    def test_knapsack_generation_and_execution(self):
        gen = SyntheticChallengeGenerator()
        ch = gen.generate_challenge(
            domain="dynamic_programming",
            language="python",
            challenge_key="multi_constrained_knapsack",
        )
        assert ch.domain == "dynamic_programming"
        assert "multi_constrained_knapsack" in ch.prompt
        assert len(ch.invariants) >= 4
        assert "capacity_bounded" in ch.invariants

        # Execute reference solution in sandbox
        res = execute_sandboxed_code(ch.reference_solution, ch.test_suite, timeout=5.0)
        assert res.success is True, f"Knapsack test suite failed: {res.stderr}"
        assert res.returncode == 0
        assert res.duration_s < 2.0
        assert res.peak_memory_bytes > 0

    def test_tsp_bitmask_generation_and_execution(self):
        gen = SyntheticChallengeGenerator()
        ch = gen.generate_challenge(
            domain="dp",
            language="python",
            challenge_key="solve_tsp_bitmask",
        )
        assert ch.domain == "dynamic_programming"
        assert "solve_tsp_bitmask" in ch.prompt
        assert "hamiltonian_cycle_completeness" in ch.invariants

        # Execute reference solution in sandbox
        res = execute_sandboxed_code(ch.reference_solution, ch.test_suite, timeout=5.0)
        assert res.success is True, f"TSP test suite failed: {res.stderr}"
        assert res.returncode == 0
        assert res.duration_s < 2.0

    def test_dp_faulty_solution_fails_assertions(self):
        gen = SyntheticChallengeGenerator()
        ch = gen.generate_challenge(
            domain="dynamic_programming",
            challenge_key="multi_constrained_knapsack",
        )
        faulty_code = (
            "def multi_constrained_knapsack(weights, volumes, values, max_weight, max_volume):\n"
            "    return 0, []\n"
        )
        res = execute_sandboxed_code(faulty_code, ch.test_suite, timeout=5.0)
        assert res.success is False
        assert "AssertionError" in res.stderr


class TestGraphAlgorithmsChallenges:
    """Verifies Graph Algorithms challenges and 4-tier harnesses."""

    def test_max_flow_edmonds_karp_and_min_cut(self):
        gen = SyntheticChallengeGenerator()
        ch = gen.generate_challenge(
            domain="graph_algorithms",
            language="python",
            challenge_key="max_flow_edmonds_karp",
        )
        assert ch.domain == "graph_algorithms"
        assert "flow_conservation" in ch.invariants
        assert "max_flow_min_cut_equality" in ch.invariants

        res = execute_sandboxed_code(ch.reference_solution, ch.test_suite, timeout=5.0)
        assert res.success is True, f"Max flow test suite failed: {res.stderr}"
        assert res.returncode == 0

    def test_bellman_ford_negative_cycles(self):
        gen = SyntheticChallengeGenerator()
        ch = gen.generate_challenge(
            domain="graphs",
            language="python",
            challenge_key="bellman_ford_negative_cycles",
        )
        assert ch.domain == "graph_algorithms"
        assert "triangle_inequality" in ch.invariants
        assert "negative_cycle_certificate_negative_sum" in ch.invariants

        res = execute_sandboxed_code(ch.reference_solution, ch.test_suite, timeout=5.0)
        assert res.success is True, f"Bellman Ford test suite failed: {res.stderr}"
        assert res.returncode == 0


class TestConcurrencyChallenges:
    """Verifies Concurrency challenges and thread-safety invariants."""

    def test_bounded_ring_buffer_concurrency(self):
        gen = SyntheticChallengeGenerator()
        ch = gen.generate_challenge(
            domain="concurrency",
            language="python",
            challenge_key="bounded_ring_buffer",
        )
        assert ch.domain == "concurrency"
        assert "fifo_ordering_per_producer" in ch.invariants
        assert "lossless_multithread_accounting" in ch.invariants

        res = execute_sandboxed_code(ch.reference_solution, ch.test_suite, timeout=5.0)
        assert res.success is True, f"RingBuffer test suite failed: {res.stderr}"
        assert res.returncode == 0

    def test_memory_pool_lease_and_double_free(self):
        gen = SyntheticChallengeGenerator()
        ch = gen.generate_challenge(
            domain="systems",
            language="python",
            challenge_key="thread_safe_memory_pool",
        )
        assert ch.domain == "concurrency"
        assert "double_free_protection" in ch.invariants
        assert "block_conservation" in ch.invariants

        res = execute_sandboxed_code(ch.reference_solution, ch.test_suite, timeout=5.0)
        assert res.success is True, f"MemoryPool test suite failed: {res.stderr}"
        assert res.returncode == 0


class TestNumericalPhysicsChallenges:
    """Verifies Numerical Physics challenges and physical conservation laws."""

    def test_symplectic_verlet_orbit_conservation(self):
        gen = SyntheticChallengeGenerator()
        ch = gen.generate_challenge(
            domain="numerical_physics",
            language="python",
            challenge_key="symplectic_velocity_verlet",
        )
        assert ch.domain == "numerical_physics"
        assert "symplectic_hamiltonian_conservation" in ch.invariants
        assert "angular_momentum_exact_conservation" in ch.invariants

        res = execute_sandboxed_code(ch.reference_solution, ch.test_suite, timeout=5.0)
        assert res.success is True, f"Symplectic Verlet test suite failed: {res.stderr}"
        assert res.returncode == 0

    def test_damped_harmonic_oscillator_dissipation(self):
        gen = SyntheticChallengeGenerator()
        ch = gen.generate_challenge(
            domain="physics",
            language="python",
            challenge_key="damped_harmonic_oscillator",
        )
        assert ch.domain == "numerical_physics"
        assert "energy_dissipation_monotonicity" in ch.invariants
        assert "undamped_energy_conservation" in ch.invariants

        res = execute_sandboxed_code(ch.reference_solution, ch.test_suite, timeout=5.0)
        assert res.success is True, f"Damped oscillator test suite failed: {res.stderr}"
        assert res.returncode == 0


class TestDomainAliasesAndBackwardCompatibility:
    """Verifies domain alias resolution and legacy template access."""

    def test_domain_aliases(self):
        gen = SyntheticChallengeGenerator()
        for alias, target in [
            ("dp", "dynamic_programming"),
            ("graphs", "graph_algorithms"),
            ("graph", "graph_algorithms"),
            ("systems", "concurrency"),
            ("physics", "numerical_physics"),
        ]:
            ch = gen.generate_challenge(domain=alias, language="python")
            assert ch.domain == target

    def test_legacy_templates_preserved(self):
        gen = SyntheticChallengeGenerator()
        ch_rust = gen.generate_challenge(domain="physics", language="rust")
        assert ch_rust.language == "rust"
        assert "orbital_velocity" in ch_rust.prompt

        ch_cpp = gen.generate_challenge(domain="systems", language="cpp")
        assert ch_cpp.language == "cpp"
        assert "ring buffer" in ch_cpp.prompt.lower()
        assert "RingBuffer" in ch_cpp.starter_code


class TestASTSecurityCompliance:
    """Verifies that all starter codes and reference solutions pass AST guard."""

    def test_all_reference_solutions_pass_ast_guard(self):
        gen = SyntheticChallengeGenerator()
        for dom, templates in gen.CHALLENGE_TEMPLATES.items():
            for name, tmpl in templates.items():
                ref = tmpl["reference_solution"]
                starter = tmpl["starter_code"]

                is_safe_ref, err_ref = check_ast_safety(ref)
                assert is_safe_ref is True, f"Reference solution for {dom}:{name} failed AST guard: {err_ref}"

                is_safe_start, err_start = check_ast_safety(starter)
                assert is_safe_start is True, f"Starter code for {dom}:{name} failed AST guard: {err_start}"


class TestAutonomousModelSolver:
    """Verifies solve_challenge, code extraction, and offline fallback."""

    def test_solve_challenge_offline_fallback(self):
        gen = SyntheticChallengeGenerator()
        ch = gen.generate_challenge(domain="dp", language="python")
        sol = solve_challenge(ch, use_live_model=False)
        assert sol == ch.reference_solution

    def test_solve_challenge_ollama_unreachable_fallback(self):
        gen = SyntheticChallengeGenerator()
        ch = gen.generate_challenge(domain="graphs", language="python")
        t0 = time.time()
        sol = solve_challenge(ch, use_live_model=True, ollama_url="http://127.0.0.1:65530")
        duration = time.time() - t0
        # Pre-flight check must return fallback within ~2.0 seconds
        assert duration < 2.5
        assert sol == ch.reference_solution

    def test_extract_runnable_code_closed_fence(self):
        raw = """
Here is my step-by-step reasoning:
1. First we import math.
2. Then we define the function.

```python
def compute(x):
    return x * 2
```
This satisfies the requirements.
"""
        code = extract_runnable_code(raw, language="python")
        assert code == "def compute(x):\n    return x * 2"

    def test_extract_runnable_code_unclosed_fence(self):
        raw = """
```python
def run():
    return 42
"""
        code = extract_runnable_code(raw, language="python")
        assert code == "def run():\n    return 42"

    def test_extract_runnable_code_syntax_error_rejected(self):
        raw = """
```python
def broken_syntax(:
    return 1
```
"""
        code = extract_runnable_code(raw, language="python")
        assert code is None

    def test_extract_runnable_code_identifier_preference(self):
        raw = """
```python
def helper():
    return 1
```
```python
def target_function(x):
    return helper() + x
```
"""
        code = extract_runnable_code(
            raw,
            language="python",
            starter_code="def target_function(x): pass",
        )
        assert "target_function" in code

    def test_solve_challenge_mock_live_response(self):
        gen = SyntheticChallengeGenerator()
        ch = gen.generate_challenge(domain="physics", challenge_key="symplectic_velocity_verlet")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "response": "Here is the solution:\n```python\ndef symplectic_verlet_orbit(r0, v0, mu, dt, steps):\n    return {'positions': []}\n```"
        }).encode("utf-8")

        with patch("scripts.learning.synthetic_challenge_generator.is_ollama_available", return_value=True):
            with patch("urllib.request.urlopen", return_value=mock_response):
                sol = solve_challenge(ch, use_live_model=True)
                assert "def symplectic_verlet_orbit" in sol


class TestEndToEndSolverSandboxIntegration:
    """Verifies end-to-end integration: solve_challenge -> execute_sandboxed_code."""

    @pytest.mark.parametrize(
        "domain,key",
        [
            ("dynamic_programming", "multi_constrained_knapsack"),
            ("dynamic_programming", "solve_tsp_bitmask"),
            ("graph_algorithms", "max_flow_edmonds_karp"),
            ("graph_algorithms", "bellman_ford_negative_cycles"),
            ("concurrency", "bounded_ring_buffer"),
            ("concurrency", "thread_safe_memory_pool"),
            ("numerical_physics", "symplectic_velocity_verlet"),
            ("numerical_physics", "damped_harmonic_oscillator"),
        ],
    )
    def test_end_to_end_solve_and_sandboxed_execution(self, domain, key):
        gen = SyntheticChallengeGenerator()
        ch = gen.generate_challenge(domain=domain, language="python", challenge_key=key)

        # 1. Autonomously solve challenge (hermetic offline reference fallback)
        sol = solve_challenge(ch, use_live_model=False)
        assert sol, f"Failed to obtain solution for {domain}:{key}"

        # 2. Execute candidate solution within Win32 Job Object sandbox
        exec_res = execute_sandboxed_code(
            source_code=sol,
            test_suite=ch.test_suite,
            language="python",
            timeout=5.0,
            max_memory_mb=256,
        )

        assert exec_res.success is True, f"Execution failed for {domain}:{key}: {exec_res.stderr} | {exec_res.error_message}"
        assert exec_res.returncode == 0
        assert exec_res.duration_s < 5.0
        assert exec_res.peak_memory_bytes > 0
        assert exec_res.timeout is False
        assert exec_res.ast_violation is False
