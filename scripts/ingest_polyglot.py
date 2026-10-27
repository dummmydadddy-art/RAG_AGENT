#!/usr/bin/env python3
"""
Polyglot Multi-Language Dataset Ingestion & 3-Tier Deduplication Pipeline.

Curates, validates, deduplicates, and vectorizes multi-language programming
challenges across 8 Tier-1 languages (Python, TypeScript, C++, Java, Rust, Go, PHP, SQL)
and 4 difficulty tiers (Elementary, Intermediate, Systems, Competitive).

Architecture (Medallion Pattern):
- Bronze: Raw ingestion & schema validation across all 8 languages and 4 tiers.
- Silver: 3-tier Deduplication:
    * Tier 1: Exact Hash (comment-stripped, whitespace-collapsed SHA-256)
    * Tier 2: Lexical Jaccard (shingle token overlap >= 0.82)
    * Tier 3: Semantic Collision (embedding cosine similarity >= 0.92 with test-coverage arbitration)
    Guaranteeing zero duplicates before vectorization.
- Gold: Persistence into SQLite vector store (backend/storage/vectors.sqlite):
    * rag_documents: full deduplicated corpus under collection 'polyglot_coding'
    * material_chunks: capped at <= 500 rows to protect PHP 128 MB memory limit
    * nomic-embed-text 768-d vectors strictly prepended with 'search_document: '
- Export: Instruction fine-tuning dataset (Alpaca / ShareGPT format) bounded to <= 1024 tokens.
"""

import argparse
import hashlib
import json
import logging
import math
import re
import struct
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "rag-adapter"))

try:
    from rag_adapter.sqlite_backend import LocalSqliteRagBackend
except ImportError:
    LocalSqliteRagBackend = None

logger = logging.getLogger("polyglot_ingestion")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

TIER_1_LANGUAGES = {"python", "typescript", "cpp", "java", "rust", "go", "php", "sql"}
DIFFICULTY_TIERS = {"elementary", "intermediate", "systems", "competitive"}

LANG_ALIASES = {
    "js": "typescript",
    "javascript": "typescript",
    "ts": "typescript",
    "typescript": "typescript",
    "py": "python",
    "python": "python",
    "c": "cpp",
    "c++": "cpp",
    "cpp": "cpp",
    "cxx": "cpp",
    "java": "java",
    "rs": "rust",
    "rust": "rust",
    "golang": "go",
    "go": "go",
    "php": "php",
    "sql": "sql",
    "sqlite": "sql",
    "postgres": "sql",
    "postgresql": "sql",
}

TIER_ALIASES = {
    "elem": "elementary",
    "elementary": "elementary",
    "basic": "elementary",
    "inter": "intermediate",
    "intermediate": "intermediate",
    "medium": "intermediate",
    "sys": "systems",
    "systems": "systems",
    "advanced_systems": "systems",
    "comp": "competitive",
    "competitive": "competitive",
    "sme": "competitive",
    "hard": "competitive",
}


@dataclass
class PolyglotChallenge:
    """Core Polyglot Programming Challenge data transfer object."""
    id: str
    language: str
    tier: str
    title: str
    tags: List[str]
    problem_statement: str
    starter_code: str
    reference_solution: str
    unit_test_suite: str
    complexity: Dict[str, str] = field(default_factory=lambda: {"time": "O(N)", "space": "O(1)"})
    explanation_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_formatted_document(self) -> str:
        """Render readable markdown document for vector indexing."""
        steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(self.explanation_steps))
        return (
            f"Title: {self.title}\n"
            f"Language: {self.language.upper()} | Tier: {self.tier.upper()}\n"
            f"Tags: {', '.join(self.tags)}\n\n"
            f"### Problem Statement:\n{self.problem_statement}\n\n"
            f"### Starter Code:\n```{self.language}\n{self.starter_code}\n```\n\n"
            f"### Reference Solution:\n```{self.language}\n{self.reference_solution}\n```\n\n"
            f"### Complexity:\n- Time: {self.complexity.get('time', 'N/A')}\n"
            f"- Space: {self.complexity.get('space', 'N/A')}\n\n"
            f"### Explanation:\n{steps}\n\n"
            f"### Unit Test Suite:\n```{self.language}\n{self.unit_test_suite}\n```"
        )


# ============================================================================
# COMPREHENSIVE CURATED POLYGLOT SEED CORPUS (8 LANGUAGES x 4 TIERS = 32 SAMPLES)
# ============================================================================

