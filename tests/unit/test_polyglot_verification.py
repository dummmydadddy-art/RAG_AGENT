"""
tests/unit/test_polyglot_verification.py

Comprehensive Unit Test Suite for Feature F10 (Automated Polyglot Verification & Quality Gate).

Verifies:
1. Toolchain & Runtime Locators (Python, Node.js v24 strip-types, PHP 8.3 CLI, SQLite, Compilers).
2. Code Extraction & Markdown Parsing (fence unwrapping, ChatML meta token stripping, leakage detection).
3. Delimiter & Lexical Structural Checking (brackets, Rust lifetimes, comments, strings).
4. Pillar 1: Syntax Validity Rate (SVR) across all 8 Tier-1 languages (Python, TS, C++, Rust, SQL, PHP, Java, Go).
5. Pillar 2: Language Conformance Rate (LCR) idiom evaluation and threshold enforcement (>= 85%).
6. Pillar 3: Execution Pass Rate (EPR) on locally available runtimes (Python 3.12, Node.js, PHP, SQLite).
7. Pillar 4: Refactoring Correctness (RFC) evaluation and semantic/invariant preservation.
8. Ollama Verifier Client and Query Handling (ChatML formatting, ping, offline fallback).
9. Full Quality Gate Aggregation, JSON/Text Report Export, and CLI Driver.
"""

import json
import os
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from scripts.verify_polyglot import (
    EPR_THRESHOLD,
    LCR_THRESHOLD,
    RFC_THRESHOLD,
    SVR_THRESHOLD,
    TIER1_LANGUAGES,
    OllamaVerifier,
    PolyglotVerificationHarness,
    QualityGateSummary,
    check_balanced_delimiters,
    check_language_conformance,
    check_meta_token_leakage,
    detect_available_runtimes,
    evaluate_refactoring_task,
    execute_code_and_tests,
    export_json_report,
    export_text_report,
    extract_code,
    generate_text_summary,
    get_compiler_executable,
    get_curated_refactoring_tasks,
    get_node_executable,
    get_php_executable,
    get_polyglot_benchmark_catalog,
    get_python_executable,
    get_stem_curriculum_polyglot_challenges,
    load_stem_curriculum_modules,
    main,
    validate_syntax,
)

ROOT = Path(__file__).resolve().parents[2]


# ============================================================================
# 1. TOOLCHAIN & RUNTIME DETECTION TESTS
# ============================================================================

class TestToolchainAndRuntimeLocators:
    """Verifies environment discovery and toolchain detection."""

    def test_python_executable_locator(self):
        """Active python executable is verified and non-empty."""
        py_bin = get_python_executable()
        assert os.path.exists(py_bin)
        assert "python" in py_bin.lower()

    def test_node_executable_locator(self):
        """Node.js executable is found and verified on host."""
        node_bin = get_node_executable()
        assert node_bin is not None
        assert os.path.exists(node_bin)
        assert "node" in node_bin.lower()

    def test_php_executable_locator(self):
        """PHP 8.3 CLI binary is located and verified."""
        php_bin = get_php_executable()
        assert php_bin is not None
        assert os.path.exists(php_bin)
        assert "php" in php_bin.lower()

    def test_detect_available_runtimes_structure(self):
        """Runtime detector returns all 8 Tier-1 languages with metadata."""
        runtimes = detect_available_runtimes()
        for lang in TIER1_LANGUAGES:
            assert lang in runtimes
            assert "available" in runtimes[lang]
            assert "type" in runtimes[lang]
        assert runtimes["python"]["available"] is True
        assert runtimes["typescript"]["available"] is True
        assert runtimes["php"]["available"] is True
        assert runtimes["sql"]["available"] is True


# ============================================================================
# 2. CODE EXTRACTION & SANITIZATION TESTS
# ============================================================================

