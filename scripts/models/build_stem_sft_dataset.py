#!/usr/bin/env python3
"""
scripts/models/build_stem_sft_dataset.py

SFT Dataset Ingestion Pipeline & Autonomous Self-Play Bridge (Milestone 1 / Feature F9).
Harvests verified self-play cycles and distilled APERL lessons from SQLite (`vectors.sqlite`),
filters out retired or malformed entries, deduplicates via 3-tier hashing/shingling,
formats into Alpaca / ShareGPT schemas conditioned on canonical engineering lessons,
bounds sequences to <= 1024 tokens (<= 4096 characters), and routes samples into modular
LoRA domain datasets (`stem-physics-math`, `systems-lowlevel`, `web-data`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.models.adapter_manager import AdapterDomain, LoRAAdapterManager

logger = logging.getLogger("build_stem_sft_dataset")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_DB_PATH = ROOT / "backend" / "storage" / "vectors.sqlite"
DEFAULT_OUTPUT_PATH = ROOT / "data" / "sft_self_play_dataset.json"
TRUNCATION_SUFFIX = "\n... [truncated]"


# ============================================================================
# 1. LESSON VALIDATION & CASCADE TRUNCATION
# ============================================================================

def _is_valid_lesson(text: str, meta: Optional[Dict[str, Any]] = None) -> bool:
    """Returns True iff lesson is non-empty, non-retired, and free of 'When None' corruption."""
    clean = str(text or "").strip()
    if not clean or "When None" in clean:
        return False
    if meta and str(meta.get("status", "")).strip().lower() == "retired":
        return False
    return True


def cascade_truncate(text: str, max_chars: int = 4096) -> str:
    """
    Truncates `text` to at most `max_chars` characters while preserving line
    boundaries and closing unclosed markdown code fences whenever possible.
    """
    raw = str(text or "")
    if max_chars <= 0:
        return ""
    if len(raw) <= max_chars:
        return raw

    # Determine whether closing an open markdown fence is needed
    reserve_plain = len(TRUNCATION_SUFFIX)
    reserve_fence = len("\n```") + len(TRUNCATION_SUFFIX)

    if max_chars <= reserve_plain + 4:
        return raw[:max_chars]

    # Tentative slice leaving room for plain suffix
    tentative_limit = max_chars - reserve_plain
    prefix = raw[:tentative_limit]

    # Snap back to last newline if it retains >= 70% of budget
    last_nl = prefix.rfind("\n")
    if last_nl >= int(tentative_limit * 0.7):
        prefix = prefix[:last_nl]

    # Avoid splitting an opening/closing triple-backtick token in half
    if prefix.endswith("``") or (prefix.endswith("`") and not prefix.endswith("```")):
        prefix = prefix.rstrip("`")

    # If cutting inside an odd number of triple-backtick fences, close fence cleanly
    if prefix.count("```") % 2 == 1 and max_chars > reserve_fence + 8:
        fence_limit = max_chars - reserve_fence
        prefix = raw[:fence_limit]
        last_nl = prefix.rfind("\n")
        if last_nl >= int(fence_limit * 0.7):
            prefix = prefix[:last_nl]
        if prefix.endswith("``") or (prefix.endswith("`") and not prefix.endswith("```")):
            prefix = prefix.rstrip("`")
        # Re-check parity after potential snapback
        if prefix.count("```") % 2 == 1:
            result = f"{prefix}\n```{TRUNCATION_SUFFIX}"
        else:
            result = f"{prefix}{TRUNCATION_SUFFIX}"
    else:
        result = f"{prefix}{TRUNCATION_SUFFIX}"

    if len(result) > max_chars:
        result = result[:max_chars]
    return result


def truncate_alpaca_fields(
    instruction: str,
    input_text: str,
    output_text: str,
    max_char_limit: int = 4096,
) -> Tuple[str, str, str]:
    """
    Symmetrically bounds (instruction, input_text, output_text) so their combined
    character length is strictly <= max_char_limit (default 4096 chars ~= 1024 tokens).
    Priority: truncate output first, then input, then instruction.
    """
    inst = str(instruction or "")
    inp = str(input_text or "")
    out = str(output_text or "")

    if max_char_limit <= 0:
        return "", "", ""

    if len(inst) + len(inp) + len(out) <= max_char_limit:
        return inst, inp, out

    out_floor = min(200, max_char_limit)
    inp_floor = min(100, max_char_limit)
    inst_floor = min(50, max_char_limit)

    # 1. Truncate output first (preserving floor when budget allows)
    if len(out) > out_floor:
        target_out = max(out_floor, max_char_limit - len(inst) - len(inp))
        if target_out < len(out):
            out = cascade_truncate(out, max_chars=target_out)

    # 2. Truncate input if still overflowing
    if len(inst) + len(inp) + len(out) > max_char_limit and len(inp) > inp_floor:
        target_inp = max(inp_floor, max_char_limit - len(inst) - len(out))
        if target_inp < len(inp):
            inp = cascade_truncate(inp, max_chars=target_inp)

    # 3. Truncate instruction if still overflowing
    if len(inst) + len(inp) + len(out) > max_char_limit and len(inst) > inst_floor:
        target_inst = max(inst_floor, max_char_limit - len(inp) - len(out))
        if target_inst < len(inst):
            inst = cascade_truncate(inst, max_chars=target_inst)

    # 4. Iterative clamp with cascade_truncate if tight max_char_limit still exceeded
    if len(inst) + len(inp) + len(out) > max_char_limit:
        target_out = max(0, max_char_limit - len(inst) - len(inp))
        if len(out) > target_out:
            out = cascade_truncate(out, max_chars=target_out) if target_out > 0 else ""

    if len(inst) + len(inp) + len(out) > max_char_limit:
        target_inp = max(0, max_char_limit - len(inst) - len(out))
        if len(inp) > target_inp:
            inp = cascade_truncate(inp, max_chars=target_inp) if target_inp > 0 else ""

    if len(inst) + len(inp) + len(out) > max_char_limit:
        target_inst = max(0, max_char_limit - len(inp) - len(out))
        if len(inst) > target_inst:
            inst = cascade_truncate(inst, max_chars=target_inst) if target_inst > 0 else ""

    # 5. Final mathematical safety clamp across out -> inp -> inst
    total = len(inst) + len(inp) + len(out)
    if total > max_char_limit:
        excess = total - max_char_limit
        trim = min(len(out), excess)
        if trim:
            out = out[:-trim]
            excess -= trim
        trim = min(len(inp), excess)
        if trim:
            inp = inp[:-trim]
            excess -= trim
        if excess > 0:
            inst = inst[: max(0, len(inst) - excess)]

    return inst, inp, out


# ============================================================================
# 2. SELF-PLAY HARVESTING FROM SQLITE
# ============================================================================

def _resolve_legacy_challenge_template(domain: str, language: str) -> Tuple[str, str]:
    """
    Resolves prompt and reference_solution for legacy accuracy_benchmarks rows
    that predate storing full prompt/solution inside `details`.
    """
    try:
        from scripts.learning.synthetic_challenge_generator import SyntheticChallengeGenerator

        gen = SyntheticChallengeGenerator()
        dom_norm = str(domain or "").strip().lower()
        gen_dom = "concurrency" if dom_norm == "systems_concurrency" else dom_norm
        canonical_dom = gen.DOMAIN_ALIASES.get(gen_dom, gen_dom)
        lang_norm = str(language or "python").strip().lower()

        if canonical_dom in gen.CHALLENGE_TEMPLATES and lang_norm == "python":
            ch = gen.generate_challenge(domain=canonical_dom, language=lang_norm)
            return ch.prompt, ch.reference_solution
    except Exception as exc:
        logger.debug("Legacy template fallback skipped for domain=%s: %s", domain, exc)
    return "", ""


def _load_active_lessons(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    """Loads non-retired, non-corrupt lessons from `rag_documents` indexed by id."""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rag_documents';")
    if not cur.fetchone():
        return {}

    cur.execute(
        "SELECT id, text, metadata FROM rag_documents WHERE collection = 'lessons' ORDER BY created_at DESC"
    )
    lessons_by_id: Dict[str, Dict[str, Any]] = {}
    for row in cur.fetchall():
        doc_id = str(row["id"])
        text = str(row["text"] or "")
        raw_meta = row["metadata"]
        try:
            meta = json.loads(raw_meta) if raw_meta else {}
        except Exception:
            meta = {}

        if not _is_valid_lesson(text, meta):
            continue

        lessons_by_id[doc_id] = {
            "id": doc_id,
            "text": text.strip(),
            "meta": meta,
            "status": str(meta.get("status", "candidate")).lower(),
            "source_task": str(meta.get("source_task", "")),
            "domain": str(meta.get("domain", "")).lower(),
            "usage_count": int(meta.get("usage_count", meta.get("use_count", 0)) or 0),
            "strength": float(meta.get("strength", 10.0) or 10.0),
        }
    return lessons_by_id


def _load_all_lesson_statuses(conn: sqlite3.Connection) -> Dict[str, Tuple[str, str]]:
    """Maps every lesson_id (including retired/malformed) to (status, text) for explicit exclusion checks."""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rag_documents';")
    if not cur.fetchone():
        return {}

    cur.execute("SELECT id, text, metadata FROM rag_documents WHERE collection = 'lessons'")
    statuses: Dict[str, Tuple[str, str]] = {}
    for row in cur.fetchall():
        doc_id = str(row["id"])
        text = str(row["text"] or "")
        try:
            meta = json.loads(row["metadata"]) if row["metadata"] else {}
        except Exception:
            meta = {}
        statuses[doc_id] = (str(meta.get("status", "candidate")).lower(), text)
    return statuses


def _match_lesson_for_sample(
    challenge_id: str,
    domain: str,
    details: Dict[str, Any],
    active_lessons: Dict[str, Dict[str, Any]],
    all_lesson_statuses: Dict[str, Tuple[str, str]],
) -> Tuple[str, str]:
    """
    Matches the most relevant valid canonical lesson for a benchmark sample.
    Explicitly excludes retired or 'When None' lessons.
    Returns (lesson_id, lesson_text).
    """
    explicit_id = str(details.get("lesson_id") or "").strip()
    if explicit_id:
        if explicit_id in active_lessons:
            entry = active_lessons[explicit_id]
            return entry["id"], entry["text"]
        if explicit_id in all_lesson_statuses:
            # Explicit lesson exists in DB and was retired/malformed -> must NOT attach!
            return "", ""

    # Check inline lesson only if not flagged malformed and not matching a retired DB entry
    inline_lesson = str(details.get("lesson") or "").strip()
    retired_texts = {
        txt.strip() for st, txt in all_lesson_statuses.values() if st == "retired" and txt
    }
    inline_status = str(details.get("lesson_status") or "").strip().lower()
    if (
        inline_lesson
        and _is_valid_lesson(inline_lesson, {"status": inline_status} if inline_status else None)
        and inline_lesson not in retired_texts
    ):
        return explicit_id, inline_lesson

    # Match by source_task == challenge_id
    if challenge_id:
        for entry in active_lessons.values():
            if entry["source_task"] == challenge_id:
                return entry["id"], entry["text"]

    # Match by domain (preferring verified + high usage)
    dom_norm = str(domain or "").strip().lower()
    dom_aliases = {dom_norm}
    if dom_norm == "systems_concurrency":
        dom_aliases.add("concurrency")
    elif dom_norm == "concurrency":
        dom_aliases.add("systems_concurrency")

    domain_candidates = [
        entry for entry in active_lessons.values()
        if entry["domain"] in dom_aliases
    ]
    if domain_candidates:
        domain_candidates.sort(
            key=lambda e: (1 if e["status"] == "verified" else 0, e["usage_count"], e["strength"]),
            reverse=True,
        )
        best = domain_candidates[0]
        return best["id"], best["text"]

    return "", ""


def harvest_verified_self_play_samples(
    db_path: Path | str,
    min_pass_rate: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Queries `accuracy_benchmarks` in SQLite for verified self-play executions
    (`pass_at_1 >= min_pass_rate` and `test_pass_rate >= min_pass_rate`),
    extracts problem-solution pairs, matches them with active canonical APERL
    lessons in `rag_documents` (`collection = 'lessons'`), and strictly excludes
    retired or malformed ('When None...') lessons.
    """
    target_path = Path(db_path)
    if not target_path.exists():
        logger.warning("SQLite database not found at %s; returning empty sample list.", target_path)
        return []

    harvested: List[Dict[str, Any]] = []
    try:
        uri = f"file:{target_path.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=10.0) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 10000;")
            cur = conn.cursor()

            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accuracy_benchmarks';")
            if not cur.fetchone():
                return []

            active_lessons = _load_active_lessons(conn)
            all_statuses = _load_all_lesson_statuses(conn)

            cur.execute(
                """
                SELECT id, timestamp, cycle_iteration, pass_at_1, test_pass_rate,
                       invariant_violation_rate, details
                FROM accuracy_benchmarks
                WHERE pass_at_1 >= ? AND test_pass_rate >= ?
                ORDER BY cycle_iteration ASC, timestamp ASC
                """,
                (float(min_pass_rate), float(min_pass_rate)),
            )
            rows = cur.fetchall()
    except Exception as exc:
        logger.warning("Failed harvesting samples from %s: %s", target_path, exc)
        return []

    for row in rows:
        raw_details = row["details"]
        if isinstance(raw_details, str):
            try:
                details = json.loads(raw_details) if raw_details.strip() else {}
            except Exception:
                logger.debug("Skipping benchmark %s with malformed JSON details.", row["id"])
                continue
        elif isinstance(raw_details, dict):
            details = raw_details
        else:
            continue

        if not isinstance(details, dict):
            continue

        if float(min_pass_rate) > 0.0 and (details.get("ast_violation") or details.get("timeout")):
            continue
        if float(min_pass_rate) >= 1.0 and float(row["invariant_violation_rate"] or 0.0) > 0.0:
            continue

        domain = str(details.get("domain") or "stem").strip().lower()
        language = str(details.get("language") or "python").strip().lower()
        difficulty = str(details.get("difficulty") or "advanced").strip().lower()
        challenge_id = str(details.get("challenge_id") or row["id"]).strip()

        prompt = str(details.get("prompt") or details.get("instruction") or details.get("question") or "").strip()
        solution = str(
            details.get("solution") or details.get("answer") or details.get("output") or details.get("code") or ""
        ).strip()

        if not prompt or not solution:
            # Resolve legacy self-play benchmark entries lacking inline prompt/solution
            fb_prompt, fb_solution = _resolve_legacy_challenge_template(domain, language)
            prompt = prompt or fb_prompt
            solution = solution or fb_solution

        if not prompt or not solution:
            continue

        lesson_id, lesson_text = _match_lesson_for_sample(
            challenge_id=challenge_id,
            domain=domain,
            details=details,
            active_lessons=active_lessons,
            all_lesson_statuses=all_statuses,
        )

        harvested.append({
            "benchmark_id": str(row["id"]),
            "cycle_iteration": int(row["cycle_iteration"]),
            "challenge_id": challenge_id,
            "domain": domain,
            "language": language,
            "difficulty": difficulty,
            "prompt": prompt,
            "solution": solution,
            "lesson_id": lesson_id,
            "lesson": lesson_text,
            "pass_at_1": float(row["pass_at_1"]),
            "test_pass_rate": float(row["test_pass_rate"]),
            "timestamp": str(row["timestamp"] or ""),
        })

    return harvested


