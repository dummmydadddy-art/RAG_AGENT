# Project: Polyglot Coding Agent (stem-coder-expert:latest)

## Architecture
- **Ingestion & Deduplication Pipeline**: `scripts/ingest_stem_knowledge.py` curates multi-language challenges across 8 Tier-1 languages, runs 3-tier deduplication (Exact Hash, Lexical Jaccard, Semantic Collision), and ingests embeddings into `backend/storage/vectors.sqlite` via Ollama (`nomic-embed-text`) with dual-table capping (<= 500 rows in `material_chunks`) to protect PHP's 128 MB limit.
- **Fine-Tuning Engine**: `scripts/train_stem_model.py` and `models/llama_factory_stem_qlora.yaml` enforce pre-flight VRAM eviction (`keep_alive: 0`), 4-bit NF4 double quant, paged 8-bit AdamW, gradient checkpointing, and seq cutoff <= 1024 on `Qwen/Qwen2.5-Coder-1.5B-Instruct` to guarantee peak GPU VRAM <= 3.8 GB.
- **Merge & Quantization Engine**: `models/merge_cpu.py` performs CPU RAM LoRA merging (<= 12 GB RAM, 0 MiB VRAM), followed by `llama-quantize.exe` (Q4_K_M) and Ollama registration (`stem-coder-expert:latest`), with immediate atomic purging of unquantized weights to keep net SSD <= 10 GB.
- **Polyglot Verification Engine**: `scripts/verify_polyglot.py` runs automated verification across all 8 languages against the 4-pillar quality gate (SVR 100%, LCR >= 85%, EPR 100%, RFC 100%).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | F1: Polyglot Dataset Curation | Curate programming challenges, reference solutions, and unit tests across 8 languages and 4 difficulty tiers | M1 | Survey (Explorer 2) |
| 2 | F2: 3-Tier Deduplication | Exact SHA-256 hash, Lexical Jaccard (0.82), and Semantic Collision (0.92) deduplication | M1 | Survey (Explorer 2) |
| 3 | F3: SQLite Vector Ingestion | 768-d vector embedding with dual-table segregation protecting PHP 128 MB memory limit | M1 | Survey (Explorer 1, 2) |
| 4 | F4: Pre-Flight VRAM Eviction | Evict background GPU processes and Ollama models (`keep_alive: 0`) for 0 MiB active baseline | M2 | Survey (Explorer 1, 2) |
| 5 | F5: 4-Bit QLoRA Fine-Tuning | QLoRA on Qwen2.5-Coder-1.5B with paged 8-bit AdamW, grad checkpointing, seq <= 1024, peak VRAM <= 3.8 GB | M2 | Survey (Explorer 2) |
| 6 | F6: CPU RAM LoRA Merge | Merge adapter into base model on CPU RAM using <= 12 GB RAM with 0 MiB GPU VRAM | M3 | Survey (Explorer 3) |
| 7 | F7: GGUF Q4_K_M Quantization | Convert merged model to GGUF and quantize using local native llama-quantize.exe | M3 | Survey (Explorer 1, 3) |
| 8 | F8: Zero-Redundancy SSD Purge | Atomic purge of intermediate checkpoints and FP16 weights keeping net SSD <= 10 GB | M3 | Survey (Explorer 3) |
| 9 | F9: Ollama Registration | Create custom Modelfile with ChatML template and deploy as stem-coder-expert:latest | M3 | Survey (Explorer 3) |
| 10 | F10: Automated Polyglot Quality Gate | Comprehensive automated verification across 8 languages and 4-pillar quality gate | M4 | Survey (Explorer 3) |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Polyglot Dataset Ingestion & Deduplication | Features F1, F2, F3 | none | DONE |
| M2 | Low-Resource 4-Bit QLoRA Fine-Tuning | Features F4, F5 | M1 | DONE |
| M3 | CPU Merge, GGUF Quantization & Ollama Deployment | Features F6, F7, F8, F9 | M2 | DONE |
| M4 | Automated Polyglot Verification & Quality Gate | Feature F10 | M3 | DONE |

## Interface Contracts
### M1 ↔ M2 (Dataset Ingestion ↔ Training Engine)
- Output File: `data/polyglot_instruct_dataset.json` (Alpaca / ShareGPT format with `instruction`, `input`, `output`).
- Required Schema: Valid JSON array containing balanced samples across all 8 languages (Python, TypeScript, C++, Java, Rust, Go, PHP, SQL).
- Validation: Non-empty, zero duplicates per 3-tier deduplication, valid UTF-8, sequence tokens <= 1024.

### M2 ↔ M3 (Training Engine ↔ Merge & Quantization)
- Output Directory: `models/lora_adapters/stem-coder-expert/`
- Required Files: `adapter_model.safetensors`, `adapter_config.json`, `tokenizer.json`, `tokenizer_config.json`.
- Peak Hardware Constraint: Training strictly verified peak VRAM <= 3.8 GB with zero CUDA OOM.

### M3 ↔ M4 (Deployment ↔ Verification Gate)
- Ollama Tag: `stem-coder-expert:latest`
- Quantization: GGUF `q4_k_m` format (~1.05 GB)
- Net SSD Footprint: Purged unquantized weights; net disk usage <= 10 GB.
- API Endpoint: `http://localhost:11434/api/generate` and `http://localhost:11434/api/chat` responding with ChatML format.

## Code Layout
- `backend/`
  - `rag_service.php`: PHP 8.3 RAG API endpoint and hybrid retrieval
  - `storage/vectors.sqlite`: SQLite vector database
- `scripts/`
  - `ingest_stem_knowledge.py`: Polyglot ingestion and 3-tier deduplication
  - `train_stem_model.py`: Training engine with pre-flight VRAM eviction
  - `verify_polyglot.py`: 8-language verification harness
- `models/`
  - `merge_cpu.py`: CPU-only weight merger
  - `Modelfile`: Ollama model configuration
  - `llama_factory_stem_qlora.yaml`: Training hyperparameters
- `tests/`
  - `unit/`: Unit tests for components
  - `e2e/`: Opaque-box requirement-driven E2E test suite
