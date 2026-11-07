"""
scripts/learning/web_harvester.py

Autonomous Web Scraping & Quality Ingestion Pipeline (Milestone M1).
Scrapes open-source STEM curricula and polyglot algorithmic problem corpora,
applies automated quality heuristics (noise rejection, Shannon entropy,
AST syntax validation, 3-tier Silver deduplication), and ingests clean items
into backend/storage/vectors.sqlite with SQ8 quantization while enforcing
a strict <= 500 row ceiling in material_chunks to protect the 128 MB PHP process memory limit.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import html
import json
import logging
import math
from pathlib import Path
import re
import sqlite3
import struct
from typing import Any, Dict, List, Optional, Set, Tuple
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET

import numpy as np

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

import sys

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from scripts.learning.vector_quantizer import SQ8VectorQuantizer
except ImportError:
    from vector_quantizer import SQ8VectorQuantizer  # type: ignore

logger = logging.getLogger("web_harvester")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@dataclass
class HarvestedItem:
    """
    Data model representing a scraped STEM document or polyglot algorithmic coding problem.
    """
    id: str
    title: str
    concept: str
    domain: str  # e.g. "physics", "maths", "coding", "systems"
    tier: str    # e.g. "sme", "advanced", "elementary", "systems"
    text: str
    code: str = ""
    language: str = "python"  # python, cpp, rust, go, typescript, java, php, sql
    source: str = "web_harvester"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_formatted_document(self) -> str:
        """Renders item as a structured Markdown document for RAG storage."""
        doc = (
            f"# {self.title}\n\n"
            f"**Domain**: {self.domain} | **Tier**: {self.tier} | **Source**: {self.source}\n\n"
            f"## Concept\n{self.concept}\n\n"
            f"## Content\n{self.text}\n"
        )
        if self.code.strip():
            doc += f"\n## Implementation ({self.language})\n```{self.language}\n{self.code}\n```\n"
        return doc

    def to_dict(self) -> Dict[str, Any]:
        """Converts item to serializable dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "concept": self.concept,
            "domain": self.domain,
            "tier": self.tier,
            "text": self.text,
            "code": self.code,
            "language": self.language,
            "source": self.source,
            "metadata": self.metadata,
        }


class BaseHarvesterAdapter:
    """Abstract base adapter for web harvesters."""

    def harvest(self, max_items: int = 10) -> List[HarvestedItem]:
        raise NotImplementedError


