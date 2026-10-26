#!/usr/bin/env python
"""
Git pre-commit hook: Enforces canary leak protection and protected paths authorization.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple

CANARY_TOKEN = "CANARY-RAG-AGENT-CHECK-V2-7A8B9C0D-E1F2-3456-7890-ABCDEF123456"
PROTECTED_PREFIXES = (".agents/", "GEMINI.md", "AGENTS.md", "evals/")


def check_commit_allowed(staged_files: Dict[str, str]) -> Tuple[bool, str]:
    override_active = (os.environ.get("ALLOW_PROTECTED_OVERRIDE") == "1")

    for path, content in staged_files.items():
        normalized_path = path.replace("\\", "/")

        # Allow hook definitions, hook unit tests, and eval harness runners to declare CANARY_TOKEN definition
        is_scanner_def = (
            normalized_path.startswith("scripts/hooks/")
            or "test_git_hooks" in normalized_path
            or normalized_path.startswith("evals/")
        )
        if not is_scanner_def and (CANARY_TOKEN in content or CANARY_TOKEN in path):
            return False, f"Canary token detected in staged file: {path}"

        # Check protected paths
        if normalized_path.startswith(PROTECTED_PREFIXES) or normalized_path in PROTECTED_PREFIXES:
            if not override_active:
                return (
                    False,
                    f"Protected path modification detected ({normalized_path}). "
                    f"Set ALLOW_PROTECTED_OVERRIDE=1 to authorize this change.",
                )

    return True, "Commit allowed"


def main():
    # Query staged files from git
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
        filenames = [f.strip() for f in proc.stdout.splitlines() if f.strip()]
    except Exception as e:
        sys.stderr.write(f"Failed to query staged files: {e}\n")
        sys.exit(0)

    staged_files: Dict[str, str] = {}
    for fn in filenames:
        try:
            show_proc = subprocess.run(
                ["git", "show", f":{fn}"],
                capture_output=True,
                text=True,
                errors="ignore",
            )
            staged_files[fn] = show_proc.stdout
        except Exception:
            staged_files[fn] = ""

    allowed, msg = check_commit_allowed(staged_files)
    if not allowed:
        sys.stderr.write(f"\n[GIT GUARD PRE-COMMIT ERROR] {msg}\n\n")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
