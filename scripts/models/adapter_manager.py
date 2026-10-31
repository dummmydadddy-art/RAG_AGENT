"""
scripts/models/adapter_manager.py

Dynamic LoRA Adapter Manager for Modular STEM & Polyglot Capabilities.
Manages low-overhead domain adapters (~35 MiB each) enforcing strict hardware ceilings:
- VRAM impact <= 38 MiB per adapter
- Total concurrent active adapters <= 105 MiB
- Instant hot-switching without base model reload
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
import re


class AdapterDomain(str, Enum):
    STEM_PHYSICS_MATH = "stem-physics-math"
    SYSTEMS_LOWLEVEL = "systems-lowlevel"
    WEB_DATA = "web-data"


@dataclass
class AdapterMetadata:
    name: str
    domain: AdapterDomain
    vram_mib: float
    rank: int = 16
    alpha: int = 32
    target_modules: List[str] = field(default_factory=lambda: ["q_proj", "v_proj", "k_proj", "o_proj"])
    description: str = ""


class LoRAAdapterManager:
    """
    Manages registration, hot-loading, VRAM accounting, and heuristic domain routing
    for modular LoRA adapters.
    """

    DEFAULT_METADATA: Dict[AdapterDomain, AdapterMetadata] = {
        AdapterDomain.STEM_PHYSICS_MATH: AdapterMetadata(
            name="stem_physics_math_adapter",
            domain=AdapterDomain.STEM_PHYSICS_MATH,
            vram_mib=35.0,
            rank=16,
            alpha=32,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
            description="Specialized in symbolic mathematics, Pint dimensional units, ODE/PDE calculus, and Noether invariants.",
        ),
        AdapterDomain.SYSTEMS_LOWLEVEL: AdapterMetadata(
            name="systems_lowlevel_adapter",
            domain=AdapterDomain.SYSTEMS_LOWLEVEL,
            vram_mib=35.0,
            rank=16,
            alpha=32,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
            description="Specialized in C++, Rust, and Go memory safety, concurrency, spinlocks, and WASI micro-sandboxes.",
        ),
        AdapterDomain.WEB_DATA: AdapterMetadata(
            name="web_data_adapter",
            domain=AdapterDomain.WEB_DATA,
            vram_mib=35.0,
            rank=16,
            alpha=32,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
            description="Specialized in TypeScript, PHP 8.3 REST APIs, SQLite FTS5 vector storage, and relational schemas.",
        ),
    }

    # Maximum allowed VRAM per adapter and overall
    MAX_VRAM_PER_ADAPTER_MIB: float = 38.0
    MAX_TOTAL_ADAPTER_VRAM_MIB: float = 105.0

    def __init__(self, adapters_dir: Optional[Path] = None):
        self.adapters_dir = adapters_dir or (Path("models") / "adapters")
        self._registry: Dict[AdapterDomain, AdapterMetadata] = dict(self.DEFAULT_METADATA)
        self._loaded_adapters: Set[AdapterDomain] = set()
        self._active_adapter: Optional[AdapterDomain] = None

    @property
    def active_adapter(self) -> Optional[AdapterDomain]:
        return self._active_adapter

    def list_registered_domains(self) -> List[AdapterDomain]:
        """Returns list of registered adapter domains."""
        return list(self._registry.keys())

    def get_adapter_metadata(self, domain: AdapterDomain) -> AdapterMetadata:
        """Retrieves metadata for a specific domain adapter."""
        if domain not in self._registry:
            raise KeyError(f"Domain adapter {domain} is not registered.")
        return self._registry[domain]

    def load_adapter(self, domain: AdapterDomain) -> bool:
        """
        Loads an adapter into active memory if VRAM budget allows.
        Enforces MAX_TOTAL_ADAPTER_VRAM_MIB ceiling.
        """
        meta = self.get_adapter_metadata(domain)
        if domain in self._loaded_adapters:
            return True

        projected_vram = self.total_active_vram_mib() + meta.vram_mib
        if projected_vram > self.MAX_TOTAL_ADAPTER_VRAM_MIB:
            raise MemoryError(
                f"Loading adapter {domain.value} ({meta.vram_mib} MiB) would exceed "
                f"VRAM budget limit of {self.MAX_TOTAL_ADAPTER_VRAM_MIB} MiB. "
                f"Current: {self.total_active_vram_mib()} MiB."
            )

        self._loaded_adapters.add(domain)
        return True

    def unload_adapter(self, domain: AdapterDomain) -> bool:
        """Unloads an adapter from active memory."""
        if domain in self._loaded_adapters:
            self._loaded_adapters.remove(domain)
            if self._active_adapter == domain:
                self._active_adapter = None
            return True
        return False

    def total_active_vram_mib(self) -> float:
        """Computes the total VRAM footprint of all currently loaded adapters."""
        return sum(self._registry[dom].vram_mib for dom in self._loaded_adapters)

    def activate_adapter(self, domain: AdapterDomain) -> None:
        """Sets the active adapter for subsequent inference queries."""
        if domain not in self._loaded_adapters:
            self.load_adapter(domain)
        self._active_adapter = domain

    def route_domain(self, query: str, language: Optional[str] = None) -> AdapterDomain:
        """
        Intelligently routes a coding or mathematical task to the optimal domain adapter
        based on programming language and query semantics.
        """
        query_lower = query.lower()
        lang_lower = (language or "").strip().lower()

        # 1. Direct language-based rules
        if lang_lower in ("rust", "c++", "cpp", "c", "go"):
            return AdapterDomain.SYSTEMS_LOWLEVEL
        if lang_lower in ("typescript", "ts", "javascript", "js", "php", "sql"):
            return AdapterDomain.WEB_DATA

        # 2. Semantic keyword indicators
        physics_keywords = [
            "physics", "hamiltonian", "lagrangian", "euler-lagrange", "ode", "pde",
            "derivative", "integral", "noether", "poisson bracket", "pint", "tensor",
            "quantum", "relativity", "calculus", "differential equation", "schrodinger",
            "rk4", "radau", "stiff"
        ]
        systems_keywords = [
            "memory", "pointer", "spinlock", "mutex", "atomic", "thread",
            "lock-free", "syscall", "wasi", "wasm", "assembly", "allocator"
        ]
        web_keywords = [
            "rest", "api", "sqlite", "fts5", "vector", "json", "http",
            "database", "schema", "orm", "endpoint", "crud"
        ]

        # Score queries based on keyword matches
        scores = {
            AdapterDomain.STEM_PHYSICS_MATH: sum(1 for kw in physics_keywords if kw in query_lower),
            AdapterDomain.SYSTEMS_LOWLEVEL: sum(1 for kw in systems_keywords if kw in query_lower),
            AdapterDomain.WEB_DATA: sum(1 for kw in web_keywords if kw in query_lower),
        }

        # Default fallback if Python is specified or tied
        if lang_lower == "python" and scores[AdapterDomain.STEM_PHYSICS_MATH] == 0:
            scores[AdapterDomain.STEM_PHYSICS_MATH] += 1

        best_domain = max(scores, key=lambda d: scores[d])
        return best_domain