class TestCodeExtractionAndSanitization:
    """Verifies markdown fence unwrapping and ChatML token stripping."""

    def test_extract_code_from_language_markdown_block(self):
        """Extracts clean source code from tagged markdown block."""
        raw = "Here is the code:\n```python\ndef solve():\n    return 42\n```\nDone."
        extracted = extract_code(raw, "python")
        assert extracted == "def solve():\n    return 42"

    def test_extract_code_from_generic_markdown_fence(self):
        """Extracts code from generic ``` block without language tag."""
        raw = "```\nconst a: number = 1;\n```"
        extracted = extract_code(raw, "typescript")
        assert extracted == "const a: number = 1;"

    def test_extract_code_strips_chatml_meta_tokens(self):
        """Removes internal ChatML tokens if leaked into response."""
        raw = "<|im_start|>assistant\ndef f(): pass<|im_end|>"
        extracted = extract_code(raw, "python")
        assert "<|im_start|>" not in extracted
        assert "<|im_end|>" not in extracted
        assert extracted == "def f(): pass"

    def test_check_meta_token_leakage(self):
        """Detects presence of internal ChatML tokens."""
        assert check_meta_token_leakage("def f(): pass<|im_end|>") is True
        assert check_meta_token_leakage("<|im_start|>system") is True
        assert check_meta_token_leakage("def f(): return 42") is False


# ============================================================================
# 3. DELIMITER & LEXICAL STRUCTURAL PARSER TESTS
# ============================================================================

class TestDelimiterAndStructuralParser:
    """Verifies delimiter balancing, string escaping, and Rust lifetimes."""

    def test_balanced_delimiters_valid_code(self):
        """Balanced code returns (True, 'OK')."""
        code = "template<typename T> class Foo { void bar() { auto x = (1 + [2]()); } };"
        ok, msg = check_balanced_delimiters(code)
        assert ok is True
        assert msg == "OK"

    def test_balanced_delimiters_unmatched_closer(self):
        """Catches unexpected closing delimiter."""
        code = "int x = (1 + 2];"
        ok, msg = check_balanced_delimiters(code)
        assert ok is False
        assert "Mismatched delimiter" in msg

    def test_balanced_delimiters_unclosed_opener(self):
        """Catches unclosed opening brace."""
        code = "class A { void f() {"
        ok, msg = check_balanced_delimiters(code)
        assert ok is False
        assert "Unclosed delimiter" in msg

    def test_balanced_delimiters_rust_lifetimes_handling(self):
        """Rust lifetime parameters ('a, 'static) do not disrupt delimiter tracking."""
        rust_code = (
            "pub struct Tokenizer<'a> {\n"
            "    remainder: &'a str,\n"
            "    delimiter: char,\n"
            "}\n"
            "impl<'a> Tokenizer<'a> {\n"
            "    pub fn new(input: &'a str, d: char) -> Self { Self { remainder: input, delimiter: d } }\n"
            "}\n"
        )
        ok, msg = check_balanced_delimiters(rust_code)
        assert ok is True, f"Failed on Rust lifetimes: {msg}"

    def test_balanced_delimiters_ignores_strings_and_comments(self):
        """Delimiters inside strings or comments are ignored."""
        code = (
            "// unclosed bracket { in line comment\n"
            "/* unclosed [ in block comment */\n"
            "const s = \"{ [ (\";\n"
            "const valid = true;\n"
        )
        ok, msg = check_balanced_delimiters(code)
        assert ok is True


# ============================================================================
# 4. PILLAR 1: SYNTAX VALIDITY RATE (SVR) TESTS
# ============================================================================