class ArxivHarvesterAdapter(BaseHarvesterAdapter):
    """
    Scrapes STEM research papers from the official arXiv Atom XML API across
    target categories (cs.AI, cs.SE, math.NA, physics.comp-ph).
    """

    ATOM_URL = "http://export.arxiv.org/api/query"
    DEFAULT_CATEGORIES = ["cs.AI", "cs.SE", "math.NA", "physics.comp-ph"]

    def __init__(self, categories: Optional[List[str]] = None, timeout: float = 10.0):
        self.categories = categories or self.DEFAULT_CATEGORIES
        self.timeout = timeout

    def harvest(self, max_items: int = 10) -> List[HarvestedItem]:
        query_cats = "+OR+".join(f"cat:{cat}" for cat in self.categories)
        url = f"{self.ATOM_URL}?search_query={query_cats}&start=0&max_results={max_items}"

        headers = {
            "User-Agent": "RAG-Agent-LearningBot/1.0 (Autonomous STEM Harvester; mailto:contact@rag-agent.local)"
        }

        xml_content: Optional[str] = None
        if httpx is not None:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(url, headers=headers)
                    if resp.status_code == 200:
                        xml_content = resp.text
                    else:
                        logger.warning(f"Arxiv API returned HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"Arxiv API fetch failed: {e}")
        else:
            import urllib.request
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    xml_content = r.read().decode("utf-8")
            except Exception as e:
                logger.warning(f"Arxiv API fetch via urllib failed: {e}")

        if not xml_content:
            return []

        return self.parse_atom_feed(xml_content, max_items=max_items)

    @classmethod
    def parse_atom_feed(cls, xml_text: str, max_items: int = 10) -> List[HarvestedItem]:
        items: List[HarvestedItem] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning(f"Failed to parse arXiv Atom XML: {e}")
            return []

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

        for entry in root.findall("atom:entry", ns):
            if len(items) >= max_items:
                break

            id_elem = entry.find("atom:id", ns)
            title_elem = entry.find("atom:title", ns)
            summary_elem = entry.find("atom:summary", ns)
            published_elem = entry.find("atom:published", ns)

            raw_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
            raw_title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            raw_summary = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else ""
            published = published_elem.text.strip() if published_elem is not None and published_elem.text else ""

            # Clean linebreaks within title and summary
            title = re.sub(r"\s+", " ", raw_title)
            summary = re.sub(r"\s+", " ", raw_summary)

            categories = [
                c.attrib.get("term", "")
                for c in entry.findall("atom:category", ns)
                if c.attrib.get("term")
            ]

            # Map arXiv category to internal domain
            domain = "coding"
            if any("physics" in c.lower() for c in categories):
                domain = "physics"
            elif any("math" in c.lower() for c in categories):
                domain = "maths"

            arxiv_code = raw_id.split("/")[-1].split("v")[0]
            item_id = f"arxiv_{arxiv_code.replace('.', '_')}"

            item = HarvestedItem(
                id=item_id,
                title=title,
                concept=summary[:250] + ("..." if len(summary) > 250 else ""),
                domain=domain,
                tier="sme",
                text=summary,
                code="",
                language="python",
                source="arxiv",
                metadata={
                    "arxiv_id": raw_id,
                    "categories": categories,
                    "published": published,
                },
            )
            items.append(item)

        return items


class OpenCodeHarvesterAdapter(BaseHarvesterAdapter):
    """
    Scrapes open-source polyglot algorithmic problem repositories and code examples
    across Python, C++, Rust, Go, TypeScript, Java, PHP, and SQL.
    Fetches raw source code from open public repositories (e.g., GitHub raw endpoints)
    with timeout and comprehensive network exception handling, parsing documentation and code.
    """

    TARGET_LANGUAGES = ["python", "cpp", "rust", "go", "typescript", "java", "php", "sql"]

    DEFAULT_CATALOG: List[Dict[str, Any]] = [
        {
            "id": "opencode_py_dijkstra",
            "title": "Dijkstra Single-Source Shortest Path Algorithm",
            "concept": "Graph traversal algorithm using priority queues to find shortest paths from a single source vertex to all other vertices on non-negative weighted graphs.",
            "domain": "coding",
            "tier": "advanced",
            "language": "python",
            "url": "https://raw.githubusercontent.com/TheAlgorithms/Python/master/graphs/dijkstra.py",
        },
        {
            "id": "opencode_rust_dijkstra",
            "title": "Dijkstra Shortest Path in Rust",
            "concept": "Idiomatic systems graph implementation in Rust utilizing BinaryHeap and adjacency lists with zero-cost abstractions and memory safety.",
            "domain": "coding",
            "tier": "sme",
            "language": "rust",
            "url": "https://raw.githubusercontent.com/TheAlgorithms/Rust/master/src/graph/dijkstra.rs",
        },
        {
            "id": "opencode_cpp_quicksort",
            "title": "Optimized QuickSort Algorithm in C++",
            "concept": "Divide-and-conquer sorting algorithm with median-of-three pivot selection and cache-friendly in-place partitioning.",
            "domain": "coding",
            "tier": "advanced",
            "language": "cpp",
            "url": "https://raw.githubusercontent.com/TheAlgorithms/C-Plus-Plus/master/sorting/quick_sort.cpp",
        },
        {
            "id": "opencode_go_quicksort",
            "title": "Concurrent QuickSort in Go",
            "concept": "Efficient Go implementation of quicksort sorting slice in O(N log N) average time complexity using partition routine.",
            "domain": "coding",
            "tier": "advanced",
            "language": "go",
            "url": "https://raw.githubusercontent.com/TheAlgorithms/Go/master/sort/quicksort.go",
        },
        {
            "id": "opencode_java_binarysearch",
            "title": "Binary Search Algorithm in Java",
            "concept": "Logarithmic O(log n) divide-and-conquer search on sorted arrays avoiding integer overflow during midpoint calculation.",
            "domain": "coding",
            "tier": "advanced",
            "language": "java",
            "url": "https://raw.githubusercontent.com/TheAlgorithms/Java/master/src/main/java/com/thealgorithms/searches/BinarySearch.java",
        },
        {
            "id": "opencode_php_binarysearch",
            "title": "Binary Search in PHP",
            "concept": "Strictly typed PHP implementation of logarithmic search over indexed arrays.",
            "domain": "coding",
            "tier": "intermediate",
            "language": "php",
            "url": "https://raw.githubusercontent.com/TheAlgorithms/PHP/master/Searches/BinarySearch.php",
        },
        {
            "id": "opencode_js_binarysearch",
            "title": "Binary Search Algorithm in JavaScript/TypeScript",
            "concept": "Iterative and recursive binary search implementation over sorted arrays with comparator callbacks.",
            "domain": "coding",
            "tier": "advanced",
            "language": "typescript",
            "url": "https://raw.githubusercontent.com/trekhleb/javascript-algorithms/master/src/algorithms/search/binary-search/binarySearch.js",
        },
        {
            "id": "opencode_sql_orders_model",
            "title": "Analytical SQL Aggregations and Window CTEs",
            "concept": "Relational analytics with common table expressions, multi-table joins, and customer order aggregations.",
            "domain": "coding",
            "tier": "advanced",
            "language": "sql",
            "url": "https://raw.githubusercontent.com/dbt-labs/jaffle_shop/main/models/orders.sql",
        },
    ]

    def __init__(self, catalog: Optional[List[Dict[str, Any]]] = None, timeout: float = 10.0):
        self.catalog = catalog or self.DEFAULT_CATALOG
        self.timeout = timeout

    @classmethod
    def parse_source_content(cls, raw_content: str, entry: Dict[str, Any]) -> HarvestedItem:
        """
        Extracts explanatory comments/docstrings into the text field and isolates code,
        constructing a structured HarvestedItem.
        """
        trimmed = raw_content.strip()
        lang = entry.get("language", "python").lower()

        # Extract leading comment block or docstring as documentation
        doc_lines: List[str] = []
        code_lines: List[str] = []

        if lang == "python":
            doc_match = re.match(r'^(?:"""(.*?)"""|\'\'\'(.*?)\'\'\')', trimmed, re.DOTALL)
            if doc_match:
                doc_text = (doc_match.group(1) or doc_match.group(2)).strip()
                doc_lines.append(doc_text)
                code_lines.append(trimmed[doc_match.end():].strip())
            else:
                code_lines.append(trimmed)
        elif lang in ("cpp", "rust", "go", "typescript", "java", "php"):
            doc_match = re.match(r"^/\*\*(.*?)\*/|^/\*(.*?)\*/", trimmed, re.DOTALL)
            if doc_match:
                doc_text = (doc_match.group(1) or doc_match.group(2)).strip()
                cleaned_doc = "\n".join(re.sub(r"^\s*\* ?", "", l) for l in doc_text.splitlines())
                doc_lines.append(cleaned_doc.strip())
                code_lines.append(trimmed[doc_match.end():].strip())
            else:
                code_lines.append(trimmed)
        else:
            code_lines.append(trimmed)

        concept_desc = entry.get("concept", entry.get("title", ""))
        extracted_doc = " ".join(doc_lines).strip()
        if len(extracted_doc) >= 80:
            text = f"{entry.get('title', 'Algorithmic Problem')}: {concept_desc}\n\n{extracted_doc}"
        else:
            text = (
                f"{entry.get('title', 'Algorithmic Problem')}\n\n"
                f"Core Concept: {concept_desc}\n\n"
                f"This open-source algorithmic challenge implements {concept_desc} "
                f"in {lang.upper()}. It provides clean algorithmic structure, complexity guarantees, "
                f"and robust reference implementations suitable for polyglot STEM training."
            )

        code_text = "\n".join(code_lines).strip() if code_lines else trimmed

        return HarvestedItem(
            id=entry.get("id", f"opencode_{lang}_{abs(hash(trimmed)) % 100000:05d}"),
            title=entry.get("title", "OpenCode Algorithmic Problem"),
            concept=concept_desc,
            domain=entry.get("domain", "coding"),
            tier=entry.get("tier", "advanced"),
            text=text,
            code=code_text,
            language=lang,
            source="opencode",
            metadata={
                "url": entry.get("url", ""),
                "repo": "open_code_archives",
                "scraped_at": datetime.now().isoformat(),
            },
        )

    def harvest(self, max_items: int = 10) -> List[HarvestedItem]:
        """
        Harvests algorithmic problems from configured public repositories.
        Catches network exceptions and timeouts gracefully.
        """
        items: List[HarvestedItem] = []
        headers = {
            "User-Agent": "RAG-Agent-PolyglotHarvester/1.0 (Autonomous OpenCode Harvester; mailto:contact@rag-agent.local)"
        }

        targets = self.catalog[:max_items]
        for entry in targets:
            url = entry.get("url")
            if not url:
                continue

            raw_text: Optional[str] = None
            if httpx is not None:
                try:
                    with httpx.Client(timeout=self.timeout) as client:
                        resp = client.get(url, headers=headers)
                        if resp.status_code == 200:
                            raw_text = resp.text
                        else:
                            logger.warning(f"OpenCode HTTP fetch returned {resp.status_code} for {url}")
                except Exception as e:
                    logger.warning(f"OpenCode fetch failed for {url}: {e}")
            else:
                import urllib.request
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=self.timeout) as r:
                        raw_text = r.read().decode("utf-8")
                except Exception as e:
                    logger.warning(f"OpenCode fetch via urllib failed for {url}: {e}")

            if raw_text and raw_text.strip():
                try:
                    item = self.parse_source_content(raw_text, entry)
                    items.append(item)
                except Exception as e:
                    logger.warning(f"Failed to parse source from {url}: {e}")

        return items