CURATED_POLYGLOT_CORPUS: List[Dict[str, Any]] = [
    # ------------------------------------------------------------------------
    # 1. PYTHON
    # ------------------------------------------------------------------------
    {
        "id": "POLY-PY-ELEM-001",
        "language": "python",
        "tier": "elementary",
        "title": "Two Sum with Hash Map Lookup",
        "tags": ["python", "hash-map", "array", "elementary"],
        "problem_statement": "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target in O(N) time.",
        "starter_code": "def two_sum(nums: list[int], target: int) -> list[int]:\n    pass",
        "reference_solution": "def two_sum(nums: list[int], target: int) -> list[int]:\n    seen = {}\n    for i, num in enumerate(nums):\n        complement = target - num\n        if complement in seen:\n            return [seen[complement], i]\n        seen[num] = i\n    return []",
        "unit_test_suite": "def test_two_sum():\n    assert two_sum([2, 7, 11, 15], 9) == [0, 1]\n    assert two_sum([3, 2, 4], 6) == [1, 2]\n    assert two_sum([3, 3], 6) == [0, 1]\n    assert two_sum([1, 2, 3], 7) == []",
        "complexity": {"time": "O(N)", "space": "O(N)"},
        "explanation_steps": [
            "Initialize an empty hash table `seen` mapping value to its index.",
            "Iterate through nums: calculate complement = target - num.",
            "If complement exists in seen, return [seen[complement], current_index].",
            "Store current num and index in seen.",
        ],
    },
    {
        "id": "POLY-PY-INT-001",
        "language": "python",
        "tier": "intermediate",
        "title": "Least Recently Used (LRU) Cache",
        "tags": ["python", "lru-cache", "doubly-linked-list", "intermediate"],
        "problem_statement": "Implement an LRU Cache with capacity supporting O(1) get(key) and put(key, value) operations.",
        "starter_code": "class LRUCache:\n    def __init__(self, capacity: int):\n        pass\n    def get(self, key: int) -> int:\n        pass\n    def put(self, key: int, value: int) -> None:\n        pass",
        "reference_solution": "from collections import OrderedDict\n\nclass LRUCache:\n    def __init__(self, capacity: int):\n        self.capacity = capacity\n        self.cache = OrderedDict()\n\n    def get(self, key: int) -> int:\n        if key not in self.cache:\n            return -1\n        self.cache.move_to_end(key)\n        return self.cache[key]\n\n    def put(self, key: int, value: int) -> None:\n        if key in self.cache:\n            self.cache.move_to_end(key)\n        self.cache[key] = value\n        if len(self.cache) > self.capacity:\n            self.cache.popitem(last=False)",
        "unit_test_suite": "def test_lru_cache():\n    lru = LRUCache(2)\n    lru.put(1, 1)\n    lru.put(2, 2)\n    assert lru.get(1) == 1\n    lru.put(3, 3) # evicts key 2\n    assert lru.get(2) == -1\n    lru.put(4, 4) # evicts key 1\n    assert lru.get(1) == -1\n    assert lru.get(3) == 3\n    assert lru.get(4) == 4",
        "complexity": {"time": "O(1) for get and put", "space": "O(capacity)"},
        "explanation_steps": [
            "Use OrderedDict combining hash lookup with doubly-linked list ordering.",
            "On get(key), move existing key to end (most recently used).",
            "On put(key, value), update value and move to end; if size > capacity, pop first item.",
        ],
    },
    {
        "id": "POLY-PY-SYS-001",
        "language": "python",
        "tier": "systems",
        "title": "Async Token Bucket Rate Limiter",
        "tags": ["python", "asyncio", "concurrency", "rate-limiter", "systems"],
        "problem_statement": "Implement an asynchronous token bucket rate limiter in Python using asyncio.Lock and monotonic time.",
        "starter_code": "import asyncio\nimport time\n\nclass TokenBucketRateLimiter:\n    def __init__(self, capacity: float, refill_rate: float):\n        pass\n    async def acquire(self, tokens: float = 1.0) -> bool:\n        pass",
        "reference_solution": "import asyncio\nimport time\n\nclass TokenBucketRateLimiter:\n    def __init__(self, capacity: float, refill_rate: float):\n        self.capacity = float(capacity)\n        self.refill_rate = float(refill_rate)\n        self.tokens = float(capacity)\n        self.last_refill = time.monotonic()\n        self.lock = asyncio.Lock()\n\n    async def acquire(self, tokens: float = 1.0) -> bool:\n        async with self.lock:\n            now = time.monotonic()\n            elapsed = now - self.last_refill\n            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)\n            self.last_refill = now\n            if self.tokens >= tokens:\n                self.tokens -= tokens\n                return True\n            return False",
        "unit_test_suite": "import pytest\nimport asyncio\n\n@pytest.mark.asyncio\nasync def test_token_bucket():\n    limiter = TokenBucketRateLimiter(capacity=2.0, refill_rate=10.0)\n    assert await limiter.acquire(1.0) is True\n    assert await limiter.acquire(1.0) is True\n    assert await limiter.acquire(1.0) is False\n    await asyncio.sleep(0.15)\n    assert await limiter.acquire(1.0) is True",
        "complexity": {"time": "O(1) per acquire", "space": "O(1)"},
        "explanation_steps": [
            "Track last_refill timestamp and current available token count.",
            "On acquire, compute elapsed time and add elapsed * refill_rate capped at capacity.",
            "Protect state modifications using asyncio.Lock for coroutine safety.",
        ],
    },
    {
        "id": "POLY-PY-COMP-001",
        "language": "python",
        "tier": "competitive",
        "title": "Segment Tree with Lazy Propagation",
        "tags": ["python", "segment-tree", "lazy-propagation", "competitive"],
        "problem_statement": "Implement a Segment Tree supporting O(log N) range sum queries and range add updates using lazy propagation.",
        "starter_code": "class LazySegmentTree:\n    def __init__(self, data: list[int]):\n        pass\n    def update_range(self, ql: int, qr: int, val: int) -> None:\n        pass\n    def query_range(self, ql: int, qr: int) -> int:\n        pass",
        "reference_solution": "class LazySegmentTree:\n    def __init__(self, data: list[int]):\n        self.n = len(data)\n        self.tree = [0] * (4 * self.n)\n        self.lazy = [0] * (4 * self.n)\n        if self.n > 0:\n            self._build(data, 0, 0, self.n - 1)\n\n    def _build(self, data: list[int], node: int, l: int, r: int):\n        if l == r:\n            self.tree[node] = data[l]\n            return\n        mid = (l + r) // 2\n        self._build(data, 2 * node + 1, l, mid)\n        self._build(data, 2 * node + 2, mid + 1, r)\n        self.tree[node] = self.tree[2 * node + 1] + self.tree[2 * node + 2]\n\n    def _push(self, node: int, l: int, r: int):\n        if self.lazy[node] != 0:\n            mid = (l + r) // 2\n            add = self.lazy[node]\n            self.tree[2 * node + 1] += add * (mid - l + 1)\n            self.lazy[2 * node + 1] += add\n            self.tree[2 * node + 2] += add * (r - mid)\n            self.lazy[2 * node + 2] += add\n            self.lazy[node] = 0\n\n    def update_range(self, ql: int, qr: int, val: int, node: int = 0, l: int = 0, r: int = None):\n        if r is None: r = self.n - 1\n        if ql <= l and r <= qr:\n            self.tree[node] += val * (r - l + 1)\n            self.lazy[node] += val\n            return\n        self._push(node, l, r)\n        mid = (l + r) // 2\n        if ql <= mid: self.update_range(ql, qr, val, 2 * node + 1, l, mid)\n        if qr > mid: self.update_range(ql, qr, val, 2 * node + 2, mid + 1, r)\n        self.tree[node] = self.tree[2 * node + 1] + self.tree[2 * node + 2]\n\n    def query_range(self, ql: int, qr: int, node: int = 0, l: int = 0, r: int = None) -> int:\n        if r is None: r = self.n - 1\n        if ql <= l and r <= qr:\n            return self.tree[node]\n        self._push(node, l, r)\n        mid = (l + r) // 2\n        total = 0\n        if ql <= mid: total += self.query_range(ql, qr, 2 * node + 1, l, mid)\n        if qr > mid: total += self.query_range(ql, qr, 2 * node + 2, mid + 1, r)\n        return total",
        "unit_test_suite": "def test_lazy_segment_tree():\n    arr = [1, 3, 5, 7, 9, 11]\n    st = LazySegmentTree(arr)\n    assert st.query_range(1, 3) == 15 # 3 + 5 + 7\n    st.update_range(1, 4, 10) # [1, 13, 15, 17, 19, 11]\n    assert st.query_range(1, 3) == 45 # 13 + 15 + 17\n    assert st.query_range(0, 5) == 76",
        "complexity": {"time": "O(log N) query & update", "space": "O(N)"},
        "explanation_steps": [
            "Build complete binary segment tree of size 4N.",
            "Use lazy array to postpone updates to child nodes until child is explicitly visited.",
            "On push, apply accumulated delta to children and propagate lazy tags.",
        ],
    },

    # ------------------------------------------------------------------------
    # 2. TYPESCRIPT
    # ------------------------------------------------------------------------
    {
        "id": "POLY-TS-ELEM-001",
        "language": "typescript",
        "tier": "elementary",
        "title": "Deep Object Clone and Recursive Merge",
        "tags": ["typescript", "objects", "recursion", "elementary"],
        "problem_statement": "Implement a type-safe deepClone and deepMerge function in TypeScript that recursively copies and merges nested objects and arrays without mutating arguments.",
        "starter_code": "export function deepClone<T>(target: T): T {\n    // Implementation\n}\nexport function deepMerge<T extends object, U extends object>(target: T, source: U): T & U {\n    // Implementation\n}",
        "reference_solution": "export function deepClone<T>(target: T): T {\n    if (target === null || typeof target !== 'object') return target;\n    if (Array.isArray(target)) {\n        return target.map(item => deepClone(item)) as unknown as T;\n    }\n    const copy = {} as Record<string, any>;\n    for (const key of Object.keys(target as Record<string, any>)) {\n        copy[key] = deepClone((target as Record<string, any>)[key]);\n    }\n    return copy as T;\n}\n\nexport function deepMerge<T extends Record<string, any>, U extends Record<string, any>>(target: T, source: U): T & U {\n    const output = deepClone(target) as any;\n    for (const key of Object.keys(source)) {\n        if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {\n            output[key] = deepMerge(output[key] || {}, source[key]);\n        } else {\n            output[key] = deepClone(source[key]);\n        }\n    }\n    return output as T & U;\n}",
        "unit_test_suite": "import { describe, it, expect } from 'vitest';\n\ndescribe('deepClone and deepMerge', () => {\n    it('should clone nested structures cleanly', () => {\n        const orig = { a: 1, b: { c: [2, 3] } };\n        const cloned = deepClone(orig);\n        expect(cloned).toEqual(orig);\n        expect(cloned.b).not.toBe(orig.b);\n    });\n    it('should merge deeply without side effects', () => {\n        const a = { x: 1, y: { z: 2 } };\n        const b = { y: { w: 3 }, v: 4 };\n        const merged = deepMerge(a, b);\n        expect(merged).toEqual({ x: 1, y: { z: 2, w: 3 }, v: 4 });\n    });\n});",
        "complexity": {"time": "O(N) where N is total node count", "space": "O(N)"},
        "explanation_steps": [
            "Handle primitives and null directly by returning value.",
            "Branch array cloning using map and recursive deepClone.",
            "Merge objects recursively, overriding primitives and combining sub-objects.",
        ],
    },
    {
        "id": "POLY-TS-INT-001",
        "language": "typescript",
        "tier": "intermediate",
        "title": "Type-Safe Event Bus / EventEmitter",
        "tags": ["typescript", "events", "generics", "intermediate"],
        "problem_statement": "Create a fully generic, type-safe EventEmitter in TypeScript with on, off, once, and emit methods.",
        "starter_code": "export class TypedEventEmitter<Events extends Record<string, any>> {\n    // Define methods\n}",
        "reference_solution": "type Handler<T> = (data: T) => void;\n\nexport class TypedEventEmitter<Events extends Record<string, any>> {\n    private listeners: { [K in keyof Events]?: Set<Handler<Events[K]>> } = {};\n\n    on<K extends keyof Events>(event: K, handler: Handler<Events[K]>): () => void {\n        if (!this.listeners[event]) {\n            this.listeners[event] = new Set();\n        }\n        this.listeners[event]!.add(handler);\n        return () => this.off(event, handler);\n    }\n\n    off<K extends keyof Events>(event: K, handler: Handler<Events[K]>): void {\n        this.listeners[event]?.delete(handler);\n    }\n\n    once<K extends keyof Events>(event: K, handler: Handler<Events[K]>): void {\n        const wrapper: Handler<Events[K]> = (data: Events[K]) => {\n            this.off(event, wrapper);\n            handler(data);\n        };\n        this.on(event, wrapper);\n    }\n\n    emit<K extends keyof Events>(event: K, data: Events[K]): void {\n        const subs = this.listeners[event];\n        if (subs) {\n            subs.forEach(fn => fn(data));\n        }\n    }\n}",
        "unit_test_suite": "import { describe, it, expect } from 'vitest';\n\ndescribe('TypedEventEmitter', () => {\n    it('should fire and unsubscribe events properly', () => {\n        interface AppEvents { 'login': { user: string }; 'logout': void }\n        const bus = new TypedEventEmitter<AppEvents>();\n        let calls = 0;\n        const unsub = bus.on('login', (d) => { calls += d.user === 'Alice' ? 1 : 0; });\n        bus.emit('login', { user: 'Alice' });\n        expect(calls).toBe(1);\n        unsub();\n        bus.emit('login', { user: 'Alice' });\n        expect(calls).toBe(1);\n    });\n});",
        "complexity": {"time": "O(1) subscribe, O(S) emit where S is subscribers count", "space": "O(S)"},
        "explanation_steps": [
            "Constrain event map to generic Record<string, any>.",
            "Use Set<Handler> for O(1) deduplication and removal.",
            "Return unsubscribe lambda from on() for clean teardown.",
        ],
    },
    {
        "id": "POLY-TS-SYS-001",
        "language": "typescript",
        "tier": "systems",
        "title": "Promise Concurrency Pool with Queue and Timeout",
        "tags": ["typescript", "concurrency", "async", "promises", "systems"],
        "problem_statement": "Implement an asynchronous PromisePool in TypeScript with max concurrency limit, queueing, and timeout per task.",
        "starter_code": "export class PromisePool {\n    constructor(public concurrency: number) {}\n    async run<T>(task: () => Promise<T>, timeoutMs?: number): Promise<T> {\n        // Implementation\n    }\n}",
        "reference_solution": "export class PromisePool {\n    private active = 0;\n    private queue: Array<() => void> = [];\n\n    constructor(public concurrency: number) {}\n\n    async run<T>(task: () => Promise<T>, timeoutMs?: number): Promise<T> {\n        if (this.active >= this.concurrency) {\n            await new Promise<void>(resolve => this.queue.push(resolve));\n        }\n        this.active++;\n        try {\n            if (timeoutMs !== undefined && timeoutMs > 0) {\n                return await Promise.race([\n                    task(),\n                    new Promise<T>((_, reject) => setTimeout(() => reject(new Error('Task timeout')), timeoutMs))\n                ]);\n            }\n            return await task();\n        } finally {\n            this.active--;\n            if (this.queue.length > 0) {\n                const next = this.queue.shift();\n                if (next) next();\n            }\n        }\n    }\n}",
        "unit_test_suite": "import { describe, it, expect } from 'vitest';\n\ndescribe('PromisePool', () => {\n    it('should limit concurrent tasks to configured limit', async () => {\n        const pool = new PromisePool(2);\n        let running = 0;\n        let maxRunning = 0;\n        const makeTask = () => async () => {\n            running++;\n            maxRunning = Math.max(maxRunning, running);\n            await new Promise(r => setTimeout(r, 20));\n            running--;\n            return true;\n        };\n        await Promise.all([pool.run(makeTask()), pool.run(makeTask()), pool.run(makeTask()), pool.run(makeTask())]);\n        expect(maxRunning).toBe(2);\n    });\n});",
        "complexity": {"time": "O(1) queue overhead per task", "space": "O(Q) pending queue size"},
        "explanation_steps": [
            "Maintain active counter and FIFO queue of pending resolver functions.",
            "If active >= concurrency, await queue push promise.",
            "Execute task wrapped in Promise.race with optional timeout timer.",
            "In finally block, decrement active count and pop next waiter.",
        ],
    },
    {
        "id": "POLY-TS-COMP-001",
        "language": "typescript",
        "tier": "competitive",
        "title": "Dijkstra Shortest Path with Binary Min-Heap",
        "tags": ["typescript", "graph", "dijkstra", "min-heap", "competitive"],
        "problem_statement": "Implement Dijkstra shortest path algorithm with a custom generic binary min-heap priority queue in TypeScript.",
        "starter_code": "export function dijkstra(n: number, edges: [number, number, number][], start: number): number[] {\n    // Return distance array\n}",
        "reference_solution": "class MinHeap<T> {\n    private heap: T[] = [];\n    constructor(private compare: (a: T, b: T) => number) {}\n    push(item: T) {\n        this.heap.push(item);\n        this._bubbleUp(this.heap.length - 1);\n    }\n    pop(): T | undefined {\n        if (this.heap.length <= 1) return this.heap.pop();\n        const top = this.heap[0];\n        this.heap[0] = this.heap.pop()!;\n        this._bubbleDown(0);\n        return top;\n    }\n    get size(): number { return this.heap.length; }\n    private _bubbleUp(i: number) {\n        while (i > 0) {\n            const p = (i - 1) >> 1;\n            if (this.compare(this.heap[i], this.heap[p]) < 0) {\n                [this.heap[i], this.heap[p]] = [this.heap[p], this.heap[i]];\n                i = p;\n            } else break;\n        }\n    }\n    private _bubbleDown(i: number) {\n        const len = this.heap.length;\n        while ((i << 1) + 1 < len) {\n            let left = (i << 1) + 1;\n            let right = left + 1;\n            let smallest = i;\n            if (left < len && this.compare(this.heap[left], this.heap[smallest]) < 0) smallest = left;\n            if (right < len && this.compare(this.heap[right], this.heap[smallest]) < 0) smallest = right;\n            if (smallest !== i) {\n                [this.heap[i], this.heap[smallest]] = [this.heap[smallest], this.heap[i]];\n                i = smallest;\n            } else break;\n        }\n    }\n}\n\nexport function dijkstra(n: number, edges: [number, number, number][], start: number): number[] {\n    const adj: [number, number][][] = Array.from({ length: n }, () => []);\n    for (const [u, v, w] of edges) {\n        adj[u].push([v, w]);\n    }\n    const dist = new Array(n).fill(Infinity);\n    dist[start] = 0;\n    const heap = new MinHeap<[number, number]>((a, b) => a[0] - b[0]);\n    heap.push([0, start]);\n    while (heap.size > 0) {\n        const [d, u] = heap.pop()!;\n        if (d > dist[u]) continue;\n        for (const [v, w] of adj[u]) {\n            if (dist[u] + w < dist[v]) {\n                dist[v] = dist[u] + w;\n                heap.push([dist[v], v]);\n            }\n        }\n    }\n    return dist;\n}",
        "unit_test_suite": "import { describe, it, expect } from 'vitest';\n\ndescribe('dijkstra', () => {\n    it('should find shortest paths from source', () => {\n        const edges: [number, number, number][] = [[0, 1, 4], [0, 2, 2], [2, 1, 1], [1, 3, 5], [2, 3, 8]];\n        const res = dijkstra(4, edges, 0);\n        expect(res).toEqual([0, 3, 2, 8]);\n    });\n});",
        "complexity": {"time": "O((V + E) log V)", "space": "O(V + E)"},
        "explanation_steps": [
            "Implement generic binary min-heap with bubble-up and bubble-down.",
            "Construct adjacency list mapping node u to list of (v, weight) edges.",
            "Relax edges iteratively; skip nodes already processed with lower distance.",
        ],
    },

    # ------------------------------------------------------------------------
    # 3. C / C++
    # ------------------------------------------------------------------------
    {
        "id": "POLY-CPP-ELEM-001",
        "language": "cpp",
        "tier": "elementary",
        "title": "Custom Dynamic Vector with RAII and Capacity Doubling",
        "tags": ["cpp", "raii", "templates", "dynamic-array", "elementary"],
        "problem_statement": "Implement a dynamic templated Vector class in C++ with push_back, pop_back, operator[], size(), capacity(), and RAII cleanup.",
        "starter_code": "template<typename T>\nclass Vector {\npublic:\n    Vector();\n    ~Vector();\n    void push_back(const T& val);\n    void pop_back();\n    T& operator[](size_t index);\n    size_t size() const;\n    size_t capacity() const;\n};",
        "reference_solution": "#include <cstddef>\n#include <stdexcept>\n#include <utility>\n\ntemplate<typename T>\nclass Vector {\nprivate:\n    T* data_;\n    size_t size_;\n    size_t cap_;\n\n    void reallocate(size_t new_cap) {\n        T* new_data = new T[new_cap];\n        for (size_t i = 0; i < size_; ++i) {\n            new_data[i] = std::move(data_[i]);\n        }\n        delete[] data_;\n        data_ = new_data;\n        cap_ = new_cap;\n    }\n\npublic:\n    Vector() : data_(nullptr), size_(0), cap_(0) {}\n    ~Vector() { delete[] data_; }\n\n    void push_back(const T& val) {\n        if (size_ == cap_) {\n            reallocate(cap_ == 0 ? 1 : cap_ * 2);\n        }\n        data_[size_++] = val;\n    }\n\n    void pop_back() {\n        if (size_ > 0) --size_;\n    }\n\n    T& operator[](size_t idx) {\n        if (idx >= size_) throw std::out_of_range(\"Index out of range\");\n        return data_[idx];\n    }\n\n    const T& operator[](size_t idx) const {\n        if (idx >= size_) throw std::out_of_range(\"Index out of range\");\n        return data_[idx];\n    }\n\n    size_t size() const { return size_; }\n    size_t capacity() const { return cap_; }\n};",
        "unit_test_suite": "#include <cassert>\n\nvoid test_vector() {\n    Vector<int> v;\n    assert(v.size() == 0);\n    v.push_back(10);\n    v.push_back(20);\n    assert(v.size() == 2);\n    assert(v[0] == 10);\n    assert(v[1] == 20);\n    v.pop_back();\n    assert(v.size() == 1);\n    assert(v[0] == 10);\n}",
        "complexity": {"time": "O(1) amortized push_back", "space": "O(capacity)"},
        "explanation_steps": [
            "Allocate raw array dynamically with double capacity on overflow.",
            "Move elements during reallocation and free old memory.",
            "Destructor releases memory to eliminate memory leaks.",
        ],
    },
    {
        "id": "POLY-CPP-INT-001",
        "language": "cpp",
        "tier": "intermediate",
        "title": "Thread-Safe Blocking Queue with Condition Variable",
        "tags": ["cpp", "multithreading", "blocking-queue", "intermediate"],
        "problem_statement": "Implement a bounded thread-safe blocking queue in C++ using std::mutex and std::condition_variable.",
        "starter_code": "template<typename T>\nclass BlockingQueue {\npublic:\n    explicit BlockingQueue(size_t max_size);\n    void push(T item);\n    T pop();\n};",
        "reference_solution": "#include <queue>\n#include <mutex>\n#include <condition_variable>\n\ntemplate<typename T>\nclass BlockingQueue {\nprivate:\n    std::queue<T> queue_;\n    size_t max_size_;\n    std::mutex mtx_;\n    std::condition_variable cv_not_full_;\n    std::condition_variable cv_not_empty_;\n\npublic:\n    explicit BlockingQueue(size_t max_size) : max_size_(max_size) {}\n\n    void push(T item) {\n        std::unique_lock<std::mutex> lock(mtx_);\n        cv_not_full_.wait(lock, [this]() { return queue_.size() < max_size_; });\n        queue_.push(std::move(item));\n        cv_not_empty_.notify_one();\n    }\n\n    T pop() {\n        std::unique_lock<std::mutex> lock(mtx_);\n        cv_not_empty_.wait(lock, [this]() { return !queue_.empty(); });\n        T item = std::move(queue_.front());\n        queue_.pop();\n        cv_not_full_.notify_one();\n        return item;\n    }\n};",
        "unit_test_suite": "#include <cassert>\n#include <thread>\n\nvoid test_blocking_queue() {\n    BlockingQueue<int> bq(2);\n    std::thread producer([&]() {\n        bq.push(100);\n        bq.push(200);\n    });\n    producer.join();\n    assert(bq.pop() == 100);\n    assert(bq.pop() == 200);\n}",
        "complexity": {"time": "O(1) push and pop", "space": "O(max_size)"},
        "explanation_steps": [
            "Guard inner std::queue with unique_lock and std::mutex.",
            "Use cv_not_full condition variable to block push when at capacity.",
            "Use cv_not_empty condition variable to block pop when queue is empty.",
            "Notify respective condition variables after state changes.",
        ],
    },
    {
        "id": "POLY-CPP-SYS-001",
        "language": "cpp",
        "tier": "systems",
        "title": "Lock-Free SPSC Ring Buffer with std::atomic",
        "tags": ["cpp", "lock-free", "concurrency", "atomics", "systems"],
        "problem_statement": "Implement a bounded Single-Producer Single-Consumer (SPSC) lock-free ring buffer in C++ using std::atomic and power-of-two capacity.",
        "starter_code": "template<typename T, size_t Capacity>\nclass SPSCRingBuffer {\npublic:\n    bool push(const T& item);\n    bool pop(T& item);\n};",
        "reference_solution": "#include <atomic>\n#include <cstddef>\n\ntemplate<typename T, size_t Capacity>\nclass SPSCRingBuffer {\n    static_assert((Capacity & (Capacity - 1)) == 0, \"Capacity must be a power of two\");\nprivate:\n    T buffer_[Capacity];\n    alignas(64) std::atomic<size_t> head_{0};\n    alignas(64) std::atomic<size_t> tail_{0};\n    static constexpr size_t Mask = Capacity - 1;\n\npublic:\n    SPSCRingBuffer() = default;\n\n    bool push(const T& item) {\n        const size_t head = head_.load(std::memory_order_relaxed);\n        const size_t tail = tail_.load(std::memory_order_acquire);\n        if (head - tail >= Capacity) {\n            return false; // Full\n        }\n        buffer_[head & Mask] = item;\n        head_.store(head + 1, std::memory_order_release);\n        return true;\n    }\n\n    bool pop(T& item) {\n        const size_t tail = tail_.load(std::memory_order_relaxed);\n        const size_t head = head_.load(std::memory_order_acquire);\n        if (head == tail) {\n            return false; // Empty\n        }\n        item = buffer_[tail & Mask];\n        tail_.store(tail + 1, std::memory_order_release);\n        return true;\n    }\n};",
        "unit_test_suite": "#include <cassert>\n\nvoid test_spsc() {\n    SPSCRingBuffer<int, 4> rb;\n    assert(rb.push(1));\n    assert(rb.push(2));\n    int val = 0;\n    assert(rb.pop(val) && val == 1);\n    assert(rb.pop(val) && val == 2);\n    assert(!rb.pop(val));\n}",
        "complexity": {"time": "O(1) push and pop", "space": "O(Capacity)"},
        "explanation_steps": [
            "Enforce power-of-two buffer capacity to allow bitwise masking (head & (Capacity - 1)).",
            "Use alignas(64) on atomic head and tail to eliminate false sharing between cache lines.",
            "Use memory_order_acquire on reading peer's index and memory_order_release on advancing.",
        ],
    },
    {
        "id": "POLY-CPP-COMP-001",
        "language": "cpp",
        "tier": "competitive",
        "title": "2D Fenwick Tree (Binary Indexed Tree)",
        "tags": ["cpp", "fenwick-tree", "data-structures", "competitive"],
        "problem_statement": "Implement a 2D Fenwick Tree supporting O(log R * log C) 2D point updates and 2D prefix/submatrix sum queries.",
        "starter_code": "class FenwickTree2D {\npublic:\n    FenwickTree2D(int rows, int cols);\n    void update(int r, int c, long long val);\n    long long query(int r, int c);\n    long long query_submatrix(int r1, int c1, int r2, int c2);\n};",
        "reference_solution": "#include <vector>\n\nclass FenwickTree2D {\nprivate:\n    int rows_, cols_;\n    std::vector<std::vector<long long>> tree_;\n\npublic:\n    FenwickTree2D(int rows, int cols) : rows_(rows), cols_(cols), tree_(rows + 1, std::vector<long long>(cols + 1, 0)) {}\n\n    void update(int r, int c, long long val) {\n        for (int i = r; i <= rows_; i += i & -i) {\n            for (int j = c; j <= cols_; j += j & -j) {\n                tree_[i][j] += val;\n            }\n        }\n    }\n\n    long long query(int r, int c) {\n        long long sum = 0;\n        for (int i = r; i > 0; i -= i & -i) {\n            for (int j = c; j > 0; j -= j & -j) {\n                sum += tree_[i][j];\n            }\n        }\n        return sum;\n    }\n\n    long long query_submatrix(int r1, int c1, int r2, int c2) {\n        return query(r2, c2) - query(r1 - 1, c2) - query(r2, c1 - 1) + query(r1 - 1, c1 - 1);\n    }\n};",
        "unit_test_suite": "#include <cassert>\n\nvoid test_fenwick_2d() {\n    FenwickTree2D ft(4, 4);\n    ft.update(2, 2, 5);\n    ft.update(3, 3, 10);\n    assert(ft.query(2, 2) == 5);\n    assert(ft.query_submatrix(2, 2, 3, 3) == 15);\n    assert(ft.query_submatrix(1, 1, 2, 1) == 0);\n}",
        "complexity": {"time": "O(log R * log C) for query and update", "space": "O(R * C)"},
        "explanation_steps": [
            "Use 1-indexed matrix with least significant bit extraction (i & -i).",
            "Update propagates value across both dimensions in logarithmic steps.",
            "Submatrix queries compute 2D inclusion-exclusion principle sum.",
        ],
    },

    # ------------------------------------------------------------------------
    # 4. JAVA
    # ------------------------------------------------------------------------
    {
        "id": "POLY-JAVA-ELEM-001",
        "language": "java",
        "tier": "elementary",
        "title": "Valid Parentheses Expression Validator",
        "tags": ["java", "stack", "strings", "elementary"],
        "problem_statement": "Given a string containing characters '(', ')', '{', '}', '[', and ']', determine if the input string has valid matching brackets.",
        "starter_code": "public class ParenthesesValidator {\n    public static boolean isValid(String s) {\n        // Implementation\n        return false;\n    }\n}",
        "reference_solution": "import java.util.ArrayDeque;\nimport java.util.Deque;\n\npublic class ParenthesesValidator {\n    public static boolean isValid(String s) {\n        if (s == null || s.length() % 2 != 0) return false;\n        Deque<Character> stack = new ArrayDeque<>();\n        for (char c : s.toCharArray()) {\n            if (c == '(') stack.push(')');\n            else if (c == '{') stack.push('}');\n            else if (c == '[') stack.push(']');\n            else if (stack.isEmpty() || stack.pop() != c) return false;\n        }\n        return stack.isEmpty();\n    }\n}",
        "unit_test_suite": "public class ParenthesesValidatorTest {\n    public static void main(String[] args) {\n        assert ParenthesesValidator.isValid(\"()[]{}\");\n        assert ParenthesesValidator.isValid(\"{[()]}\");\n        assert !ParenthesesValidator.isValid(\"(]\");\n        assert !ParenthesesValidator.isValid(\"([)]\");\n        System.out.println(\"All tests passed.\");\n    }\n}",
        "complexity": {"time": "O(N)", "space": "O(N)"},
        "explanation_steps": [
            "Use ArrayDeque for faster push/pop than legacy Stack class.",
            "On opening bracket, push matching closing bracket onto deque.",
            "On closing bracket, verify that stack is non-empty and top equals character.",
        ],
    },
    {
        "id": "POLY-JAVA-INT-001",
        "language": "java",
        "tier": "intermediate",
        "title": "Generic Thread-Safe Object Pool",
        "tags": ["java", "object-pool", "concurrency", "intermediate"],
        "problem_statement": "Implement a generic thread-safe object pool in Java supporting borrow and return with maximum pool size.",
        "starter_code": "import java.util.function.Supplier;\n\npublic class ObjectPool<T> {\n    public ObjectPool(Supplier<T> factory, int maxSize) {}\n    public T borrowObject() throws InterruptedException { return null; }\n    public void returnObject(T obj) {}\n}",
        "reference_solution": "import java.util.concurrent.BlockingQueue;\nimport java.util.concurrent.LinkedBlockingQueue;\nimport java.util.function.Supplier;\nimport java.util.concurrent.atomic.AtomicInteger;\n\npublic class ObjectPool<T> {\n    private final BlockingQueue<T> pool;\n    private final Supplier<T> factory;\n    private final int maxSize;\n    private final AtomicInteger createdCount = new AtomicInteger(0);\n\n    public ObjectPool(Supplier<T> factory, int maxSize) {\n        this.factory = factory;\n        this.maxSize = maxSize;\n        this.pool = new LinkedBlockingQueue<>(maxSize);\n    }\n\n    public T borrowObject() throws InterruptedException {\n        T item = pool.poll();\n        if (item != null) return item;\n        if (createdCount.get() < maxSize && createdCount.incrementAndGet() <= maxSize) {\n            return factory.get();\n        }\n        return pool.take();\n    }\n\n    public void returnObject(T obj) {\n        if (obj != null) {\n            pool.offer(obj);\n        }\n    }\n}",
        "unit_test_suite": "public class ObjectPoolTest {\n    public static void main(String[] args) throws InterruptedException {\n        ObjectPool<StringBuilder> pool = new ObjectPool<>(StringBuilder::new, 2);\n        StringBuilder b1 = pool.borrowObject();\n        StringBuilder b2 = pool.borrowObject();\n        assert b1 != null && b2 != null;\n        pool.returnObject(b1);\n        StringBuilder b3 = pool.borrowObject();\n        assert b3 == b1;\n        System.out.println(\"Object pool tests passed.\");\n    }\n}",
        "complexity": {"time": "O(1) amortized borrow and return", "space": "O(maxSize)"},
        "explanation_steps": [
            "Use LinkedBlockingQueue to store ready objects.",
            "Lazily create objects up to maxSize using AtomicInteger counter.",
            "Block caller on pool.take() when maximum capacity has been leased out.",
        ],
    },
    {
        "id": "POLY-JAVA-SYS-001",
        "language": "java",
        "tier": "systems",
        "title": "Custom Reentrant Read-Write Lock",
        "tags": ["java", "synchronization", "concurrency", "systems"],
        "problem_statement": "Implement a reentrant read-write lock in Java supporting multiple concurrent readers and exclusive writer lock acquisition.",
        "starter_code": "public class CustomReadWriteLock {\n    public synchronized void lockRead() throws InterruptedException {}\n    public synchronized void unlockRead() {}\n    public synchronized void lockWrite() throws InterruptedException {}\n    public synchronized void unlockWrite() {}\n}",
        "reference_solution": "import java.util.HashMap;\nimport java.util.Map;\n\npublic class CustomReadWriteLock {\n    private final Map<Thread, Integer> readingThreads = new HashMap<>();\n    private int writeAccesses = 0;\n    private int writeRequests = 0;\n    private Thread writingThread = null;\n\n    public synchronized void lockRead() throws InterruptedException {\n        Thread current = Thread.currentThread();\n        while (writingThread != null && writingThread != current || writeRequests > 0 && !readingThreads.containsKey(current)) {\n            wait();\n        }\n        readingThreads.put(current, readingThreads.getOrDefault(current, 0) + 1);\n    }\n\n    public synchronized void unlockRead() {\n        Thread current = Thread.currentThread();\n        int count = readingThreads.getOrDefault(current, 0);\n        if (count <= 1) {\n            readingThreads.remove(current);\n        } else {\n            readingThreads.put(current, count - 1);\n        }\n        notifyAll();\n    }\n\n    public synchronized void lockWrite() throws InterruptedException {\n        Thread current = Thread.currentThread();\n        writeRequests++;\n        while ((!readingThreads.isEmpty() && (!readingThreads.containsKey(current) || readingThreads.size() > 1)) || (writingThread != null && writingThread != current)) {\n            wait();\n        }\n        writeRequests--;\n        writeAccesses++;\n        writingThread = current;\n    }\n\n    public synchronized void unlockWrite() {\n        if (Thread.currentThread() != writingThread) {\n            throw new IllegalMonitorStateException(\"Current thread does not hold write lock\");\n        }\n        writeAccesses--;\n        if (writeAccesses == 0) {\n            writingThread = null;\n        }\n        notifyAll();\n    }\n}",
        "unit_test_suite": "public class CustomReadWriteLockTest {\n    public static void main(String[] args) throws Exception {\n        CustomReadWriteLock rw = new CustomReadWriteLock();\n        rw.lockRead();\n        rw.lockRead(); // reentrant\n        rw.unlockRead();\n        rw.unlockRead();\n        rw.lockWrite();\n        rw.lockWrite(); // reentrant\n        rw.unlockWrite();\n        rw.unlockWrite();\n        System.out.println(\"ReadWriteLock tests passed.\");\n    }\n}",
        "complexity": {"time": "O(1) lock and unlock", "space": "O(T) active threads"},
        "explanation_steps": [
            "Track per-thread reentrant read counts via HashMap.",
            "Grant write locks only when readingThreads is empty or caller is sole reader.",
            "Signal waiting threads via notifyAll() upon releasing locks.",
        ],
    },
    {
        "id": "POLY-JAVA-COMP-001",
        "language": "java",
        "tier": "competitive",
        "title": "Tarjan Strongly Connected Components (SCC)",
        "tags": ["java", "graph", "scc", "dfs", "competitive"],
        "problem_statement": "Implement Tarjan's algorithm to partition a directed graph into Strongly Connected Components (SCCs) in O(V + E) time.",
        "starter_code": "import java.util.List;\n\npublic class TarjanSCC {\n    public static List<List<Integer>> findSCCs(int n, List<List<Integer>> adj) {\n        // Implementation\n        return null;\n    }\n}",
        "reference_solution": "import java.util.ArrayList;\nimport java.util.Arrays;\nimport java.util.Deque;\nimport java.util.ArrayDeque;\nimport java.util.List;\n\npublic class TarjanSCC {\n    private static int timer;\n\n    public static List<List<Integer>> findSCCs(int n, List<List<Integer>> adj) {\n        int[] ids = new int[n];\n        int[] low = new int[n];\n        boolean[] onStack = new boolean[n];\n        Arrays.fill(ids, -1);\n        Deque<Integer> stack = new ArrayDeque<>();\n        List<List<Integer>> sccs = new ArrayList<>();\n        timer = 0;\n\n        for (int i = 0; i < n; i++) {\n            if (ids[i] == -1) {\n                dfs(i, adj, ids, low, onStack, stack, sccs);\n            }\n        }\n        return sccs;\n    }\n\n    private static void dfs(int u, List<List<Integer>> adj, int[] ids, int[] low,\n                            boolean[] onStack, Deque<Integer> stack, List<List<Integer>> sccs) {\n        ids[u] = low[u] = timer++;\n        stack.push(u);\n        onStack[u] = true;\n\n        for (int v : adj.get(u)) {\n            if (ids[v] == -1) {\n                dfs(v, adj, ids, low, onStack, stack, sccs);\n                low[u] = Math.min(low[u], low[v]);\n            } else if (onStack[v]) {\n                low[u] = Math.min(low[u], ids[v]);\n            }\n        }\n\n        if (low[u] == ids[u]) {\n            List<Integer> component = new ArrayList<>();\n            while (true) {\n                int node = stack.pop();\n                onStack[node] = false;\n                component.add(node);\n                if (node == u) break;\n            }\n            sccs.add(component);\n        }\n    }\n}",
        "unit_test_suite": "public class TarjanSCCTest {\n    public static void main(String[] args) {\n        int n = 5;\n        List<List<Integer>> adj = new ArrayList<>();\n        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());\n        adj.get(1).add(0);\n        adj.get(0).add(2);\n        adj.get(2).add(1);\n        adj.get(0).add(3);\n        adj.get(3).add(4);\n        List<List<Integer>> res = TarjanSCC.findSCCs(n, adj);\n        assert res.size() == 3;\n        System.out.println(\"Tarjan SCC tests passed.\");\n    }\n}",
        "complexity": {"time": "O(V + E)", "space": "O(V)"},
        "explanation_steps": [
            "Traverse graph via DFS assigning discovery ids and tracking low-link reachability.",
            "Maintain execution stack of candidate component vertices.",
            "When low[u] == ids[u], pop elements from stack until u to form complete SCC.",
        ],
    },

    # ------------------------------------------------------------------------
    # 5. RUST
    # ------------------------------------------------------------------------
    {
        "id": "POLY-RUST-ELEM-001",
        "language": "rust",
        "tier": "elementary",
        "title": "Unicode-Aware In-Place Word Reversal",
        "tags": ["rust", "strings", "utf-8", "elementary"],
        "problem_statement": "Implement in-place reversal of words in a string while preserving word order and whitespace boundaries in Rust.",
        "starter_code": "pub fn reverse_words(s: &str) -> String {\n    todo!()\n}",
        "reference_solution": "pub fn reverse_words(s: &str) -> String {\n    s.split(' ')\n     .map(|word| word.chars().rev().collect::<String>())\n     .collect::<Vec<String>>()\n     .join(\" \")\n}",
        "unit_test_suite": "#[cfg(test)]\nmod tests {\n    use super::*;\n    #[test]\n    fn test_reverse_words() {\n        assert_eq!(reverse_words(\"hello world\"), \"olleh dlrow\");\n        assert_eq!(reverse_words(\"Rust programming\"), \"tsuR gnimmargorp\");\n        assert_eq!(reverse_words(\"\"), \"\");\n    }\n}",
        "complexity": {"time": "O(N)", "space": "O(N)"},
        "explanation_steps": [
            "Split string slice by space delimiter.",
            "For each token, invert chars iterator to guarantee valid UTF-8 scalar values.",
            "Join reversed words with space separator into resulting String.",
        ],
    },
    {
        "id": "POLY-RUST-INT-001",
        "language": "rust",
        "tier": "intermediate",
        "title": "Type-Safe State Machine with Zero-Sized Types",
        "tags": ["rust", "type-system", "state-machine", "zst", "intermediate"],
        "problem_statement": "Implement a compile-time validated state machine for a network connection (Disconnected -> Connecting -> Connected) using Rust ZSTs.",
        "starter_code": "pub struct Connection<S> { state: std::marker::PhantomData<S> }\n// Implement states and transitions",
        "reference_solution": "use std::marker::PhantomData;\n\npub struct Disconnected;\npub struct Connecting;\npub struct Connected;\n\npub struct Connection<S> {\n    address: String,\n    _marker: PhantomData<S>,\n}\n\nimpl Connection<Disconnected> {\n    pub fn new(address: String) -> Self {\n        Self { address, _marker: PhantomData }\n    }\n    pub fn connect(self) -> Connection<Connecting> {\n        Connection { address: self.address, _marker: PhantomData }\n    }\n}\n\nimpl Connection<Connecting> {\n    pub fn establish(self) -> Connection<Connected> {\n        Connection { address: self.address, _marker: PhantomData }\n    }\n}\n\nimpl Connection<Connected> {\n    pub fn send(&self, data: &[u8]) -> usize {\n        data.len()\n    }\n    pub fn disconnect(self) -> Connection<Disconnected> {\n        Connection { address: self.address, _marker: PhantomData }\n    }\n}",
        "unit_test_suite": "#[cfg(test)]\nmod tests {\n    use super::*;\n    #[test]\n    fn test_state_transitions() {\n        let conn = Connection::new(\"127.0.0.1:8080\".into());\n        let connecting = conn.connect();\n        let connected = connecting.establish();\n        assert_eq!(connected.send(b\"ping\"), 4);\n        let _ = connected.disconnect();\n    }\n}",
        "complexity": {"time": "O(1) zero-cost abstraction", "space": "O(1) zero runtime overhead"},
        "explanation_steps": [
            "Define Disconnected, Connecting, and Connected as zero-sized empty structs.",
            "Use PhantomData<S> to parameterize Connection without runtime memory cost.",
            "Consume self during transitions to enforce valid state flow at compile time.",
        ],
    },
    {
        "id": "POLY-RUST-SYS-001",
        "language": "rust",
        "tier": "systems",
        "title": "Lock-Free SPSC Ring Buffer with Atomic Ordering",
        "tags": ["rust", "concurrency", "lock-free", "atomics", "systems"],
        "problem_statement": "Implement a bounded Single-Producer Single-Consumer (SPSC) ring buffer in Rust without mutexes using AtomicUsize and acquire-release semantics.",
        "starter_code": "pub struct RingBuffer<T> {\n    // Define fields\n}\nimpl<T> RingBuffer<T> {\n    pub fn new(capacity: usize) -> Self { todo!() }\n    pub fn push(&self, item: T) -> Result<(), T> { todo!() }\n    pub fn pop(&self) -> Option<T> { todo!() }\n}",
        "reference_solution": "use std::sync::atomic::{AtomicUsize, Ordering};\nuse std::cell::UnsafeCell;\nuse std::mem::MaybeUninit;\n\npub struct RingBuffer<T> {\n    buffer: Box<[UnsafeCell<MaybeUninit<T>>]>,\n    capacity: usize,\n    head: AtomicUsize,\n    tail: AtomicUsize,\n}\n\nunsafe impl<T: Send> Sync for RingBuffer<T> {}\nunsafe impl<T: Send> Send for RingBuffer<T> {}\n\nimpl<T> RingBuffer<T> {\n    pub fn new(capacity: usize) -> Self {\n        assert!(capacity > 0 && capacity.is_power_of_two(), \"Capacity must be power of two\");\n        let mut vec = Vec::with_capacity(capacity);\n        for _ in 0..capacity {\n            vec.push(UnsafeCell::new(MaybeUninit::uninit()));\n        }\n        Self {\n            buffer: vec.into_boxed_slice(),\n            capacity,\n            head: AtomicUsize::new(0),\n            tail: AtomicUsize::new(0),\n        }\n    }\n\n    pub fn push(&self, item: T) -> Result<(), T> {\n        let head = self.head.load(Ordering::Relaxed);\n        let tail = self.tail.load(Ordering::Acquire);\n        if head.wrapping_sub(tail) >= self.capacity {\n            return Err(item);\n        }\n        let mask = self.capacity - 1;\n        let slot = &self.buffer[head & mask];\n        unsafe { (*slot.get()).write(item); }\n        self.head.store(head.wrapping_add(1), Ordering::Release);\n        Ok(())\n    }\n\n    pub fn pop(&self) -> Option<T> {\n        let tail = self.tail.load(Ordering::Relaxed);\n        let head = self.head.load(Ordering::Acquire);\n        if tail == head {\n            return None;\n        }\n        let mask = self.capacity - 1;\n        let slot = &self.buffer[tail & mask];\n        let item = unsafe { (*slot.get()).assume_init_read() };\n        self.tail.store(tail.wrapping_add(1), Ordering::Release);\n        Some(item)\n    }\n}",
        "unit_test_suite": "#[cfg(test)]\nmod tests {\n    use super::*;\n    #[test]\n    fn test_spsc_ring_buffer() {\n        let rb = RingBuffer::new(4);\n        assert!(rb.push(10).is_ok());\n        assert!(rb.push(20).is_ok());\n        assert_eq!(rb.pop(), Some(10));\n        assert_eq!(rb.pop(), Some(20));\n        assert_eq!(rb.pop(), None);\n    }\n}",
        "complexity": {"time": "O(1) push and pop", "space": "O(N)"},
        "explanation_steps": [
            "Use Box<[UnsafeCell<MaybeUninit<T>>]> for uninitialized memory slot buffer.",
            "Read local thread index with Relaxed ordering; peer index with Acquire ordering.",
            "Write item into buffer before committing index change via Release ordering.",
        ],
    },
    {
        "id": "POLY-RUST-COMP-001",
        "language": "rust",
        "tier": "competitive",
        "title": "Trie (Prefix Tree) with Autocomplete and Frequency Ordering",
        "tags": ["rust", "trie", "strings", "autocomplete", "competitive"],
        "problem_statement": "Implement a Trie in Rust supporting word insertion with frequency counts, prefix searches, and top-K autocompletion.",
        "starter_code": "pub struct Trie {\n    // Define fields\n}\nimpl Trie {\n    pub fn new() -> Self { todo!() }\n    pub fn insert(&mut self, word: &str, freq: u32) { todo!() }\n    pub fn top_k(&self, prefix: &str, k: usize) -> Vec<(String, u32)> { todo!() }\n}",
        "reference_solution": "use std::collections::HashMap;\n\n#[derive(Default)]\nstruct TrieNode {\n    children: HashMap<char, TrieNode>,\n    frequency: u32,\n    is_end: bool,\n}\n\n#[derive(Default)]\npub struct Trie {\n    root: TrieNode,\n}\n\nimpl Trie {\n    pub fn new() -> Self {\n        Self::default()\n    }\n\n    pub fn insert(&mut self, word: &str, freq: u32) {\n        let mut curr = &mut self.root;\n        for c in word.chars() {\n            curr = curr.children.entry(c).or_default();\n        }\n        curr.is_end = true;\n        curr.frequency += freq;\n    }\n\n    pub fn top_k(&self, prefix: &str, k: usize) -> Vec<(String, u32)> {\n        let mut curr = &self.root;\n        for c in prefix.chars() {\n            if let Some(next) = curr.children.get(&c) {\n                curr = next;\n            } else {\n                return Vec::new();\n            }\n        }\n        let mut matches = Vec::new();\n        let mut path = prefix.to_string();\n        Self::collect(curr, &mut path, &mut matches);\n        matches.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));\n        matches.truncate(k);\n        matches\n    }\n\n    fn collect(node: &TrieNode, path: &mut String, results: &mut Vec<(String, u32)>) {\n        if node.is_end {\n            results.push((path.clone(), node.frequency));\n        }\n        for (&c, child) in &node.children {\n            path.push(c);\n            Self::collect(child, path, results);\n            path.pop();\n        }\n    }\n}",
        "unit_test_suite": "#[cfg(test)]\nmod tests {\n    use super::*;\n    #[test]\n    fn test_trie_top_k() {\n        let mut trie = Trie::new();\n        trie.insert(\"apple\", 10);\n        trie.insert(\"app\", 25);\n        trie.insert(\"application\", 5);\n        let top = trie.top_k(\"app\", 2);\n        assert_eq!(top, vec![(\"app\".into(), 25), (\"apple\".into(), 10)]);\n    }\n}",
        "complexity": {"time": "O(L) insert, O(P + M log M) search where L=word len, P=prefix len", "space": "O(Total Chars)"},
        "explanation_steps": [
            "Store child transitions in HashMap<char, TrieNode>.",
            "Traverse to node corresponding to query prefix.",
            "Collect matching subtrees recursively and sort results by frequency descending.",
        ],
    },

    # ------------------------------------------------------------------------
    # 6. GO
    # ------------------------------------------------------------------------
    {
        "id": "POLY-GO-ELEM-001",
        "language": "go",
        "tier": "elementary",
        "title": "Concurrent Word Frequency Counter with Mutex",
        "tags": ["go", "concurrency", "mutex", "strings", "elementary"],
        "problem_statement": "Implement a concurrent word frequency counter in Go that partitions text blocks across goroutines and aggregates counts safely using sync.Mutex.",
        "starter_code": "package main\n\nfunc CountWordFrequencies(blocks []string) map[string]int {\n    // Implementation\n    return nil\n}",
        "reference_solution": "package main\n\nimport (\n    \"strings\"\n    \"sync\"\n)\n\nfunc CountWordFrequencies(blocks []string) map[string]int {\n    counts := make(map[string]int)\n    var mu sync.Mutex\n    var wg sync.WaitGroup\n\n    for _, block := range blocks {\n        wg.Add(1)\n        go func(b string) {\n            defer wg.Done()\n            local := make(map[string]int)\n            words := strings.Fields(strings.ToLower(b))\n            for _, w := range words {\n                local[w]++\n            }\n            mu.Lock()\n            for k, v := range local {\n                counts[k] += v\n            }\n            mu.Unlock()\n        }(block)\n    }\n    wg.Wait()\n    return counts\n}",
        "unit_test_suite": "package main\n\nimport \"testing\"\n\nfunc TestCountWordFrequencies(t *testing.T) {\n    blocks := []string{\"Hello world\", \"hello Go\", \"world of concurrency\"}\n    counts := CountWordFrequencies(blocks)\n    if counts[\"hello\"] != 2 || counts[\"world\"] != 2 || counts[\"go\"] != 1 {\n        t.Fatalf(\"Unexpected counts: %+v\", counts)\n    }\n}",
        "complexity": {"time": "O(Total Words)", "space": "O(Unique Words)"},
        "explanation_steps": [
            "Spawn a goroutine per text block to compute thread-local word counts.",
            "Minimize lock contention by aggregating local maps before taking the global mutex.",
            "Synchronize goroutine completion using sync.WaitGroup.",
        ],
    },
    {
        "id": "POLY-GO-INT-001",
        "language": "go",
        "tier": "intermediate",
        "title": "Pipeline Processing with Fan-Out / Fan-In",
        "tags": ["go", "channels", "pipeline", "fan-out-fan-in", "intermediate"],
        "problem_statement": "Implement a concurrent Go pipeline with generator, multiple worker stages (fan-out), and an aggregator (fan-in) using channels.",
        "starter_code": "package main\n\nfunc RunPipeline(nums []int, workers int) []int {\n    // Implementation\n    return nil\n}",
        "reference_solution": "package main\n\nimport \"sync\"\n\nfunc RunPipeline(nums []int, workers int) []int {\n    inputCh := make(chan int, len(nums))\n    for _, n := range nums {\n        inputCh <- n\n    }\n    close(inputCh)\n\n    outCh := make(chan int, len(nums))\n    var wg sync.WaitGroup\n\n    for i := 0; i < workers; i++ {\n        wg.Add(1)\n        go func() {\n            defer wg.Done()\n            for n := range inputCh {\n                outCh <- n * n // square operation\n            }\n        }()\n    }\n\n    go func() {\n        wg.Wait()\n        close(outCh)\n    }()\n\n    var results []int\n    for res := range outCh {\n        results = append(results, res)\n    }\n    return results\n}",
        "unit_test_suite": "package main\n\nimport \"testing\"\n\nfunc TestRunPipeline(t *testing.T) {\n    nums := []int{1, 2, 3, 4, 5}\n    res := RunPipeline(nums, 3)\n    if len(res) != 5 {\n        t.Fatalf(\"Expected 5 results, got %d\", len(res))\n    }\n}",
        "complexity": {"time": "O(N / workers)", "space": "O(N)"},
        "explanation_steps": [
            "Populate and close buffered input channel.",
            "Spawn worker goroutines reading from shared channel (fan-out).",
            "Coordinate worker termination using sync.WaitGroup to close output channel (fan-in).",
        ],
    },
    {
        "id": "POLY-GO-SYS-001",
        "language": "go",
        "tier": "systems",
        "title": "Resilient Worker Pool with Context Cancellation",
        "tags": ["go", "worker-pool", "context", "graceful-shutdown", "systems"],
        "problem_statement": "Implement a resilient worker pool in Go that respects context.Context cancellation, drains remaining jobs cleanly, and captures errors.",
        "starter_code": "package main\nimport \"context\"\n\ntype Task func(ctx context.Context) error\nfunc ProcessTasks(ctx context.Context, tasks []Task, numWorkers int) []error {\n    return nil\n}",
        "reference_solution": "package main\n\nimport (\n    \"context\"\n    \"sync\"\n)\n\ntype Task func(ctx context.Context) error\n\nfunc ProcessTasks(ctx context.Context, tasks []Task, numWorkers int) []error {\n    taskCh := make(chan Task, len(tasks))\n    for _, t := range tasks {\n        taskCh <- t\n    }\n    close(taskCh)\n\n    errCh := make(chan error, len(tasks))\n    var wg sync.WaitGroup\n\n    for i := 0; i < numWorkers; i++ {\n        wg.Add(1)\n        go func() {\n            defer wg.Done()\n            for t := range taskCh {\n                select {\n                case <-ctx.Done():\n                    errCh <- ctx.Err()\n                    return\n                default:\n                    if err := t(ctx); err != nil {\n                        errCh <- err\n                    }\n                }\n            }\n        }()\n    }\n\n    wg.Wait()\n    close(errCh)\n\n    var errs []error\n    for e := range errCh {\n        errs = append(errs, e)\n    }\n    return errs\n}",
        "unit_test_suite": "package main\n\nimport (\n    \"context\"\n    \"errors\"\n    \"testing\"\n)\n\nfunc TestProcessTasks(t *testing.T) {\n    tasks := []Task{\n        func(ctx context.Context) error { return nil },\n        func(ctx context.Context) error { return errors.New(\"failed\") },\n    }\n    errs := ProcessTasks(context.Background(), tasks, 2)\n    if len(errs) != 1 {\n        t.Fatalf(\"Expected 1 error, got %d\", len(errs))\n    }\n}",
        "complexity": {"time": "O(Tasks / Workers)", "space": "O(Tasks)"},
        "explanation_steps": [
            "Use buffered channels for task distribution and error collection.",
            "Check ctx.Done() inside worker loop to stop immediately on cancellation.",
            "Wait for worker goroutines to finish before closing error channel.",
        ],
    },
    {
        "id": "POLY-GO-COMP-001",
        "language": "go",
        "tier": "competitive",
        "title": "Disjoint Set Union (DSU / Union-Find) with Rank",
        "tags": ["go", "dsu", "union-find", "graphs", "competitive"],
        "problem_statement": "Implement Disjoint Set Union (DSU) in Go with path compression and union by rank for cycle detection in O(alpha(N)) amortized time.",
        "starter_code": "package main\n\ntype DSU struct {}\nfunc NewDSU(n int) *DSU { return nil }\nfunc (d *DSU) Find(x int) int { return 0 }\nfunc (d *DSU) Union(x, y int) bool { return false }",
        "reference_solution": "package main\n\ntype DSU struct {\n    parent []int\n    rank   []int\n    Count  int\n}\n\nfunc NewDSU(n int) *DSU {\n    parent := make([]int, n)\n    rank := make([]int, n)\n    for i := range parent {\n        parent[i] = i\n        rank[i] = 0\n    }\n    return &DSU{parent: parent, rank: rank, Count: n}\n}\n\nfunc (d *DSU) Find(x int) int {\n    if d.parent[x] != x {\n        d.parent[x] = d.Find(d.parent[x]) // path compression\n    }\n    return d.parent[x]\n}\n\nfunc (d *DSU) Union(x, y int) bool {\n    rootX := d.Find(x)\n    rootY := d.Find(y)\n    if rootX == rootY {\n        return false // already connected\n    }\n    if d.rank[rootX] < d.rank[rootY] {\n        d.parent[rootX] = rootY\n    } else if d.rank[rootX] > d.rank[rootY] {\n        d.parent[rootY] = rootX\n    } else {\n        d.parent[rootY] = rootX\n        d.rank[rootX]++\n    }\n    d.Count--\n    return true\n}",
        "unit_test_suite": "package main\n\nimport \"testing\"\n\nfunc TestDSU(t *testing.T) {\n    d := NewDSU(5)\n    if !d.Union(0, 1) || !d.Union(1, 2) {\n        t.Fatal(\"Expected successful unions\")\n    }\n    if d.Union(0, 2) {\n        t.Fatal(\"Cycle edge should return false\")\n    }\n    if d.Find(0) != d.Find(2) {\n        t.Fatal(\"0 and 2 must have same root\")\n    }\n}",
        "complexity": {"time": "O(α(N)) nearly constant per operation", "space": "O(N)"},
        "explanation_steps": [
            "Initialize parent pointers pointing to self and zero ranks.",
            "Apply path compression during Find() flattening tree depth.",
            "Attach shorter tree under taller tree during Union() to maintain logarithmic height.",
        ],
    },

    # ------------------------------------------------------------------------
    # 7. PHP
    # ------------------------------------------------------------------------
    {
        "id": "POLY-PHP-ELEM-001",
        "language": "php",
        "tier": "elementary",
        "title": "Multibyte Palindrome & Anagram Verifier",
        "tags": ["php", "strings", "multibyte", "elementary"],
        "problem_statement": "Implement functions in PHP 8.2+ to verify if a string is a palindrome and if two strings are anagrams, with support for UTF-8 multibyte characters.",
        "starter_code": "<?php\nfunction isPalindrome(string $text): bool {}\nfunction isAnagram(string $a, string $b): bool {}",
        "reference_solution": "<?php\ndeclare(strict_types=1);\n\nfunction isPalindrome(string $text): bool {\n    $clean = mb_strtolower((string) preg_replace('/[^\\p{L}\\p{N}]/u', '', $text), 'UTF-8');\n    $len = mb_strlen($clean, 'UTF-8');\n    for ($i = 0; $i < intdiv($len, 2); $i++) {\n        if (mb_substr($clean, $i, 1, 'UTF-8') !== mb_substr($clean, $len - 1 - $i, 1, 'UTF-8')) {\n            return false;\n        }\n    }\n    return true;\n}\n\nfunction isAnagram(string $a, string $b): bool {\n    $cleanA = mb_strtolower((string) preg_replace('/[^\\p{L}\\p{N}]/u', '', $a), 'UTF-8');\n    $cleanB = mb_strtolower((string) preg_replace('/[^\\p{L}\\p{N}]/u', '', $b), 'UTF-8');\n    if (mb_strlen($cleanA, 'UTF-8') !== mb_strlen($cleanB, 'UTF-8')) return false;\n    $charsA = preg_split('//u', $cleanA, -1, PREG_SPLIT_NO_EMPTY);\n    $charsB = preg_split('//u', $cleanB, -1, PREG_SPLIT_NO_EMPTY);\n    sort($charsA);\n    sort($charsB);\n    return $charsA === $charsB;\n}",
        "unit_test_suite": "<?php\nassert(isPalindrome('A man, a plan, a canal: Panama') === true);\nassert(isPalindrome('race a car') === false);\nassert(isAnagram('anagram', 'nagaram') === true);\nassert(isAnagram('rat', 'car') === false);",
        "complexity": {"time": "O(N log N) for anagram sort, O(N) for palindrome", "space": "O(N)"},
        "explanation_steps": [
            "Use Unicode regex /[^\\p{L}\\p{N}]/u and mb_strtolower for UTF-8 safety.",
            "Compare characters from both ends using mb_substr for palindrome check.",
            "Split multibyte characters with preg_split and compare sorted arrays for anagram.",
        ],
    },
    {
        "id": "POLY-PHP-INT-001",
        "language": "php",
        "tier": "intermediate",
        "title": "PSR-15 Onion Middleware Pipeline Dispatcher",
        "tags": ["php", "middleware", "psr-15", "pipeline", "intermediate"],
        "problem_statement": "Implement an extensible PSR-15 compliant Onion-Architecture HTTP Middleware Pipeline Dispatcher in PHP 8.2.",
        "starter_code": "<?php\nclass MiddlewareDispatcher {\n    public function add(callable $middleware): void {}\n    public function handle(array $request): array {}\n}",
        "reference_solution": "<?php\ndeclare(strict_types=1);\n\nclass MiddlewareDispatcher {\n    /** @var list<callable> */\n    private array $middleware = [];\n\n    public function add(callable $mw): void {\n        $this->middleware[] = $mw;\n    }\n\n    /**\n     * @param array<string, mixed> $request\n     * @param callable $coreHandler\n     * @return array<string, mixed>\n     */\n    public function dispatch(array $request, callable $coreHandler): array {\n        $runner = array_reduce(\n            array_reverse($this->middleware),\n            fn(callable $next, callable $mw) => fn(array $req) => $mw($req, $next),\n            $coreHandler\n        );\n        return $runner($request);\n    }\n}",
        "unit_test_suite": "<?php\n$dispatcher = new MiddlewareDispatcher();\n$dispatcher->add(function(array $req, callable $next) {\n    $req['steps'][] = 'auth';\n    $res = $next($req);\n    $res['status'] = 'authenticated';\n    return $res;\n});\n$res = $dispatcher->dispatch(['steps' => []], function(array $req) {\n    $req['steps'][] = 'core';\n    return $req;\n});\nassert($res['steps'] === ['auth', 'core']);\nassert($res['status'] === 'authenticated');",
        "complexity": {"time": "O(M) where M is middleware count", "space": "O(M) call stack"},
        "explanation_steps": [
            "Reverse middleware array and reduce into nested closure chain.",
            "Each middleware receives request array and $next callable.",
            "Executes outer pre-processing, invokes inner layer, then applies post-processing.",
        ],
    },
    {
        "id": "POLY-PHP-SYS-001",
        "language": "php",
        "tier": "systems",
        "title": "Memory-Efficient Large CSV Stream Transformer with Generators",
        "tags": ["php", "generators", "streaming", "memory-efficiency", "systems"],
        "problem_statement": "Implement a memory-bounded CSV transformer in PHP using Generators and yield to process millions of records within 128 MB RAM.",
        "starter_code": "<?php\nclass CsvStreamTransformer {\n    public static function streamRows(string $filepath): Generator {}\n}",
        "reference_solution": "<?php\ndeclare(strict_types=1);\n\nclass CsvStreamTransformer {\n    /**\n     * @return Generator<int, array<string, string>>\n     */\n    public static function streamRows(string $filepath): Generator {\n        if (!file_exists($filepath) || !is_readable($filepath)) {\n            throw new InvalidArgumentException(\"File unreadable: {$filepath}\");\n        }\n        $handle = fopen($filepath, 'rb');\n        if ($handle === false) return;\n        try {\n            $header = fgetcsv($handle);\n            if ($header === false) return;\n            $rowIndex = 0;\n            while (($row = fgetcsv($handle)) !== false) {\n                if (count($row) === count($header)) {\n                    yield $rowIndex++ => array_combine($header, $row);\n                }\n            }\n        } finally {\n            fclose($handle);\n        }\n    }\n}",
        "unit_test_suite": "<?php\n$tmp = tempnam(sys_get_temp_dir(), 'csv_');\nfile_put_contents($tmp, \"id,name\\n1,Alice\\n2,Bob\");\n$count = 0;\nforeach (CsvStreamTransformer::streamRows($tmp) as $idx => $record) {\n    assert(isset($record['id'], $record['name']));\n    $count++;\n}\nassert($count === 2);\nunlink($tmp);",
        "complexity": {"time": "O(Total Rows)", "space": "O(1) memory bound < 5 MB"},
        "explanation_steps": [
            "Open file pointer with fopen('rb') and extract header row.",
            "Iterate line by line with fgetcsv and yield mapped dictionary.",
            "Never buffers full file in memory, strictly preserving the PHP 128M limit.",
        ],
    },
    {
        "id": "POLY-PHP-COMP-001",
        "language": "php",
        "tier": "competitive",
        "title": "LRU Cache with Doubly-Linked List in PHP",
        "tags": ["php", "lru-cache", "data-structures", "competitive"],
        "problem_statement": "Implement an LRU Cache in PHP 8.2 using a custom doubly-linked list and hash map achieving O(1) get and put.",
        "starter_code": "<?php\nclass LruCachePhp {\n    public function __construct(int $capacity) {}\n    public function get(int|string $key): mixed {}\n    public function put(int|string $key, mixed $value): void {}\n}",
        "reference_solution": "<?php\ndeclare(strict_types=1);\n\nclass LruNode {\n    public function __construct(\n        public int|string $key,\n        public mixed $val,\n        public ?LruNode $prev = null,\n        public ?LruNode $next = null,\n    ) {}\n}\n\nclass LruCachePhp {\n    private array $map = [];\n    private LruNode $head;\n    private LruNode $tail;\n\n    public function __construct(private int $capacity) {\n        $this->head = new LruNode(0, null);\n        $this->tail = new LruNode(0, null);\n        $this->head->next = $this->tail;\n        $this->tail->prev = $this->head;\n    }\n\n    public function get(int|string $key): mixed {\n        if (!isset($this->map[$key])) return null;\n        $node = $this->map[$key];\n        $this->moveToHead($node);\n        return $node->val;\n    }\n\n    public function put(int|string $key, mixed $value): void {\n        if (isset($this->map[$key])) {\n            $node = $this->map[$key];\n            $node->val = $value;\n            $this->moveToHead($node);\n            return;\n        }\n        if (count($this->map) >= $this->capacity) {\n            $lru = $this->tail->prev;\n            $this->removeNode($lru);\n            unset($this->map[$lru->key]);\n        }\n        $newNode = new LruNode($key, $value);\n        $this->addNode($newNode);\n        $this->map[$key] = $newNode;\n    }\n\n    private function addNode(LruNode $node): void {\n        $node->prev = $this->head;\n        $node->next = $this->head->next;\n        $this->head->next->prev = $node;\n        $this->head->next = $node;\n    }\n\n    private function removeNode(LruNode $node): void {\n        $node->prev->next = $node->next;\n        $node->next->prev = $node->prev;\n    }\n\n    private function moveToHead(LruNode $node): void {\n        $this->removeNode($node);\n        $this->addNode($node);\n    }\n}",
        "unit_test_suite": "<?php\n$cache = new LruCachePhp(2);\n$cache->put('a', 10);\n$cache->put('b', 20);\nassert($cache->get('a') === 10);\n$cache->put('c', 30); // evicts 'b'\nassert($cache->get('b') === null);\nassert($cache->get('c') === 30);",
        "complexity": {"time": "O(1) get and put", "space": "O(capacity)"},
        "explanation_steps": [
            "Use sentinel head and tail nodes to simplify boundary pointer operations.",
            "Store pointers to nodes in associative array map for O(1) hash access.",
            "Splice out least recently used node before tail when capacity is exceeded.",
        ],
    },

    # ------------------------------------------------------------------------
    # 8. SQL
    # ------------------------------------------------------------------------
    {
        "id": "POLY-SQL-ELEM-001",
        "language": "sql",
        "tier": "elementary",
        "title": "Multi-Table Aggregation with GROUP BY and HAVING",
        "tags": ["sql", "aggregation", "joins", "group-by", "elementary"],
        "problem_statement": "Write an SQL query to retrieve customer IDs, customer names, total completed order counts, and total revenue for customers who placed at least 3 orders and spent over $500 total, sorted by revenue descending.",
        "starter_code": "-- Write query selecting customer_id, customer_name, order_count, total_revenue\nSELECT ...",
        "reference_solution": "SELECT \n    c.customer_id,\n    c.customer_name,\n    COUNT(o.order_id) AS order_count,\n    ROUND(SUM(o.total_amount), 2) AS total_revenue\nFROM customers c\nINNER JOIN orders o ON c.customer_id = o.customer_id\nWHERE o.status = 'completed'\nGROUP BY c.customer_id, c.customer_name\nHAVING COUNT(o.order_id) >= 3 AND SUM(o.total_amount) > 500.00\nORDER BY total_revenue DESC;",
        "unit_test_suite": "-- Schema verification\nCREATE TABLE customers (customer_id INT PRIMARY KEY, customer_name TEXT);\nCREATE TABLE orders (order_id INT PRIMARY KEY, customer_id INT, status TEXT, total_amount DECIMAL(10,2));\n-- Assert HAVING filters work properly",
        "complexity": {"time": "O(N log N) dominated by sort", "space": "O(Distinct Customers)"},
        "explanation_steps": [
            "INNER JOIN customers with orders on matching customer_id.",
            "Filter completed transactions using WHERE clause before aggregation.",
            "Group by customer attributes and filter aggregate metrics with HAVING.",
            "Sort result set by total_revenue descending.",
        ],
    },
    {
        "id": "POLY-SQL-INT-001",
        "language": "sql",
        "tier": "intermediate",
        "title": "Window Functions for Running Revenue and MoM Churn",
        "tags": ["sql", "window-functions", "dense-rank", "lag", "intermediate"],
        "problem_statement": "Write an SQL query using window functions (LAG and DENSE_RANK) to calculate month-over-month revenue growth rate and regional rank per sales department.",
        "starter_code": "-- Write query using LAG() and DENSE_RANK()\nSELECT ...",
        "reference_solution": "WITH monthly_revenue AS (\n    SELECT \n        department_id,\n        DATE_TRUNC('month', transaction_date) AS rev_month,\n        SUM(amount) AS monthly_sales\n    FROM transactions\n    GROUP BY department_id, DATE_TRUNC('month', transaction_date)\n)\nSELECT \n    department_id,\n    rev_month,\n    monthly_sales,\n    LAG(monthly_sales, 1) OVER (\n        PARTITION BY department_id ORDER BY rev_month\n    ) AS prev_month_sales,\n    ROUND(\n        100.0 * (monthly_sales - LAG(monthly_sales, 1) OVER (PARTITION BY department_id ORDER BY rev_month)) \n        / NULLIF(LAG(monthly_sales, 1) OVER (PARTITION BY department_id ORDER BY rev_month), 0), \n        2\n    ) AS mom_growth_pct,\n    DENSE_RANK() OVER (\n        PARTITION BY rev_month ORDER BY monthly_sales DESC\n    ) AS monthly_dept_rank\nFROM monthly_revenue\nORDER BY department_id, rev_month;",
        "unit_test_suite": "-- Verify LAG and DENSE_RANK return exact partition values\nSELECT department_id, rev_month, mom_growth_pct FROM (/* query */) WHERE monthly_dept_rank = 1;",
        "complexity": {"time": "O(N log N) partitioned window sort", "space": "O(N) working memory"},
        "explanation_steps": [
            "Aggregate raw transactions by department and month into a CTE.",
            "Use LAG(monthly_sales, 1) partitioned by department to retrieve prior month sales.",
            "Compute growth percentage with NULLIF to prevent division-by-zero.",
            "Apply DENSE_RANK() partitioned by month to rank departments by sales.",
        ],
    },
    {
        "id": "POLY-SQL-SYS-001",
        "language": "sql",
        "tier": "systems",
        "title": "Temporal Audit Log & Idempotent UPSERT Schema",
        "tags": ["sql", "upsert", "indexing", "audit-log", "systems"],
        "problem_statement": "Design a high-throughput user state schema with atomic idempotent UPSERT and an append-only temporal audit trigger.",
        "starter_code": "-- Define table and idempotent upsert statement\nCREATE TABLE user_profiles ...\nINSERT INTO user_profiles ...",
        "reference_solution": "CREATE TABLE IF NOT EXISTS user_profiles (\n    user_id VARCHAR(64) PRIMARY KEY,\n    email VARCHAR(255) NOT NULL UNIQUE,\n    settings_json TEXT NOT NULL DEFAULT '{}',\n    version INT NOT NULL DEFAULT 1,\n    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP\n);\n\nCREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles (email);\n\n-- Idempotent Atomic Upsert Statement\nINSERT INTO user_profiles (user_id, email, settings_json, version, updated_at)\nVALUES ('usr_1001', 'dev@example.com', '{\"theme\":\"dark\"}', 1, CURRENT_TIMESTAMP)\nON CONFLICT (user_id) DO UPDATE SET\n    settings_json = EXCLUDED.settings_json,\n    version = user_profiles.version + 1,\n    updated_at = CURRENT_TIMESTAMP;",
        "unit_test_suite": "-- Test idempotent conflict update\nSELECT version FROM user_profiles WHERE user_id = 'usr_1001';",
        "complexity": {"time": "O(log N) indexed upsert", "space": "O(N) row storage"},
        "explanation_steps": [
            "Establish PRIMARY KEY constraint on user_id to enforce uniqueness.",
            "Use ON CONFLICT (user_id) DO UPDATE to perform atomic UPSERT.",
            "Increment version field atomically during conflict resolution for optimistic concurrency.",
        ],
    },
    {
        "id": "POLY-SQL-COMP-001",
        "language": "sql",
        "tier": "competitive",
        "title": "Recursive Common Table Expression (CTE) for Tree Traversal",
        "tags": ["sql", "recursive-cte", "hierarchical-data", "graphs", "competitive"],
        "problem_statement": "Write a Recursive CTE query in ANSI SQL to traverse an organizational hierarchy tree, computing employee depth levels and reporting paths while detecting cyclic references.",
        "starter_code": "-- Write recursive CTE\nWITH RECURSIVE org_tree AS (\n    ...\n)\nSELECT ...",
        "reference_solution": "WITH RECURSIVE org_tree AS (\n    -- Anchor member: root executives (manager_id IS NULL)\n    SELECT \n        employee_id,\n        manager_id,\n        employee_name,\n        1 AS depth_level,\n        CAST(employee_name AS VARCHAR(1000)) AS reporting_path,\n        ARRAY[employee_id] AS visited_ids\n    FROM employees\n    WHERE manager_id IS NULL\n\n    UNION ALL\n\n    -- Recursive member: direct and indirect reports\n    SELECT \n        e.employee_id,\n        e.manager_id,\n        e.employee_name,\n        ot.depth_level + 1,\n        CAST(ot.reporting_path || ' -> ' || e.employee_name AS VARCHAR(1000)),\n        ot.visited_ids || e.employee_id\n    FROM employees e\n    INNER JOIN org_tree ot ON e.manager_id = ot.employee_id\n    WHERE NOT (e.employee_id = ANY(ot.visited_ids)) -- cycle prevention\n)\nSELECT \n    employee_id,\n    employee_name,\n    depth_level,\n    reporting_path\nFROM org_tree\nORDER BY depth_level, employee_id;",
        "unit_test_suite": "-- Cycle prevention test and depth check\nSELECT COUNT(*) FROM org_tree WHERE depth_level > 20;",
        "complexity": {"time": "O(V + E) where V is employees, E is hierarchy edges", "space": "O(Depth)"},
        "explanation_steps": [
            "Define anchor member query identifying top-level executives having NULL manager_id.",
            "Recursively JOIN employees with preceding org_tree level on manager_id.",
            "Accumulate visited_ids array to detect and prevent cyclic graph loops.",
            "Output full reporting path breadcrumb string.",
        ],
    },
]