# ============================================================================
# 3. DEDUPLICATION (3-TIER SILVER DEDUP)
# ============================================================================

def _normalize_for_hash(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", str(text or "").lower())
    return " ".join(cleaned.split())


def _word_shingles(text: str, k: int = 3) -> Set[str]:
    words = _normalize_for_hash(text).split()
    if not words:
        return set()
    if len(words) < k:
        return {" ".join(words)}
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a.intersection(b)) / len(a.union(b))


def deduplicate_samples(
    samples: Sequence[Dict[str, Any]],
    fuzzy_threshold: float = 0.85,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Applies 3-tier deduplication (Exact SHA-256, Lexical Jaccard shingles, Semantic signature)
    while preserving genuinely distinct problems and distinct implementations.
    """
    retained: List[Dict[str, Any]] = []
    seen_hashes: Set[str] = set()
    retained_shingles: List[Tuple[str, Set[str]]] = []
    seen_semantic_keys: Set[str] = set()

    stats = {
        "total_input": len(samples),
        "tier1_exact_duplicates": 0,
        "tier2_fuzzy_duplicates": 0,
        "tier3_semantic_duplicates": 0,
        "retained": 0,
    }

    for sample in samples:
        prompt = str(sample.get("prompt") or sample.get("question") or sample.get("instruction") or "").strip()
        solution = str(
            sample.get("solution") or sample.get("answer") or sample.get("output") or sample.get("code") or ""
        ).strip()
        domain = str(sample.get("domain") or "stem").strip().lower()
        language = str(sample.get("language") or "python").strip().lower()

        norm_prompt = _normalize_for_hash(prompt)
        norm_solution = _normalize_for_hash(solution)

        # Tier 1: Exact Hash
        exact_hash = hashlib.sha256(
            f"{domain}||{language}||{norm_prompt}||{norm_solution}".encode("utf-8")
        ).hexdigest()
        if exact_hash in seen_hashes:
            stats["tier1_exact_duplicates"] += 1
            continue

        # Tier 2: Lexical Jaccard similarity on combined problem+solution text
        shingles = _word_shingles(f"{prompt} {solution}")
        is_fuzzy_dup = False
        for existing_dom, existing_shingles in retained_shingles:
            if existing_dom == domain and _jaccard(shingles, existing_shingles) >= fuzzy_threshold:
                is_fuzzy_dup = True
                break
        if is_fuzzy_dup:
            stats["tier2_fuzzy_duplicates"] += 1
            continue

        # Tier 3: Semantic key collision across prompt signature and sampled solution tokens
        prompt_tokens = [w for w in norm_prompt.split() if len(w) > 3][:8]
        sol_words = [w for w in norm_solution.split() if len(w) > 2]
        if len(sol_words) > 9:
            mid = len(sol_words) // 2
            sol_sample = sol_words[:3] + sol_words[mid - 1 : mid + 2] + sol_words[-3:]
        else:
            sol_sample = sol_words
        sem_key = f"{domain}:{language}:{'_'.join(prompt_tokens)}::{'_'.join(sol_sample)}"
        if sem_key in seen_semantic_keys:
            stats["tier3_semantic_duplicates"] += 1
            continue

        seen_hashes.add(exact_hash)
        retained_shingles.append((domain, shingles))
        seen_semantic_keys.add(sem_key)
        retained.append(dict(sample))

    stats["retained"] = len(retained)
    return retained, stats


# ============================================================================
# 4. DATASET FORMATTING (ALPACA & SHAREGPT)
# ============================================================================

def _extract_prompt_fields(rec: Dict[str, Any]) -> Tuple[str, str, str, str, str, str]:
    """Extracts normalized (instruction, base_input, output, domain, language, lesson) from a sample."""
    domain = str(rec.get("domain") or "stem").strip().lower()
    language = str(rec.get("language") or "python").strip().lower()
    difficulty = str(rec.get("difficulty") or "advanced").strip().lower()

    raw_lesson = str(rec.get("lesson") or "").strip()
    lesson_status = str(rec.get("lesson_status") or "").strip().lower()
    lesson_meta = {"status": lesson_status} if lesson_status else None
    lesson = raw_lesson if _is_valid_lesson(raw_lesson, lesson_meta) else ""

    if "instruction" in rec and any(k in rec for k in ("output", "solution", "answer", "code")):
        instruction = str(rec.get("instruction") or "").strip()
        base_input = str(rec.get("input") or "").strip()
        output = str(
            rec.get("output") or rec.get("solution") or rec.get("answer") or rec.get("code") or ""
        ).strip()
    else:
        prompt = str(rec.get("prompt") or rec.get("question") or "").strip()
        instruction = (
            f"Domain: {domain.upper()} | Language: {language.upper()} | Difficulty: {difficulty}\n"
            f"Question / Challenge:\n{prompt}"
        ) if prompt else ""
        base_input = str(rec.get("input") or "").strip()
        output = str(
            rec.get("solution") or rec.get("answer") or rec.get("output") or rec.get("code") or ""
        ).strip()

    return instruction, base_input, output, domain, language, lesson


def build_alpaca_records(
    samples: Sequence[Dict[str, Any]],
    condition_with_lessons: bool = True,
    max_tokens: int = 1024,
) -> List[Dict[str, str]]:
    """
    Formats verified samples into Alpaca instruction-tuning schema:
    {"instruction": str, "input": str, "output": str, "domain": str, "lesson": str, "language": str}.
    When `condition_with_lessons=True`, embeds the canonical APERL lesson in `input`.
    Strictly enforces combined sequence cutoff <= max_tokens * 4 characters (<= 4096 chars).
    """
    max_char_limit = max(64, int(max_tokens * 4))
    records: List[Dict[str, str]] = []

    for sample in samples:
        instruction, base_input, output, domain, language, lesson = _extract_prompt_fields(sample)
        if not instruction or not output:
            continue

        if condition_with_lessons and lesson:
            if base_input and lesson not in base_input:
                input_text = f"{base_input}\n\nEngineering Lesson:\n{lesson}"
            elif not base_input:
                input_text = f"Engineering Lesson:\n{lesson}"
            else:
                input_text = base_input
            effective_lesson = lesson
        else:
            input_text = base_input
            effective_lesson = ""

        inst_b, inp_b, out_b = truncate_alpaca_fields(
            instruction=instruction,
            input_text=input_text,
            output_text=output,
            max_char_limit=max_char_limit,
        )

        records.append({
            "instruction": inst_b,
            "input": inp_b,
            "output": out_b,
            "domain": domain,
            "language": language,
            "lesson": effective_lesson,
        })

    return records


def build_sharegpt_records(
    samples: Sequence[Dict[str, Any]],
    condition_with_lessons: bool = True,
    max_tokens: int = 1024,
    include_system: bool = False,
) -> List[Dict[str, Any]]:
    """
    Formats verified samples into ShareGPT / ChatML conversation format:
    {"conversations": [{"from": "human", "value": ...}, {"from": "gpt", "value": ...}], "domain": ..., "lesson": ...}.
    Enforces total sequence character cutoff <= max_tokens * 4 (<= 4096 chars).
    """
    max_char_limit = max(64, int(max_tokens * 4))
    records: List[Dict[str, Any]] = []
    system_prompt = (
        "You are STEM-Coder-Expert, an elite algorithmic, systems, and numerical physics engineer."
    )

    for sample in samples:
        instruction, base_input, output, domain, language, lesson = _extract_prompt_fields(sample)
        if not instruction or not output:
            continue

        human_parts = [instruction]
        if base_input:
            human_parts.append(f"Context / Input:\n{base_input}")
        if condition_with_lessons and lesson and lesson not in base_input:
            human_parts.append(f"Relevant Engineering Lesson:\n{lesson}")
        human_text = "\n\n".join(human_parts)
        effective_lesson = lesson if condition_with_lessons else ""

        sys_value = system_prompt
        if include_system and len(sys_value) >= max_char_limit:
            sys_value = sys_value[: max(0, max_char_limit // 2)]
        sys_budget = len(sys_value) if include_system else 0
        available = max(0, max_char_limit - sys_budget)
        human_b, _, gpt_b = truncate_alpaca_fields(
            instruction=human_text,
            input_text="",
            output_text=output,
            max_char_limit=available,
        )

        conversations: List[Dict[str, str]] = []
        if include_system:
            conversations.append({"from": "system", "value": sys_value})
        conversations.append({"from": "human", "value": human_b})
        conversations.append({"from": "gpt", "value": gpt_b})

        records.append({
            "conversations": conversations,
            "domain": domain,
            "language": language,
            "lesson": effective_lesson,
        })

    return records


# ============================================================================
# 5. MODULAR LORA DOMAIN ROUTING
# ============================================================================

def route_samples_to_modular_domains(
    samples: Sequence[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Routes samples into the three modular LoRA adapter domains defined in
    `scripts/models/adapter_manager.py`:
    - `stem-physics-math` (Physics, Math, Dynamic Programming, Graph Algorithms)
    - `systems-lowlevel` (Systems Concurrency, Rust, C++, C, Go, Lock-Free / Pools)
    - `web-data` (TypeScript, JavaScript, PHP, SQL, REST, SQLite)
    """
    manager = LoRAAdapterManager()
    routed: Dict[str, List[Dict[str, Any]]] = {
        domain.value: [] for domain in manager.list_registered_domains()
    }
    valid_domain_values = set(routed.keys())

    for sample in samples:
        dom = str(sample.get("domain") or "").strip().lower()
        lang = str(sample.get("language") or "").strip().lower()

        # Construct combined text for semantic fallback
        text_parts = [
            str(sample.get("prompt") or ""),
            str(sample.get("question") or ""),
            str(sample.get("instruction") or ""),
            str(sample.get("input") or ""),
            str(sample.get("solution") or sample.get("answer") or sample.get("output") or ""),
        ]
        if "conversations" in sample and isinstance(sample["conversations"], list):
            for turn in sample["conversations"]:
                if isinstance(turn, dict):
                    text_parts.append(str(turn.get("value") or ""))
        query_text = "\n".join(p for p in text_parts if p)

        # 1. Explicit modular domain tag
        if dom in valid_domain_values:
            target_domain = dom
        # 2. Explicit programming language overrides matching LoRAAdapterManager
        elif lang in ("rust", "c++", "cpp", "c", "go"):
            target_domain = AdapterDomain.SYSTEMS_LOWLEVEL.value
        elif lang in ("typescript", "ts", "javascript", "js", "php", "sql"):
            target_domain = AdapterDomain.WEB_DATA.value
        # 3. Explicit self-play domain tags
        elif dom in ("systems_concurrency", "concurrency", "systems", "lowlevel", "systems_lowlevel"):
            target_domain = AdapterDomain.SYSTEMS_LOWLEVEL.value
        elif dom in (
            "numerical_physics", "physics", "maths", "math",
            "dynamic_programming", "dp", "graph_algorithms", "graphs", "graph",
        ):
            target_domain = AdapterDomain.STEM_PHYSICS_MATH.value
        elif dom in ("web", "web_data", "web_api", "database", "sql", "api"):
            target_domain = AdapterDomain.WEB_DATA.value
        else:
            # 4. Delegate to LoRAAdapterManager heuristic keyword router
            target_domain = manager.route_domain(query=query_text, language=lang or None).value

        routed[target_domain].append(dict(sample))

    return routed


def export_modular_domain_datasets(
    samples: Sequence[Dict[str, Any]],
    output_dir: Path | str,
    format_type: str = "alpaca",
    max_tokens: int = 1024,
    condition_with_lessons: bool = True,
) -> Dict[str, int]:
    """
    Routes deduplicated samples across modular LoRA domains and writes
    `<domain>.json` files into `output_dir`. Returns sample count per domain.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    routed = route_samples_to_modular_domains(samples)
    counts: Dict[str, int] = {}

    fmt = format_type.strip().lower()
    if fmt not in ("alpaca", "sharegpt"):
        raise ValueError(f"Unsupported format_type '{format_type}'. Expected 'alpaca' or 'sharegpt'.")

    for domain_name, domain_samples in routed.items():
        if fmt == "sharegpt":
            formatted = build_sharegpt_records(
                domain_samples,
                condition_with_lessons=condition_with_lessons,
                max_tokens=max_tokens,
            )
        else:
            formatted = build_alpaca_records(
                domain_samples,
                condition_with_lessons=condition_with_lessons,
                max_tokens=max_tokens,
            )

        out_file = out_dir / f"{domain_name}.json"
        out_file.write_text(json.dumps(formatted, indent=2, ensure_ascii=False), encoding="utf-8")
        counts[domain_name] = len(formatted)

    return counts


# ============================================================================
# 6. UNIFIED INGESTION ENTRYPOINT & CLI
# ============================================================================

def _is_sqlite_file(path: Path) -> bool:
    if path.suffix.lower() in (".sqlite", ".sqlite3", ".db"):
        return True
    try:
        with open(path, "rb") as f:
            return f.read(16) == b"SQLite format 3\x00"
    except Exception:
        return False


def _filter_verified_json_samples(
    raw_samples: Sequence[Dict[str, Any]],
    min_pass_rate: float = 1.0,
) -> List[Dict[str, Any]]:
    """Filters JSON/JSONL samples by pass_at_1/test_pass_rate, AST/timeout flags, and lesson status."""
    filtered: List[Dict[str, Any]] = []
    threshold = float(min_pass_rate)
    for item in raw_samples:
        p1 = float(item.get("pass_at_1", 1.0))
        tpr = float(item.get("test_pass_rate", p1))
        if p1 < threshold or tpr < threshold:
            continue
        if threshold > 0.0 and (item.get("ast_violation") or item.get("timeout")):
            continue
        if threshold >= 1.0 and float(item.get("invariant_violation_rate", 0.0) or 0.0) > 0.0:
            continue

        cleaned = dict(item)
        lesson_val = str(cleaned.get("lesson") or "")
        lesson_status = str(cleaned.get("lesson_status") or "").strip().lower()
        if not _is_valid_lesson(lesson_val, {"status": lesson_status} if lesson_status else None):
            cleaned["lesson"] = ""
            cleaned["lesson_id"] = ""
        filtered.append(cleaned)
    return filtered


def _load_samples_from_source(src_path: Path, min_pass_rate: float = 1.0) -> List[Dict[str, Any]]:
    """Loads and validates samples from SQLite, JSON, or JSONL source."""
    if _is_sqlite_file(src_path):
        return harvest_verified_self_play_samples(src_path, min_pass_rate=min_pass_rate)

    raw_text = src_path.read_text(encoding="utf-8")
    loaded: Any = None
    try:
        loaded = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        # Support JSONL files when each non-empty line is a JSON object
        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
        if src_path.suffix.lower() == ".jsonl" and lines:
            parsed_lines: List[Dict[str, Any]] = []
            for ln in lines:
                try:
                    obj = json.loads(ln)
                except json.JSONDecodeError as line_exc:
                    raise ValueError(f"Corrupt JSONL line in {src_path}: {line_exc}") from line_exc
                if not isinstance(obj, dict):
                    raise ValueError(f"Each JSONL line in {src_path} must be a JSON object.")
                parsed_lines.append(obj)
            loaded = parsed_lines
        else:
            raise ValueError(f"Corrupt JSON in verified samples file {src_path}: {exc}") from exc

    if isinstance(loaded, dict) and isinstance(loaded.get("samples"), list):
        raw_samples = loaded["samples"]
    elif isinstance(loaded, list):
        raw_samples = loaded
    else:
        raise ValueError(
            f"Verified samples file {src_path} must contain a JSON list or {{\"samples\": [...]}}."
        )

    for idx, item in enumerate(raw_samples):
        if not isinstance(item, dict):
            raise ValueError(f"Sample at index {idx} in {src_path} must be a JSON object.")

    return _filter_verified_json_samples(raw_samples, min_pass_rate=min_pass_rate)


def ingest_self_play_samples(
    verified_samples_path: Path | str,
    output_dataset_path: Path | str,
    format_type: str = "alpaca",
    max_tokens: int = 1024,
    condition_with_lessons: bool = True,
    deduplicate: bool = True,
    min_pass_rate: float = 1.0,
) -> int:
    """
    Loads verified self-play samples (from JSON/JSONL file or SQLite DB), validates schema,
    applies 3-tier deduplication, formats to Alpaca or ShareGPT with sequence cutoff
    <= max_tokens * 4 characters, writes to `output_dataset_path`, and returns count.
    """
    fmt = str(format_type or "").strip().lower()
    if fmt not in ("alpaca", "sharegpt"):
        raise ValueError(f"Unsupported format_type '{format_type}'. Expected 'alpaca' or 'sharegpt'.")

    src_path = Path(verified_samples_path)
    if not src_path.exists():
        raise FileNotFoundError(f"Verified samples source not found: {src_path}")

    raw_samples = _load_samples_from_source(src_path, min_pass_rate=min_pass_rate)

    if deduplicate and raw_samples:
        clean_samples, dedup_stats = deduplicate_samples(raw_samples)
        logger.info("Deduplication stats: %s", dedup_stats)
    else:
        clean_samples = list(raw_samples)

    if fmt == "sharegpt":
        dataset = build_sharegpt_records(
            clean_samples,
            condition_with_lessons=condition_with_lessons,
            max_tokens=max_tokens,
        )
    else:
        dataset = build_alpaca_records(
            clean_samples,
            condition_with_lessons=condition_with_lessons,
            max_tokens=max_tokens,
        )

    out_path = Path(output_dataset_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("Exported %d %s SFT records to %s", len(dataset), fmt, out_path)
    return len(dataset)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Harvest verified self-play cycles and build modular SFT training datasets."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to SQLite vectors/benchmarks database.",
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        default=None,
        help="Optional pre-harvested JSON samples file instead of querying --db-path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output SFT dataset JSON path.",
    )
    parser.add_argument(
        "--format",
        choices=["alpaca", "sharegpt"],
        default="alpaca",
        help="Target SFT dataset schema format.",
    )
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=1.0,
        help="Minimum pass_at_1 threshold for harvesting self-play cycles.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1024,
        help="Maximum sequence token cutoff (4 chars/token => 4096 chars at 1024).",
    )
    parser.add_argument(
        "--no-lessons",
        action="store_true",
        help="Disable conditioning prompts with canonical APERL engineering lessons.",
    )
    parser.add_argument(
        "--split-domains-dir",
        type=Path,
        default=None,
        help="Optional directory to also write modular LoRA domain datasets.",
    )

    args = parser.parse_args(argv)
    source_path = args.input_json if args.input_json is not None else args.db_path

    count = ingest_self_play_samples(
        verified_samples_path=source_path,
        output_dataset_path=args.output,
        format_type=args.format,
        max_tokens=args.max_tokens,
        condition_with_lessons=not args.no_lessons,
        min_pass_rate=args.min_pass_rate,
    )

    if args.split_domains_dir is not None:
        samples = _load_samples_from_source(source_path, min_pass_rate=args.min_pass_rate)
        clean_samples, _ = deduplicate_samples(samples)
        split_counts = export_modular_domain_datasets(
            clean_samples,
            output_dir=args.split_domains_dir,
            format_type=args.format,
            max_tokens=args.max_tokens,
            condition_with_lessons=not args.no_lessons,
        )
        logger.info("Modular domain export counts: %s", split_counts)

    print(json.dumps({"exported_samples": count, "output": str(args.output), "format": args.format}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