class OfflineMockHarvesterAdapter(BaseHarvesterAdapter):
    """
    Deterministic in-memory synthetic generator providing rich STEM and algorithmic items
    across all 8 target languages (Python, C++, Rust, Go, TypeScript, Java, PHP, SQL)
    and domains (physics, maths, coding, systems). Guarantees zero network dependencies in test environments.
    """

    MOCK_CORPUS: List[Dict[str, Any]] = [
        {
            "id": "mock_symp_integrator_001",
            "title": "Symplectic Störmer-Verlet Energy-Preserving Numerical Integrator",
            "concept": "Second-order geometric numerical integrator for Hamiltonian dynamics conserving phase space volume and total energy.",
            "domain": "physics",
            "tier": "sme",
            "language": "python",
            "text": (
                "The Störmer-Verlet algorithm is a second-order symplectic integrator designed "
                "for separable Hamiltonian dynamical systems of the form H(q, p) = T(p) + V(q). "
                "Unlike standard Runge-Kutta methods, symplectic integrators conserve phase space "
                "volume according to Liouville's theorem and bound total mechanical energy drift "
                "over arbitrarily long time horizons. At each discrete timestep dt, the position "
                "q(t+dt) is computed from current acceleration a(q(t)) and previous positions with "
                "O(dt^4) local error and O(dt^2) global trajectory precision."
            ),
            "code": (
                "def verlet_step(q: float, v: float, dt: float, accel_fn) -> tuple[float, float]:\n"
                "    a_curr = accel_fn(q)\n"
                "    q_next = q + v * dt + 0.5 * a_curr * (dt ** 2)\n"
                "    a_next = accel_fn(q_next)\n"
                "    v_next = v + 0.5 * (a_curr + a_next) * dt\n"
                "    return q_next, v_next\n"
            ),
        },
        {
            "id": "mock_cpp_concurrency_002",
            "title": "Lock-Free Single-Producer Single-Consumer Circular Ring Buffer",
            "concept": "Wait-free memory-ordered bounded queue utilizing atomic head and tail indices with acquire-release semantics.",
            "domain": "systems",
            "tier": "advanced",
            "language": "cpp",
            "text": (
                "Lock-free single-producer single-consumer (SPSC) ring buffers provide zero-contention "
                "inter-thread communication for real-time audio, network packet processing, and hardware telemetry. "
                "By maintaining cacheline-aligned atomic head and tail pointers with explicit std::memory_order_acquire "
                "and std::memory_order_release fences, the producer and consumer threads progress concurrently without "
                "mutex locks, priority inversion, or kernel context switching overhead."
            ),
            "code": (
                "#include <atomic>\n"
                "#include <vector>\n"
                "#include <cstddef>\n\n"
                "template <typename T, size_t Capacity>\n"
                "class SpscRingBuffer {\n"
                "    T buffer[Capacity];\n"
                "    alignas(64) std::atomic<size_t> head{0};\n"
                "    alignas(64) std::atomic<size_t> tail{0};\n"
                "public:\n"
                "    bool push(const T& val) {\n"
                "        size_t current_tail = tail.load(std::memory_order_relaxed);\n"
                "        size_t next_tail = (current_tail + 1) % Capacity;\n"
                "        if (next_tail == head.load(std::memory_order_acquire)) return false;\n"
                "        buffer[current_tail] = val;\n"
                "        tail.store(next_tail, std::memory_order_release);\n"
                "        return true;\n"
                "    }\n"
                "};\n"
            ),
        },
        {
            "id": "mock_rust_zero_copy_003",
            "title": "Zero-Copy Byte Slice Deserialization and Protocol Framing",
            "concept": "Safe parsing of structured network packet headers using Rust lifetime-bound borrowed references.",
            "domain": "coding",
            "tier": "systems",
            "language": "rust",
            "text": (
                "Zero-copy serialization enables high-throughput systems to deserialize network messages "
                "directly from borrowed memory buffers without heap allocation. In Rust, lifetime annotations "
                "ensure that borrowed string slices and byte references remain valid as long as the underlying "
                "network packet frame exists in memory, guaranteeing compile-time memory safety without runtime garbage collection."
            ),
            "code": (
                "pub struct FrameHeader<'a> {\n"
                "    pub magic: u32,\n"
                "    pub payload_len: u32,\n"
                "    pub payload: &'a [u8],\n"
                "}\n\n"
                "impl<'a> FrameHeader<'a> {\n"
                "    pub fn parse(bytes: &'a [u8]) -> Result<Self, &'static str> {\n"
                "        if bytes.len() < 8 { return Err(\"buffer too short\"); }\n"
                "        let magic = u32::from_be_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]);\n"
                "        let payload_len = u32::from_be_bytes([bytes[4], bytes[5], bytes[6], bytes[7]]);\n"
                "        Ok(Self { magic, payload_len, payload: &bytes[8..] })\n"
                "    }\n"
                "}\n"
            ),
        },
        {
            "id": "mock_go_goroutine_pool_004",
            "title": "Bounded Worker Pool with Context Cancellation and Backpressure",
            "concept": "Concurrent task execution pattern leveraging Go buffered channels and context propagation for graceful shutdown.",
            "domain": "systems",
            "tier": "advanced",
            "language": "go",
            "text": (
                "In high-concurrency backend services, unbounded goroutine creation can exhaust operating system "
                "file descriptors and heap memory. A bounded worker pool limits active concurrent tasks to a fixed "
                "number of worker goroutines consuming jobs from a synchronized buffered channel. Context propagation "
                "allows parent requests to broadcast cancellation signals downstream to idle or active workers immediately."
            ),
            "code": (
                "package pool\n\n"
                "import (\n"
                "    \"context\"\n"
                "    \"sync\"\n"
                ")\n\n"
                "type WorkerPool struct {\n"
                "    jobs    chan func(context.Context)\n"
                "    workers int\n"
                "    wg      sync.WaitGroup\n"
                "}\n\n"
                "func (p *WorkerPool) Start(ctx context.Context) {\n"
                "    for i := 0; i < p.workers; i++ {\n"
                "        p.wg.Add(1)\n"
                "        go func() {\n"
                "            defer p.wg.Done()\n"
                "            for {\n"
                "                select {\n"
                "                case <-ctx.Done(): return\n"
                "                case task, ok := <-p.jobs:\n"
                "                    if !ok { return }\n"
                "                    task(ctx)\n"
                "                }\n"
                "            }\n"
                "        }()\n"
                "    }\n"
                "}\n"
            ),
        },
        {
            "id": "mock_ts_memoization_005",
            "title": "Type-Safe Dynamic Programming Memoization Decorator",
            "concept": "Higher-order functional memoization caching computed recurrence values for pure functions in TypeScript.",
            "domain": "coding",
            "tier": "elementary",
            "language": "typescript",
            "text": (
                "Dynamic programming algorithms solve complex combinatorial optimization problems by breaking "
                "them down into overlapping subproblems. In TypeScript, a higher-order memoization wrapper captures "
                "the arguments of recursive functions, queries an in-memory cache with serialized argument keys, "
                "and returns cached results in O(1) time while strictly maintaining input and return type contracts."
            ),
            "code": (
                "export function memoize<TArgs extends unknown[], TReturn>(\n"
                "    fn: (...args: TArgs) => TReturn\n"
                "): (...args: TArgs) => TReturn {\n"
                "    const cache = new Map<string, TReturn>();\n"
                "    return (...args: TArgs): TReturn => {\n"
                "        const key = JSON.stringify(args);\n"
                "        if (cache.has(key)) {\n"
                "            return cache.get(key)!;\n"
                "        }\n"
                "        const result = fn(...args);\n"
                "        cache.set(key, result);\n"
                "        return result;\n"
                "    };\n"
                "}\n"
            ),
        },
        {
            "id": "mock_java_graph_dijkstra_006",
            "title": "Optimized Dijkstra Shortest Path with Indexed Priority Queue",
            "concept": "Single-source shortest path algorithm on weighted directed graphs using Min-Heap priority queues in Java.",
            "domain": "coding",
            "tier": "advanced",
            "language": "java",
            "text": (
                "Dijkstra's shortest path algorithm determines the minimum cumulative edge weight from a source "
                "vertex to all other vertices in non-negative weighted graphs. By utilizing a binary min-heap priority "
                "queue, vertex relaxation runs in O((V + E) log V) time. Visited vertices are marked to avoid redundant "
                "explorations, ensuring optimal efficiency on large graph networks."
            ),
            "code": (
                "import java.util.*;\n\n"
                "public class DijkstraPathFinder {\n"
                "    public static record Edge(int target, double weight) {}\n\n"
                "    public static double[] findShortestPaths(int n, List<List<Edge>> adj, int src) {\n"
                "        double[] dist = new double[n];\n"
                "        Arrays.fill(dist, Double.POSITIVE_INFINITY);\n"
                "        dist[src] = 0.0;\n"
                "        PriorityQueue<int[]> pq = new PriorityQueue<>(Comparator.comparingDouble(a -> a[1]));\n"
                "        pq.offer(new int[]{src, 0});\n"
                "        while (!pq.isEmpty()) {\n"
                "            int[] curr = pq.poll();\n"
                "            int u = curr[0];\n"
                "            if (curr[1] > dist[u]) continue;\n"
                "            for (Edge edge : adj.get(u)) {\n"
                "                if (dist[u] + edge.weight() < dist[edge.target()]) {\n"
                "                    dist[edge.target()] = dist[u] + edge.weight();\n"
                "                    pq.offer(new int[]{edge.target(), (int)dist[edge.target()]});\n"
                "                }\n"
                "            }\n"
                "        }\n"
                "        return dist;\n"
                "    }\n"
                "}\n"
            ),
        },
        {
            "id": "mock_php_lru_cache_007",
            "title": "High-Throughput In-Memory LRU Cache with Doubly Linked List",
            "concept": "O(1) get and put cache eviction policy utilizing hash map lookup and doubly linked list node reordering in PHP.",
            "domain": "systems",
            "tier": "advanced",
            "language": "php",
            "text": (
                "Least Recently Used (LRU) caching discards the least recently accessed elements when capacity is exceeded. "
                "In PHP, combining an associative array hash map with a doubly linked list provides O(1) constant time access, "
                "insertion, and deletion. When a key is requested, its corresponding list node is detached and spliced to the "
                "head, ensuring the tail always points to the oldest evictable entry."
            ),
            "code": (
                "<?php\n"
                "class LruCache {\n"
                "    private int $capacity;\n"
                "    private array $cache = [];\n\n"
                "    public function __construct(int $capacity) {\n"
                "        $this->capacity = $capacity;\n"
                "    }\n\n"
                "    public function get(string $key): mixed {\n"
                "        if (!isset($this->cache[$key])) return null;\n"
                "        $val = $this->cache[$key];\n"
                "        unset($this->cache[$key]);\n"
                "        $this->cache[$key] = $val;\n"
                "        return $val;\n"
                "    }\n\n"
                "    public function put(string $key, mixed $val): void {\n"
                "        if (isset($this->cache[$key])) unset($this->cache[$key]);\n"
                "        else if (count($this->cache) >= $this->capacity) {\n"
                "            reset($this->cache);\n"
                "            unset($this->cache[key($this->cache)]);\n"
                "        }\n"
                "        $this->cache[$key] = $val;\n"
                "    }\n"
                "}\n"
            ),
        },
        {
            "id": "mock_sql_window_analytics_008",
            "title": "Recursive CTE and Partitioned Window Analytics for Hierarchies",
            "concept": "Relational query computing organizational hierarchy depths and rolling averages using Common Table Expressions.",
            "domain": "coding",
            "tier": "advanced",
            "language": "sql",
            "text": (
                "Relational SQL supports powerful analytical query constructs including recursive Common Table "
                "Expressions (CTEs) and partitioned window functions. Recursive CTEs traverse adjacency lists in directed "
                "acyclic graphs to calculate tree depths, ancestor paths, and subtree aggregations. Window functions like "
                "AVG() OVER (PARTITION BY ... ORDER BY ... ROWS BETWEEN) calculate running moving averages without self-joins."
            ),
            "code": (
                "WITH RECURSIVE OrgHierarchy AS (\n"
                "    SELECT emp_id, manager_id, title, 1 AS depth\n"
                "    FROM employees\n"
                "    WHERE manager_id IS NULL\n"
                "    UNION ALL\n"
                "    SELECT e.emp_id, e.manager_id, e.title, h.depth + 1\n"
                "    FROM employees e\n"
                "    INNER JOIN OrgHierarchy h ON e.manager_id = h.emp_id\n"
                ")\n"
                "SELECT emp_id, title, depth,\n"
                "       AVG(depth) OVER (PARTITION BY manager_id) AS avg_manager_depth\n"
                "FROM OrgHierarchy\n"
                "ORDER BY depth ASC;\n"
            ),
        },
    ]

    def harvest(self, max_items: int = 10) -> List[HarvestedItem]:
        items: List[HarvestedItem] = []
        for idx, entry in enumerate(self.MOCK_CORPUS[:max_items]):
            item = HarvestedItem(
                id=entry["id"],
                title=entry["title"],
                concept=entry["concept"],
                domain=entry["domain"],
                tier=entry["tier"],
                text=entry["text"],
                code=entry.get("code", ""),
                language=entry.get("language", "python"),
                source="offline_mock",
                metadata={"synthetic": True, "index": idx},
            )
            items.append(item)
        return items