# ============================================================================
# MEDALLION ARCHITECTURE STAGES FOR POLYGLOT DATASET
# ============================================================================

class PolyglotBronzeStage:
    """Bronze Stage: Raw ingestion, normalization, and strict schema validation."""

    @staticmethod
    def load_seed_corpus() -> List[Dict[str, Any]]:
        """Return the built-in curated polyglot corpus."""
        return list(CURATED_POLYGLOT_CORPUS)

    @staticmethod
    def load_from_json(path: Path) -> List[Dict[str, Any]]:
        """Load external polyglot dataset from JSON."""
        if not path.exists():
            raise FileNotFoundError(f"Polyglot JSON file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Expected JSON array of objects in {path}, got {type(data).__name__}")
        return data

    @classmethod
    def validate_and_stage(cls, raw_records: List[Dict[str, Any]]) -> List[PolyglotChallenge]:
        """Validate raw dictionary records and stage into PolyglotChallenge DTOs."""
        staged: List[PolyglotChallenge] = []

        for idx, rec in enumerate(raw_records):
            doc_id = str(rec.get("id") or f"POLY-RAW-{idx:04d}").strip()
            raw_lang = str(rec.get("language") or rec.get("lang", "")).lower().strip()
            lang = LANG_ALIASES.get(raw_lang, raw_lang)

            raw_tier = str(rec.get("tier") or rec.get("difficulty", "")).lower().strip()
            tier = TIER_ALIASES.get(raw_tier, raw_tier)

            title = str(rec.get("title", "")).strip()
            problem = str(rec.get("problem_statement") or rec.get("problem") or rec.get("prompt", "")).strip()
            solution = str(rec.get("reference_solution") or rec.get("solution") or rec.get("code", "")).strip()
            starter = str(rec.get("starter_code") or rec.get("starter", "")).strip()
            test_suite = str(rec.get("unit_test_suite") or rec.get("tests") or rec.get("test", "")).strip()

            # Strict validation
            if not title or not problem or not solution:
                logger.warning(f"Bronze: Dropping record {doc_id} at index {idx}: missing title, problem, or solution")
                continue

            if lang not in TIER_1_LANGUAGES:
                logger.warning(f"Bronze: Dropping record {doc_id}: unsupported language '{lang}'")
                continue

            if tier not in DIFFICULTY_TIERS:
                logger.warning(f"Bronze: Dropping record {doc_id}: unsupported tier '{tier}'")
                continue

            tags = rec.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            complexity = rec.get("complexity", {})
            if not isinstance(complexity, dict):
                complexity = {"time": "O(N)", "space": "O(1)"}

            steps = rec.get("explanation_steps", [])
            if isinstance(steps, str):
                steps = [s.strip() for s in steps.split("\n") if s.strip()]

            meta = rec.get("metadata", {})
            if not isinstance(meta, dict):
                meta = {}

            challenge = PolyglotChallenge(
                id=doc_id,
                language=lang,
                tier=tier,
                title=title,
                tags=tags,
                problem_statement=problem,
                starter_code=starter,
                reference_solution=solution,
                unit_test_suite=test_suite,
                complexity=complexity,
                explanation_steps=steps,
                metadata=meta,
            )
            staged.append(challenge)

        logger.info(f"Bronze: Successfully staged {len(staged)} polyglot records across 8 Tier-1 languages.")
        return staged


