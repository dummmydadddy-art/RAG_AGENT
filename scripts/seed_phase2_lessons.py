#!/usr/bin/env python3
"""
Seed initial verified lessons for Phase 2 learning loop evaluation.
Only training tasks (Tasks 01, 02, 03, 04, 05, 08) are seeded.
Held-out tasks (Tasks 06 and 07) are strictly excluded.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rag-adapter"))
sys.path.insert(0, str(ROOT / "rag-mcp"))

from rag_adapter.sqlite_backend import LocalSqliteRagBackend
from rag_adapter.models import LessonStatus

SEEDED_LESSONS = [
    {
        "id": "L-2026-10-0001",
        "title": "Use collections.OrderedDict for O(1) LRU eviction",
        "rule": "When implementing LRU cache eviction in Python, do use collections.OrderedDict move_to_end and popitem(last=False), because it provides guaranteed O(1) amortized access and eviction without manual doubly linked list pointers.",
        "domain": ["python", "architecture"],
        "evidence": {
            "task_id": "TASK-01-CODE-LRU",
            "commit": "8af35bb",
            "tests": ["test_lru_basic", "test_lru_eviction", "test_lru_types"],
            "review": "passed",
        },
        "status": LessonStatus.VERIFIED,
    },
    {
        "id": "L-2026-10-0002",
        "title": "Enforce Kahn algorithm for topological sort and cycle detection",
        "rule": "When resolving directed dependency graphs, do use Kahn algorithm tracking in-degrees, because it simultaneously computes topological order and isolates cycles in O(V + E) time.",
        "domain": ["python", "architecture"],
        "evidence": {
            "task_id": "TASK-02-CODE-GRAPH",
            "commit": "8af35bb",
            "tests": ["test_topological_sort", "test_cycle_error"],
            "review": "passed",
        },
        "status": LessonStatus.VERIFIED,
    },
    {
        "id": "L-2026-10-0003",
        "title": "Enforce bracket fallback in Halley root finding",
        "rule": "When finding roots with available second derivative and a bracket, do fall back to bisection when candidate steps land outside the bracket or derivative is near zero, because Halley steps diverge near local extrema.",
        "domain": ["numerics", "maths"],
        "evidence": {
            "task_id": "TASK-03-MATH-ROOTS",
            "commit": "8af35bb",
            "tests": ["test_halley_cubic", "test_extremum_bracket_fallback"],
            "review": "passed",
        },
        "status": LessonStatus.VERIFIED,
    },
    {
        "id": "L-2026-10-0004",
        "title": "Normalize quaternions before spherical linear interpolation",
        "rule": "When computing quaternion slerp or product, do normalize input quaternions and check sign of dot product, because unnormalized quaternions distort 3D rotations and acute angle flipping prevents 360-degree long paths.",
        "domain": ["physics", "maths"],
        "evidence": {
            "task_id": "TASK-04-MATH-QUATERNION",
            "commit": "8af35bb",
            "tests": ["test_quaternion_norm", "test_slerp_shortest_path"],
            "review": "passed",
        },
        "status": LessonStatus.VERIFIED,
    },
    {
        "id": "L-2026-10-0005",
        "title": "Bound initial eccentric anomaly guess for Kepler solver",
        "rule": "When solving Kepler equation for eccentric anomaly, do initialize E_0 using Danby or Machin bounds rather than raw mean anomaly M, because high eccentricity e > 0.8 causes standard Newton-Raphson to diverge.",
        "domain": ["physics", "numerics"],
        "evidence": {
            "task_id": "TASK-05-PHYS-KEPLER",
            "commit": "8af35bb",
            "tests": ["test_kepler_near_parabolic", "test_kepler_convergence"],
            "review": "passed",
        },
        "status": LessonStatus.VERIFIED,
    },
    {
        "id": "L-2026-10-0006",
        "title": "Störmer-Verlet half-step velocity update",
        "rule": "When advancing second-order dynamical systems with velocity-dependent forces, do compute half-step velocity before position update, because symplectic phase space volume is strictly conserved.",
        "domain": ["physics", "numerics"],
        "evidence": {
            "task_id": "TASK-08-RETRIEVAL-SYMPLECTIC",
            "commit": "8af35bb",
            "tests": ["test_stormer_verlet_symplectic", "test_energy_conservation"],
            "review": "passed",
        },
        "status": LessonStatus.VERIFIED,
    },
]


def seed_lessons(db_path: Path = ROOT / "backend" / "storage" / "vectors.sqlite"):
    backend = LocalSqliteRagBackend(str(db_path))
    seeded_count = 0
    for l in SEEDED_LESSONS:
        backend.upsert_lesson(l)
        seeded_count += 1
        print(f"  [SEEDED] {l['id']}: {l['title']} ({l['status']})")
    print(f"\nTotal seeded lessons: {seeded_count}")


if __name__ == "__main__":
    seed_lessons()