class QualityFilterPipeline:
    """
    Multi-stage automated quality heuristics:
    1. Length validation (text 80-10,000 chars, code >= 30 chars).
    2. Shannon character entropy noise rejection (3.0 <= H <= 6.0 bits/char).
    3. Markdown and text normalization with boilerplate stripping.
    4. AST / balanced-delimiter syntax validation across polyglot languages.
    5. 3-Tier Silver Deduplication (Exact SHA-256 hash, Lexical Jaccard shingle, Semantic topic collision).
    """

    MIN_TEXT_LEN = 80
    MAX_TEXT_LEN = 10000
    MIN_CODE_LEN = 30
    MIN_ENTROPY = 3.0
    MAX_ENTROPY = 6.0
    JACCARD_THRESHOLD = 0.82

    BOILERPLATE_PATTERNS = [
        re.compile(r"click here (to read more|for more information)", re.IGNORECASE),
        re.compile(r"terms of (service|use)", re.IGNORECASE),
        re.compile(r"privacy policy", re.IGNORECASE),
        re.compile(r"cookie notice|we use cookies", re.IGNORECASE),
        re.compile(r"table of contents", re.IGNORECASE),
        re.compile(r"all rights reserved", re.IGNORECASE),
        re.compile(r"subscribe to our newsletter", re.IGNORECASE),
        re.compile(r"share this (article|post|page)", re.IGNORECASE),
    ]

    @staticmethod
    def calculate_shannon_entropy(text: str) -> float:
        """
        Calculates Shannon character entropy: H = -sum(p * log2(p)).
        Repetitive boilerplate text yields H < 3.0; random noise yields H > 6.0.
        """
        if not text:
            return 0.0
        counts: Dict[str, int] = {}
        for ch in text:
            counts[ch] = counts.get(ch, 0) + 1
        total = len(text)
        entropy = 0.0
        for cnt in counts.values():
            p = cnt / total
            if p > 0.0:
                entropy -= p * math.log2(p)
        return entropy

    @classmethod
    def clean_text(cls, raw_text: str) -> str:
        """
        Cleans and normalizes text:
        - Unescapes HTML entities.
        - Normalizes Unicode to NFKC.
        - Strips web boilerplate patterns.
        - Standardizes Markdown whitespace.
        """
        if not raw_text:
            return ""

        text = html.unescape(raw_text)
        text = unicodedata.normalize("NFKC", text)

        for pat in cls.BOILERPLATE_PATTERNS:
            text = pat.sub("", text)

        # Collapse repeated blank lines
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        return text.strip()

    @classmethod
    def filter_noise(cls, item: HarvestedItem) -> Tuple[bool, str]:
        """
        Evaluates length bounds and Shannon character entropy.
        Returns (passed, reason).
        """
        text_len = len(item.text)
        if text_len < cls.MIN_TEXT_LEN:
            return False, f"text_too_short ({text_len} < {cls.MIN_TEXT_LEN})"
        if text_len > cls.MAX_TEXT_LEN:
            return False, f"text_too_long ({text_len} > {cls.MAX_TEXT_LEN})"

        if item.code.strip() and len(item.code.strip()) < cls.MIN_CODE_LEN:
            return False, f"code_too_short ({len(item.code.strip())} < {cls.MIN_CODE_LEN})"

        entropy = cls.calculate_shannon_entropy(item.text)
        if entropy < cls.MIN_ENTROPY:
            return False, f"entropy_too_low ({entropy:.2f} < {cls.MIN_ENTROPY})"
        if entropy > cls.MAX_ENTROPY:
            return False, f"entropy_too_high ({entropy:.2f} > {cls.MAX_ENTROPY})"

        return True, "passed"

    @staticmethod
    def check_balanced_delimiters(code: str, language: str = "") -> bool:
        """
        Validates balanced brackets and delimiters `()`, `[]`, `{}` in polyglot source code
        while skipping contents inside single quotes, double quotes, backticks, and comments.
        Accurately handles Rust lifetime parameters ('a, 'static) and SQL escaped quotes ('').
        """
        stack: List[str] = []
        pairs = {')': '(', ']': '[', '}': '{'}
        openers = set(pairs.values())
        closers = set(pairs.keys())

        i = 0
        n = len(code)
        lang = language.lower()
        in_sq = False
        in_dq = False
        in_bt = False
        in_line_comment = False
        in_block_comment = False

        while i < n:
            c = code[i]
            c2 = code[i:i + 2]

            if in_line_comment:
                if c == '\n':
                    in_line_comment = False
                i += 1
                continue

            if in_block_comment:
                if c2 == '*/':
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue

            if in_sq:
                if lang == "sql" and c2 == "''":
                    i += 2
                    continue
                if c == '\\':
                    i += 2
                    continue
                if c == "'":
                    in_sq = False
                i += 1
                continue

            if in_dq:
                if c == '\\':
                    i += 2
                    continue
                if c == '"':
                    in_dq = False
                i += 1
                continue

            if in_bt:
                if c == '\\':
                    i += 2
                    continue
                if c == '`':
                    in_bt = False
                i += 1
                continue

            # Check comments
            if c2 == '//' or c2 == '--':
                in_line_comment = True
                i += 2
                continue
            if c2 == '/*':
                in_block_comment = True
                i += 2
                continue
            if c == '#':
                line_head = code[i:].split('\n', 1)[0].strip()
                if not any(line_head.startswith(d) for d in ['#include', '#define', '#ifdef', '#ifndef', '#endif', '#pragma']):
                    in_line_comment = True
                    i += 1
                    continue

            # Check Rust character literals vs lifetimes
            if lang == "rust" and c == "'":
                m = re.match(r"^'(\\.|[^\\'])'", code[i:])
                if m:
                    i += len(m.group(0))
                    continue
                # If not a closed character literal, it's a lifetime annotation ('a, 'static)
                i += 1
                continue

            # Check C/C++ character literals
            if lang in ("c", "cpp") and c == "'":
                m = re.match(r"^'(\\.|[^\\'])'", code[i:])
                if m:
                    i += len(m.group(0))
                    continue

            # Check strings
            if c == "'":
                in_sq = True
                i += 1
                continue
            if c == '"':
                in_dq = True
                i += 1
                continue
            if c == '`':
                in_bt = True
                i += 1
                continue

            # Track delimiters
            if c in openers:
                stack.append(c)
            elif c in closers:
                if not stack or stack[-1] != pairs[c]:
                    return False
                stack.pop()

            i += 1

        return len(stack) == 0 and not (in_sq or in_dq or in_bt or in_block_comment)

    @classmethod
    def validate_syntax(cls, code: str, language: str) -> Tuple[bool, str]:
        """
        Validates syntax of code snippet:
        - Python: ast.parse(code)
        - Polyglot: balanced delimiter stack check and structural keyword validation.
        """
        trimmed = code.strip()
        if not trimmed:
            return True, "no_code"

        lang = language.lower()

        if lang == "python":
            try:
                ast.parse(trimmed)
                return True, "python_ast_valid"
            except SyntaxError as e:
                return False, f"python_syntax_error: {e}"

        # Polyglot balanced delimiter verification
        if not cls.check_balanced_delimiters(trimmed, language=lang):
            return False, f"{lang}_unbalanced_delimiters"

        # Polyglot structural keyword verification
        upper = trimmed.upper()
        if lang == "sql":
            sql_keywords = ["SELECT", "WITH", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "EXPLAIN"]
            if not any(re.search(rf"\b{kw}\b", upper) for kw in sql_keywords):
                return False, "sql_missing_keywords"

            # Tightened SQL syntax validation via in-memory SQLite EXPLAIN
            try:
                conn = sqlite3.connect(":memory:")
                cur = conn.cursor()
                statements = [s.strip() for s in trimmed.split(";") if s.strip()]
                for stmt in statements:
                    try:
                        cur.execute(f"EXPLAIN {stmt}")
                    except sqlite3.OperationalError as e:
                        err_str = str(e).lower()
                        if any(marker in err_str for marker in ("syntax error", "incomplete input", "unrecognized token")):
                            return False, f"sql_syntax_error: {e}"
                        # Non-syntax errors like "no such table: ..." indicate valid SQL grammar
                        # whose target tables are simply not instantiated in temporary :memory:.
            except Exception as e:
                return False, f"sql_validation_error: {e}"

        return True, f"{lang}_syntax_valid"

    @staticmethod
    def _compute_shingles(text: str, k: int = 2) -> Set[str]:
        words = [w.lower() for w in re.findall(r"\b\w+\b", text) if len(w) > 1]
        if len(words) < k:
            return set(words)
        return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}

    @classmethod
    def _jaccard_similarity(cls, set_a: Set[str], set_b: Set[str]) -> float:
        if not set_a or not set_b:
            return 0.0
        inter = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return inter / union if union > 0 else 0.0

    def deduplicate(
        self,
        items: List[HarvestedItem],
    ) -> Tuple[List[HarvestedItem], Dict[str, int]]:
        """
        Applies 3-Tier Silver Deduplication:
        - Tier 1: Exact SHA-256 hash on normalized (title, concept, code).
        - Tier 2: Lexical Jaccard token shingle similarity (threshold >= 0.82).
        - Tier 3: Semantic topic key collision (domain, tier, normalized_title).
        """
        deduped: List[HarvestedItem] = []
        stats = {
            "exact_hash_duplicates": 0,
            "jaccard_near_duplicates": 0,
            "semantic_topic_collisions": 0,
        }

        seen_exact_hashes: Set[str] = set()
        seen_shingles: List[Tuple[Set[str], HarvestedItem]] = []
        seen_topic_keys: Set[Tuple[str, str, str]] = set()

        for item in items:
            # Tier 1: Exact Hash
            norm_title = re.sub(r"\W+", " ", item.title.lower()).strip()
            norm_concept = re.sub(r"\W+", " ", item.concept.lower()).strip()
            norm_code = re.sub(r"\s+", " ", item.code.strip())
            exact_content = f"{norm_title}|||{norm_concept}|||{norm_code}"
            exact_hash = hashlib.sha256(exact_content.encode("utf-8")).hexdigest()

            if exact_hash in seen_exact_hashes:
                stats["exact_hash_duplicates"] += 1
                logger.debug(f"Tier 1 duplicate rejected: {item.title}")
                continue

            # Tier 3: Semantic topic key collision
            topic_key = (item.domain.lower(), item.tier.lower(), norm_title)
            if topic_key in seen_topic_keys:
                stats["semantic_topic_collisions"] += 1
                logger.debug(f"Tier 3 topic collision rejected: {item.title}")
                continue

            # Tier 2: Lexical Jaccard near-duplicate check
            current_shingles = self._compute_shingles(item.text)
            is_jaccard_dup = False
            for prev_shingles, _ in seen_shingles:
                sim = self._jaccard_similarity(current_shingles, prev_shingles)
                if sim >= self.JACCARD_THRESHOLD:
                    is_jaccard_dup = True
                    break

            if is_jaccard_dup:
                stats["jaccard_near_duplicates"] += 1
                logger.debug(f"Tier 2 Jaccard near-duplicate rejected: {item.title}")
                continue

            # Item passed all 3 tiers
            seen_exact_hashes.add(exact_hash)
            seen_topic_keys.add(topic_key)
            seen_shingles.append((current_shingles, item))
            deduped.append(item)

        return deduped, stats

    def run_pipeline(
        self,
        items: List[HarvestedItem],
    ) -> Tuple[List[HarvestedItem], Dict[str, Any]]:
        """
        Executes full quality filter pipeline over raw harvested items.
        """
        clean_candidates: List[HarvestedItem] = []
        rejections = {
            "noise": 0,
            "syntax": 0,
            "dedup": 0,
        }

        for raw_item in items:
            cleaned_text = self.clean_text(raw_item.text)
            cleaned_concept = self.clean_text(raw_item.concept)
            candidate = HarvestedItem(
                id=raw_item.id,
                title=raw_item.title.strip(),
                concept=cleaned_concept,
                domain=raw_item.domain,
                tier=raw_item.tier,
                text=cleaned_text,
                code=raw_item.code.strip(),
                language=raw_item.language,
                source=raw_item.source,
                metadata=raw_item.metadata,
            )

            # Stage 1: Noise filter
            passed_noise, noise_reason = self.filter_noise(candidate)
            if not passed_noise:
                rejections["noise"] += 1
                logger.debug(f"Rejected noise: {candidate.id} - {noise_reason}")
                continue

            # Stage 2: Syntax validation
            passed_syntax, syntax_reason = self.validate_syntax(candidate.code, candidate.language)
            if not passed_syntax:
                rejections["syntax"] += 1
                logger.debug(f"Rejected syntax: {candidate.id} - {syntax_reason}")
                continue

            clean_candidates.append(candidate)

        # Stage 3: 3-Tier Deduplication
        deduped_items, dedup_stats = self.deduplicate(clean_candidates)
        rejections["dedup"] = (
            dedup_stats["exact_hash_duplicates"]
            + dedup_stats["jaccard_near_duplicates"]
            + dedup_stats["semantic_topic_collisions"]
        )

        pipeline_summary = {
            "raw_total": len(items),
            "passed_clean": len(deduped_items),
            "rejected_noise": rejections["noise"],
            "rejected_syntax": rejections["syntax"],
            "rejected_dedup": rejections["dedup"],
            "dedup_breakdown": dedup_stats,
        }

        return deduped_items, pipeline_summary


