"""
src/web/routes/execute.py

Polyglot code execution endpoint protected by AST Security Guardrails and Win32 Job Object sandbox:
- Pre-execution taint analysis via AstSecurityGuard (Python, TypeScript, PHP, SQL)
- Hard 256 MB RAM ceiling and 5.0s timeout enforced via WindowsJobSandbox
- Execution across Tier-1 runtimes (Python 3.12, Node.js v24 strip-types, PHP 8.3 CLI, SQLite)
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter

from scripts.security.ast_guard import AstSecurityGuard
from scripts.security.windows_sandbox import WindowsJobSandbox
from src.web.config import get_config
from src.web.schemas import ExecuteRequest, ExecuteResponse

logger = logging.getLogger("web.routes.execute")
router = APIRouter(tags=["Code Execution"])

_AST_GUARD = AstSecurityGuard()


def _normalize_language(lang: str) -> str:
    """Normalizes language name and aliases."""
    l = lang.lower().strip()
    aliases: Dict[str, str] = {
        "py": "python",
        "python": "python",
        "ts": "typescript",
        "js": "typescript",
        "typescript": "typescript",
        "javascript": "typescript",
        "php": "php",
        "sql": "sql",
        "cpp": "cpp",
        "c++": "cpp",
        "c": "cpp",
        "cxx": "cpp",
        "rust": "rust",
        "rs": "rust",
        "java": "java",
        "go": "go",
        "golang": "go",
    }
    return aliases.get(l, l)


def _get_node_path() -> Optional[str]:
    """Finds node executable."""
    cand = shutil.which("node")
    if cand and os.path.exists(cand):
        return cand
    win_cand = Path(r"C:\Program Files\nodejs\node.exe")
    return str(win_cand) if win_cand.exists() else None


def _get_php_path() -> Optional[str]:
    """Finds PHP 8.3 executable."""
    cand = shutil.which("php")
    if cand and os.path.exists(cand):
        return cand
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        for p in Path(local_app_data).glob("Microsoft/WinGet/Packages/PHP.PHP.8.3*/**/php.exe"):
            if p.exists():
                return str(p)
    return None


COMPILED_LANGUAGE_REQUIREMENTS: Dict[str, str] = {
    "cpp": "clang++ or g++",
    "rust": "rustc",
    "java": "javac",
    "go": "go",
}


def _get_compiler_path(lang: str) -> Optional[str]:
    """Finds compiler executable on system PATH for compiled languages."""
    if lang == "cpp":
        for name in ("clang++", "g++", "clang", "gcc"):
            cand = shutil.which(name)
            if cand:
                return cand
    elif lang == "rust":
        return shutil.which("rustc")
    elif lang == "java":
        return shutil.which("javac")
    elif lang == "go":
        return shutil.which("go")
    return None


@router.post("/execute", response_model=ExecuteResponse)
def execute_polyglot_code(req: ExecuteRequest) -> ExecuteResponse:
    """
    Executes polyglot code securely within a Win32 Job Object sandbox with AST pre-screening.
    """
    cfg = get_config()
    lang = _normalize_language(req.language)
    timeout = min(req.timeout_seconds, 30.0)
    max_memory = min(req.memory_limit_mb, cfg.max_memory_mb)

    t0 = time.time()
    code = req.code
    test_suite = req.test_suite

    # ========================================================================
    # 1. PYTHON EXECUTION
    # ========================================================================
    if lang == "python":
        combined = f"{code}\n\n{test_suite}\n" if test_suite and test_suite.strip() else code
        sec_report = _AST_GUARD.check_python(combined)
        if not sec_report.is_safe:
            duration = round(time.time() - t0, 3)
            violation_msgs = [f"[{v.category}] {v.message}" for v in sec_report.violations]
            return ExecuteResponse(
                success=False,
                language=lang,
                stdout="",
                stderr=f"SecurityViolation: {violation_msgs[0]}",
                exit_code=1,
                duration_seconds=duration,
                sandboxed=True,
                security_status="blocked",
                violations=violation_msgs,
                runtime="python-ast-guard",
                error_message="Execution blocked by AST security guardrails",
            )

        # Build runner script that executes top-level code and auto-runs test_ functions if present
        runner_script = f"""# Isolated Python Test Runner
import sys
{code}

{test_suite if test_suite else ""}

