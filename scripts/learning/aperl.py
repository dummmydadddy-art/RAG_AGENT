"""
scripts/learning/aperl.py

APERL: Automated Post-Execution Reflection Loop.
Automatically distills execution traces, test failures, and passing recovery patches
into canonical lessons formatted as:
When <situation>, do <action>, because <reason>.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json
import logging
import re
import sqlite3
import time

logger = logging.getLogger("APERLEngine")


@dataclass
class ExecutionTrace:
    task_id: str
    language: str
    error_type: str
    error_message: str
    failed_code: str
    fixed_code: str
    test_output: str
    domain: Optional[str] = None
    invariants: Optional[List[str]] = None


@dataclass
class DistilledLesson:
    situation: str
    action: str
    reason: str

    def to_canonical_format(self) -> str:
        """Formats the lesson in the mandatory project-wide canonical format."""
        sit = self.situation.strip().rstrip(",")
        act = self.action.strip().rstrip(",")
        rea = self.reason.strip().rstrip(".")
        return f"When {sit}, do {act}, because {rea}."


class APERLEngine:
    """
    Automated reflection engine analyzing execution traces and distilling candidate lessons.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (Path("backend") / "storage" / "vectors.sqlite")
        self._init_db()

    def _init_db(self) -> None:
        if self.db_path:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                conn.execute("PRAGMA busy_timeout = 10000;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS rag_documents (
                        id TEXT NOT NULL,
                        collection TEXT NOT NULL,
                        text TEXT NOT NULL,
                        metadata TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (collection, id)
                    );
                """)
                conn.commit()

    def distill_lesson(
        self,
        trace: ExecutionTrace,
        challenge: Optional[Any] = None,
    ) -> DistilledLesson:
        """
        Analyzes the failure pattern or passing run, the resolved fix, and test feedback
        to synthesize a structured, non-obvious engineering lesson.
        Guarantees strict compliance with: When <situation>, do <action>, because <reason>.
        Eliminates malformed 'When None...' entries.
        """
        err_type_str = str(trace.error_type or "").strip()
        err_msg_str = str(trace.error_message or "").strip()
        err_lower = (err_type_str + " " + err_msg_str).lower()
        test_lower = str(trace.test_output or "").lower()
        lang = trace.language or "python"

        # -------------------------------------------------------------
        # BRANCH 1: PASSING VERIFICATION (POSITIVE ARCHITECTURAL LESSONS)
        # -------------------------------------------------------------
        is_success = (
            err_type_str.lower() in ("none", "", "success")
            or "all unit tests and physical constraints passed" in err_msg_str.lower()
        )

        if is_success:
            return self._distill_positive_lesson(trace, challenge)

        # -------------------------------------------------------------
        # BRANCH 2: SECURITY & AST SANDBOX VIOLATIONS
        # -------------------------------------------------------------
        if any(k in err_lower for k in ("astviolation", "securityviolation", "forbidden", "ast violation")):
            return DistilledLesson(
                situation=f"authoring algorithmic solutions in security-sandboxed {lang} environments",
                action="restrict imports to standard algorithmic libraries (math, collections, heapq) without system modules ('os', 'sys', 'subprocess', 'shutil', 'ctypes', 'socket')",
                reason="the Win32 sandbox AST security guard statically detects and rejects unauthorized system module imports prior to execution",
            )

        # -------------------------------------------------------------
        # BRANCH 3: EXECUTION TIMEOUTS
        # -------------------------------------------------------------
        if (
            err_type_str.lower() in ("timeouterror", "timelimitexceeded", "timeout")
            or any(k in err_lower for k in ("timelimitexceeded", "timed out", "timeoutexpired"))
        ):
            return DistilledLesson(
                situation=f"processing large state spaces, deep recursions, or dense graphs in {lang}",
                action="implement memoization, iterative dynamic programming tables, or early bounding pruning",
                reason="unoptimized exponential branching O(2^N) or unbounded depth-first search exceeds the 5.0-second execution sandbox timeout",
            )

        # -------------------------------------------------------------
        # BRANCH 3B: SANDBOX MEMORY LIMIT / OPENBLAS ALLOCATION FAILURES
        # -------------------------------------------------------------
        if any(k in err_lower for k in ("memory limit", "memoryerror", "out of memory", "openblas")):
            return DistilledLesson(
                situation=f"executing numerical or graph algorithms inside a 256 MB memory-capped Win32 sandbox in {lang}",
                action="use pure standard library data structures and bound cycle-extraction loops instead of importing numpy/OpenBLAS or allocating unbounded lists",
                reason="native BLAS thread pools and unbounded allocation loops exceed the 256 MB Win32 Job Object memory ceiling",
            )

        # -------------------------------------------------------------
        # BRANCH 4: PRESERVED SCIENTIFIC CALCULUS PATTERNS
        # (Evaluated before general AssertionError so scientific errors match precisely)
        # -------------------------------------------------------------
        if "offsetunitcalculuserror" in err_lower or "degc" in err_lower:
            return DistilledLesson(
                situation="performing arithmetic on offset temperature units like degC in Pint",
                action="construct quantities using ureg.Quantity and convert temperature differences to kelvin",
                reason="Pint scalar multiplication with offset units raises OffsetUnitCalculusError on arithmetic subtraction",
            )

        failed_code_lower = str(trace.failed_code or "").lower()
        if "commutative" in err_lower or ("a*b" in failed_code_lower and "b*a" in failed_code_lower):
            return DistilledLesson(
                situation="verifying non-commutative operator algebras or quantum Lie brackets in SymPy",
                action="explicitly pre-bind symbols with commutative=False in local_dict before expression parsing",
                reason="SymPy default symbols are commutative and automatically collapse commutators like A*B - B*A to zero during AST generation",
            )

        if "sqrt" in failed_code_lower and "x**2" in failed_code_lower:
            return DistilledLesson(
                situation="verifying symbolic equivalence across branch cuts like sqrt(x^2)",
                action="use stratified numerical sampling across negative reals and declare explicit positive assumptions",
                reason="without explicit positive assumptions, sqrt(x^2) equals |x| which does not equal x for negative reals",
            )

        # -------------------------------------------------------------
        # BRANCH 4B: MISSING IMPORTS & SYNTAX ERRORS IN SANDBOXED CODE
        # -------------------------------------------------------------
        if "nameerror" in err_lower or "is not defined" in err_lower:
            return DistilledLesson(
                situation=f"emitting standalone sandboxed code blocks in {lang}",
                action="include all required typing and standard library imports (such as typing.Any, typing.Optional, math, threading, collections) at the top of the solution",
                reason="isolated sandbox execution runs only the emitted code block and omits imports declared outside it",
            )
        if "syntaxerror" in err_lower or "indentationerror" in err_lower:
            return DistilledLesson(
                situation=f"generating multi-function or nested-scope implementations in {lang}",
                action="verify balanced delimiters, valid scoping keywords, and complete syntax before emitting the final code block",
                reason="syntactically invalid or truncated blocks fail pre-execution AST parsing in the sandbox",
            )

        # -------------------------------------------------------------
        # BRANCH 5: INVARIANT & ASSERTION ERRORS
        # -------------------------------------------------------------
        if "assertionerror" in err_lower or "invariant" in err_lower:
            trace_dom = str(getattr(challenge, "domain", trace.domain) or "").lower()
            if re.search(r"\b(?:energy|drift|hamiltonian|symplectic)\b", err_lower):
                return DistilledLesson(
                    situation=f"integrating orbital or oscillatory Hamiltonian dynamics in numerical physics ({lang})",
                    action="replace explicit forward Euler schemes with symplectic Velocity-Verlet integrators",
                    reason="first-order explicit Euler introduces artificial secular energy growth that breaches physical conservation invariants",
                )
            if (
                trace_dom in ("concurrency", "systems", "systems_concurrency")
                or re.search(r"\b(?:race|thread|threading|concurrency|lock|lost update|deadlock)\b", err_lower)
            ):
                return DistilledLesson(
                    situation=f"coordinating shared state across multiple concurrent threads in {lang}",
                    action="wrap state modifications in threading.Lock context managers and signal state transitions via Condition variables",
                    reason="unsynchronized access creates race conditions and lost updates that violate count conservation invariants",
                )
            if (
                trace_dom in ("graph_algorithms", "graphs", "graph")
                or re.search(r"\b(?:flow|min[-_ ]?cut|edmonds|kirchhoff)\b", err_lower)
            ):
                return DistilledLesson(
                    situation=f"updating edge flows in network flow optimization algorithms ({lang})",
                    action="maintain skew-symmetry (flow[u][v] == -flow[v][u]) and verify inflow equals outflow at all intermediate nodes",
                    reason="violating skew-symmetry corrupts residual graph capacities and breaches Kirchhoff flow conservation",
                )
            if trace_dom in ("dynamic_programming", "dp"):
                return DistilledLesson(
                    situation=f"solving optimal substructure dynamic programming challenges in {lang}",
                    action="verify base cases, reverse capacity iteration order, and parent backtracking reconstruction against small boundary inputs",
                    reason="incorrect state transition bounds or greedy approximations violate optimality and feasibility assertions",
                )
            return DistilledLesson(
                situation=f"encountering AssertionError during multi-tier test execution in {lang}",
                action="verify boundary condition preconditions and enforce mathematical state invariants prior to returning results",
                reason="unverified intermediate calculations produce edge-case drift that violates contract test assertions",
            )

        # -------------------------------------------------------------
        # BRANCH 6: GENERIC ERROR FALLBACK (NEVER "WHEN NONE...")
        # -------------------------------------------------------------
        err_name = err_type_str if err_type_str and err_type_str.lower() != "none" else "ExecutionError"
        err_lines = [ln.strip() for ln in err_msg_str.splitlines() if ln.strip() and not ln.strip().startswith("Traceback")]
        summary_msg = (err_lines[-1] if err_lines else err_msg_str)[:60].strip()
        clean_fix = str(trace.fixed_code or "").replace("\n", " ")[:60].strip() or "verify edge cases and invariants"
        return DistilledLesson(
            situation=f"handling {err_name} in {lang} ({summary_msg})",
            action=f"apply structured refactoring: {clean_fix}",
            reason=f"it resolves {err_name} and satisfies test suite requirements",
        )

    def _distill_positive_lesson(
        self,
        trace: ExecutionTrace,
        challenge: Optional[Any] = None,
    ) -> DistilledLesson:
        """Synthesizes structured positive architectural reflections across domains."""
        # Determine domain
        dom = ""
        if challenge and hasattr(challenge, "domain") and challenge.domain:
            dom = str(challenge.domain).lower()
        elif trace.domain:
            dom = str(trace.domain).lower()
        else:
            combined = (
                str(trace.task_id or "") + " " +
                str(trace.failed_code or "") + " " +
                str(trace.fixed_code or "")
            ).lower()
            if any(k in combined for k in ("knapsack", "tsp", "bitmask", "dp")):
                dom = "dynamic_programming"
            elif any(k in combined for k in ("flow", "cut", "edmonds", "bellman", "graph")):
                dom = "graph_algorithms"
            elif any(k in combined for k in ("ring_buffer", "memory_pool", "thread", "lock", "concurrency", "counter")):
                dom = "concurrency"
            elif any(k in combined for k in ("symplectic", "verlet", "kepler", "orbit", "oscillator", "physics", "kinetic")):
                dom = "numerical_physics"

        lang = trace.language or "python"
        code_combined = (str(trace.failed_code or "") + " " + str(trace.fixed_code or "")).lower()

        # Domain 1: Dynamic Programming
        if dom in ("dynamic_programming", "dp"):
            if "knapsack" in code_combined or "volume" in code_combined or "capacity" in code_combined:
                return DistilledLesson(
                    situation="solving multi-constrained 0/1 knapsack problems with integer weight and volume bounds",
                    action="iterate capacity dimensions in reverse order in a multi-dimensional DP table",
                    reason="reverse iteration prevents item reuse within the same state transition while bounding auxiliary memory complexity to O(W * V)",
                )
            if "tsp" in code_combined or "bitmask" in code_combined or "held" in code_combined:
                return DistilledLesson(
                    situation="computing exact optimal Hamiltonian tours on small graphs (N <= 16)",
                    action="use Held-Karp bitmask dynamic programming with memoized state transitions and parent backtracking",
                    reason="bitmask memoization reduces factorial complexity O(N!) to O(N^2 * 2^N) while guaranteeing global optimality",
                )
            return DistilledLesson(
                situation=f"optimizing algorithmic problems with overlapping subproblems and optimal substructure in {lang}",
                action="formulate explicit recurrence relations with tabular memoization or bottom-up DP tables",
                reason="memoization eliminates redundant exponential recomputation of identical subproblems",
            )

        # Domain 2: Graph Algorithms
        if dom in ("graph_algorithms", "graphs", "graph"):
            if "flow" in code_combined or "edmonds" in code_combined or "capacity" in code_combined or "cut" in code_combined:
                return DistilledLesson(
                    situation="computing maximum network flow and minimum capacity cuts in directed networks",
                    action="implement the Edmonds-Karp algorithm with breadth-first search augmenting paths and residual graphs",
                    reason="BFS augmenting paths guarantee polynomial O(V * E^2) convergence and prevent non-terminating augmenting cycles on real capacities",
                )
            if "bellman" in code_combined or "negative" in code_combined or "cycle" in code_combined or "relax" in code_combined:
                return DistilledLesson(
                    situation="detecting negative weight cycles and computing single-source shortest paths in directed graphs",
                    action="execute V-1 relaxation passes followed by a V-th relaxation cycle recovery check",
                    reason="a distance update on the V-th pass provides a definitive certificate of a reachable negative weight cycle",
                )
            return DistilledLesson(
                situation=f"traversing complex directed graphs and network topologies in {lang}",
                action="maintain explicit visited sets, residual capacity tracking, and invariant-checked edge relaxations",
                reason="systematic cycle detection and flow tracking prevent infinite loops and ensure valid graph reachability",
            )

        # Domain 3: Systems Concurrency
        if dom in ("concurrency", "systems", "systems_concurrency"):
            if "ring" in code_combined or "buffer" in code_combined or "queue" in code_combined or "counter" in code_combined:
                return DistilledLesson(
                    situation="implementing bounded FIFO circular queues under multi-threaded contention",
                    action="synchronize head and tail pointer updates with threading.Lock and separate not_full and not_empty Condition variables",
                    reason="dual condition variables eliminate busy-wait spinning and protect against race conditions and pointer corruption across concurrent threads",
                )
            if "pool" in code_combined or "memory" in code_combined or "lease" in code_combined:
                return DistilledLesson(
                    situation="managing fixed-size pre-allocated buffer blocks across concurrent worker threads",
                    action="guard block allocation and deallocation with mutex locks and validate lease ownership before freeing",
                    reason="lease ownership validation prevents double-free vulnerabilities and preserves total capacity conservation invariants",
                )
            return DistilledLesson(
                situation=f"sharing mutable data structures across concurrent threads in {lang}",
                action="enforce mutual exclusion using atomic locks, condition variables, and strict resource ownership boundaries",
                reason="atomic synchronization prevents race conditions, lost updates, and memory corruptions across concurrent execution paths",
            )

        # Domain 4: Numerical Physics
        if dom in ("numerical_physics", "physics"):
            if "verlet" in code_combined or "orbit" in code_combined or "kepler" in code_combined:
                return DistilledLesson(
                    situation="integrating Hamiltonian dynamical systems or gravitational Kepler orbits over long durations",
                    action="use a second-order symplectic Velocity-Verlet numerical integrator with half-step velocity updates",
                    reason="symplectic integrators preserve the phase-space symplectic 2-form and bound total mechanical energy drift over thousands of integration steps",
                )
            if "damped" in code_combined or "oscillator" in code_combined or "dissipat" in code_combined:
                return DistilledLesson(
                    situation="simulating damped mechanical or electrical oscillatory systems",
                    action="verify that total mechanical energy dissipates monotonically across consecutive time steps",
                    reason="dissipative viscous friction forces strictly satisfy the second law of thermodynamics by removing kinetic and potential energy",
                )
            return DistilledLesson(
                situation=f"solving numerical physics differential equations in {lang}",
                action="assert physical conservation laws (energy, momentum, mass) and verify dimensional homogeneity with Pint units",
                reason="physical invariant assertions detect numerical integration instabilities and unphysical drift before simulation completion",
            )

        # Universal fallback positive reflection
        return DistilledLesson(
            situation=f"implementing verified algorithmic solutions in {lang}",
            action="assert mathematical state invariants, boundary limits, and contract test assertions",
            reason="invariant-driven verification guarantees algorithmic soundness and prevents boundary regressions",
        )

    def process_and_save(
        self,
        trace: ExecutionTrace,
        challenge: Optional[Any] = None,
    ) -> str:
        """
        Distills a canonical lesson from trace and upserts it into the SQLite database.
        Returns unique lesson_id.
        """
        lesson = self.distill_lesson(trace, challenge=challenge)
        canonical_text = lesson.to_canonical_format()

        # Hash canonical text for deterministic deduplication
        lesson_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()[:8]
        lesson_id = f"lesson_{lesson_hash}"

        domain_val = getattr(challenge, "domain", trace.domain) or "general"

        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            conn.execute("PRAGMA busy_timeout = 10000;")
            existing_row = conn.execute(
                "SELECT metadata FROM rag_documents WHERE collection = 'lessons' AND id = ?",
                (lesson_id,),
            ).fetchone()
            existing_meta: Dict[str, Any] = {}
            if existing_row and existing_row[0]:
                try:
                    existing_meta = json.loads(existing_row[0])
                except Exception:
                    existing_meta = {}

            meta = {
                "source_task": trace.task_id,
                "language": trace.language,
                "error_type": trace.error_type,
                "domain": domain_val,
                "status": existing_meta.get("status", "candidate"),
                "strength": existing_meta.get("strength", 10.0),
                "usage_count": existing_meta.get("usage_count", 0),
                "success_count": existing_meta.get("success_count", 0),
                "fail_count": existing_meta.get("fail_count", 0),
                "created_at": existing_meta.get("created_at", time.time()),
                "last_used_at": existing_meta.get("last_used_at", None),
            }
            if "status_reason" in existing_meta:
                meta["status_reason"] = existing_meta["status_reason"]
            if "promoted_at" in existing_meta:
                meta["promoted_at"] = existing_meta["promoted_at"]
            if "retired_at" in existing_meta:
                meta["retired_at"] = existing_meta["retired_at"]

            conn.execute(
                """
                INSERT OR REPLACE INTO rag_documents (id, collection, text, metadata)
                VALUES (?, 'lessons', ?, ?)
                """,
                (lesson_id, canonical_text, json.dumps(meta)),
            )
            conn.commit()

        return lesson_id
