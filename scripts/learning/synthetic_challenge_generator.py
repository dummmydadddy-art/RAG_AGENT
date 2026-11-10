"""
scripts/learning/synthetic_challenge_generator.py

Active Synthetic Challenge Generator (ASCG).
Autonomous background self-play engine that synthesizes polyglot coding challenges
across Dynamic Programming, Graph Algorithms, Low-Level Systems Concurrency,
and Numerical Physics Solvers.
Includes automated multi-tier test suites (Smoke, Boundary, Scale Stress, and Invariants),
autonomous model solver querying local Ollama (stem-coder-expert:latest) with Chain-of-Thought (CoT),
AST syntax verification, and seamless offline reference fallback.
"""

from __future__ import annotations

import ast
import json
import logging
import math
import random
import re
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("SyntheticChallengeGenerator")


@dataclass
class SyntheticChallenge:
    """
    Metadata contract for active synthetic coding challenges.
    Maintains 9 fields with full backward compatibility for legacy 6-positional invocations.
    """
    challenge_id: str
    domain: str
    language: str
    prompt: str
    starter_code: str
    test_suite: str
    difficulty: str = "intermediate"
    reference_solution: str = ""
    invariants: List[str] = field(default_factory=list)


def is_ollama_available(ollama_url: str = "http://localhost:11434", probe_timeout: float = 1.5) -> bool:
    """
    Fast pre-flight connectivity probe checking whether the local Ollama daemon is reachable.
    """
    try:
        endpoint = f"{ollama_url.rstrip('/')}/api/tags"
        req = urllib.request.Request(endpoint, headers={"User-Agent": "RAG-Agent-Solver/1.0"})
        with urllib.request.urlopen(req, timeout=probe_timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def extract_runnable_code(
    raw_response: str,
    language: str = "python",
    starter_code: Optional[str] = None,
) -> Optional[str]:
    """
    Extracts, cleans, and validates candidate code blocks from raw LLM responses.
    Handles closed markdown fences, unclosed fences, untagged code, and verifies AST syntax.
    """
    if not raw_response or not raw_response.strip():
        return None

    lang_aliases = {
        "python": ["python", "py", "python3"],
        "rust": ["rust", "rs"],
        "cpp": ["cpp", "c++", "c"],
        "typescript": ["typescript", "ts", "javascript", "js"],
        "php": ["php"],
        "java": ["java"],
        "go": ["go", "golang"],
        "sql": ["sql"],
    }
    aliases = lang_aliases.get(language.lower(), [language.lower()])
    alias_group = "|".join(re.escape(a) for a in aliases)

    candidates: List[str] = []

    # 1. Closed fence pattern: ```python ... ```
    closed_pattern = rf"```(?:{alias_group})?\s*\n(.*?)```"
    matches = re.findall(closed_pattern, raw_response, flags=re.DOTALL | re.IGNORECASE)
    if matches:
        candidates.extend(matches)

    # 2. Unclosed trailing fence pattern (handling 1024 token cutoff)
    if not candidates:
        unclosed_pattern = rf"```(?:{alias_group})?\s*\n(.*)$"
        unclosed = re.findall(unclosed_pattern, raw_response, flags=re.DOTALL | re.IGNORECASE)
        if unclosed:
            candidates.extend(unclosed)

    # 3. Raw code fallback if no markdown fences exist
    if not candidates:
        stripped = raw_response.strip()
        code_start_keywords = ("def ", "class ", "import ", "from ", "pub fn ", "#", "//", "struct ")
        if any(stripped.startswith(kw) for kw in code_start_keywords):
            candidates = [stripped]

    if not candidates:
        return None

    # 4. AST and Syntactic Validation for Python
    valid_candidates: List[str] = []
    for cand in candidates:
        code_str = cand.strip()
        if not code_str:
            continue
        if language.lower() == "python":
            try:
                ast.parse(code_str)
                valid_candidates.append(code_str)
            except SyntaxError:
                # Strip extraneous markdown backtick lines if any
                lines = [l for l in code_str.splitlines() if not l.strip().startswith("```")]
                cleaned = "\n".join(lines).strip()
                try:
                    ast.parse(cleaned)
                    valid_candidates.append(cleaned)
                except SyntaxError:
                    continue
        else:
            valid_candidates.append(code_str)

    if not valid_candidates:
        return None

    # 5. Identifier Matching (prefer candidate containing target identifier)
    if starter_code:
        identifiers = re.findall(r"(?:def|class)\s+([a-zA-Z0-9_]+)", starter_code)
        if identifiers:
            for cand in reversed(valid_candidates):
                if any(ident in cand for ident in identifiers):
                    return cand

    # Return the last valid candidate (final implementation block in CoT)
    return valid_candidates[-1]


def solve_challenge(
    challenge: SyntheticChallenge,
    model_tag: str = "stem-coder-expert:latest",
    use_live_model: bool = True,
    ollama_url: str = "http://localhost:11434",
    timeout: float = 60.0,
    retrieved_lessons: Optional[List[str]] = None,
    allow_fallback: bool = True,
) -> str:
    """
    Autonomously generates a solution to a SyntheticChallenge using the local
    Ollama LLM with Chain-of-Thought (CoT) reasoning.

    When Ollama is offline, unreachable, or returns unparseable code and
    `allow_fallback=True`, seamlessly falls back to `challenge.reference_solution`
    to ensure hermetic offline testability. When `allow_fallback=False`, returns
    empty string if the live model fails to produce runnable code.
    """
    fallback_solution = (challenge.reference_solution or challenge.starter_code) if allow_fallback else ""

    if not use_live_model:
        return challenge.reference_solution or challenge.starter_code

    # Fast pre-flight check (<= 1.5s)
    if not is_ollama_available(ollama_url, probe_timeout=1.5):
        logger.info(f"Ollama daemon unreachable at {ollama_url}; using reference solution fallback.")
        return fallback_solution

    # Build Chain-of-Thought user prompt
    invariants_text = "\n".join(f"- {inv}" for inv in challenge.invariants) if challenge.invariants else "- None"
    lessons_section = ""
    if retrieved_lessons:
        lessons_text = "\n".join(f"- {l}" for l in retrieved_lessons)
        lessons_section = f"\n### Relevant Engineering Lessons (RAG Context)\n{lessons_text}\n"

    system_prompt = (
        "You are STEM-Coder-Expert, an elite algorithmic and systems engineer. "
        "Your task is to write correct, optimal, standalone sandboxed code. "
        "Constraints: max 256 MB RAM, max 5.0 seconds runtime, pure standard library ONLY "
        "(no numpy, scipy, os, sys, subprocess, shutil, ctypes, socket). "
        "Your code block MUST include ALL required imports at the top "
        "(e.g., `from typing import Any, Optional`, `import math, threading, time`, `from collections import deque`). "
        "First provide brief reasoning, then output the complete runnable code in a markdown block."
    )

    user_prompt = f"""### Problem Specification
- Domain: {challenge.domain}
- Difficulty: {challenge.difficulty}
- Language: {challenge.language}

Prompt:
{challenge.prompt}

### Mandatory Invariants & Constraints
{invariants_text}
- Max RAM: 256 MB
- Max Runtime: 5.0 seconds
- Include ALL required imports (such as `from typing import Any, Optional`) at the top of your code block.

### Starter Code
```{challenge.language}
{challenge.starter_code}
```
{lessons_section}
Please solve the problem step-by-step and output your complete, self-contained, runnable implementation (including all imports and exact function/class names from Starter Code) inside a single ```{challenge.language} ... ``` code block.
"""

    payload = {
        "model": model_tag,
        "prompt": user_prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.95,
            "num_predict": 1024,
            "stop": ["<|endoftext|>", "<|im_end|>"],
        },
        "keep_alive": "5m",
    }

    try:
        endpoint = f"{ollama_url.rstrip('/')}/api/generate"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "RAG-Agent-Solver/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                response_text = body.get("response", "")
                extracted = extract_runnable_code(
                    response_text,
                    language=challenge.language,
                    starter_code=challenge.starter_code,
                )
                if extracted:
                    return extracted
    except Exception as e:
        logger.warning(f"Ollama inference failed ({e}); falling back to reference solution.")

    return fallback_solution