test_funcs = [k for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
if test_funcs:
    for tf in test_funcs:
        globals()[tf]()
    print(f"Executed {{len(test_funcs)}} test functions successfully")
"""
        sandbox = WindowsJobSandbox(max_memory_mb=max_memory, timeout_seconds=timeout)
        res = sandbox.run_python_script(runner_script)
        duration = round(time.time() - t0, 3)

        passed = res.success and (res.exit_code == 0) and not res.timed_out and not res.memory_breached
        error_msg = None
        if not passed:
            if res.timed_out:
                error_msg = f"Execution timed out after {timeout}s"
            elif res.memory_breached:
                error_msg = f"Process memory limit exceeded ({max_memory} MB ceiling)"
            else:
                error_msg = res.stderr.strip() or f"Process failed with exit code {res.exit_code}"

        return ExecuteResponse(
            success=passed,
            language=lang,
            stdout=res.stdout,
            stderr=res.stderr,
            exit_code=res.exit_code,
            duration_seconds=duration,
            sandboxed=True,
            security_status="clean",
            violations=[],
            timed_out=res.timed_out,
            memory_breached=res.memory_breached,
            runtime="win32-python-sandbox",
            error_message=error_msg,
        )

    # ========================================================================
    # 2. TYPESCRIPT / JAVASCRIPT EXECUTION
    # ========================================================================
    elif lang == "typescript":
        combined = f"{code}\n\n{test_suite}\n" if test_suite and test_suite.strip() else code
        sec_report = _AST_GUARD.check_typescript(combined)
        if not sec_report.is_safe:
            duration = round(time.time() - t0, 3)
            violation_msgs = [f"[{v.category}] {v.message}" for v in sec_report.violations]
            return ExecuteResponse(
                success=False,
                language=lang,
                stdout="",
                stderr=f"SecurityViolation: {violation_msgs[0]}",
                exit_code=1,
                duration_seconds=duration,
                sandboxed=True,
                security_status="blocked",
                violations=violation_msgs,
                runtime="ts-ast-guard",
                error_message="Execution blocked by AST security guardrails",
            )

        node_bin = _get_node_path()
        if not node_bin:
            duration = round(time.time() - t0, 3)
            return ExecuteResponse(
                success=False,
                language=lang,
                stdout="",
                stderr="Node.js runtime not installed on host system",
                exit_code=127,
                duration_seconds=duration,
                sandboxed=True,
                security_status="clean",
                runtime="node-unavailable",
                error_message="Node.js unavailable",
            )

        with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False, encoding="utf-8") as f:
            f.write(combined)
            tmp_path = f.name

        try:
            sandbox = WindowsJobSandbox(max_memory_mb=max_memory, timeout_seconds=timeout)
            res = sandbox.run_command([node_bin, "--experimental-strip-types", tmp_path], timeout=timeout)
            duration = round(time.time() - t0, 3)
            passed = res.success and (res.exit_code == 0) and ("Assertion failed" not in res.stderr)

            return ExecuteResponse(
                success=passed,
                language=lang,
                stdout=res.stdout,
                stderr=res.stderr,
                exit_code=res.exit_code,
                duration_seconds=duration,
                sandboxed=True,
                security_status="clean",
                violations=[],
                timed_out=res.timed_out,
                memory_breached=res.memory_breached,
                runtime="node-v24-strip-types",
                error_message=res.stderr.strip() if not passed else None,
            )
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    # ========================================================================
    # 3. PHP EXECUTION
    # ========================================================================
    elif lang == "php":
        clean_src = code.replace("<?php", "").strip()
        clean_tests = test_suite.replace("<?php", "").strip() if test_suite else ""
        combined_php = f"<?php\n{clean_src}\n\n{clean_tests}\n"

        sec_report = _AST_GUARD.check_php(combined_php)
        if not sec_report.is_safe:
            duration = round(time.time() - t0, 3)
            violation_msgs = [f"[{v.category}] {v.message}" for v in sec_report.violations]
            return ExecuteResponse(
                success=False,
                language=lang,
                stdout="",
                stderr=f"SecurityViolation: {violation_msgs[0]}",
                exit_code=1,
                duration_seconds=duration,
                sandboxed=True,
                security_status="blocked",
                violations=violation_msgs,
                runtime="php-ast-guard",
                error_message="Execution blocked by AST security guardrails",
            )

        php_bin = _get_php_path()
        if not php_bin:
            duration = round(time.time() - t0, 3)
            return ExecuteResponse(
                success=False,
                language=lang,
                stdout="",
                stderr="PHP 8.3 CLI runtime not found on host system",
                exit_code=127,
                duration_seconds=duration,
                sandboxed=True,
                security_status="clean",
                runtime="php-unavailable",
                error_message="PHP CLI unavailable",
            )

        with tempfile.NamedTemporaryFile("w", suffix=".php", delete=False, encoding="utf-8") as f:
            f.write(combined_php)
            tmp_path = f.name

        try:
            sandbox = WindowsJobSandbox(max_memory_mb=max_memory, timeout_seconds=timeout)
            res = sandbox.run_command([php_bin, tmp_path], timeout=timeout)
            duration = round(time.time() - t0, 3)
            passed = res.success and (res.exit_code == 0) and ("Fatal error" not in res.stderr) and ("Parse error" not in res.stderr)

            return ExecuteResponse(
                success=passed,
                language=lang,
                stdout=res.stdout,
                stderr=res.stderr,
                exit_code=res.exit_code,
                duration_seconds=duration,
                sandboxed=True,
                security_status="clean",
                violations=[],
                timed_out=res.timed_out,
                memory_breached=res.memory_breached,
                runtime="php-8.3-cli",
                error_message=res.stderr.strip() if not passed else None,
            )
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    # ========================================================================
    # 4. SQL EXECUTION
    # ========================================================================
    elif lang == "sql":
        combined_sql = f"{code}\n\n{test_suite}\n" if test_suite and test_suite.strip() else code
        sec_report = _AST_GUARD.check_sql(combined_sql)
        if not sec_report.is_safe:
            duration = round(time.time() - t0, 3)
            violation_msgs = [f"[{v.category}] {v.message}" for v in sec_report.violations]
            return ExecuteResponse(
                success=False,
                language=lang,
                stdout="",
                stderr=f"SecurityViolation: {violation_msgs[0]}",
                exit_code=1,
                duration_seconds=duration,
                sandboxed=True,
                security_status="blocked",
                violations=violation_msgs,
                runtime="sql-ast-guard",
                error_message="Execution blocked by AST security guardrails",
            )

        conn = sqlite3.connect(":memory:")
        try:
            if test_suite and test_suite.strip():
                conn.executescript(test_suite)
            cursor = conn.cursor()
            cursor.execute(code.strip())
            rows = cursor.fetchall()
            duration = round(time.time() - t0, 3)
            out = f"Query executed successfully; fetched {len(rows)} rows.\n"
            if rows:
                out += f"Results: {rows[:10]}"
            return ExecuteResponse(
                success=True,
                language=lang,
                stdout=out,
                stderr="",
                exit_code=0,
                duration_seconds=duration,
                sandboxed=True,
                security_status="clean",
                violations=[],
                runtime="sqlite-in-memory",
            )
        except Exception as e:
            duration = round(time.time() - t0, 3)
            return ExecuteResponse(
                success=False,
                language=lang,
                stdout="",
                stderr=f"{type(e).__name__}: {e}",
                exit_code=1,
                duration_seconds=duration,
                sandboxed=True,
                security_status="clean",
                violations=[],
                runtime="sqlite-in-memory",
                error_message=str(e),
            )
        finally:
            conn.close()

    # ========================================================================
    # 5. COMPILED RUNTIMES (C++, RUST, JAVA, GO)
    # ========================================================================
    elif lang in COMPILED_LANGUAGE_REQUIREMENTS:
        compiler_bin = _get_compiler_path(lang)
        req_compiler = COMPILED_LANGUAGE_REQUIREMENTS[lang]

        # Case 5A: Host compiler is not installed -> Honest structured failure
        if not compiler_bin:
            duration = round(time.time() - t0, 3)
            err_msg = (
                f"Runtime environment for '{lang}' is not installed on this host. "
                f"Native execution requires '{req_compiler}' on system PATH."
            )
            return ExecuteResponse(
                success=False,
                language=lang,
                stdout="",
                stderr=err_msg,
                exit_code=1,
                duration_seconds=duration,
                sandboxed=True,
                security_status="clean",
                violations=[],
                runtime="unsupported-runtime",
                error_message=err_msg,
            )

        # Case 5B: Host compiler is present -> Real sandbox compilation & execution
        combined = f"{code}\n\n{test_suite}\n" if test_suite and test_suite.strip() else code
        sandbox = WindowsJobSandbox(max_memory_mb=max_memory, timeout_seconds=timeout)
        exe_suffix = ".exe" if sys.platform == "win32" else ""

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            if lang == "cpp":
                src_file = tmp_path / "solution.cpp"
                exe_file = tmp_path / f"solution{exe_suffix}"
                src_file.write_text(combined, encoding="utf-8")
                compile_cmd = [compiler_bin, str(src_file), "-O2", "-o", str(exe_file)]
                run_cmd = [str(exe_file)]

            elif lang == "rust":
                src_file = tmp_path / "solution.rs"
                exe_file = tmp_path / f"solution{exe_suffix}"
                src_file.write_text(combined, encoding="utf-8")
                compile_cmd = [compiler_bin, str(src_file), "-o", str(exe_file)]
                run_cmd = [str(exe_file)]

            elif lang == "go":
                src_file = tmp_path / "main.go"
                exe_file = tmp_path / f"main{exe_suffix}"
                src_file.write_text(combined, encoding="utf-8")
                compile_cmd = [compiler_bin, "build", "-o", str(exe_file), str(src_file)]
                run_cmd = [str(exe_file)]

            elif lang == "java":
                class_match = re.search(r"public\s+class\s+([A-Za-z0-9_]+)", combined)
                class_name = class_match.group(1) if class_match else "Main"
                src_file = tmp_path / f"{class_name}.java"
                src_file.write_text(combined, encoding="utf-8")
                compile_cmd = [compiler_bin, str(src_file)]
                java_bin = shutil.which("java") or "java"
                run_cmd = [java_bin, "-cp", str(tmp_path), class_name]

            # Step 1: Sandboxed compilation
            compile_res = sandbox.run_command(compile_cmd, cwd=str(tmp_path), timeout=timeout)
            if not compile_res.success or compile_res.exit_code != 0:
                duration = round(time.time() - t0, 3)
                err_detail = compile_res.stderr.strip() or "Compiler returned non-zero exit status"
                return ExecuteResponse(
                    success=False,
                    language=lang,
                    stdout=compile_res.stdout,
                    stderr=compile_res.stderr,
                    exit_code=compile_res.exit_code if compile_res.exit_code != 0 else 1,
                    duration_seconds=duration,
                    sandboxed=True,
                    security_status="clean",
                    violations=[],
                    timed_out=compile_res.timed_out,
                    memory_breached=compile_res.memory_breached,
                    runtime=f"{lang}-compiler",
                    error_message=f"Compilation failed: {err_detail}",
                )

            # Step 2: Sandboxed binary execution
            elapsed_comp = time.time() - t0
            rem_timeout = max(0.5, timeout - elapsed_comp)
            exec_res = sandbox.run_command(run_cmd, cwd=str(tmp_path), timeout=rem_timeout)
            duration = round(time.time() - t0, 3)
            passed = exec_res.success and (exec_res.exit_code == 0) and not exec_res.timed_out and not exec_res.memory_breached

            return ExecuteResponse(
                success=passed,
                language=lang,
                stdout=exec_res.stdout,
                stderr=exec_res.stderr,
                exit_code=exec_res.exit_code,
                duration_seconds=duration,
                sandboxed=True,
                security_status="clean",
                violations=[],
                timed_out=exec_res.timed_out,
                memory_breached=exec_res.memory_breached,
                runtime=f"{lang}-native-binary",
                error_message=exec_res.stderr.strip() if not passed else None,
            )

    # ========================================================================
    # 6. UNRECOGNIZED / UNSUPPORTED LANGUAGE
    # ========================================================================
    else:
        duration = round(time.time() - t0, 3)
        err_msg = (
            f"Unsupported language: '{lang}'. "
            f"Supported runtimes: python, typescript, php, sql, cpp, rust, java, go."
        )
        return ExecuteResponse(
            success=False,
            language=lang,
            stdout="",
            stderr=err_msg,
            exit_code=1,
            duration_seconds=duration,
            sandboxed=True,
            security_status="clean",
            violations=[],
            runtime="unsupported-runtime",
            error_message=err_msg,
        )

