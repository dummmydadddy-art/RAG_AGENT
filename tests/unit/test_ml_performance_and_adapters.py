"""
tests/unit/test_ml_performance_and_adapters.py

TDD Acceptance Tests for Milestone 3: ML Performance, Dynamic Adapters & Context Expansion.
Verifies:
1. Context Expansion & Truncation:
   - Modelfile specifies PARAMETER num_ctx 4096.
   - SftDatasetBuilder supports max_tokens=2048 and max_char_limit=16384 without truncating rich derivations.
2. Dynamic LoRA Adapter Architecture:
   - Modular adapters for stem-physics-math, systems-lowlevel, web-data.
   - Domain router selects appropriate adapter based on query / code metadata.
   - Adapter VRAM accounting strictly enforces <= 38 MiB per adapter, <= 105 MiB total.
3. Inference Acceleration & Static Prompt Caching:
   - Static prefix caching identifies matching prefixes for sub-35ms TTFT.
   - N-gram speculative prompt lookup matches recurring polyglot syntax patterns.
"""

from pathlib import Path
import pytest
from scripts.train_stem_model import SftDatasetBuilder
from scripts.models.adapter_manager import (
    LoRAAdapterManager,
    AdapterDomain,
    AdapterMetadata,
)
from scripts.models.inference_accelerator import (
    PromptCacheEngine,
    SpeculativeLookupEngine,
    InferenceAccelerator,
)


class TestContextExpansionAndTruncation:
    """Verifies 4,096 token context expansion and relaxed cascade truncation."""

    def test_modelfile_specifies_4096_context(self):
        """Verifies models/Modelfile explicitly sets PARAMETER num_ctx 4096."""
        modelfile_path = Path("models/Modelfile")
        assert modelfile_path.exists(), "models/Modelfile must exist"
        content = modelfile_path.read_text(encoding="utf-8")
        assert "PARAMETER num_ctx 4096" in content, "models/Modelfile must configure PARAMETER num_ctx 4096"

    def test_cascade_truncate_allows_expanded_16k_char_limit(self):
        """Rich derivations with 6,000 chars should not be truncated under expanded limits."""
        builder = SftDatasetBuilder()
        instruction = "Derive and implement the Runge-Kutta 4th order method in Rust with tests."
        input_text = "Physics mechanics initial value problem y'(t) = -k*y(t)."
        output_text = "// Rust implementation\n" + ("pub fn rk4_step() { /* computation */ }\n" * 150)
        total_len = len(instruction) + len(input_text) + len(output_text)
        assert total_len > 5000, "Synthetic output must exceed legacy 4096 char limit"

        inst_res, inp_res, out_res = builder.cascade_truncate(
            instruction=instruction,
            input_text=input_text,
            output_text=output_text,
            max_char_limit=16384,
        )
        # Should not be truncated because total_len < 16384!
        assert "... [truncated]" not in out_res
        assert len(inst_res) + len(inp_res) + len(out_res) == total_len

    def test_cascade_truncate_safely_clamps_when_exceeding_16k(self):
        """Inputs exceeding 16,384 characters are symmetrically truncated to exactly <= 16384."""
        builder = SftDatasetBuilder()
        instruction = "Solve boundary value problem.\n" * 200
        input_text = "Large dataset schema.\n" * 200
        output_text = "C++ numerical code.\n" * 600
        total_len = len(instruction) + len(input_text) + len(output_text)
        assert total_len > 16384

        inst_res, inp_res, out_res = builder.cascade_truncate(
            instruction=instruction,
            input_text=input_text,
            output_text=output_text,
            max_char_limit=16384,
        )
        assert len(inst_res) + len(inp_res) + len(out_res) <= 16384
        assert "... [truncated]" in out_res

    def test_build_alpaca_dataset_preserves_2048_tokens(self):
        """build_alpaca_dataset respects max_tokens=2048 with max_char_limit=8192."""
        builder = SftDatasetBuilder()
        records = [
            {
                "task_id": "test_exp_1",
                "language": "python",
                "instruction": "Derive Hamiltonian.",
                "input": "H = p^2/2m + V(x)",
                "output": "# Long derivation\n" + ("x = compute(x)\n" * 200),
            }
        ]
        samples = builder.build_alpaca_dataset(records, max_tokens=2048)
        assert len(samples) == 1
        sample = samples[0]
        assert len(sample["instruction"]) + len(sample["input"]) + len(sample["output"]) > 2000
        assert "... [truncated]" not in sample["output"]