class SyntheticChallengeGenerator:
    """
    Synthesizes diverse polyglot coding challenges with rigorous automated test suites.
    """

    DOMAIN_ALIASES = {
        "dp": "dynamic_programming",
        "dynamic_programming": "dynamic_programming",
        "graphs": "graph_algorithms",
        "graph": "graph_algorithms",
        "graph_algorithms": "graph_algorithms",
        "concurrency": "concurrency",
        "systems": "concurrency",
        "systems_concurrency": "concurrency",
        "numerical_physics": "numerical_physics",
        "physics": "numerical_physics",
    }

    CHALLENGE_TEMPLATES: Dict[str, Dict[str, Dict[str, Any]]] = {
        "dynamic_programming": {
            "multi_constrained_knapsack": {
                "difficulty": "advanced",
                "invariants": [
                    "capacity_bounded",
                    "exact_value_sum",
                    "monotonicity_of_capacity",
                    "subset_index_validity",
                ],
                "prompt": (
                    "Implement a function `multi_constrained_knapsack(weights: list[int], volumes: list[int], values: list[int], "
                    "max_weight: int, max_volume: int) -> tuple[int, list[int]]` that solves the 2-dimensional 0/1 Knapsack problem. "
                    "Given item weights, volumes, and values, find the maximum achievable total value such that total weight <= max_weight "
                    "and total volume <= max_volume. Return a tuple `(max_value, selected_indices)` where `selected_indices` is the sorted "
                    "list of 0-based indices of items included in the optimal knapsack."
                ),
                "starter_code": (
                    "def multi_constrained_knapsack(\n"
                    "    weights: list[int],\n"
                    "    volumes: list[int],\n"
                    "    values: list[int],\n"
                    "    max_weight: int,\n"
                    "    max_volume: int\n"
                    ") -> tuple[int, list[int]]:\n"
                    "    \"\"\"\n"
                    "    Solves the multi-constrained 0/1 knapsack problem with index backtracking.\n"
                    "    \"\"\"\n"
                    "    # TODO: Implement 2D state transition and path reconstruction\n"
                    "    return 0, []\n"
                ),
                "reference_solution": (
                    "def multi_constrained_knapsack(\n"
                    "    weights: list[int],\n"
                    "    volumes: list[int],\n"
                    "    values: list[int],\n"
                    "    max_weight: int,\n"
                    "    max_volume: int\n"
                    ") -> tuple[int, list[int]]:\n"
                    "    n = len(weights)\n"
                    "    if n == 0 or max_weight <= 0 or max_volume <= 0:\n"
                    "        return 0, []\n"
                    "    dp = [[0] * (max_volume + 1) for _ in range(max_weight + 1)]\n"
                    "    history = []\n"
                    "    for i in range(n):\n"
                    "        w_i = weights[i]\n"
                    "        v_i = volumes[i]\n"
                    "        val_i = values[i]\n"
                    "        taken = [[False] * (max_volume + 1) for _ in range(max_weight + 1)]\n"
                    "        for w in range(max_weight, w_i - 1, -1):\n"
                    "            for v in range(max_volume, v_i - 1, -1):\n"
                    "                if dp[w - w_i][v - v_i] + val_i > dp[w][v]:\n"
                    "                    dp[w][v] = dp[w - w_i][v - v_i] + val_i\n"
                    "                    taken[w][v] = True\n"
                    "        history.append(taken)\n"
                    "    max_val = dp[max_weight][max_volume]\n"
                    "    chosen = []\n"
                    "    cw, cv = max_weight, max_volume\n"
                    "    for i in range(n - 1, -1, -1):\n"
                    "        if history[i][cw][cv]:\n"
                    "            chosen.append(i)\n"
                    "            cw -= weights[i]\n"
                    "            cv -= volumes[i]\n"
                    "    chosen.reverse()\n"
                    "    return max_val, chosen\n"
                ),
                "test_suite": (
                    "# --- TIER 1: SMOKE TESTS ---\n"
                    "val, chosen = multi_constrained_knapsack([1, 2, 3], [2, 1, 3], [12, 20, 30], 3, 3)\n"
                    "assert val == 32\n"
                    "assert chosen == [0, 1]\n\n"
                    "# --- TIER 2: BOUNDARY & EDGE CASES ---\n"
                    "v_empty, c_empty = multi_constrained_knapsack([], [], [], 10, 10)\n"
                    "assert v_empty == 0 and c_empty == []\n"
                    "v_zero, c_zero = multi_constrained_knapsack([1, 2], [1, 2], [10, 20], 0, 5)\n"
                    "assert v_zero == 0 and c_zero == []\n\n"
                    "# --- TIER 3: SCALE STRESS TESTS ---\n"
                    "import time\n"
                    "t0 = time.time()\n"
                    "big_w = [i % 7 + 1 for i in range(25)]\n"
                    "big_v = [i % 5 + 1 for i in range(25)]\n"
                    "big_val = [i * 3 + 2 for i in range(25)]\n"
                    "res_val, res_idx = multi_constrained_knapsack(big_w, big_v, big_val, 30, 25)\n"
                    "assert time.time() - t0 < 1.0\n"
                    "assert res_val > 0\n\n"
                    "# --- TIER 4: INVARIANTS & CONSTRAINTS ---\n"
                    "total_w = sum(big_w[i] for i in res_idx)\n"
                    "total_v = sum(big_v[i] for i in res_idx)\n"
                    "total_val = sum(big_val[i] for i in res_idx)\n"
                    "assert total_w <= 30, 'Total weight exceeded max_weight'\n"
                    "assert total_v <= 25, 'Total volume exceeded max_volume'\n"
                    "assert total_val == res_val, 'Reconstructed items sum must match max_val'\n"
                    "assert res_idx == sorted(res_idx), 'Selected indices must be sorted'\n"
                ),
            },
            "solve_tsp_bitmask": {
                "difficulty": "expert",
                "invariants": [
                    "hamiltonian_cycle_completeness",
                    "cost_consistency",
                    "optimal_lower_bound",
                    "symmetry_invariance",
                ],
                "prompt": (
                    "Implement `solve_tsp_bitmask(dist_matrix: list[list[int]]) -> tuple[int, list[int]]` solving the Traveling "
                    "Salesperson Problem on N vertices (N <= 16) using O(N^2 * 2^N) bitmask dynamic programming. "
                    "Return `(min_cost, tour)` where `tour` is the optimal Hamiltonian cycle starting at vertex 0, visiting every vertex "
                    "exactly once, and returning to vertex 0."
                ),
                "starter_code": (
                    "def solve_tsp_bitmask(dist_matrix: list[list[int]]) -> tuple[int, list[int]]:\n"
                    "    \"\"\"\n"
                    "    Computes exact minimum TSP tour cost and path using Held-Karp bitmask DP.\n"
                    "    \"\"\"\n"
                    "    # TODO: Implement bitmask DP\n"
                    "    return 0, []\n"
                ),
                "reference_solution": (
                    "def solve_tsp_bitmask(dist_matrix: list[list[int]]) -> tuple[int, list[int]]:\n"
                    "    n = len(dist_matrix)\n"
                    "    if n <= 1:\n"
                    "        return 0, [0, 0] if n == 1 else []\n"
                    "    if n == 2:\n"
                    "        return dist_matrix[0][1] + dist_matrix[1][0], [0, 1, 0]\n"
                    "    num_states = 1 << n\n"
                    "    INF = float('inf')\n"
                    "    dp = [[INF] * n for _ in range(num_states)]\n"
                    "    parent = [[-1] * n for _ in range(num_states)]\n"
                    "    dp[1][0] = 0\n"
                    "    for mask in range(1, num_states):\n"
                    "        if not (mask & 1):\n"
                    "            continue\n"
                    "        for u in range(n):\n"
                    "            if not (mask & (1 << u)) or dp[mask][u] == INF:\n"
                    "                continue\n"
                    "            for v in range(n):\n"
                    "                if not (mask & (1 << v)):\n"
                    "                    next_mask = mask | (1 << v)\n"
                    "                    cost = dp[mask][u] + dist_matrix[u][v]\n"
                    "                    if cost < dp[next_mask][v]:\n"
                    "                        dp[next_mask][v] = cost\n"
                    "                        parent[next_mask][v] = u\n"
                    "    all_visited = num_states - 1\n"
                    "    best_cost = INF\n"
                    "    last_node = -1\n"
                    "    for u in range(1, n):\n"
                    "        total = dp[all_visited][u] + dist_matrix[u][0]\n"
                    "        if total < best_cost:\n"
                    "            best_cost = total\n"
                    "            last_node = u\n"
                    "    tour = [0]\n"
                    "    curr_mask = all_visited\n"
                    "    curr_node = last_node\n"
                    "    subpath = []\n"
                    "    while curr_node != 0:\n"
                    "        subpath.append(curr_node)\n"
                    "        p = parent[curr_mask][curr_node]\n"
                    "        curr_mask ^= (1 << curr_node)\n"
                    "        curr_node = p\n"
                    "    subpath.reverse()\n"
                    "    tour.extend(subpath)\n"
                    "    tour.append(0)\n"
                    "    return int(best_cost), tour\n"
                ),
                "test_suite": (
                    "# --- TIER 1: SMOKE TESTS ---\n"
                    "d = [[0, 10, 15, 20], [10, 0, 35, 25], [15, 35, 0, 30], [20, 25, 30, 0]]\n"
                    "cost, tour = solve_tsp_bitmask(d)\n"
                    "assert cost == 80\n"
                    "assert tour[0] == 0 and tour[-1] == 0\n"
                    "assert len(tour) == 5\n\n"
                    "# --- TIER 2: BOUNDARY CASES ---\n"
                    "cost2, tour2 = solve_tsp_bitmask([[0, 5], [7, 0]])\n"
                    "assert cost2 == 12\n"
                    "assert tour2 == [0, 1, 0]\n\n"
                    "# --- TIER 3: SCALE STRESS TESTS ---\n"
                    "import time\n"
                    "n = 8\n"
                    "mat = [[abs(i - j) * 10 for j in range(n)] for i in range(n)]\n"
                    "t0 = time.time()\n"
                    "c8, t8 = solve_tsp_bitmask(mat)\n"
                    "assert time.time() - t0 < 0.5\n\n"
                    "# --- TIER 4: HAMILTONIAN INVARIANTS ---\n"
                    "assert len(t8) == n + 1\n"
                    "assert set(t8[:-1]) == set(range(n)), 'All vertices must be visited exactly once'\n"
                    "calc_cost = sum(mat[t8[k]][t8[k + 1]] for k in range(n))\n"
                    "assert calc_cost == c8, 'Tour path cost must equal computed cost'\n"
                ),
            },
        },
        "graph_algorithms": {
            "max_flow_edmonds_karp": {
                "difficulty": "advanced",
                "invariants": [
                    "flow_conservation",
                    "capacity_constraint",
                    "max_flow_min_cut_equality",
                    "net_source_sink_duality",
                ],
                "prompt": (
                    "Implement `max_flow_edmonds_karp(capacity: list[list[int]], source: int, sink: int) -> tuple[int, list[list[int]], list[int]]` "
                    "computing the maximum flow in a directed capacity network using the Edmonds-Karp BFS augmenting paths algorithm. "
                    "Return `(max_flow_value, flow_matrix, min_cut_reachable_nodes)` where `flow_matrix[u][v]` is the forward flow along edge (u, v) "
                    "and `min_cut_reachable_nodes` is the sorted list of vertices reachable from source in the final residual graph."
                ),
                "starter_code": (
                    "def max_flow_edmonds_karp(\n"
                    "    capacity: list[list[int]],\n"
                    "    source: int,\n"
                    "    sink: int\n"
                    ") -> tuple[int, list[list[int]], list[int]]:\n"
                    "    \"\"\"\n"
                    "    Computes maximum s-t flow and minimum cut partition via Edmonds-Karp.\n"
                    "    \"\"\"\n"
                    "    # TODO: Implement BFS augmenting paths and residual capacity tracking\n"
                    "    return 0, [], []\n"
                ),
                "reference_solution": (
                    "from collections import deque\n\n"
                    "def max_flow_edmonds_karp(\n"
                    "    capacity: list[list[int]],\n"
                    "    source: int,\n"
                    "    sink: int\n"
                    ") -> tuple[int, list[list[int]], list[int]]:\n"
                    "    n = len(capacity)\n"
                    "    if source == sink or n == 0:\n"
                    "        return 0, [[0] * n for _ in range(n)], [source] if n > 0 else []\n"
                    "    flow = [[0] * n for _ in range(n)]\n"
                    "    res = [row[:] for row in capacity]\n"
                    "    max_flow = 0\n"
                    "    while True:\n"
                    "        parent = [-1] * n\n"
                    "        parent[source] = source\n"
                    "        q = deque([source])\n"
                    "        while q and parent[sink] == -1:\n"
                    "            u = q.popleft()\n"
                    "            for v in range(n):\n"
                    "                if parent[v] == -1 and res[u][v] > 0:\n"
                    "                    parent[v] = u\n"
                    "                    q.append(v)\n"
                    "        if parent[sink] == -1:\n"
                    "            break\n"
                    "        bottleneck = float('inf')\n"
                    "        curr = sink\n"
                    "        while curr != source:\n"
                    "            prev = parent[curr]\n"
                    "            bottleneck = min(bottleneck, res[prev][curr])\n"
                    "            curr = prev\n"
                    "        curr = sink\n"
                    "        while curr != source:\n"
                    "            prev = parent[curr]\n"
                    "            flow[prev][curr] += bottleneck\n"
                    "            flow[curr][prev] -= bottleneck\n"
                    "            res[prev][curr] -= bottleneck\n"
                    "            res[curr][prev] += bottleneck\n"
                    "            curr = prev\n"
                    "        max_flow += bottleneck\n"
                    "    visited = [False] * n\n"
                    "    q = deque([source])\n"
                    "    visited[source] = True\n"
                    "    while q:\n"
                    "        u = q.popleft()\n"
                    "        for v in range(n):\n"
                    "            if not visited[v] and res[u][v] > 0:\n"
                    "                visited[v] = True\n"
                    "                q.append(v)\n"
                    "    reachable = sorted([i for i in range(n) if visited[i]])\n"
                    "    clean_flow = [[max(0, flow[i][j]) for j in range(n)] for i in range(n)]\n"
                    "    return int(max_flow), clean_flow, reachable\n"
                ),
                "test_suite": (
                    "# --- TIER 1: SMOKE TESTS ---\n"
                    "cap = [\n"
                    "    [0, 16, 13, 0, 0, 0],\n"
                    "    [0, 0, 10, 12, 0, 0],\n"
                    "    [0, 4, 0, 0, 14, 0],\n"
                    "    [0, 0, 9, 0, 0, 20],\n"
                    "    [0, 0, 0, 7, 0, 4],\n"
                    "    [0, 0, 0, 0, 0, 0],\n"
                    "]\n"
                    "max_f, f_mat, cut = max_flow_edmonds_karp(cap, 0, 5)\n"
                    "assert max_f == 23\n"
                    "assert 0 in cut and 5 not in cut\n\n"
                    "# --- TIER 2: BOUNDARY CASES ---\n"
                    "assert max_flow_edmonds_karp([[0]], 0, 0)[0] == 0\n"
                    "assert max_flow_edmonds_karp([[0, 0], [0, 0]], 0, 1)[0] == 0\n\n"
                    "# --- TIER 3: SCALE STRESS TESTS ---\n"
                    "import time\n"
                    "t0 = time.time()\n"
                    "n = 10\n"
                    "grid_cap = [[10 if j == i + 1 else 0 for j in range(n)] for i in range(n)]\n"
                    "res_f, _, _ = max_flow_edmonds_karp(grid_cap, 0, n - 1)\n"
                    "assert time.time() - t0 < 0.5\n"
                    "assert res_f == 10\n\n"
                    "# --- TIER 4: FLOW CONSERVATION & MIN-CUT DUALITY ---\n"
                    "for v in range(1, 5):\n"
                    "    inflow = sum(f_mat[u][v] for u in range(6))\n"
                    "    outflow = sum(f_mat[v][w] for w in range(6))\n"
                    "    assert inflow == outflow, f'Conservation failed at vertex {v}'\n"
                    "cut_set = set(cut)\n"
                    "min_cut_cap = sum(cap[u][v] for u in cut_set for v in range(6) if v not in cut_set)\n"
                    "assert min_cut_cap == max_f, 'Min-cut capacity must equal max flow'\n"
                ),
            },
            "bellman_ford_negative_cycles": {
                "difficulty": "advanced",
                "invariants": [
                    "triangle_inequality",
                    "negative_cycle_certificate_negative_sum",
                    "source_distance_zero",
                    "unreachable_infinity",
                ],
                "prompt": (
                    "Implement `bellman_ford_negative_cycles(n: int, edges: list[tuple[int, int, float]], source: int) -> tuple[bool, dict[int, float], list[int]]` "
                    "finding shortest path distances from source in a directed weighted graph. If a negative weight cycle reachable from source exists, "
                    "return `(True, {}, cycle_vertices)` where `cycle_vertices` is a list of vertices forming the cycle starting and ending at the same node. "
                    "If no negative cycle is reachable, return `(False, distances, [])`."
                ),
                "starter_code": (
                    "def bellman_ford_negative_cycles(\n"
                    "    n: int,\n"
                    "    edges: list[tuple[int, int, float]],\n"
                    "    source: int\n"
                    ") -> tuple[bool, dict[int, float], list[int]]:\n"
                    "    \"\"\"\n"
                    "    Computes shortest paths or extracts exact negative cycle certificate.\n"
                    "    \"\"\"\n"
                    "    # TODO: Implement V-1 relaxations and cycle recovery\n"
                    "    return False, {}, []\n"
                ),
                "reference_solution": (
                    "def bellman_ford_negative_cycles(\n"
                    "    n: int,\n"
                    "    edges: list[tuple[int, int, float]],\n"
                    "    source: int\n"
                    ") -> tuple[bool, dict[int, float], list[int]]:\n"
                    "    dist = [float('inf')] * n\n"
                    "    parent = [-1] * n\n"
                    "    dist[source] = 0.0\n"
                    "    for _ in range(n - 1):\n"
                    "        updated = False\n"
                    "        for u, v, w in edges:\n"
                    "            if dist[u] != float('inf') and dist[u] + w < dist[v] - 1e-12:\n"
                    "                dist[v] = dist[u] + w\n"
                    "                parent[v] = u\n"
                    "                updated = True\n"
                    "        if not updated:\n"
                    "            break\n"
                    "    cycle_node = -1\n"
                    "    for u, v, w in edges:\n"
                    "        if dist[u] != float('inf') and dist[u] + w < dist[v] - 1e-12:\n"
                    "            cycle_node = v\n"
                    "            parent[v] = u\n"
                    "            break\n"
                    "    if cycle_node != -1:\n"
                    "        curr = cycle_node\n"
                    "        for _ in range(n):\n"
                    "            curr = parent[curr]\n"
                    "        cycle = []\n"
                    "        start = curr\n"
                    "        while True:\n"
                    "            cycle.append(curr)\n"
                    "            if curr == start and len(cycle) > 1:\n"
                    "                break\n"
                    "            curr = parent[curr]\n"
                    "        cycle.reverse()\n"
                    "        return True, {}, cycle\n"
                    "    distances = {i: dist[i] for i in range(n)}\n"
                    "    return False, distances, []\n"
                ),
                "test_suite": (
                    "# --- TIER 1: SMOKE TESTS ---\n"
                    "edges = [(0, 1, 1.0), (1, 2, 2.0), (2, 3, -5.0), (3, 1, 1.0)]\n"
                    "has_neg, dists, cycle = bellman_ford_negative_cycles(4, edges, 0)\n"
                    "assert has_neg is True\n"
                    "assert cycle[0] == cycle[-1] and len(cycle) >= 3\n\n"
                    "# --- TIER 2: BOUNDARY CASES (NO CYCLE) ---\n"
                    "safe_edges = [(0, 1, 2.0), (1, 2, 3.0), (0, 2, 6.0)]\n"
                    "has_neg2, dists2, cycle2 = bellman_ford_negative_cycles(3, safe_edges, 0)\n"
                    "assert has_neg2 is False\n"
                    "assert dists2[2] == 5.0\n"
                    "assert cycle2 == []\n\n"
                    "# --- TIER 3: SCALE STRESS TESTS ---\n"
                    "import time\n"
                    "t0 = time.time()\n"
                    "line_edges = [(i, i + 1, 1.0) for i in range(30)]\n"
                    "has_neg3, dists3, _ = bellman_ford_negative_cycles(31, line_edges, 0)\n"
                    "assert time.time() - t0 < 0.5\n"
                    "assert dists3[30] == 30.0\n\n"
                    "# --- TIER 4: NEGATIVE CYCLE INVARIANT ---\n"
                    "edge_weights = {(u, v): w for u, v, w in edges}\n"
                    "cycle_sum = sum(edge_weights[(cycle[i], cycle[i + 1])] for i in range(len(cycle) - 1))\n"
                    "assert cycle_sum < 0.0, 'Extracted cycle must have strictly negative sum'\n"
                ),
            },
        },
        "concurrency": {
            "bounded_ring_buffer": {
                "difficulty": "advanced",
                "invariants": [
                    "fifo_ordering_per_producer",
                    "capacity_ceiling_strict",
                    "lossless_multithread_accounting",
                    "no_duplicate_consumption",
                    "deadlock_freedom",
                ],
                "prompt": (
                    "Implement `ThreadSafeRingBuffer` in Python: a thread-safe, bounded, circular FIFO queue using `threading.Lock` and "
                    "`threading.Condition`. It must provide `push(item, timeout=None) -> bool`, `pop(timeout=None) -> tuple[bool, Any]`, "
                    "`size() -> int`, `is_empty() -> bool`, and `is_full() -> bool`. Must operate safely without race conditions or deadlocks "
                    "under high concurrency with multiple producer and consumer threads."
                ),
                "starter_code": (
                    "from typing import Any, Optional\n\n"
                    "class ThreadSafeRingBuffer:\n"
                    "    def __init__(self, capacity: int):\n"
                    "        # TODO: Initialize internal buffer, synchronization primitives\n"
                    "        pass\n\n"
                    "    def push(self, item: Any, timeout: Optional[float] = None) -> bool:\n"
                    "        # TODO: Implement bounded blocking push with timeout\n"
                    "        return False\n\n"
                    "    def pop(self, timeout: Optional[float] = None) -> tuple[bool, Any]:\n"
                    "        # TODO: Implement bounded blocking pop with timeout\n"
                    "        return False, None\n\n"
                    "    def size(self) -> int:\n"
                    "        return 0\n\n"
                    "    def is_empty(self) -> bool:\n"
                    "        return True\n\n"
                    "    def is_full(self) -> bool:\n"
                    "        return False\n"
                ),
                "reference_solution": (
                    "import threading\n"
                    "import time\n"
                    "from typing import Any, Optional\n\n"
                    "class ThreadSafeRingBuffer:\n"
                    "    def __init__(self, capacity: int):\n"
                    "        if capacity <= 0:\n"
                    "            raise ValueError('Capacity must be positive')\n"
                    "        self.capacity = capacity\n"
                    "        self.buffer = [None] * capacity\n"
                    "        self.head = 0\n"
                    "        self.tail = 0\n"
                    "        self.count = 0\n"
                    "        self.lock = threading.Lock()\n"
                    "        self.not_full = threading.Condition(self.lock)\n"
                    "        self.not_empty = threading.Condition(self.lock)\n\n"
                    "    def push(self, item: Any, timeout: Optional[float] = None) -> bool:\n"
                    "        deadline = time.time() + timeout if timeout is not None else None\n"
                    "        with self.lock:\n"
                    "            while self.count == self.capacity:\n"
                    "                if timeout is not None:\n"
                    "                    remaining = deadline - time.time()\n"
                    "                    if remaining <= 0:\n"
                    "                        return False\n"
                    "                    if not self.not_full.wait(remaining):\n"
                    "                        return False\n"
                    "                else:\n"
                    "                    self.not_full.wait()\n"
                    "            self.buffer[self.tail] = item\n"
                    "            self.tail = (self.tail + 1) % self.capacity\n"
                    "            self.count += 1\n"
                    "            self.not_empty.notify()\n"
                    "            return True\n\n"
                    "    def pop(self, timeout: Optional[float] = None) -> tuple[bool, Any]:\n"
                    "        deadline = time.time() + timeout if timeout is not None else None\n"
                    "        with self.lock:\n"
                    "            while self.count == 0:\n"
                    "                if timeout is not None:\n"
                    "                    remaining = deadline - time.time()\n"
                    "                    if remaining <= 0:\n"
                    "                        return False, None\n"
                    "                    if not self.not_empty.wait(remaining):\n"
                    "                        return False, None\n"
                    "                else:\n"
                    "                    self.not_empty.wait()\n"
                    "            item = self.buffer[self.head]\n"
                    "            self.buffer[self.head] = None\n"
                    "            self.head = (self.head + 1) % self.capacity\n"
                    "            self.count -= 1\n"
                    "            self.not_full.notify()\n"
                    "            return True, item\n\n"
                    "    def size(self) -> int:\n"
                    "        with self.lock:\n"
                    "            return self.count\n\n"
                    "    def is_empty(self) -> bool:\n"
                    "        with self.lock:\n"
                    "            return self.count == 0\n\n"
                    "    def is_full(self) -> bool:\n"
                    "        with self.lock:\n"
                    "            return self.count == self.capacity\n"
                ),
                "test_suite": (
                    "# --- TIER 1: SMOKE TESTS ---\n"
                    "rb = ThreadSafeRingBuffer(3)\n"
                    "assert rb.is_empty() and not rb.is_full()\n"
                    "assert rb.push(10) and rb.push(20) and rb.push(30)\n"
                    "assert rb.is_full() and rb.size() == 3\n"
                    "assert rb.pop()[1] == 10\n"
                    "assert rb.size() == 2\n\n"
                    "# --- TIER 2: BOUNDARY CASES ---\n"
                    "assert not rb.push(40, timeout=0.001) if rb.is_full() else True\n"
                    "empty_b = ThreadSafeRingBuffer(2)\n"
                    "ok, val = empty_b.pop(timeout=0.01)\n"
                    "assert not ok and val is None\n\n"
                    "# --- TIER 3 & 4: SCALE CONCURRENCY & LOSSLESS ACCOUNTING ---\n"
                    "import threading\n"
                    "buf = ThreadSafeRingBuffer(10)\n"
                    "consumed = []\n"
                    "con_lock = threading.Lock()\n"
                    "num_items = 400\n"
                    "def producer(pid):\n"
                    "    for i in range(100):\n"
                    "        buf.push((pid, i))\n"
                    "def consumer():\n"
                    "    for _ in range(100):\n"
                    "        success, item = buf.pop(timeout=2.0)\n"
                    "        if success:\n"
                    "            with con_lock:\n"
                    "                consumed.append(item)\n"
                    "threads = [threading.Thread(target=producer, args=(p,)) for p in range(4)]\n"
                    "threads += [threading.Thread(target=consumer) for _ in range(4)]\n"
                    "for t in threads:\n"
                    "    t.start()\n"
                    "for t in threads:\n"
                    "    t.join(timeout=3.0)\n"
                    "assert len(consumed) == num_items, f'Expected {num_items} items, got {len(consumed)}'\n"
                    "assert buf.size() == 0, 'Buffer must be drained'\n"
                ),
            },
            "thread_safe_memory_pool": {
                "difficulty": "intermediate",
                "invariants": [
                    "block_conservation",
                    "mutual_exclusion_of_blocks",
                    "double_free_protection",
                    "zero_leakage",
                ],
                "prompt": (
                    "Implement `ThreadSafeMemoryPool(block_size: int, pool_capacity: int)` which pre-allocates `pool_capacity` bytearray blocks "
                    "of `block_size` bytes. Methods: `acquire(timeout=None) -> tuple[Optional[int], Optional[bytearray]]`, `release(block_id: int) -> bool`, "
                    "`active_leases_count() -> int`, `available_count() -> int`. Must prevent double-free, track active leases, and preserve total capacity "
                    "conservation across concurrent threads."
                ),
                "starter_code": (
                    "from typing import Optional\n\n"
                    "class ThreadSafeMemoryPool:\n"
                    "    def __init__(self, block_size: int, pool_capacity: int):\n"
                    "        pass\n\n"
                    "    def acquire(self, timeout: Optional[float] = None) -> tuple[Optional[int], Optional[bytearray]]:\n"
                    "        return None, None\n\n"
                    "    def release(self, block_id: int) -> bool:\n"
                    "        return False\n\n"
                    "    def active_leases_count(self) -> int:\n"
                    "        return 0\n\n"
                    "    def available_count(self) -> int:\n"
                    "        return 0\n"
                ),
                "reference_solution": (
                    "import threading\n"
                    "import time\n"
                    "from typing import Optional\n\n"
                    "class ThreadSafeMemoryPool:\n"
                    "    def __init__(self, block_size: int, pool_capacity: int):\n"
                    "        self.block_size = block_size\n"
                    "        self.pool_capacity = pool_capacity\n"
                    "        self.blocks = [bytearray(block_size) for _ in range(pool_capacity)]\n"
                    "        self.available_ids = list(range(pool_capacity))\n"
                    "        self.leased_ids = set()\n"
                    "        self.lock = threading.Lock()\n"
                    "        self.cond = threading.Condition(self.lock)\n\n"
                    "    def acquire(self, timeout: Optional[float] = None) -> tuple[Optional[int], Optional[bytearray]]:\n"
                    "        deadline = time.time() + timeout if timeout is not None else None\n"
                    "        with self.lock:\n"
                    "            while not self.available_ids:\n"
                    "                if timeout is not None:\n"
                    "                    remaining = deadline - time.time()\n"
                    "                    if remaining <= 0:\n"
                    "                        return None, None\n"
                    "                    if not self.cond.wait(remaining):\n"
                    "                        return None, None\n"
                    "                else:\n"
                    "                    self.cond.wait()\n"
                    "            bid = self.available_ids.pop()\n"
                    "            self.leased_ids.add(bid)\n"
                    "            return bid, self.blocks[bid]\n\n"
                    "    def release(self, block_id: int) -> bool:\n"
                    "        with self.lock:\n"
                    "            if block_id not in self.leased_ids:\n"
                    "                return False\n"
                    "            self.leased_ids.remove(block_id)\n"
                    "            self.available_ids.append(block_id)\n"
                    "            self.cond.notify()\n"
                    "            return True\n\n"
                    "    def active_leases_count(self) -> int:\n"
                    "        with self.lock:\n"
                    "            return len(self.leased_ids)\n\n"
                    "    def available_count(self) -> int:\n"
                    "        with self.lock:\n"
                    "            return len(self.available_ids)\n"
                ),
                "test_suite": (
                    "# --- TIER 1: SMOKE TESTS ---\n"
                    "pool = ThreadSafeMemoryPool(64, 4)\n"
                    "assert pool.available_count() == 4 and pool.active_leases_count() == 0\n"
                    "bid, buf = pool.acquire()\n"
                    "assert bid is not None and len(buf) == 64\n"
                    "assert pool.available_count() == 3 and pool.active_leases_count() == 1\n"
                    "assert pool.release(bid) is True\n"
                    "assert pool.available_count() == 4\n\n"
                    "# --- TIER 2: DOUBLE-FREE & BOUNDARY ---\n"
                    "assert pool.release(bid) is False, 'Double-free must return False'\n"
                    "assert pool.release(999) is False, 'Invalid block_id release must return False'\n\n"
                    "# --- TIER 3 & 4: CONSERVATION INVARIANT ---\n"
                    "leases = [pool.acquire()[0] for _ in range(4)]\n"
                    "assert pool.available_count() == 0\n"
                    "assert pool.acquire(timeout=0.01)[0] is None\n"
                    "for b in leases:\n"
                    "    pool.release(b)\n"
                    "assert pool.available_count() + pool.active_leases_count() == pool.pool_capacity\n"
                ),
            },
        },
        "numerical_physics": {
            "symplectic_velocity_verlet": {
                "difficulty": "expert",
                "invariants": [
                    "symplectic_hamiltonian_conservation",
                    "angular_momentum_exact_conservation",
                    "orbital_period_kepler",
                    "time_reversibility",
                ],
                "prompt": (
                    "Implement `symplectic_verlet_orbit(r0: tuple[float, float], v0: tuple[float, float], mu: float, dt: float, steps: int) -> dict[str, Any]` "
                    "numerically integrating a 2D gravitational Kepler orbit using the second-order symplectic Velocity-Verlet algorithm. "
                    "Return a dictionary containing `times`, `positions`, `velocities`, `energies`, and `angular_momenta`. "
                    "Solutions must conserve mechanical energy to within 1e-4 relative drift over complete periods and preserve angular momentum to 1e-10."
                ),
                "starter_code": (
                    "from typing import Any\n\n"
                    "def symplectic_verlet_orbit(\n"
                    "    r0: tuple[float, float],\n"
                    "    v0: tuple[float, float],\n"
                    "    mu: float,\n"
                    "    dt: float,\n"
                    "    steps: int\n"
                    ") -> dict[str, Any]:\n"
                    "    \"\"\"\n"
                    "    Integrates gravitational central force orbits using symplectic Velocity-Verlet.\n"
                    "    \"\"\"\n"
                    "    # TODO: Implement Velocity-Verlet position and velocity updates\n"
                    "    return {}\n"
                ),
                "reference_solution": (
                    "import math\n"
                    "from typing import Any\n\n"
                    "def symplectic_verlet_orbit(\n"
                    "    r0: tuple[float, float],\n"
                    "    v0: tuple[float, float],\n"
                    "    mu: float,\n"
                    "    dt: float,\n"
                    "    steps: int\n"
                    ") -> dict[str, Any]:\n"
                    "    rx, ry = r0\n"
                    "    vx, vy = v0\n"
                    "    times = [0.0]\n"
                    "    positions = [(rx, ry)]\n"
                    "    velocities = [(vx, vy)]\n\n"
                    "    def compute_accel(x: float, y: float) -> tuple[float, float]:\n"
                    "        r = math.sqrt(x * x + y * y)\n"
                    "        if r < 1e-12:\n"
                    "            return 0.0, 0.0\n"
                    "        factor = -mu / (r ** 3)\n"
                    "        return factor * x, factor * y\n\n"
                    "    def compute_energy(x: float, y: float, vx_: float, vy_: float) -> float:\n"
                    "        r = math.sqrt(x * x + y * y)\n"
                    "        kin = 0.5 * (vx_ * vx_ + vy_ * vy_)\n"
                    "        pot = -mu / r if r > 1e-12 else 0.0\n"
                    "        return kin + pot\n\n"
                    "    def compute_ang_momentum(x: float, y: float, vx_: float, vy_: float) -> float:\n"
                    "        return x * vy_ - y * vx_\n\n"
                    "    energies = [compute_energy(rx, ry, vx, vy)]\n"
                    "    ang_momenta = [compute_ang_momentum(rx, ry, vx, vy)]\n"
                    "    ax, ay = compute_accel(rx, ry)\n"
                    "    t = 0.0\n\n"
                    "    for _ in range(steps):\n"
                    "        v_mid_x = vx + 0.5 * ax * dt\n"
                    "        v_mid_y = vy + 0.5 * ay * dt\n"
                    "        rx += v_mid_x * dt\n"
                    "        ry += v_mid_y * dt\n"
                    "        new_ax, new_ay = compute_accel(rx, ry)\n"
                    "        vx = v_mid_x + 0.5 * new_ax * dt\n"
                    "        vy = v_mid_y + 0.5 * new_ay * dt\n"
                    "        ax, ay = new_ax, new_ay\n"
                    "        t += dt\n"
                    "        times.append(t)\n"
                    "        positions.append((rx, ry))\n"
                    "        velocities.append((vx, vy))\n"
                    "        energies.append(compute_energy(rx, ry, vx, vy))\n"
                    "        ang_momenta.append(compute_ang_momentum(rx, ry, vx, vy))\n\n"
                    "    return {\n"
                    "        'times': times,\n"
                    "        'positions': positions,\n"
                    "        'velocities': velocities,\n"
                    "        'energies': energies,\n"
                    "        'angular_momenta': ang_momenta,\n"
                    "    }\n"
                ),
                "test_suite": (
                    "# --- TIER 1: SMOKE TESTS ---\n"
                    "res = symplectic_verlet_orbit((1.0, 0.0), (0.0, 1.0), 1.0, 0.01, 10)\n"
                    "assert isinstance(res, dict) and 'energies' in res\n"
                    "assert len(res['positions']) == 11\n\n"
                    "# --- TIER 2: BOUNDARY CASES ---\n"
                    "res_zero_dt = symplectic_verlet_orbit((1.0, 0.0), (0.0, 1.0), 1.0, 0.0, 5)\n"
                    "assert res_zero_dt['positions'][-1] == (1.0, 0.0)\n\n"
                    "# --- TIER 3: SCALE STRESS TESTS ---\n"
                    "import time\n"
                    "t0 = time.time()\n"
                    "res_long = symplectic_verlet_orbit((1.0, 0.0), (0.0, 1.0), 1.0, 0.005, 1256)\n"
                    "assert time.time() - t0 < 0.5\n\n"
                    "# --- TIER 4: PHYSICAL INVARIANTS & CONSERVATION LAWS ---\n"
                    "e0 = res_long['energies'][0]\n"
                    "l0 = res_long['angular_momenta'][0]\n"
                    "max_e_drift = max(abs(e - e0) / abs(e0) for e in res_long['energies'])\n"
                    "max_l_drift = max(abs(l - l0) / abs(l0) for l in res_long['angular_momenta'])\n"
                    "assert max_e_drift < 1e-4, f'Symplectic energy drift {max_e_drift} exceeded 1e-4'\n"
                    "assert max_l_drift < 1e-10, f'Angular momentum drift {max_l_drift} exceeded 1e-10'\n"
                ),
            },
            "damped_harmonic_oscillator": {
                "difficulty": "advanced",
                "invariants": [
                    "energy_dissipation_monotonicity",
                    "undamped_energy_conservation",
                    "asymptotic_rest_convergence",
                ],
                "prompt": (
                    "Implement `damped_harmonic_oscillator(m: float, k: float, c: float, x0: float, v0: float, dt: float, steps: int) -> dict[str, Any]` "
                    "solving m*x'' + c*x' + k*x = 0 using a 4th-order Runge-Kutta (RK4) integrator. Returns `times`, `positions`, `velocities`, and `energies`. "
                    "For c > 0, mechanical energy must be non-increasing at each step. When c = 0, mechanical energy must be conserved within 1e-5 relative drift."
                ),
                "starter_code": (
                    "from typing import Any\n\n"
                    "def damped_harmonic_oscillator(\n"
                    "    m: float,\n"
                    "    k: float,\n"
                    "    c: float,\n"
                    "    x0: float,\n"
                    "    v0: float,\n"
                    "    dt: float,\n"
                    "    steps: int\n"
                    ") -> dict[str, Any]:\n"
                    "    \"\"\"\n"
                    "    Solves the damped linear oscillator ODE with Runge-Kutta 4th order.\n"
                    "    \"\"\"\n"
                    "    # TODO: Implement RK4 system of first-order ODEs\n"
                    "    return {}\n"
                ),
                "reference_solution": (
                    "from typing import Any\n\n"
                    "def damped_harmonic_oscillator(\n"
                    "    m: float,\n"
                    "    k: float,\n"
                    "    c: float,\n"
                    "    x0: float,\n"
                    "    v0: float,\n"
                    "    dt: float,\n"
                    "    steps: int\n"
                    ") -> dict[str, Any]:\n"
                    "    times = [0.0]\n"
                    "    positions = [x0]\n"
                    "    velocities = [v0]\n"
                    "    energies = [0.5 * m * v0**2 + 0.5 * k * x0**2]\n"
                    "    t = 0.0\n"
                    "    x = x0\n"
                    "    v = v0\n\n"
                    "    def derivatives(curr_x: float, curr_v: float) -> tuple[float, float]:\n"
                    "        dxdt = curr_v\n"
                    "        dvdt = (-k * curr_x - c * curr_v) / m\n"
                    "        return dxdt, dvdt\n\n"
                    "    for _ in range(steps):\n"
                    "        k1_x, k1_v = derivatives(x, v)\n"
                    "        k2_x, k2_v = derivatives(x + 0.5 * dt * k1_x, v + 0.5 * dt * k1_v)\n"
                    "        k3_x, k3_v = derivatives(x + 0.5 * dt * k2_x, v + 0.5 * dt * k2_v)\n"
                    "        k4_x, k4_v = derivatives(x + dt * k3_x, v + dt * k3_v)\n"
                    "        x += (dt / 6.0) * (k1_x + 2.0 * k2_x + 2.0 * k3_x + k4_x)\n"
                    "        v += (dt / 6.0) * (k1_v + 2.0 * k2_v + 2.0 * k3_v + k4_v)\n"
                    "        t += dt\n"
                    "        energy = 0.5 * m * v**2 + 0.5 * k * x**2\n"
                    "        times.append(t)\n"
                    "        positions.append(x)\n"
                    "        velocities.append(v)\n"
                    "        energies.append(energy)\n\n"
                    "    return {\n"
                    "        'times': times,\n"
                    "        'positions': positions,\n"
                    "        'velocities': velocities,\n"
                    "        'energies': energies,\n"
                    "    }\n"
                ),
                "test_suite": (
                    "# --- TIER 1: SMOKE TESTS ---\n"
                    "res = damped_harmonic_oscillator(1.0, 10.0, 0.5, 1.0, 0.0, 0.01, 100)\n"
                    "assert len(res['positions']) == 101\n"
                    "assert res['energies'][-1] < res['energies'][0]\n\n"
                    "# --- TIER 2: BOUNDARY CASES (ZERO VELOCITY, REST) ---\n"
                    "res_rest = damped_harmonic_oscillator(1.0, 10.0, 0.5, 0.0, 0.0, 0.01, 10)\n"
                    "assert all(abs(p) < 1e-12 for p in res_rest['positions'])\n\n"
                    "# --- TIER 3 & 4: ENERGY DISSIPATION MONOTONICITY & UNDAMPED CONSERVATION ---\n"
                    "for i in range(len(res['energies']) - 1):\n"
                    "    assert res['energies'][i + 1] <= res['energies'][i] + 1e-9, 'Energy must dissipate monotonically'\n"
                    "res_undamped = damped_harmonic_oscillator(1.0, 10.0, 0.0, 1.0, 0.0, 0.005, 500)\n"
                    "e0 = res_undamped['energies'][0]\n"
                    "max_drift = max(abs(e - e0) / e0 for e in res_undamped['energies'])\n"
                    "assert max_drift < 1e-5, f'Undamped energy drift {max_drift} exceeded 1e-5'\n"
                ),
            },
        },
    }

    # Backward compatibility with legacy templates
    LEGACY_TEMPLATES = {
        "physics": {
            "python": {
                "prompt": "Implement a function `compute_kinetic_energy(m: float, v: float) -> float` calculating classical kinetic energy E = 0.5 * m * v^2 in Joules.",
                "starter_code": "def compute_kinetic_energy(m: float, v: float) -> float:\n    # TODO: implement\n    pass\n",
                "test_suite": "assert abs(compute_kinetic_energy(2.0, 3.0) - 9.0) < 1e-6\nassert abs(compute_kinetic_energy(0.0, 10.0) - 0.0) < 1e-6\n",
                "reference_solution": "def compute_kinetic_energy(m: float, v: float) -> float:\n    return 0.5 * m * v**2\n",
                "difficulty": "intermediate",
                "invariants": ["energy_positivity", "quadratic_velocity_scaling"],
            },
            "rust": {
                "prompt": "Implement a function `pub fn orbital_velocity(m: f64, r: f64) -> f64` calculating circular orbit speed v = sqrt(G*M/r).",
                "starter_code": "pub fn orbital_velocity(m: f64, r: f64) -> f64 {\n    // TODO: implement\n    0.0\n}\n",
                "test_suite": "fn main() { assert!((orbital_velocity(5.972e24, 6.771e6) - 7672.0).abs() < 100.0); }\n",
                "reference_solution": "pub fn orbital_velocity(m: f64, r: f64) -> f64 {\n    let g = 6.67430e-11;\n    (g * m / r).sqrt()\n}\n",
                "difficulty": "intermediate",
                "invariants": ["orbital_speed_scaling"],
            },
        },
        "systems": {
            "cpp": {
                "prompt": "Implement a simple ring buffer struct in C++ with push and pop methods.",
                "starter_code": "struct RingBuffer {\n    // TODO: implement\n};\n",
                "test_suite": "int main() { return 0; }\n",
                "reference_solution": "struct RingBuffer { int size; };\n",
                "difficulty": "intermediate",
                "invariants": ["bounded_capacity"],
            },
            "python": {
                "prompt": "Implement a thread-safe atomic counter simulation.",
                "starter_code": "class AtomicCounter:\n    pass\n",
                "test_suite": "c = AtomicCounter()\nassert c is not None\n",
                "reference_solution": "class AtomicCounter:\n    def __init__(self):\n        self.val = 0\n",
                "difficulty": "intermediate",
                "invariants": ["thread_safety"],
            },
        },
    }

    def generate_challenge(
        self,
        domain: str = "physics",
        language: str = "python",
        difficulty: str = "intermediate",
        challenge_key: Optional[str] = None,
    ) -> SyntheticChallenge:
        """
        Generates a synthetic challenge tailored to a domain and language.
        Supports both the new high-difficulty domains and legacy templates.
        """
        lang = language.lower()
        dom = domain.lower()
        canonical_domain = self.DOMAIN_ALIASES.get(dom, dom)

        # 1. Check expanded templates
        if canonical_domain in self.CHALLENGE_TEMPLATES and lang == "python":
            domain_pool = self.CHALLENGE_TEMPLATES[canonical_domain]
            if challenge_key and challenge_key in domain_pool:
                tmpl = domain_pool[challenge_key]
            else:
                # Filter by difficulty if possible, else pick first
                matching = [k for k, v in domain_pool.items() if v.get("difficulty") == difficulty]
                selected_key = matching[0] if matching else list(domain_pool.keys())[0]
                tmpl = domain_pool[selected_key]

            challenge_id = f"syn_{uuid.uuid4().hex[:8]}"
            return SyntheticChallenge(
                challenge_id=challenge_id,
                domain=canonical_domain,
                language=lang,
                prompt=tmpl["prompt"],
                starter_code=tmpl["starter_code"],
                test_suite=tmpl["test_suite"],
                difficulty=tmpl.get("difficulty", difficulty),
                reference_solution=tmpl.get("reference_solution", ""),
                invariants=tmpl.get("invariants", []),
            )

        # 2. Check legacy templates
        legacy_dom = dom if dom in self.LEGACY_TEMPLATES else "physics"
        lang_dict = self.LEGACY_TEMPLATES.get(legacy_dom, self.LEGACY_TEMPLATES["physics"])
        lang_key = lang if lang in lang_dict else ("python" if "python" in lang_dict else list(lang_dict.keys())[0])

        tmpl = lang_dict[lang_key]
        challenge_id = f"syn_{uuid.uuid4().hex[:8]}"

        return SyntheticChallenge(
            challenge_id=challenge_id,
            domain=legacy_dom,
            language=lang_key,
            prompt=tmpl["prompt"],
            starter_code=tmpl["starter_code"],
            test_suite=tmpl["test_suite"],
            difficulty=tmpl.get("difficulty", "intermediate"),
            reference_solution=tmpl.get("reference_solution", ""),
            invariants=tmpl.get("invariants", []),
        )

    def verify_challenge_solution(
        self,
        solution_code: str,
        test_code: str,
        language: str = "python",
    ) -> Dict[str, Any]:
        """
        Executes candidate code and verification tests safely inside the security sandbox.
        Delegates to src.sandbox.win32_job when available, with fallback to verify_polyglot.
        """
        try:
            from src.sandbox.win32_job import execute_sandboxed_code
            res = execute_sandboxed_code(
                source_code=solution_code,
                test_suite=test_code,
                language=language,
                timeout=5.0,
                max_memory_mb=256,
            )
            return {
                "success": res.success,
                "sandboxed": True,
                "runtime": "win32-job",
                "output": res.stdout,
                "error": res.stderr or res.error_message,
                "wall_time_ms": res.duration_s * 1000.0,
                "peak_memory_bytes": res.peak_memory_bytes,
            }
        except ImportError:
            from scripts.verify_polyglot import execute_code_and_tests
            res_legacy = execute_code_and_tests(
                source_code=solution_code,
                test_suite=test_code,
                language=language,
            )
            return {
                "success": res_legacy.passed,
                "sandboxed": True,
                "runtime": res_legacy.runtime,
                "output": res_legacy.output,
                "error": res_legacy.error,
                "wall_time_ms": res_legacy.elapsed_seconds * 1000.0,
            }