class TestPillar1SyntaxValidityRate:
    """Verifies SVR syntax parsers across all 8 Tier-1 languages."""

    def test_svr_python_valid_and_invalid(self):
        """Python syntax validator detects valid AST and SyntaxError."""
        valid_py = "def add(x: int, y: int) -> int:\n    return x + y\n"
        invalid_py = "def add(x:\n   return x +"
        assert validate_syntax(valid_py, "python")[0] is True
        assert validate_syntax(invalid_py, "python")[0] is False

    def test_svr_typescript_valid_and_invalid(self):
        """TypeScript validator detects valid types and syntax errors."""
        valid_ts = "const greet = (name: string): string => `Hello ${name}`;"
        invalid_ts = "const greet = (name: string): string => { return ;;"
        assert validate_syntax(valid_ts, "typescript")[0] is True
        assert validate_syntax(invalid_ts, "typescript")[0] is False

    def test_svr_php_valid_and_invalid(self):
        """PHP validator detects valid PHP and parse errors."""
        valid_php = "<?php declare(strict_types=1);\nfunction square(int $x): int { return $x * $x; }\n"
        invalid_php = "<?php function broken( { return 1; }"
        assert validate_syntax(valid_php, "php")[0] is True
        assert validate_syntax(invalid_php, "php")[0] is False

    def test_svr_sql_valid_and_invalid(self):
        """SQL validator verifies query grammar against SQLite."""
        valid_sql = "WITH RECURSIVE t(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM t WHERE x < 5) SELECT * FROM t;"
        invalid_sql = "SELECT FROM WHERE;"
        assert validate_syntax(valid_sql, "sql")[0] is True
        assert validate_syntax(invalid_sql, "sql")[0] is False

    def test_svr_cpp_valid_and_invalid(self):
        """C++ validator verifies structural grammar and balanced templates."""
        valid_cpp = "template<typename T> class Buffer { std::atomic<size_t> head_{0}; };"
        invalid_cpp = "class Buffer { std::atomic<size_t head_{0}; };"
        assert validate_syntax(valid_cpp, "cpp")[0] is True
        assert validate_syntax(invalid_cpp, "cpp")[0] is False

    def test_svr_rust_valid_and_invalid(self):
        """Rust validator checks structural AST syntax and declarations."""
        valid_rust = "pub struct Node<'a> { val: &'a str } impl<'a> Node<'a> { pub fn get(&self) -> &'a str { self.val } }"
        invalid_rust = "pub struct Node<'a> { val: &'a str impl Node { }"
        assert validate_syntax(valid_rust, "rust")[0] is True
        assert validate_syntax(invalid_rust, "rust")[0] is False

    def test_svr_java_valid_and_invalid(self):
        """Java validator checks class declaration and brace matching."""
        valid_java = "public class ObjectPool<T> { private final int cap; public ObjectPool(int c) { this.cap = c; } }"
        invalid_java = "public class ObjectPool<T> { private final int cap; public ObjectPool(int c) { "
        assert validate_syntax(valid_java, "java")[0] is True
        assert validate_syntax(invalid_java, "java")[0] is False

    def test_svr_go_valid_and_invalid(self):
        """Go validator checks package and function structures."""
        valid_go = "package worker\nimport \"context\"\nfunc Run(ctx context.Context) error { return nil }"
        invalid_go = "package worker\nfunc Run(ctx context.Context { return nil"
        assert validate_syntax(valid_go, "go")[0] is True
        assert validate_syntax(invalid_go, "go")[0] is False

    def test_svr_empty_or_unsupported(self):
        """Empty code or unsupported language returns False."""
        assert validate_syntax("", "python")[0] is False
        assert validate_syntax("code", "unsupported_lang")[0] is False


# ============================================================================
# 5. PILLAR 2: LANGUAGE CONFORMANCE RATE (LCR) TESTS
# ============================================================================

