import re
from typing import Any, Dict, List, Optional, Tuple
from rag_adapter.interface import RagAdapter
from rag_adapter.models import Hit, LessonStatus

# Canonical regex pattern: When <situation>, do <action>, because <reason>
CANONICAL_RULE_PATTERN = re.compile(
    r"^When\s+(?P<situation>.+?),\s+do\s+(?P<action>.+?),\s+because\s+(?P<reason>.+)$",
    re.IGNORECASE | re.DOTALL,
)

NEGATION_KEYWORDS = ["not", "never", "avoid", "don't", "refrain"]


def validate_lesson_format(rule: str) -> Tuple[bool, str]:
    """
    Validate that rule string strictly complies with the canonical pattern:
    When <situation>, do <action>, because <reason>
    """
    if not rule or not isinstance(rule, str):
        return False, "Rule must be a non-empty string"

    match = CANONICAL_RULE_PATTERN.match(rule.strip())
    if not match:
        return (
            False,
            "Rule does not match canonical format: 'When <situation>, do <action>, because <reason>'",
        )

    situation = match.group("situation").strip()
    action = match.group("action").strip()
    reason = match.group("reason").strip()

    if len(situation) < 3 or len(action) < 3 or len(reason) < 3:
        return False, "Rule situation, action, or reason is too brief to be meaningful"

    return True, "Valid"


def parse_rule_components(rule: str) -> Optional[Dict[str, str]]:
    """
    Extract situation, action, and reason from canonical rule string.
    """
    match = CANONICAL_RULE_PATTERN.match(rule.strip())
    if not match:
        return None
    return {
        "situation": match.group("situation").strip().lower(),
        "action": match.group("action").strip().lower(),
        "reason": match.group("reason").strip().lower(),
    }


def _tokenize(text: str) -> set:
    return set(re.findall(r"\b[a-zA-Z0-9_\-]+\b", text.lower()))


def check_duplicate_lesson(backend: RagAdapter, rule: str, threshold: float = 0.90) -> Tuple[bool, Optional[str]]:
    """
    Check if a lesson with identical or highly similar rule already exists in the lessons collection.
    """
    target_tokens = _tokenize(rule)
    if not target_tokens:
        return False, None

    hits = backend.search(query=rule, collections=["lessons"], k=50)
    for h in hits:
        meta = h.metadata or {}
        existing_rule = meta.get("rule", "")
        if not existing_rule:
            continue

        if existing_rule.strip().lower() == rule.strip().lower():
            return True, h.doc_id

        # Jaccard similarity of token sets
        exist_tokens = _tokenize(existing_rule)
        if exist_tokens:
            jaccard = len(target_tokens & exist_tokens) / len(target_tokens | exist_tokens)
            if jaccard >= threshold:
                return True, h.doc_id

    return False, None


def check_contradiction(backend: RagAdapter, rule: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if a proposed rule contradicts an existing verified lesson.
    Detects if situation matches closely but action is inverted/negated.
    """
    cand = parse_rule_components(rule)
    if not cand:
        return False, None, None

    cand_sit_tokens = _tokenize(cand["situation"])
    cand_act_tokens = _tokenize(cand["action"])
    cand_is_negated = any(kw in cand_act_tokens for kw in NEGATION_KEYWORDS)

    # Query verified lessons
    hits = backend.search(query=cand["situation"], collections=["lessons"], k=20)
    for h in hits:
        meta = h.metadata or {}
        if meta.get("status") != LessonStatus.VERIFIED:
            continue

        verified_rule = meta.get("rule", "")
        ver = parse_rule_components(verified_rule)
        if not ver:
            continue

        ver_sit_tokens = _tokenize(ver["situation"])
        if not ver_sit_tokens:
            continue

        # Check situation overlap
        sit_overlap = len(cand_sit_tokens & ver_sit_tokens) / max(len(cand_sit_tokens), len(ver_sit_tokens))
        if sit_overlap < 0.6:
            continue

        # Situations align; check action polarity
        ver_act_tokens = _tokenize(ver["action"])
        ver_is_negated = any(kw in ver_act_tokens for kw in NEGATION_KEYWORDS)

        # Base action core tokens (excluding negation words)
        cand_core = cand_act_tokens - set(NEGATION_KEYWORDS)
        ver_core = ver_act_tokens - set(NEGATION_KEYWORDS)
        act_overlap = len(cand_core & ver_core) / max(1, len(cand_core | ver_core))

        if act_overlap >= 0.5 and (cand_is_negated != ver_is_negated):
            reason = (
                f"Contradicts verified lesson {h.doc_id}: situations match ({sit_overlap:.2f}) "
                f"but action directives conflict ('{cand['action']}' vs '{ver['action']}')."
            )
            return True, h.doc_id, reason

    return False, None, None


def can_promote_lesson(backend: RagAdapter, lesson_id: str, pr_merged: bool = False) -> Tuple[bool, str]:
    """
    Enforce promotion invariants:
    - Status must not be retired.
    - Evidence tests must be present and passing.
    - Either pr_merged is True OR lesson has >= 1 successful reuse.
    """
    doc = backend.get("lessons", lesson_id)
    if not doc:
        return False, f"Lesson {lesson_id} not found"

    meta = doc.metadata or {}
    status = meta.get("status")
    if status == LessonStatus.RETIRED:
        return False, f"Cannot promote retired lesson {lesson_id}"

    evidence = meta.get("evidence", {})
    tests = evidence.get("tests", [])
    if not tests:
        return False, f"Lesson {lesson_id} missing evidence tests"

    if evidence.get("review") != "passed":
        return False, f"Lesson {lesson_id} review status is not 'passed'"

    has_successful_reuse = meta.get("success_count", 0) >= 1
    if not pr_merged and not has_successful_reuse:
        return False, "Candidate requires PR merged or successful reuse (>=1) to be promoted to verified"

    return True, "Promotion eligible"


def format_rule_citation(hits: List[Hit]) -> str:
    """
    Format search hits into pre-plan citation text for orchestrator prompts.
    Prioritizes verified lessons and marks candidate lessons as [UNVERIFIED].
    """
    lines = []
    for h in hits:
        meta = h.metadata or {}
        status = meta.get("status", LessonStatus.CANDIDATE)
        title = meta.get("title", "")
        rule = meta.get("rule", h.text)

        if status == LessonStatus.VERIFIED:
            tag = "[VERIFIED]"
        elif status == LessonStatus.CANDIDATE:
            tag = "[UNVERIFIED]"
        else:
            continue  # Exclude retired

        lines.append(f"- {tag} {h.doc_id}: {title}\n  Rule: {rule}")

    return "\n".join(lines)