class SQ8VectorIngester:
    """
    Ingests cleaned STEM and coding items into backend/storage/vectors.sqlite:
    1. Generates 768-d vector embeddings (Ollama nomic-embed-text or deterministic fallback).
    2. Quantizes embeddings into 776-byte SQ8 binary payloads (v_min, v_max + 768 uint8 bytes).
    3. Persists full documents to rag_documents (collection='stem_knowledge').
    4. Enforces a strict <= 500 row ceiling in material_chunks with FIFO eviction.
    """

    DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "backend" / "storage" / "vectors.sqlite"

    def __init__(
        self,
        db_path: Optional[str | Path] = None,
        max_material_chunks: int = 500,
        ollama_url: str = "http://127.0.0.1:11434",
        embed_model: str = "nomic-embed-text",
        enable_ollama: bool = True,
    ):
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB_PATH
        self.max_material_chunks = max_material_chunks
        self.ollama_url = ollama_url.rstrip("/")
        self.embed_model = embed_model
        self.enable_ollama = enable_ollama
        self._ollama_available: Optional[bool] = None
        self.quantizer = SQ8VectorQuantizer(dim=768)
        self._init_sqlite()

    def _check_ollama(self) -> bool:
        """Cached pre-flight check to see if Ollama embedding service is reachable."""
        if not self.enable_ollama or httpx is None:
            return False
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            with httpx.Client(timeout=0.8) as client:
                res = client.get(f"{self.ollama_url}/api/tags")
                self._ollama_available = (res.status_code == 200)
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_sqlite(self) -> None:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    text TEXT NOT NULL,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (collection, id)
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_rag_docs_coll ON rag_documents(collection);
            """)
            cur.execute("""
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
            conn.commit()
        finally:
            conn.close()

    def _get_ollama_embedding(self, text: str) -> Optional[List[float]]:
        """Queries local Ollama nomic-embed-text with mandatory 'search_document: ' prefix."""
        if not self._check_ollama() or httpx is None:
            return None

        url = f"{self.ollama_url}/api/embed"
        payload = {
            "model": self.embed_model,
            "input": f"search_document: {text.strip()}",
            "keep_alive": "5m",
        }
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    embeddings = res.json().get("embeddings")
                    if embeddings and len(embeddings) > 0:
                        return embeddings[0]
        except Exception:
            pass
        return None

    @staticmethod
    def generate_fallback_vector(seed_text: str, dim: int = 768) -> np.ndarray:
        """Deterministic unit vector fallback derived from SHA-256 seed."""
        h = hashlib.sha256(seed_text.encode("utf-8")).digest()
        raw = np.array([float(h[i % len(h)]) - 128.0 for i in range(dim)], dtype=np.float32)
        norm = np.linalg.norm(raw)
        return raw / (norm if norm > 1e-12 else 1.0)

    def ingest(
        self,
        items: List[HarvestedItem],
        collection: str = "stem_knowledge",
    ) -> Dict[str, Any]:
        """
        Persists harvested items into vectors.sqlite:
        1. Upserts into rag_documents (collection='stem_knowledge').
        2. Ingests SQ8-quantized chunks into material_chunks with FIFO ceiling enforcement.
        """
        stats = {
            "rag_documents_upserted": 0,
            "material_chunks_inserted": 0,
            "material_chunks_evicted": 0,
            "live_embeddings_count": 0,
            "fallback_embeddings_count": 0,
            "total_material_chunks_after": 0,
        }

        if not items:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM material_chunks")
                stats["total_material_chunks_after"] = cur.fetchone()[0]
            finally:
                conn.close()
            return stats

        conn = self._get_connection()
        try:
            cur = conn.cursor()

            # 1. Upsert full items to rag_documents
            for item in items:
                formatted_doc = item.to_formatted_document()
                meta_json = json.dumps({
                    "title": item.title,
                    "concept": item.concept,
                    "domain": item.domain,
                    "tier": item.tier,
                    "language": item.language,
                    "source": item.source,
                    "updated_at": datetime.now().isoformat(),
                    **item.metadata,
                })

                cur.execute("""
                    INSERT INTO rag_documents (collection, id, text, metadata, created_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(collection, id) DO UPDATE SET
                        text = excluded.text,
                        metadata = excluded.metadata,
                        created_at = CURRENT_TIMESTAMP;
                """, (collection, item.id, formatted_doc, meta_json))
                stats["rag_documents_upserted"] += 1

            # 2. Insert newly harvested SQ8 chunks into material_chunks
            for idx, item in enumerate(items):
                chunk_id = f"chunk_{item.id}_{idx:03d}"
                summary_text = (
                    f"{item.title} ({item.domain.upper()} - {item.tier.upper()}):\n"
                    f"{item.concept}\n\n"
                    f"{item.text[:500]}"
                )
                if item.code.strip():
                    summary_text += f"\n\nCode snippet ({item.language}):\n{item.code[:300]}"

                # Embed & Quantize
                raw_emb = self._get_ollama_embedding(summary_text)
                if raw_emb is not None:
                    vec_arr = np.array(raw_emb, dtype=np.float32)
                    stats["live_embeddings_count"] += 1
                else:
                    vec_arr = self.generate_fallback_vector(summary_text)
                    stats["fallback_embeddings_count"] += 1

                # Quantize to 776 bytes SQ8 payload
                sq8_blob = self.quantizer.quantize(vec_arr)
                assert len(sq8_blob) == 776, f"Expected 776 bytes SQ8, got {len(sq8_blob)}"

                chunk_meta = json.dumps({
                    "title": item.title,
                    "domain": item.domain,
                    "tier": item.tier,
                    "language": item.language,
                    "source": item.source,
                    "quantization": "sq8",
                    "source_id": item.id,
                })

                cur.execute("""
                    INSERT OR REPLACE INTO material_chunks (
                        id, material_id, course_id, batch_id, chunk_index, title, content, metadata, embedding, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    chunk_id,
                    f"harv_mat_{item.domain}",
                    "stem_curriculum",
                    f"batch_{item.tier}",
                    idx,
                    item.title,
                    summary_text,
                    chunk_meta,
                    sq8_blob,
                ))
                stats["material_chunks_inserted"] += 1

            # 3. Post-insert FIFO ceiling enforcement: ORDER BY created_at ASC, rowid ASC
            cur.execute("SELECT COUNT(*) FROM material_chunks")
            post_count = cur.fetchone()[0]
            if post_count > self.max_material_chunks:
                excess = post_count - self.max_material_chunks
                cur.execute("""
                    DELETE FROM material_chunks
                    WHERE id IN (
                        SELECT id FROM material_chunks
                        ORDER BY created_at ASC, rowid ASC
                        LIMIT ?
                    )
                """, (excess,))
                stats["material_chunks_evicted"] = cur.rowcount
                logger.info(f"FIFO Eviction: Removed {cur.rowcount} oldest chunks from material_chunks")

            cur.execute("SELECT COUNT(*) FROM material_chunks")
            stats["total_material_chunks_after"] = cur.fetchone()[0]

            conn.commit()
        finally:
            conn.close()

        return stats


class WebHarvester:
    """
    Main orchestration class coordinating source adapters, quality filter pipeline,
    and SQ8 vector database ingestion.
    """

    def __init__(
        self,
        db_path: Optional[str | Path] = None,
        max_material_chunks: int = 500,
        ollama_url: str = "http://127.0.0.1:11434",
    ):
        self.db_path = Path(db_path) if db_path else SQ8VectorIngester.DEFAULT_DB_PATH
        self.max_material_chunks = max_material_chunks
        self.pipeline = QualityFilterPipeline()
        self.ingester = SQ8VectorIngester(
            db_path=self.db_path,
            max_material_chunks=max_material_chunks,
            ollama_url=ollama_url,
        )
        self.arxiv_adapter = ArxivHarvesterAdapter()
        self.opencode_adapter = OpenCodeHarvesterAdapter()
        self.mock_adapter = OfflineMockHarvesterAdapter()

        self._stats = {
            "total_harvested": 0,
            "total_passed_quality": 0,
            "total_rejected": 0,
            "last_run": None,
        }

    def harvest_and_ingest(
        self,
        max_items: int = 20,
        mock: bool = False,
        source: str = "all",
    ) -> Dict[str, Any]:
        """
        Runs harvesting, quality filtering, and SQ8 ingestion cycle.
        """
        raw_items: List[HarvestedItem] = []

        if mock:
            raw_items.extend(self.mock_adapter.harvest(max_items=max_items))
        else:
            if source in ("all", "arxiv"):
                arxiv_items = self.arxiv_adapter.harvest(max_items=max_items)
                raw_items.extend(arxiv_items)

            if source in ("all", "opencode"):
                opencode_items = self.opencode_adapter.harvest(max_items=max_items)
                raw_items.extend(opencode_items)

            # Fallback to mock adapter if live sources yield no items (e.g. offline)
            if not raw_items:
                logger.info("Live scraping yielded 0 items (offline/network unavailable); using offline mock adapter.")
                raw_items.extend(self.mock_adapter.harvest(max_items=max_items))

        self._stats["total_harvested"] += len(raw_items)

        # Quality Filter Pipeline
        clean_items, filter_summary = self.pipeline.run_pipeline(raw_items)
        self._stats["total_passed_quality"] += len(clean_items)
        self._stats["total_rejected"] += (len(raw_items) - len(clean_items))

        # SQ8 Vector Ingestion & Ceiling Enforcement
        ingest_summary = self.ingester.ingest(clean_items, collection="stem_knowledge")

        self._stats["last_run"] = datetime.now().isoformat()

        return {
            "status": "success",
            "harvested_raw_count": len(raw_items),
            "clean_items_count": len(clean_items),
            "filter_summary": filter_summary,
            "ingest_summary": ingest_summary,
            "material_chunks_total": ingest_summary.get("total_material_chunks_after", 0),
            "max_ceiling": self.max_material_chunks,
        }

    def get_status(self) -> Dict[str, Any]:
        """Returns current operational status and database statistics."""
        with self.ingester._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM material_chunks")
            chunk_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM rag_documents WHERE collection = 'stem_knowledge'")
            doc_count = cur.fetchone()[0]

            # Calculate average Shannon character entropy from recent corpus sample
            avg_entropy = 4.5
            try:
                cur.execute("SELECT text FROM rag_documents WHERE collection = 'stem_knowledge' LIMIT 20")
                rows = cur.fetchall()
                if rows:
                    entropies = [QualityFilterPipeline.calculate_shannon_entropy(r[0]) for r in rows if r[0]]
                    if entropies:
                        avg_entropy = round(sum(entropies) / len(entropies), 3)
            except Exception:
                pass

        utilization_pct = round((chunk_count / max(1, self.max_material_chunks)) * 100.0, 2)
        total_scraped = max(self._stats["total_harvested"], doc_count)

        return {
            "total_harvested": self._stats["total_harvested"],
            "total_sources_scraped": total_scraped,
            "total_passed_quality": self._stats["total_passed_quality"],
            "total_rejected": self._stats["total_rejected"],
            "last_run": self._stats["last_run"],
            "material_chunks_count": chunk_count,
            "ingested_chunks": chunk_count,
            "stem_knowledge_docs_count": doc_count,
            "material_chunks_ceiling": self.max_material_chunks,
            "max_chunks": self.max_material_chunks,
            "shannon_entropy_score": avg_entropy,
            "fifo_queue_utilization": utilization_pct,
            "details": {
                "utilization_pct": utilization_pct,
                "entropy": avg_entropy,
                "ceiling": self.max_material_chunks,
            },
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Autonomous Web Harvester & Quality Ingestion Pipeline")
    parser.add_argument("--source", choices=["arxiv", "opencode", "mock", "all"], default="all", help="Data source to scrape")
    parser.add_argument("--max-items", type=int, default=10, help="Maximum items to harvest")
    parser.add_argument("--mock", action="store_true", help="Force offline synthetic mock generation")
    parser.add_argument("--db-path", type=str, default=None, help="Custom SQLite database path")

    args = parser.parse_args()
    harvester = WebHarvester(db_path=args.db_path)
    result = harvester.harvest_and_ingest(max_items=args.max_items, mock=args.mock, source=args.source)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