class TestPillar2LanguageConformanceRate:
    """Verifies LCR idiom rules across all 8 Tier-1 languages."""

    def test_lcr_python_idiomatic_scoring(self):
        """Idiomatic Python achieves 100% conformance score."""
        code = (
            "def binary_search(arr: list[int], target: int) -> int:\n"
            "    \"\"\"Binary search implementation with type hints.\"\"\"\n"
            "    left, right = 0, len(arr) - 1\n"
            "    while left <= right:\n"
            "        mid = (left + right) // 2\n"
            "        if arr[mid] == target: return mid\n"
            "        elif arr[mid] < target: left = mid + 1\n"
            "        else: right = mid - 1\n"
            "    return -1\n"
        )
        res = check_language_conformance(code, "python")
        assert res.score >= LCR_THRESHOLD
        assert "typed_parameters" in res.passed_rules
        assert "typed_returns" in res.passed_rules

    def test_lcr_typescript_idiomatic_scoring(self):
        """Idiomatic TypeScript satisfies typing and immutability rules."""
        code = (
            "export type Result<T, E> = { readonly ok: true; readonly value: T } | { readonly ok: false; readonly error: E };\n"
            "export function ok<T>(val: T): Result<T, never> { return { ok: true, value: val }; }\n"
        )
        res = check_language_conformance(code, "typescript")
        assert res.score >= LCR_THRESHOLD
        assert "explicit_typing" in res.passed_rules
        assert "immutability_modifiers" in res.passed_rules

    def test_lcr_cpp_idiomatic_scoring(self):
        """Idiomatic C++ satisfies atomic synchronization and alignment."""
        code = (
            "#include <atomic>\n"
            "#include <array>\n"
            "template<typename T, size_t Cap> class SPSCQueue {\n"
            "    static_assert((Cap & (Cap - 1)) == 0);\n"
            "    std::array<T, Cap> buf_{};\n"
            "    alignas(64) std::atomic<size_t> head_{0};\n"
            "public:\n"
            "    bool push(const T& item) {\n"
            "        const size_t h = head_.load(std::memory_order_relaxed);\n"
            "        return true;\n"
            "    }\n"
            "};"
        )
        res = check_language_conformance(code, "cpp")
        assert res.score >= LCR_THRESHOLD
        assert "atomic_synchronization" in res.passed_rules
        assert "raii_or_cache_alignment" in res.passed_rules

    def test_lcr_rust_idiomatic_scoring(self):
        """Idiomatic Rust satisfies lifetime and zero-copy rules."""
        code = (
            "pub struct Tokenizer<'a> { remainder: &'a str }\n"
            "impl<'a> Iterator for Tokenizer<'a> {\n"
            "    type Item = &'a str;\n"
            "    fn next(&mut self) -> Option<Self::Item> { None }\n"
            "}\n"
        )
        res = check_language_conformance(code, "rust")
        assert res.score >= LCR_THRESHOLD
        assert "explicit_lifetimes" in res.passed_rules
        assert "zero_copy_hygiene" in res.passed_rules

    def test_lcr_php_idiomatic_scoring(self):
        """Idiomatic PHP satisfies strict_types, functional compose, and typed exceptions."""
        code = (
            "<?php declare(strict_types=1);\n"
            "class Router {\n"
            "    private array $routes = [];\n"
            "    public function dispatch(string $method, string $path): mixed {\n"
            "        if (!isset($this->routes[$path])) throw new RuntimeException('404');\n"
            "        return array_reduce([], fn($next, $mw) => $mw, null);\n"
            "    }\n"
            "}\n"
        )
        res = check_language_conformance(code, "php")
        assert res.score >= LCR_THRESHOLD
        assert "strict_types_directive" in res.passed_rules
        assert "typed_exception_handling" in res.passed_rules

    def test_lcr_sql_idiomatic_scoring(self):
        """Idiomatic SQL satisfies recursive CTE and ANSI keywords."""
        code = (
            "WITH RECURSIVE org_tree AS (\n"
            "    SELECT emp_id, name, 0 AS depth FROM employees WHERE manager_id IS NULL\n"
            "    UNION ALL\n"
            "    SELECT e.emp_id, e.name, ot.depth + 1 FROM employees e JOIN org_tree ot ON e.manager_id = ot.emp_id\n"
            ")\n"
            "SELECT * FROM org_tree ORDER BY depth ASC;\n"
        )
        res = check_language_conformance(code, "sql")
        assert res.score >= LCR_THRESHOLD
        assert "ansi_keywords_capitalized" in res.passed_rules
        assert "recursive_cte_or_window" in res.passed_rules


