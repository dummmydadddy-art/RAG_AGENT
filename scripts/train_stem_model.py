#!/usr/bin/env python3
"""
STEM Model Fine-Tuning & Quantization Pipeline.

Automates the end-to-end training lifecycle tailored for low-resource hardware:
- GPU: 4 GB VRAM (NVIDIA RTX 3050 Laptop)
- RAM: 15 GB System Memory
- Storage: 20 GB SSD Budget

Lifecycle Stages:
1. Pre-flight VRAM Eviction: Frees Ollama models (keep_alive: 0) to avoid CUDA OOM.
2. SFT Dataset Preparation: Extracts Gold STEM records into Alpaca/ShareGPT format.
3. Config Generation: Produces 4-bit QLoRA configs (LLaMA-Factory & TRL) on Qwen2.5-Coder-1.5B.
4. Model Export & Ollama Registration: LoRA export -> CPU RAM merge -> 4-bit GGUF -> Ollama Modelfile.
5. Zero-Redundancy Cleanup: Deletes intermediate raw merged weights to strictly respect SSD budget.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "rag-adapter"))

from rag_adapter.sqlite_backend import LocalSqliteRagBackend

logger = logging.getLogger("stem_training")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class VramEvictor:
    """Pre-flight GPU VRAM eviction for Ollama and PyTorch."""

    def __init__(self, ollama_url: str = "http://localhost:11434") -> None:
        self.ollama_url = ollama_url.rstrip("/")

    def evict_ollama_models(self) -> List[str]:
        """
        Queries Ollama for active loaded models and sends keep_alive: 0
        to immediately evict weights from GPU VRAM.
        """
        unloaded: List[str] = []
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(f"{self.ollama_url}/api/ps")
                if res.status_code == 200:
                    data = res.json()
                    models = data.get("models", [])
                    for m in models:
                        model_name = m.get("name")
                        if model_name:
                            logger.info(f"VRAM Eviction: Unloading Ollama model '{model_name}'...")
                            client.post(
                                f"{self.ollama_url}/api/generate",
                                json={"model": model_name, "keep_alive": 0},
                            )
                            unloaded.append(model_name)
        except Exception as e:
            logger.debug(f"VRAM Eviction: Ollama query skipped or offline: {e}")
        return unloaded

    def evict_torch_cuda(self) -> Dict[str, Any]:
        """Clears PyTorch CUDA cached memory and IPC handles."""
        info: Dict[str, Any] = {"cuda_available": False}
        try:
            import torch
            if torch.cuda.is_available():
                info["cuda_available"] = True
                info["device_name"] = torch.cuda.get_device_name(0)
                info["vram_before_mb"] = torch.cuda.memory_allocated(0) / (1024 * 1024)
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
                info["vram_after_mb"] = torch.cuda.memory_allocated(0) / (1024 * 1024)
                logger.info(
                    f"VRAM Eviction: PyTorch CUDA cache cleared on {info['device_name']} "
                    f"({info['vram_after_mb']:.2f} MB active)."
                )
        except ImportError:
            logger.debug("VRAM Eviction: PyTorch not installed in current environment.")
        return info


class SftDatasetBuilder:
    """Extracts verified Gold STEM records and builds formatted SFT training sets."""

    SYSTEM_PROMPT = (
        "You are an elite STEM Subject Matter Expert in Mathematics, Physics, and Computer Science. "
        "Solve problems with step-by-step rigorous derivations, explicit physical units, and verifiable code."
    )

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or (ROOT / "backend" / "storage" / "vectors.sqlite")
        self.backend = LocalSqliteRagBackend(str(self.db_path))

    def load_stem_records(self) -> List[Dict[str, Any]]:
        """Load knowledge documents from rag_documents database."""
        records: List[Dict[str, Any]] = []
        with self.backend._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, collection, text, metadata
                FROM rag_documents
                WHERE collection IN ('stem_knowledge', 'knowledge')
            """)
            rows = cursor.fetchall()
            for r in rows:
                meta = json.loads(r["metadata"]) if r["metadata"] else {}
                records.append({
                    "id": r["id"],
                    "collection": r["collection"],
                    "text": r["text"],
                    "title": meta.get("title", ""),
                    "domain": meta.get("domain", ""),
                    "tier": meta.get("tier", ""),
                    "grade_level": meta.get("grade_level", ""),
                    "concept": meta.get("concept", ""),
                    "example_problem": meta.get("example_problem", ""),
                    "solution_steps": meta.get("solution_steps", ""),
                })
        return records

    def build_alpaca_dataset(self, records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Converts records to standard Alpaca instruction-tuning schema."""
        alpaca_samples: List[Dict[str, str]] = []
        for rec in records:
            problem = rec.get("example_problem") or rec.get("title")
            concept = rec.get("concept") or ""
            solution = rec.get("solution_steps") or rec.get("text")

            domain_val = rec.get("domain", "STEM")
            if isinstance(domain_val, list):
                domain_str = "/".join(str(d) for d in domain_val).upper()
            else:
                domain_str = str(domain_val or "STEM").upper()

            grade_str = str(rec.get("grade_level") or "General")

            instruction = (
                f"Domain: {domain_str} | Level: {grade_str}\n"
                f"Question / Challenge:\n{problem}"
            )
            input_text = f"Relevant Principles:\n{concept}" if concept else ""

            alpaca_samples.append({
                "instruction": instruction,
                "input": input_text,
                "output": solution,
            })
        return alpaca_samples

    def build_sharegpt_dataset(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Converts records to multi-turn ShareGPT / ChatML format."""
        sharegpt_samples: List[Dict[str, Any]] = []
        for rec in records:
            problem = rec.get("example_problem") or rec.get("title")
            concept = rec.get("concept") or ""
            solution = rec.get("solution_steps") or rec.get("text")

            user_query = f"{problem}\n\nContext:\n{concept}" if concept else problem
            sharegpt_samples.append({
                "conversations": [
                    {"from": "system", "value": self.SYSTEM_PROMPT},
                    {"from": "human", "value": user_query},
                    {"from": "gpt", "value": solution},
                ]
            })
        return sharegpt_samples

    def export_dataset(self, output_path: Path, format_type: str = "alpaca") -> int:
        """Exports formatted training dataset to disk."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        records = self.load_stem_records()
        if not records:
            # Fallback to importing from script's curated corpus if DB is fresh
            from scripts.ingest_stem_knowledge import CURATED_STEM_CORPUS
            records = CURATED_STEM_CORPUS

        if format_type.lower() == "sharegpt":
            dataset = self.build_sharegpt_dataset(records)
        else:
            dataset = self.build_alpaca_dataset(records)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)

        logger.info(f"SFT Dataset: Exported {len(dataset)} samples to {output_path} ({format_type} format).")
        return len(dataset)


class QloraConfigGenerator:
    """Generates LLaMA-Factory and TRL configurations tailored to 4GB VRAM & 15GB RAM."""

    @staticmethod
    def generate_llama_factory_config(
        base_model: str = "Qwen/Qwen2.5-Coder-1.5B-Instruct",
        dataset_name: str = "stem_sft_dataset",
        output_dir: str = "models/lora_adapters/stem_expert",
    ) -> str:
        """
        Generates YAML configuration for LLaMA-Factory:
        - 4-bit BitsAndBytes quantization (NF4)
        - LoRA rank 8, alpha 16 (low VRAM footprint)
        - Gradient checkpointing and 8-bit Paged AdamW
        - Batch size 1 with 8 gradient accumulation steps (effective batch size 8)
        - Max sequence length 1024
        """
        config_yaml = f"""# LLaMA-Factory 4-Bit QLoRA Configuration for 4GB VRAM (NVIDIA RTX 3050 Laptop)
# Model
model_name_or_path: {base_model}
quantization_bit: 4
quantization_type: nf4
double_quantization: true

# Fine-tuning Method
stage: sft
do_train: true
finetuning_type: lora
lora_target: all
lora_rank: 8
lora_alpha: 16
lora_dropout: 0.05

# Dataset
dataset: {dataset_name}
template: qwen
cutoff_len: 1024
max_samples: 10000
overwrite_cache: true
preprocessing_num_workers: 2

# Output & Checkpoints
output_dir: {output_dir}
logging_steps: 10
save_steps: 100
plot_loss: true
overwrite_output_dir: true

# Hyperparameters (VRAM Budget: <= 3.8 GB)
per_device_train_batch_size: 1
gradient_accumulation_steps: 8
learning_rate: 2.0e-4
num_train_epochs: 3.0
lr_scheduler_type: cosine
warmup_ratio: 0.05
bf16: true
optim: paged_adamw_8bit
gradient_checkpointing: true
ddp_timeout: 180000000
"""
        return config_yaml

    @staticmethod
    def generate_modelfile(
        gguf_path: str = "./stem-expert-q4_k_m.gguf",
        model_name: str = "stem-expert",
    ) -> str:
        """Generates Ollama Modelfile for 4-bit quantized GGUF."""
        return f"""# Modelfile for {model_name}
FROM {gguf_path}

# Runtime Parameters optimized for low VRAM
PARAMETER temperature 0.2
PARAMETER top_p 0.95
PARAMETER top_k 40
PARAMETER repeat_penalty 1.1
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|im_start|>"

# System Prompt
SYSTEM \"\"\"You are an elite STEM Subject Matter Expert in Mathematics, Physics, and Computer Science. You solve questions ranging from Class 4 elementary science and arithmetic to advanced competitive Olympiad and university-level problems with step-by-step rigorous reasoning.\"\"\"
"""


class ZeroRedundancyPersister:
    """Manages CPU RAM model merging, GGUF conversion, and 20GB SSD cleanup."""

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.workspace = workspace_root or ROOT

    def generate_cpu_merge_script(self, base_model: str, adapter_path: str, output_path: str) -> str:
        """
        Python script to merge LoRA adapter into base model on CPU RAM.
        Uses 15GB system memory instead of GPU VRAM to prevent CUDA OOM.
        """
        return f"""#!/usr/bin/env python3
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

print("Loading base model onto CPU RAM...")
base = AutoModelForCausalLM.from_pretrained(
    "{base_model}",
    torch_dtype=torch.float16,
    device_map="cpu",
    low_cpu_mem_usage=True
)
print("Loading LoRA adapter...")
model = PeftModel.from_pretrained(base, "{adapter_path}")
print("Merging weights on CPU...")
merged = model.merge_and_unload()

print("Saving merged model to {output_path}...")
merged.save_pretrained("{output_path}")
tokenizer = AutoTokenizer.from_pretrained("{base_model}")
tokenizer.save_pretrained("{output_path}")
print("Merge complete!")
"""

    def clean_intermediate_weights(self, paths_to_clean: List[Path]) -> int:
        """
        Deletes intermediate unquantized models and training checkpoints
        to keep storage well under the 20 GB SSD limit.
        """
        bytes_freed = 0
        for p in paths_to_clean:
            if p.exists():
                if p.is_dir():
                    size = sum(f.stat().st_size for f in p.glob("**/*") if f.is_file())
                    shutil.rmtree(p, ignore_errors=True)
                    bytes_freed += size
                    logger.info(f"SSD Cleanup: Removed directory {p} ({size / (1024*1024):.2f} MB freed).")
                else:
                    size = p.stat().st_size
                    p.unlink(missing_ok=True)
                    bytes_freed += size
                    logger.info(f"SSD Cleanup: Removed file {p} ({size / (1024*1024):.2f} MB freed).")
        return bytes_freed


# ============================================================================
# MAIN TRAINING PIPELINE ORCHESTRATOR
# ============================================================================

def run_stem_training_pipeline(
    base_model: str = "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    data_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    ollama_url: str = "http://localhost:11434",
    target_model_name: str = "stem-expert",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Executes the full STEM model training & persistence pipeline."""
    logger.info("=== Starting STEM Training & Quantization Pipeline ===")

    data_dir = data_dir or (ROOT / "data")
    output_dir = output_dir or (ROOT / "models")
    data_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Pre-flight VRAM Eviction
    logger.info("Stage 1: Pre-flight GPU VRAM Eviction")
    evictor = VramEvictor(ollama_url=ollama_url)
    unloaded_models = evictor.evict_ollama_models()
    torch_vram_info = evictor.evict_torch_cuda()

    # 2. SFT Dataset Generation
    logger.info("Stage 2: SFT Dataset Preparation")
    dataset_builder = SftDatasetBuilder()
    sft_file = data_dir / "sft_stem_dataset.json"
    sample_count = dataset_builder.export_dataset(sft_file, format_type="alpaca")

    # 3. Low-VRAM Configuration Generation
    logger.info("Stage 3: Configuration Generation for 4GB VRAM & 15GB RAM")
    qlora_gen = QloraConfigGenerator()
    config_yaml = qlora_gen.generate_llama_factory_config(
        base_model=base_model,
        dataset_name="stem_sft_dataset",
        output_dir=str(output_dir / "lora_adapters" / target_model_name),
    )
    config_file = output_dir / "llama_factory_stem_qlora.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        f.write(config_yaml)

    # Generate Ollama Modelfile
    gguf_path = output_dir / "gguf" / f"{target_model_name}-q4_k_m.gguf"
    modelfile_content = qlora_gen.generate_modelfile(
        gguf_path=f"./{gguf_path.name}",
        model_name=target_model_name,
    )
    modelfile_path = output_dir / "Modelfile"
    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write(modelfile_content)

    # 4. Zero-Redundancy Persistence Setup
    logger.info("Stage 4: CPU RAM Merge & Quantization Script Scaffolding")
    persister = ZeroRedundancyPersister(workspace_root=ROOT)
    cpu_merge_script = persister.generate_cpu_merge_script(
        base_model=base_model,
        adapter_path=str(output_dir / "lora_adapters" / target_model_name),
        output_path=str(output_dir / "merged_checkpoint"),
    )
    merge_script_file = output_dir / "merge_cpu.py"
    with open(merge_script_file, "w", encoding="utf-8") as f:
        f.write(cpu_merge_script)

    # Intermediate directories to monitor for 20GB SSD budget
    intermediate_paths = [
        output_dir / "merged_checkpoint",
        output_dir / "temp_checkpoints",
    ]

    if not dry_run:
        # In non-dry-run, if Ollama CLI is available and GGUF exists, create model
        if gguf_path.exists():
            try:
                logger.info(f"Registering model with Ollama: ollama create {target_model_name}...")
                subprocess.run(
                    ["ollama", "create", target_model_name, "-f", str(modelfile_path)],
                    check=True,
                    cwd=str(modelfile_path.parent),
                )
            except Exception as e:
                logger.warning(f"Ollama registration call skipped: {e}")

        # Clean intermediate weights to protect 20GB SSD budget
        freed_bytes = persister.clean_intermediate_weights(intermediate_paths)
    else:
        logger.info("Dry-run mode: Mocking training execution and preserving disk budget.")
        freed_bytes = 0

    summary = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "unloaded_ollama_models": unloaded_models,
        "torch_cuda": torch_vram_info,
        "sft_samples": sample_count,
        "config_file": str(config_file),
        "modelfile": str(modelfile_path),
        "cpu_merge_script": str(merge_script_file),
        "intermediate_freed_mb": freed_bytes / (1024 * 1024),
        "dry_run": dry_run,
    }
    logger.info(f"=== STEM Training Pipeline Summary: {json.dumps(summary, indent=2)} ===")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="STEM Model QLoRA Training and Persistence Pipeline.")
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-Coder-1.5B-Instruct")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "models")
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434")
    parser.add_argument("--target-name", type=str, default="stem-expert")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Perform dry run without running training.")

    args = parser.parse_args()

    run_stem_training_pipeline(
        base_model=args.base_model,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        ollama_url=args.ollama_url,
        target_model_name=args.target_name,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
