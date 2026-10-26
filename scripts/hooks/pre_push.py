#!/usr/bin/env python
"""
Git pre-push hook: Enforces branch safety, repo isolation, and canary protection.
"""

import sys
from typing import List, Tuple

CANARY_TOKEN = "CANARY-RAG-AGENT-CHECK-V2-7A8B9C0D-E1F2-3456-7890-ABCDEF123456"
FORBIDDEN_REPOS = ["lms", "lms-repo", "external-lms"]


def check_push_allowed(push_lines: List[str], remote_name: str, remote_url: str) -> Tuple[bool, str]:
    # Check repository isolation
    url_lower = remote_url.lower()
    for fr in FORBIDDEN_REPOS:
        if fr in url_lower:
            return False, f"Pushing to external or legacy LMS repository is forbidden: {remote_url}"

    for line in push_lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 3:
            local_ref, local_sha, remote_ref = parts[0], parts[1], parts[2]
            # Disallow pushing directly to main
            if remote_ref == "refs/heads/main" or remote_ref.endswith("/main"):
                return False, "Direct push to 'main' branch is strictly forbidden. Push to feature branches only."
            # Disallow canary leakage in push lines
            if CANARY_TOKEN in line:
                return False, "Canary token detected in push reference metadata"

    return True, "Push allowed"


def main():
    remote_name = sys.argv[1] if len(sys.argv) > 1 else "origin"
    remote_url = sys.argv[2] if len(sys.argv) > 2 else ""

    push_lines = sys.stdin.readlines()
    allowed, msg = check_push_allowed(push_lines, remote_name, remote_url)
    if not allowed:
        sys.stderr.write(f"\n[GIT GUARD PRE-PUSH ERROR] {msg}\n\n")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
