#!/usr/bin/env python3
"""
Full 24-Task Suite Generator for Phase 3.
Generates task metadata, contracts, traceability matrices, and encrypts all 24 hidden test fixtures.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.crypto_utils import encrypt_evals
from evals.generate_task_suite import TASKS as INITIAL_8_TASKS
from evals.tasks_batch_coding_maths import TASKS_CODING_MATHS
from evals.tasks_batch_physics_multi_heldout import TASKS_PHYSICS_MULTI_HELDOUT

TASKS_DIR = ROOT / "evals" / "tasks"
ENCRYPTED_ARCHIVE = ROOT / "evals" / "hidden_evals.enc"
DEFAULT_PASSPHRASE = "antigravity-eval-secret-2026"
CANARY = "CANARY-RAG-AGENT-CHECK-V2-7A8B9C0D-E1F2-3456-7890-ABCDEF123456"

ALL_24_TASKS = INITIAL_8_TASKS + TASKS_CODING_MATHS + TASKS_PHYSICS_MULTI_HELDOUT


def generate_full_suite():
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    encrypted_payload: dict[str, str] = {}

    print(f"Generating full 24-task suite into {TASKS_DIR}...")
    assert len(ALL_24_TASKS) == 24, f"Expected 24 tasks, found {len(ALL_24_TASKS)}"

    # Category counts
    cats = {}
    held_out_count = 0
    for t in ALL_24_TASKS:
        c = t["category"]
        cats[c] = cats.get(c, 0) + 1
        if t["held_out"]:
            held_out_count += 1

    print(f"Task Breakdown: {cats} | Held-Out Tasks: {held_out_count}")

    for t in ALL_24_TASKS:
        t_id = t["id"]
        t_dir = TASKS_DIR / t_id
        t_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "id": t_id,
            "category": t["category"],
            "held_out": t["held_out"],
            "title": t["title"],
            "target_file": t["target_file"],
            "canary": CANARY,
        }
        (t_dir / "task.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        (t_dir / "README.md").write_text(t["spec"].strip() + "\n", encoding="utf-8")
        (t_dir / "traceability.md").write_text(t["traceability"].strip() + "\n", encoding="utf-8")
        encrypted_payload[t_id] = t["test_code"].strip()

    # Encrypt all 24 hidden test suites
    encrypt_evals(encrypted_payload, DEFAULT_PASSPHRASE, ENCRYPTED_ARCHIVE)
    print(f"Successfully encrypted {len(encrypted_payload)} hidden test fixtures into {ENCRYPTED_ARCHIVE.name}")
    print(f"Archive size: {ENCRYPTED_ARCHIVE.stat().st_size} bytes")


if __name__ == "__main__":
    generate_full_suite()