class TestDynamicLoRAAdapterArchitecture:
    """Verifies modular adapter registration, domain routing, and VRAM memory accounting."""

    def test_adapter_registry_contains_core_domains(self):
        """Adapter manager discovers all three core domain adapters."""
        mgr = LoRAAdapterManager()
        domains = mgr.list_registered_domains()
        assert AdapterDomain.STEM_PHYSICS_MATH in domains
        assert AdapterDomain.SYSTEMS_LOWLEVEL in domains
        assert AdapterDomain.WEB_DATA in domains

    def test_adapter_vram_accounting_strictly_bounded(self):
        """Each adapter size is <= 38 MiB and total loaded adapters <= 105 MiB."""
        mgr = LoRAAdapterManager()
        for domain in mgr.list_registered_domains():
            meta = mgr.get_adapter_metadata(domain)
            assert meta.vram_mib <= 38.0, f"Adapter {domain.value} exceeds 38 MiB ceiling"
        
        # Test loading all 3 adapters simultaneously
        mgr.load_adapter(AdapterDomain.STEM_PHYSICS_MATH)
        mgr.load_adapter(AdapterDomain.SYSTEMS_LOWLEVEL)
        mgr.load_adapter(AdapterDomain.WEB_DATA)
        assert mgr.total_active_vram_mib() <= 105.0

    def test_domain_routing_selects_appropriate_adapter(self):
        """Domain router accurately selects the matching adapter from language and keywords."""
        mgr = LoRAAdapterManager()

        # Physics / Math -> STEM_PHYSICS_MATH
        d1 = mgr.route_domain(query="Derive Euler-Lagrange equations and solve ODE", language="python")
        assert d1 == AdapterDomain.STEM_PHYSICS_MATH

        # C++ / Rust -> SYSTEMS_LOWLEVEL
        d2 = mgr.route_domain(query="Implement atomic spinlock using memory_order_acquire", language="rust")
        assert d2 == AdapterDomain.SYSTEMS_LOWLEVEL

        # TypeScript / PHP / SQL -> WEB_DATA
        d3 = mgr.route_domain(query="Build REST API with SQLite FTS5 vector search", language="php")
        assert d3 == AdapterDomain.WEB_DATA

    def test_dynamic_adapter_activation_swapping(self):
        """Switching active adapter updates active context without base model reload."""
        mgr = LoRAAdapterManager()
        mgr.activate_adapter(AdapterDomain.STEM_PHYSICS_MATH)
        assert mgr.active_adapter == AdapterDomain.STEM_PHYSICS_MATH

        mgr.activate_adapter(AdapterDomain.SYSTEMS_LOWLEVEL)
        assert mgr.active_adapter == AdapterDomain.SYSTEMS_LOWLEVEL


class TestInferenceAccelerationAndPromptCaching:
    """Verifies static prefix caching and N-gram speculative prompt lookup."""

    def test_prefix_prompt_cache_hit(self):
        """Static system prompt prefix yields an immediate cache hit."""
        cache = PromptCacheEngine()
        system_prompt = "You are an elite STEM Subject Matter Expert and polyglot software engineer."
        cache.register_static_prefix("stem_system", system_prompt)

        # Full prompt starting with the static prefix
        full_prompt = system_prompt + "\nUser: Solve the differential equation."
        hit, remaining = cache.lookup_prefix(full_prompt)
        assert hit is True
        assert remaining == "\nUser: Solve the differential equation."

    def test_prefix_prompt_cache_miss_on_novel_prefix(self):
        """Novel prompt without registered prefix correctly reports cache miss."""
        cache = PromptCacheEngine()
        prompt = "Unrecognized custom prompt for generic chat."
        hit, remaining = cache.lookup_prefix(prompt)
        assert hit is False
        assert remaining == prompt

    def test_speculative_ngram_lookup_generates_draft_tokens(self):
        """Speculative N-gram lookup proposes candidate continuations for repeated polyglot patterns."""
        lookup = SpeculativeLookupEngine(n_gram_size=3)
        context = "import numpy as np\nimport scipy.integrate\nimport json\ndef solve_ivp():\n    pass\n"
        lookup.index_context(context)

        # Query with prefix 'import numpy as'
        candidates = lookup.propose_candidates("import numpy as", max_tokens=2)
        assert "np" in candidates

    def test_inference_accelerator_pipeline_latency(self):
        """Integrated accelerator pipeline evaluates caching and speculative lookup in <1 ms."""
        accel = InferenceAccelerator()
        system_prompt = "You are an elite STEM Subject Matter Expert."
        accel.prompt_cache.register_static_prefix("stem", system_prompt)
        accel.lookup_engine.index_context("def test_harmonic_oscillator():\n    assert True\n")

        prompt = system_prompt + "\ndef test_"
        res = accel.accelerate_prompt(prompt)
        assert res["cache_hit"] is True
        assert res["overhead_ms"] < 1.0