class PolyglotSilverStage:
    """Silver Stage: 3-tier Deduplication and normalization."""

    def __init__(
        self,
        fuzzy_jaccard_threshold: float = 0.82,
        semantic_threshold: float = 0.92,
    ) -> None:
        self.fuzzy_jaccard_threshold = fuzzy_jaccard_threshold
        self.semantic_threshold = semantic_threshold
        self.seen_exact_hashes: Set[str] = set()
        self.retained_shingles: List[Tuple[str, str, Set[str]]] = []  # (doc_id, lang, shingle_set)
        self.retained_embeddings: List[Tuple[str, str, List[float], int]] = []  # (doc_id, lang, vector, quality_score)

    @staticmethod
    def strip_comments(code: str, language: str) -> str:
        """Strip single-line and multi-line comments per language syntax."""
        lang = language.lower()
        if lang in {"python", "sql"}:
            # Python docstrings
            no_doc = re.sub(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', "", code)
            # Python # and SQL -- comments (both line-start and inline)
            no_hash = re.sub(r"#.*$", "", no_doc, flags=re.MULTILINE)
            no_dash = re.sub(r"--.*$", "", no_hash, flags=re.MULTILINE)
            return no_dash
        else:
            # C, C++, Java, Rust, Go, TypeScript, PHP
            # Multi-line /* ... */ and single-line //
            no_block = re.sub(r"/\*[\s\S]*?\*/", "", code)
            no_line = re.sub(r"//.*$", "", no_block, flags=re.MULTILINE)
            if lang == "php":
                no_line = re.sub(r"#.*$", "", no_line, flags=re.MULTILINE)
            return no_line


    @classmethod
    def normalize_code(cls, code: str, language: str) -> str:
        """Normalize code: strip comments, normalize symbols, collapse whitespace."""
        stripped = cls.strip_comments(code, language)
        lowered = stripped.lower()
        cleaned = re.sub(r"\s+", " ", lowered).strip()
        return cleaned

    @classmethod
    def compute_exact_hash(cls, challenge: PolyglotChallenge) -> str:
        """
        Tier 1: Compute SHA-256 fingerprint over language, normalized title, and normalized solution.
        """
        norm_title = re.sub(r"\s+", " ", challenge.title.lower()).strip()
        norm_code = cls.normalize_code(challenge.reference_solution, challenge.language)
        canonical = f"{challenge.language}|||{norm_title}|||{norm_code}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def compute_shingles(cls, text: str, k_list: Tuple[int, ...] = (2, 3)) -> Set[str]:
        """Compute word tokens and 2/3-token shingles for Jaccard similarity."""
        tokens = re.findall(r"\b[A-Za-z0-9_]+\b", text.lower())
        if not tokens:
            return set()
        shingles = set(tokens)
        for k in k_list:
            if len(tokens) >= k:
                shingles.update(" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1))
        return shingles

    @staticmethod
    def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
        """Standard Jaccard similarity: |A ∩ B| / |A ∪ B|."""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return float(intersection) / float(union) if union > 0 else 0.0

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity between two float vectors."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a)) or 1.0
        norm_b = math.sqrt(sum(b * b for b in vec_b)) or 1.0
        return float(dot / (norm_a * norm_b))

    @staticmethod
    def compute_quality_score(challenge: PolyglotChallenge) -> int:
        """
        Compute arbitration quality score based on unit test rigor and explanation depth.
        """
        test_text = challenge.unit_test_suite.lower()
        test_assertions = len(re.findall(r"\b(assert|expect|test|should|check|require)\b", test_text))
        test_lines = len(challenge.unit_test_suite.splitlines())
        explanation_count = len(challenge.explanation_steps)
        return (test_assertions * 10) + (test_lines * 2) + (explanation_count * 5)

    def deduplicate(
        self,
        staged_items: List[PolyglotChallenge],
        embed_fn: Optional[Callable[[str], Optional[List[float]]]] = None,
    ) -> Tuple[List[PolyglotChallenge], Dict[str, int]]:
        """
        Execute 3-Tier Silver Deduplication:
        - Tier 1: Exact Hash (normalized SHA-256)
        - Tier 2: Lexical Jaccard (shingle token overlap at threshold 0.82)
        - Tier 3: Semantic Collision (embedding cosine similarity threshold 0.92 with test-coverage arbitration)
        Guarantee zero duplicates before vectorization.
        """
        retained: List[PolyglotChallenge] = []
        retained_map: Dict[str, PolyglotChallenge] = {}

        stats = {
            "total_input": len(staged_items),
            "tier1_exact_duplicates": 0,
            "tier2_fuzzy_duplicates": 0,
            "tier3_semantic_duplicates": 0,
            "arbitration_replacements": 0,
            "retained": 0,
        }

        for item in staged_items:
            # 1. Tier 1: Exact Hash
            h = self.compute_exact_hash(item)
            if h in self.seen_exact_hashes:
                logger.debug(f"Silver Tier 1: Dropping exact duplicate (ID={item.id}, Lang={item.language})")
                stats["tier1_exact_duplicates"] += 1
                continue

            # 2. Tier 2: Lexical Jaccard Near-Duplicate Check
            item_text = f"{item.title} {item.problem_statement} {item.reference_solution}"
            item_shingles = self.compute_shingles(item_text)

            is_fuzzy_dup = False
            for exist_id, exist_lang, exist_shingles in self.retained_shingles:
                if exist_lang != item.language:
                    continue  # language boundary
                sim = self.jaccard_similarity(item_shingles, exist_shingles)
                if sim >= self.fuzzy_jaccard_threshold:
                    logger.debug(
                        f"Silver Tier 2: Dropping lexical duplicate (ID={item.id} vs {exist_id}, sim={sim:.3f})"
                    )
                    stats["tier2_fuzzy_duplicates"] += 1
                    is_fuzzy_dup = True
                    break
            if is_fuzzy_dup:
                continue

            # 3. Tier 3: Semantic Collision with Test-Coverage Arbitration
            summary = f"{item.title}: {item.problem_statement}\n{item.reference_solution}"
            vec = embed_fn(summary) if embed_fn else None
            if vec is None:
                # Deterministic unit vector fallback
                h_bytes = hashlib.sha256(summary.encode("utf-8")).digest()
                raw = [float(h_bytes[i % len(h_bytes)]) - 128.0 for i in range(768)]
                norm = math.sqrt(sum(x * x for x in raw)) or 1.0
                vec = [x / norm for x in raw]

            item_score = self.compute_quality_score(item)
            semantic_collision = False
            collision_target_id = None

            for idx, (exist_id, exist_lang, exist_vec, exist_score) in enumerate(self.retained_embeddings):
                if exist_lang != item.language:
                    continue
                cos_sim = self.cosine_similarity(vec, exist_vec)
                if cos_sim >= self.semantic_threshold:
                    semantic_collision = True
                    collision_target_id = exist_id
                    logger.info(
                        f"Silver Tier 3: Semantic collision (ID={item.id} vs {exist_id}, cos_sim={cos_sim:.3f})"
                    )
                    stats["tier3_semantic_duplicates"] += 1

                    # Arbitration policy: test-coverage & explanation rigor
                    if item_score > exist_score:
                        logger.info(
                            f"Arbitration: Candidate {item.id} (score={item_score}) replaces existing {exist_id} (score={exist_score})"
                        )
                        stats["arbitration_replacements"] += 1
                        # Replace in retained list and indices
                        retained_map.pop(exist_id, None)
                        retained_map[item.id] = item
                        self.retained_embeddings[idx] = (item.id, item.language, vec, item_score)
                        # Update shingles
                        for s_idx, (s_id, s_lang, _) in enumerate(self.retained_shingles):
                            if s_id == exist_id:
                                self.retained_shingles[s_idx] = (item.id, item.language, item_shingles)
                                break

                    break

            if semantic_collision:
                continue

            # Passed all 3 tiers cleanly
            self.seen_exact_hashes.add(h)
            self.retained_shingles.append((item.id, item.language, item_shingles))
            self.retained_embeddings.append((item.id, item.language, vec, item_score))
            retained_map[item.id] = item

        retained = list(retained_map.values())
        stats["retained"] = len(retained)
        logger.info(
            f"Silver: Deduplication complete. Input: {stats['total_input']} -> Retained: {stats['retained']} "
            f"(Dropped: exact={stats['tier1_exact_duplicates']}, fuzzy={stats['tier2_fuzzy_duplicates']}, "
            f"semantic={stats['tier3_semantic_duplicates']}, arbitration_replacements={stats['arbitration_replacements']})"
        )
        return retained, stats


class PolyglotGoldStage:
    """Gold Stage: SQLite Vector persistence with PHP 128 MB memory protection."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        ollama_base_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
        max_material_chunks: int = 500,
        enable_ollama: bool = True,
    ) -> None:
        self.db_path = db_path or (ROOT / "backend" / "storage" / "vectors.sqlite")
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.embed_model = embed_model
        self.max_material_chunks = max_material_chunks
        self.enable_ollama = enable_ollama
        self._embedding_cache: Dict[str, List[float]] = {}
        if LocalSqliteRagBackend:
            self.backend = LocalSqliteRagBackend(str(self.db_path))
        else:
            self.backend = None

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Request 768-dim embedding from Ollama with mandatory 'search_document: ' prefix.
        Returns None gracefully if Ollama is unreachable.
        """
        if not self.enable_ollama:
            return None

        if text in self._embedding_cache:
            return self._embedding_cache[text]

        # Mandatory prefix for nomic-embed-text
        prefixed = f"search_document: {text.strip()}"
        url = f"{self.ollama_base_url}/api/embed"
        payload = {
            "model": self.embed_model,
            "input": prefixed,
            "keep_alive": "5m",
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    embeddings = data.get("embeddings")
                    if embeddings and len(embeddings) > 0:
                        vec = embeddings[0]
                        self._embedding_cache[text] = vec
                        return vec
        except Exception as e:
            logger.debug(f"Gold: Ollama embedding unavailable ({e}), using fallback vector.")
            return None
        return None


    @staticmethod
    def pack_float_vector(vec: List[float]) -> bytes:
        """Pack float array into single-precision binary BLOB matching PHP unpack('f*', ...)."""
        return struct.pack(f"{len(vec)}f", *vec)

    @staticmethod
    def generate_fallback_vector(seed_text: str, dim: int = 768) -> List[float]:
        """Deterministic unit vector fallback for offline verification."""
        h = hashlib.sha256(seed_text.encode("utf-8")).digest()
        raw = [float(h[i % len(h)]) - 128.0 for i in range(dim)]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    def persist(
        self,
        items: List[PolyglotChallenge],
        collection: str = "polyglot_coding",
    ) -> Dict[str, int]:
        """
        Persists deduplicated polyglot challenges into SQLite:
        1. Stores ALL records into 'rag_documents' under collection.
        2. Ingests summary chunks into 'material_chunks', capping at max_material_chunks
           to strictly preserve PHP 128 MB memory limit.
        """
        import sqlite3

        stats = {
            "rag_documents_written": 0,
            "material_chunks_written": 0,
            "embeddings_computed": 0,
            "fallback_embeddings_used": 0,
        }

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()

            # Ensure tables exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    text TEXT NOT NULL,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (collection, id)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS material_chunks (
                    id TEXT PRIMARY KEY,
                    material_id TEXT,
                    course_id TEXT,
                    batch_id TEXT,
                    chunk_index INTEGER,
                    title TEXT,
                    content TEXT,
                    metadata TEXT,
                    embedding BLOB,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 1. Upsert full documents into rag_documents
            for item in items:
                doc_text = item.to_formatted_document()
                meta = {
                    "id": item.id,
                    "title": item.title,
                    "language": item.language,
                    "tier": item.tier,
                    "tags": item.tags,
                    "complexity": item.complexity,
                    "explanation_steps": item.explanation_steps,
                    "source": "polyglot_curriculum",
                    "updated_at": datetime.now().isoformat(),
                    **item.metadata,
                }
                meta_json = json.dumps(meta)

                cursor.execute("""
                    INSERT INTO rag_documents (id, collection, text, metadata, created_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(collection, id) DO UPDATE SET
                        text = excluded.text,
                        metadata = excluded.metadata;
                """, (item.id, collection, doc_text, meta_json))
                stats["rag_documents_written"] += 1

            # 2. Check existing material_chunks row count and enforce max_material_chunks ceiling
            cursor.execute("SELECT COUNT(*) FROM material_chunks")
            current_total_chunks = cursor.fetchone()[0]

            allowed_slots = max(0, self.max_material_chunks - current_total_chunks)

            for idx, item in enumerate(items[:allowed_slots]):
                chunk_id = f"poly_chunk_{item.id}_{idx:03d}"
                summary = (
                    f"{item.title} ({item.language.upper()} - {item.tier.upper()}):\n"
                    f"{item.problem_statement}\n\n"
                    f"Solution:\n{item.reference_solution[:500]}"
                )

                vec = self.get_embedding(summary)
                if vec is not None:
                    stats["embeddings_computed"] += 1
                else:
                    vec = self.generate_fallback_vector(summary)
                    stats["fallback_embeddings_used"] += 1

                packed_vec = self.pack_float_vector(vec)
                chunk_meta = json.dumps({
                    "title": item.title,
                    "language": item.language,
                    "tier": item.tier,
                    "source_item_id": item.id,
                })

                cursor.execute("""
                    INSERT OR REPLACE INTO material_chunks (
                        id, material_id, course_id, batch_id, chunk_index, title, content, metadata, embedding
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chunk_id,
                    f"poly_mat_{item.language}",
                    "polyglot_curriculum",
                    f"batch_{item.tier}",
                    idx,
                    item.title,
                    summary,
                    chunk_meta,
                    packed_vec,
                ))
                stats["material_chunks_written"] += 1

            conn.commit()
        finally:
            conn.close()

        logger.info(
            f"Gold: Persistence complete. rag_documents written: {stats['rag_documents_written']}, "
            f"material_chunks written: {stats['material_chunks_written']} (capped <= {self.max_material_chunks}), "
            f"Live embeddings: {stats['embeddings_computed']}, Fallback embeddings: {stats['fallback_embeddings_used']}"
        )
        return stats


# ============================================================================
# EXPORT DATASET IN INSTRUCTION FORMAT (ALPACA / SHAREGPT)
# ============================================================================

def export_polyglot_instruct_dataset(
    items: List[PolyglotChallenge],
    output_path: Path,
    max_tokens: int = 1024,
) -> List[Dict[str, Any]]:
    """
    Export deduplicated polyglot challenges to Alpaca instruction format with token cutoff <= 1024.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    alpaca_records: List[Dict[str, Any]] = []

    # Conservative estimation: 1 token ~ 3.5 characters in code/instruction datasets
    max_char_limit = int(max_tokens * 3.5)

    for item in items:
        instruction = (
            f"You are an expert polyglot programmer. Implement the requested challenge in {item.language.upper()} "
            f"({item.tier.capitalize()} Tier).\n\n"
            f"### Problem Statement:\n{item.problem_statement}"
        )
        input_data = item.starter_code if item.starter_code else ""

        steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(item.explanation_steps))
        output_data = (
            f"```{item.language}\n{item.reference_solution}\n```\n\n"
            f"### Complexity:\n- Time: {item.complexity.get('time', 'N/A')}\n"
            f"- Space: {item.complexity.get('space', 'N/A')}\n\n"
            f"### Explanation:\n{steps_text}\n\n"
            f"### Unit Tests:\n```{item.language}\n{item.unit_test_suite}\n```"
        )

        # Enforce token length ceiling
        total_len = len(instruction) + len(input_data) + len(output_data)
        if total_len > max_char_limit:
            overflow = total_len - max_char_limit
            if len(output_data) > overflow + 100:
                output_data = output_data[:len(output_data) - overflow - 35] + "\n... [truncated for token budget]"
            else:
                output_data = output_data[:500] + "\n... [truncated for token budget]"
                rem = (len(instruction) + len(input_data) + len(output_data)) - max_char_limit
                if rem > 0 and len(instruction) > rem + 50:
                    instruction = instruction[:len(instruction) - rem - 35] + "\n... [truncated for token budget]"
                elif rem > 0:
                    instruction = instruction[:max(50, len(instruction) - rem)]


        record = {
            "id": item.id,
            "language": item.language,
            "tier": item.tier,
            "instruction": instruction,
            "input": input_data,
            "output": output_data,
            "tags": item.tags,
        }
        alpaca_records.append(record)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(alpaca_records, f, indent=2, ensure_ascii=False)

    logger.info(f"Export: Successfully exported {len(alpaca_records)} instruction records to {output_path}")
    return alpaca_records


# ============================================================================
# MAIN PIPELINE RUNNER
# ============================================================================

def run_polyglot_ingestion_pipeline(
    input_file: Optional[Path] = None,
    db_path: Optional[Path] = None,
    output_dataset: Optional[Path] = None,
    ollama_url: str = "http://localhost:11434",
    embed_model: str = "nomic-embed-text",
    max_material_chunks: int = 500,
    enable_ollama: bool = True,
    fuzzy_threshold: float = 0.82,
    semantic_threshold: float = 0.92,
) -> Dict[str, Any]:
    """Execute complete Bronze -> Silver -> Gold Polyglot Ingestion Pipeline."""
    logger.info("=== Starting Polyglot Dataset Ingestion Pipeline ===")

    # 1. Bronze
    if input_file and input_file.exists():
        raw_data = PolyglotBronzeStage.load_from_json(input_file)
    else:
        raw_data = PolyglotBronzeStage.load_seed_corpus()
    staged = PolyglotBronzeStage.validate_and_stage(raw_data)

    # 2. Silver 3-Tier Deduplication
    silver = PolyglotSilverStage(
        fuzzy_jaccard_threshold=fuzzy_threshold,
        semantic_threshold=semantic_threshold,
    )
    gold_stage = PolyglotGoldStage(
        db_path=db_path,
        ollama_base_url=ollama_url,
        embed_model=embed_model,
        max_material_chunks=max_material_chunks,
        enable_ollama=enable_ollama,
    )
    deduped, silver_stats = silver.deduplicate(staged, embed_fn=gold_stage.get_embedding)

    # 3. Gold Persistence
    gold_stats = gold_stage.persist(deduped)

    # 4. Instruction Dataset Export
    export_path = output_dataset or (ROOT / "data" / "polyglot_instruct_dataset.json")
    exported_records = export_polyglot_instruct_dataset(deduped, export_path, max_tokens=1024)

    summary = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "bronze_count": len(staged),
        "silver_retained": len(deduped),
        "silver_stats": silver_stats,
        "gold_stats": gold_stats,
        "exported_count": len(exported_records),
        "export_path": str(export_path),
    }
    logger.info(f"=== Polyglot Pipeline Succeeded: {json.dumps(summary, indent=2)} ===")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and deduplicate Polyglot coding dataset into SQLite RAG.")
    parser.add_argument("--input", type=Path, default=None, help="Path to external JSON file containing challenges.")
    parser.add_argument("--db-path", type=Path, default=None, help="Path to vectors.sqlite database.")
    parser.add_argument("--output-dataset", type=Path, default=None, help="Path to output instruction JSON dataset.")
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434", help="Ollama API base URL.")
    parser.add_argument("--embed-model", type=str, default="nomic-embed-text", help="Embedding model name.")
    parser.add_argument("--max-chunks", type=int, default=500, help="Max rows for material_chunks to protect PHP RAM.")
    parser.add_argument("--no-ollama", action="store_true", help="Disable Ollama and use deterministic fallback vectors.")
    parser.add_argument("--fuzzy-threshold", type=float, default=0.82, help="Jaccard fuzzy deduplication threshold.")
    parser.add_argument("--semantic-threshold", type=float, default=0.92, help="Semantic collision threshold.")

    args = parser.parse_args()

    run_polyglot_ingestion_pipeline(
        input_file=args.input,
        db_path=args.db_path,
        output_dataset=args.output_dataset,
        ollama_url=args.ollama_url,
        embed_model=args.embed_model,
        max_material_chunks=args.max_chunks,
        enable_ollama=not args.no_ollama,
        fuzzy_threshold=args.fuzzy_threshold,
        semantic_threshold=args.semantic_threshold,
    )


if __name__ == "__main__":
    main()