# ============================================================================
# 6. PILLAR 3: EXECUTION PASS RATE (EPR) TESTS
# ============================================================================

class TestPillar3ExecutionPassRate:
    """Verifies EPR test execution across native runtimes."""

    def test_execution_python_native_success(self):
        """Python executes in-process and passes assertions."""
        src = "def add(a: int, b: int) -> int: return a + b"
        tests = "def test_add(): assert add(2, 3) == 5"
        res = execute_code_and_tests(src, tests, "python")
        assert res.executed is True
        assert res.passed is True
        assert res.runtime in ("python-inprocess", "python-sandbox")

    def test_execution_python_native_failure(self):
        """Python execution failure is captured accurately."""
        src = "def add(a: int, b: int) -> int: return a - b"
        tests = "def test_add(): assert add(2, 3) == 5"
        res = execute_code_and_tests(src, tests, "python")
        assert res.executed is True
        assert res.passed is False
        assert "AssertionError" in str(res.error)

    def test_execution_typescript_node_strip_types(self):
        """TypeScript executes natively via Node 24 strip-types."""
        src = "const multiply = (x: number, y: number): number => x * y;"
        tests = "console.assert(multiply(6, 7) === 42);"
        res = execute_code_and_tests(src, tests, "typescript")
        assert res.executed is True
        assert res.passed is True
        assert "node-v24" in res.runtime

    def test_execution_php_cli_native(self):
        """PHP executes natively via PHP 8.3 CLI."""
        src = "function calc(int $a): int { return $a * 2; }"
        tests = "assert(calc(21) === 42);"
        res = execute_code_and_tests(src, tests, "php")
        assert res.executed is True
        assert res.passed is True
        assert "php-8.3" in res.runtime

    def test_execution_sql_sqlite_in_memory(self):
        """SQL executes in-process against SQLite."""
        src = "SELECT name, val FROM t WHERE id = 1;"
        tests = "CREATE TABLE t (id INT, name TEXT, val INT); INSERT INTO t VALUES (1, 'alpha', 42);"
        res = execute_code_and_tests(src, tests, "sql")
        assert res.executed is True
        assert res.passed is True
        assert res.runtime == "sqlite-in-memory"

    def test_execution_compiled_runtime_graceful_skip(self):
        """C++, Rust, Java, Go gracefully report compiler status without failure."""
        res = execute_code_and_tests("int main() { return 0; }", "", "cpp")
        assert res.passed is True
        assert "compiler" in res.runtime


# ============================================================================
# 7. PILLAR 4: REFACTORING CORRECTNESS (RFC) TESTS
# ============================================================================

class TestPillar4RefactoringCorrectness:
    """Verifies RFC evaluation across all 8 curated refactoring tasks."""

    def test_all_eight_curated_refactoring_tasks_pass(self):
        """All 8 curated refactoring tasks satisfy 100% RFC threshold."""
        tasks = get_curated_refactoring_tasks()
        assert len(tasks) == 8
        for task in tasks:
            eval_res = evaluate_refactoring_task(task)
            assert eval_res.rfc_passed is True, f"Refactoring failed for {task['task_id']}: {eval_res.details}"
            assert eval_res.syntax_valid_before is True
            assert eval_res.syntax_valid_after is True
            assert eval_res.invariants_satisfied is True

    def test_refactoring_detects_missing_invariants(self):
        """Fails RFC when refactored code lacks mandatory invariant."""
        task = {
            "task_id": "RFC-TEST-FAIL",
            "language": "python",
            "description": "Test invariant failure",
            "initial_code": "def f(): return 1\n",
            "refactored_code": "def f() -> int: return 1\n",
            "unit_tests": "def test_f(): assert f() == 1\n",
            "invariants": ["contains:seen: dict[int, int]"],
        }
        res = evaluate_refactoring_task(task)
        assert res.rfc_passed is False
        assert "Missing required invariant" in res.details

    def test_refactoring_detects_forbidden_construct(self):
        """Fails RFC when refactored code retains forbidden construct."""
        task = {
            "task_id": "RFC-TEST-FORBIDDEN",
            "language": "typescript",
            "description": "Test forbidden any",
            "initial_code": "export function f(x: any): any { return x; }\n",
            "refactored_code": "export function f(x: any): number { return x; }\n",
            "unit_tests": "console.assert(f(10) === 10);\n",
            "invariants": ["lacks:x: any"],
        }
        res = evaluate_refactoring_task(task)
        assert res.rfc_passed is False
        assert "Forbidden construct present" in res.details


