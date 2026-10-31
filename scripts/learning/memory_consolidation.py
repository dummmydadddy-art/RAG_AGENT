"""
scripts/learning/memory_consolidation.py

Ebbinghaus Memory Consolidation Engine.
Implements cognitive forgetting curves, automated stale lesson demotion,
and semantic contradiction detection to prevent knowledge base pollution.
"""

from dataclasses import dataclass
from typing import Any, Dict, List
import math
import re


@dataclass
class LessonConsolidationRecord:
    lesson_id: str
    content: str
    elapsed_days: float
    strength: float
    usage_count: int
    status: str = "candidate"


class EbbinghausConsolidator:
    """
    Manages long-term lesson retention, lifecycle status transitions,
    and semantic conflict detection.
    """

    def calculate_retention(self, elapsed_days: float, strength: float) -> float:
        """
        Computes Ebbinghaus retention probability: R(t) = exp(-delta_t / S).
        """
        if strength <= 0.0:
            return 0.0
        exponent = -max(0.0, elapsed_days) / strength
        return float(math.exp(exponent))

    def consolidate(self, records: List[LessonConsolidationRecord]) -> Dict[str, List[str]]:
        """
        Evaluates a batch of lesson records and groups actions into 'retire', 'promote', and 'keep'.
        - Retire: Retention < 0.2 AND usage_count == 0 (unreinforced stale knowledge).
        - Promote: Retention >= 0.7 AND usage_count >= 5 (verified high-utility knowledge).
        - Keep: All active healthy lessons.
        """
        actions: Dict[str, List[str]] = {
            "retire": [],
            "promote": [],
            "keep": [],
        }

        for rec in records:
            r = self.calculate_retention(rec.elapsed_days, rec.strength)
            if r < 0.2 and rec.usage_count == 0:
                actions["retire"].append(rec.lesson_id)
            elif r >= 0.7 and rec.usage_count >= 5 and rec.status == "candidate":
                actions["promote"].append(rec.lesson_id)
            else:
                actions["keep"].append(rec.lesson_id)

        return actions

    def detect_contradiction(self, candidate_content: str, existing_content: str) -> Dict[str, Any]:
        """
        Detects direct or semantic contradictions between two candidate lessons.
        Evaluates topic similarity and opposing directive polarity (e.g. 'do' vs 'do not').
        """
        cand_lower = candidate_content.lower()
        exist_lower = existing_content.lower()

        # Token overlap for topic similarity
        stop_words = {"when", "do", "because", "the", "a", "an", "is", "it", "with", "to", "in", "and", "or"}
        cand_tokens = {w for w in re.findall(r"\w+", cand_lower) if w not in stop_words}
        exist_tokens = {w for w in re.findall(r"\w+", exist_lower) if w not in stop_words}

        overlap = len(cand_tokens.intersection(exist_tokens))
        union = len(cand_tokens.union(exist_tokens)) or 1
        jaccard_topic = overlap / union

        # Polarity conflict detection
        negation_pattern = r"\b(do not|don't|never|avoid|not)\b"
        cand_has_negation = bool(re.search(negation_pattern, cand_lower))
        exist_has_negation = bool(re.search(negation_pattern, exist_lower))

        polarity_conflict = (cand_has_negation != exist_has_negation)

        # High topic overlap with opposing polarity indicates a strong direct contradiction
        has_conflict = False
        conflict_score = 0.0

        if jaccard_topic > 0.4 and polarity_conflict:
            has_conflict = True
            conflict_score = min(1.0, jaccard_topic + 0.4)
        elif jaccard_topic > 0.75:
            # Near identical duplicate
            conflict_score = jaccard_topic

        return {
            "has_conflict": has_conflict,
            "conflict_score": conflict_score,
            "topic_overlap": jaccard_topic,
            "polarity_conflict": polarity_conflict,
        }
