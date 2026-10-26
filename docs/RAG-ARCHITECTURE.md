# RAG Agent — Architecture & Repurposing Guide

This folder contains the **complete, standalone RAG (Retrieval-Augmented Generation) engine**
extracted from the EduConnect LMS. You can repurpose this for any domain.

---

## 📁 Folder Structure

```
D:\RAG-Agent\
├── backend/
│   ├── rag_service.php                 ← CORE: Hybrid BM25 + Dense + RRF retrieval pipeline
│   ├── rag_structured_nli_verifier.php ← Prevents hallucinations via NLI claim verification
│   ├── rag_premise_verifier.php        ← Detects false premises in questions
│   ├── rag_query_condenser.php         ← Multi-turn conversation query reformer
│   ├── rag_safety_boundary.php         ← Domain/topic safety boundary filter
│   ├── rag_intent_clause_verifier.php  ← Intent and clause verification
│   ├── document_extractor.php          ← PDF/text document parser & chunker
│   ├── seed_rag_knowledge.php          ← Seeds knowledge base with embeddings
│   ├── index.php                       ← REST API router (all RAG endpoints)
│   ├── auth_middleware.php             ← JWT authentication guard
│   ├── config.php                      ← DB credentials & Ollama config (EDIT THIS)
│   ├── db.php                          ← Supabase/PostgreSQL connection
│   └── .htaccess                       ← PHP routing rules
├── database/
│   ├── rag_migration.sql               ← Full vector DB schema (pgvector + chunks table)
│   └── remediation.sql                 ← Supplementary schema patches
├── frontend/
│   ├── AiTutorModal.tsx                ← Chat UI with SSE streaming + voice input
│   ├── ConceptDoctorModal.tsx          ← Socratic drill-down Q&A UI
│   ├── KnowledgeGapHeatmap.tsx         ← Analytics heatmap component
│   └── StudentMasteryJourney.tsx       ← Progress tracking UI
├── workflow_fixed.json                 ← n8n Telegram bot workflow (bot integration)
├── test_rag_pipeline.php               ← 10-point automated test suite
└── docs/
    └── RAG-ARCHITECTURE.md             ← This file
```

---

## 🤖 Tech Stack

| Layer | Technology |
|---|---|
| **Embeddings** | Ollama `nomic-embed-text` (768-dim vectors) |
| **LLM Synthesis** | Ollama `llama3.2` (3B param, runs locally) |
| **Vector Store** | Supabase PostgreSQL + `pgvector` extension |
| **Retrieval** | Hybrid BM25 sparse + Dense vector + RRF fusion |
| **Verification** | Structured NLI claim checking (prevents hallucinations) |
| **API** | PHP 8.x REST endpoints |

---

## 🔧 To Repurpose for a New Agent

### Step 1 — Change the Knowledge Base
Edit `backend/seed_rag_knowledge.php`:
- Replace the LMS course materials with **your domain's documents**
- Point it to your new PDF/text files
- Run it once to embed everything into the vector DB

### Step 2 — Update the Safety Boundary
Edit `backend/rag_safety_boundary.php`:
- Change the topic whitelist to match your new domain
- Remove LMS-specific restrictions (curriculum, courses, etc.)

### Step 3 — Update Config
Edit `backend/config.php`:
- Set your Supabase URL + key
- Set your Ollama endpoint (default: `http://localhost:11434`)
- Change the `SERVICE_KEY` for API auth

### Step 4 — Run the DB Migration
In your Supabase SQL editor, run:
```sql
-- database/rag_migration.sql
```

### Step 5 — Seed Your Documents
```bash
php backend/seed_rag_knowledge.php
```

### Step 6 — Test
```bash
php test_rag_pipeline.php
```

---

## 🔌 Key API Endpoints (from index.php)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/rag/search` | Main Q&A query endpoint |
| `POST` | `/api/rag/seed` | Seed documents into vector DB |
| `GET`  | `/api/rag/status` | Health check |
| `POST` | `/api/rag/stream` | SSE streaming response |

---

## 🚀 Quick Start

```powershell
# 1. Start Ollama (must be running)
ollama serve

# 2. Pull required models
ollama pull nomic-embed-text
ollama pull llama3.2

# 3. Start PHP server
php -S localhost:8000 -t backend/

# 4. Test the pipeline
php test_rag_pipeline.php
```