# ============================================================================
# 8. OLLAMA VERIFIER CLIENT & HARNESS TESTS
# ============================================================================

class TestOllamaVerifierAndHarness:
    """Verifies Ollama HTTP client, mock queries, and full quality gate summary."""

    def test_ollama_client_ping_mock(self):
        """Ollama client ping handles HTTP response correctly."""
        client = OllamaVerifier(base_url="http://localhost:11434")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_urlopen.return_value.__enter__.return_value = mock_resp
            assert client.ping() is True

    def test_ollama_client_query_mock(self):
        """Ollama client query formats ChatML payload and parses response."""
        client = OllamaVerifier(base_url="http://localhost:11434", model_tag="stem-coder-expert:latest")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "model": "stem-coder-expert:latest",
                "response": "```python\ndef solve(): return 42\n```",
                "done": True,
            }).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = client.query("Write solve function")
            assert res["success"] is True
            assert res["model"] == "stem-coder-expert:latest"
            assert "solve" in res["response"]

    def test_harness_evaluate_quality_gate_offline(self):
        """Harness evaluates the 4 pillars and confirms 100% Quality Gate pass in offline mode."""
        harness = PolyglotVerificationHarness(offline_only=True)
        summary = harness.evaluate_quality_gate()

        assert summary.svr_passed is True
        assert summary.svr_rate == SVR_THRESHOLD
        assert summary.lcr_passed is True
        assert summary.lcr_rate >= LCR_THRESHOLD
        assert summary.epr_passed is True
        assert summary.epr_rate == EPR_THRESHOLD
        assert summary.rfc_passed is True
        assert summary.rfc_rate == RFC_THRESHOLD
        assert summary.all_gates_passed is True
        assert summary.total_languages_evaluated == 8

    def test_json_and_text_report_export(self, tmp_path: Path):
        """Exports structured JSON and text reports without error."""
        harness = PolyglotVerificationHarness(offline_only=True)
        summary = harness.evaluate_quality_gate()

        json_out = tmp_path / "test_report.json"
        txt_out = tmp_path / "test_report.txt"

        export_json_report(summary, json_out)
        export_text_report(summary, txt_out)

        assert json_out.exists()
        assert txt_out.exists()

        with open(json_out, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["all_gates_passed"] is True
            assert data["svr_rate"] == 1.0

        with open(txt_out, "r", encoding="utf-8") as f:
            text = f.read()
            assert "ACCEPTED - ALL GATES PASSED" in text
            assert "4-PILLAR QUALITY GATE SUMMARY" in text

    def test_cli_main_entrypoint_arguments(self, tmp_path: Path):
        """CLI main function executes with argument flags and returns exit code 0."""
        json_file = tmp_path / "cli_report.json"
        txt_file = tmp_path / "cli_report.txt"

        exit_code = main([
            "--offline",
            "--json-out", str(json_file),
            "--txt-out", str(txt_file),
        ])
        assert exit_code == 0
        assert json_file.exists()
        assert txt_file.exists()


# ============================================================================
# 9. STEM CURRICULUM INTEGRATION TESTS
# ============================================================================

class TestSTEMCurriculumPolyglotIntegration:
    """Verifies that the 52 STEM curriculum modules are ingested, mapped, and verified."""

    def test_load_stem_curriculum_modules_from_dataset(self):
        """Verifies loading of all 52 modules with expected tier and domain breakdown."""
        modules = load_stem_curriculum_modules()
        assert len(modules) == 52

        tiers = {m["tier"] for m in modules}
        assert tiers == {"elementary", "secondary", "higher_secondary", "sme"}

        tier_counts = {}
        domain_counts = {}
        for m in modules:
            t = m["tier"]
            d = m["domain"]
            tier_counts[t] = tier_counts.get(t, 0) + 1
            domain_counts[d] = domain_counts.get(d, 0) + 1

        assert tier_counts["elementary"] == 12
        assert tier_counts["secondary"] == 14
        assert tier_counts["higher_secondary"] == 15
        assert tier_counts["sme"] == 11
        assert domain_counts["maths"] == 25
        assert domain_counts["physics"] == 27

    def test_stem_curriculum_challenges_syntax_and_conformance(self):
        """All STEM curriculum polyglot challenges satisfy 100% SVR and >= 85% LCR."""
        challenges = get_stem_curriculum_polyglot_challenges()
        assert len(challenges) >= 10

        languages_present = {c["language"] for c in challenges}
        for lang in TIER1_LANGUAGES:
            assert lang in languages_present, f"Missing STEM challenge for Tier-1 language: {lang}"

        for ch in challenges:
            c_id = ch["id"]
            lang = ch["language"]
            solution = ch["reference_solution"]

            svr_ok, svr_msg = validate_syntax(solution, lang)
            assert svr_ok is True, f"SVR failed for {c_id} ({lang}): {svr_msg}"

            lcr_res = check_language_conformance(solution, lang)
            assert lcr_res.score >= LCR_THRESHOLD, (
                f"LCR failed for {c_id} ({lang}): score={lcr_res.score}, failed={lcr_res.failed_rules}"
            )

    def test_stem_curriculum_native_execution(self):
        """Native runtime STEM challenges (Python, TypeScript, PHP, SQL) pass unit tests."""
        challenges = get_stem_curriculum_polyglot_challenges()
        native_langs = {"python", "typescript", "php", "sql"}

        for ch in challenges:
            lang = ch["language"]
            if lang in native_langs:
                res = execute_code_and_tests(ch["reference_solution"], ch["unit_test_suite"], lang)
                assert res.executed is True, f"Execution skipped for native challenge {ch['id']}"
                assert res.passed is True, f"Execution failed for {ch['id']}: {res.error}"

    def test_quality_gate_summary_includes_stem_curriculum(self):
        """Quality gate evaluation attaches STEM curriculum summary and benchmarks."""
        harness = PolyglotVerificationHarness(offline_only=True)
        summary = harness.evaluate_quality_gate()

        assert "stem_curriculum_summary" in asdict(summary)
        sc = summary.stem_curriculum_summary
        assert sc["total_curriculum_modules"] == 52
        assert sc["represented_in_polyglot"] is True
        assert sc["stem_challenges_evaluated"] >= 10
        assert sc["stem_svr_rate"] == 1.0
        assert sc["stem_lcr_rate"] >= LCR_THRESHOLD
        assert sc["stem_epr_rate"] == 1.0

        assert len(summary.stem_curriculum_benchmarks) >= 10

    def test_text_report_includes_stem_curriculum_section(self):
        """Generated text report formats STEM curriculum breakdown and metrics."""
        harness = PolyglotVerificationHarness(offline_only=True)
        summary = harness.evaluate_quality_gate()
        text = generate_text_summary(summary)

        assert "STEM CURRICULUM INTEGRATION (52 MODULES INGESTED)" in text
        assert "STEM CURRICULUM BENCHMARK BREAKDOWN:" in text
        assert "STEM-PY-ELEM-001" in text
        assert "STEM-SQL-SME-001" in text

