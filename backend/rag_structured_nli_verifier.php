<?php
/**
 * RagStructuredNliVerifier - EXP-0036 Structured Tier-2 NLI Verifier
 * 
 * Implements:
 * - N1: Structured Evidence Prompt (CLAIM, EVIDENCE, RELATIONSHIP)
 * - N2: Deterministic Polarity Reasoning Pre-processor (negation, opposites, comparative cues)
 * - N3: Atomic Claim Predicate Decomposition (ENTITY, ATTRIBUTE, RELATION, CONSTRAINT)
 * - N4: Pre-registered Few-Shot Demonstrations strictly from dev dataset
 * - N5: Structured + Polarity (N1 + N2)
 * - N6: Structured + Clause Decomposition (N1 + N3)
 * - N7: Full Candidate (N1 + N2 + N3 + N4)
 * 
 * Lineage: EXP-0035 (2bcccca) -> EXP-0036
 */

require_once __DIR__ . '/rag_intent_clause_verifier.php';

class RagStructuredNliVerifier {

    // Pre-registered Few-Shot Demonstrations (P3/P4/N4/N7) strictly from EXP-0025 development dataset
    const FEW_SHOT_DEMONSTRATIONS = <<<DEMOS
[EXAMPLE 1 - Direct Entailment]
Evidence: "const declarations create block-scoped variables that cannot be reassigned after initialization."
Claim: "const variables have block scope."
Analysis: The evidence explicitly asserts block scope for const.
Output: {"label":"ENTAILMENT","confidence":0.95,"rationale":"Directly supported by evidence statement"}

[EXAMPLE 2 - Descriptive Paraphrase Entailment]
Evidence: "Array.prototype.map creates a new array populated with the results of calling a provided function on every element in the calling array."
Claim: "map transforms every element in an array without mutating the original array."
Analysis: Creating a new array with transformed results entails the original array is not mutated and every element is transformed.
Output: {"label":"ENTAILMENT","confidence":0.95,"rationale":"Descriptive evidence supports non-mutating transformation"}

[EXAMPLE 3 - Technical Mechanism Entailment]
Evidence: "PostgreSQL B-Tree indexes sort entries in balanced tree structures to accelerate equality and range queries."
Claim: "B-Tree indexes speed up WHERE column = value lookups in SQL."
Analysis: Equality queries directly correspond to column = value lookups.
Output: {"label":"ENTAILMENT","confidence":0.95,"rationale":"Equality query acceleration entails WHERE column = value speedup"}

[EXAMPLE 4 - Explicit Contradiction]
Evidence: "JavaScript execution is single-threaded; asynchronous operations are managed via the event loop, not multi-threaded CPU execution."
Claim: "JavaScript executes asynchronous callbacks concurrently across multiple native CPU threads."
Analysis: Single-threaded event loop contradicts concurrent execution across multiple native threads.
Output: {"label":"CONTRADICTION","confidence":0.95,"rationale":"Directly contradicts single-threaded execution model"}

[EXAMPLE 5 - Polarity Inversion Contradiction]
Evidence: "display: flex defines a one-dimensional layout model along either the row or column axis."
Claim: "display: flex establishes a 2-dimensional grid layout."
Analysis: One-dimensional along either row or column directly contradicts 2-dimensional grid layout.
Output: {"label":"CONTRADICTION","confidence":0.95,"rationale":"One-dimensional flex directly conflicts with 2-dimensional claim"}

[EXAMPLE 6 - Comparative Timing Contradiction]
Evidence: "Resolved Promise microtasks are always processed before the next macrotask (such as setTimeout) runs in the event loop."
Claim: "setTimeout executes before resolved Promise microtasks."
Analysis: Microtasks run before macrotasks; claiming setTimeout runs before microtasks inverts the execution order.
Output: {"label":"CONTRADICTION","confidence":0.95,"rationale":"Inverts relative execution order between microtasks and macrotasks"}

[EXAMPLE 7 - Insufficient Evidence / Out of Curriculum]
Evidence: "React useState hook preserves local component state between re-renders."
Claim: "Django ORM automatically creates database migrations for PostgreSQL schema changes."
Analysis: The evidence discusses React state; it contains no information about Django ORM or PostgreSQL migrations.
Output: {"label":"NEUTRAL","confidence":0.35,"rationale":"Evidence does not address the claim topic"}
DEMOS;

    /**
     * N2: Deterministic Polarity Reasoning Pre-processor
     */
    public static function extractPolarityCues(string $claim, string $evidence): array {
        $cLower = strtolower($claim);
        $eLower = strtolower($evidence);

        $negationWords = ['not', 'never', 'cannot', "can't", "doesn't", "isn't", "won't", 'without', 'fails to', 'prevent', 'eliminates'];
        $claimNegations = [];
        foreach ($negationWords as $nw) {
            if (preg_match('/\b' . preg_quote($nw, '/') . '\b/i', $cLower)) {
                $claimNegations[] = $nw;
            }
        }

        $evidenceNegations = [];
        foreach ($negationWords as $nw) {
            if (preg_match('/\b' . preg_quote($nw, '/') . '\b/i', $eLower)) {
                $evidenceNegations[] = $nw;
            }
        }

        $comparativeWords = ['before', 'after', 'faster', 'slower', 'superior', 'earlier', 'later', 'more than', 'less than', 'rather than', 'instead of', 'all-or-nothing'];
        $claimComparatives = [];
        foreach ($comparativeWords as $cw) {
            if (preg_match('/\b' . preg_quote($cw, '/') . '\b/i', $cLower)) {
                $claimComparatives[] = $cw;
            }
        }

        $antonymPairs = [
            ['synchronous', 'asynchronous'],
            ['mutable', 'immutable'],
            ['1-dimensional', '2-dimensional'],
            ['one-dimensional', 'two-dimensional'],
            ['border-box', 'content-box'],
            ['commit', 'rollback'],
            ['block', 'inline'],
            ['microtask', 'macrotask'],
            ['single-threaded', 'multi-threaded'],
            ['client-side', 'server-side'],
            ['requires', 'optional'],
            ['permit', 'prohibit']
        ];

        $antonymCues = [];
        foreach ($antonymPairs as [$w1, $w2]) {
            $inC1 = (bool)preg_match('/\b' . preg_quote($w1, '/') . '\b/i', $cLower);
            $inC2 = (bool)preg_match('/\b' . preg_quote($w2, '/') . '\b/i', $cLower);
            $inE1 = (bool)preg_match('/\b' . preg_quote($w1, '/') . '\b/i', $eLower);
            $inE2 = (bool)preg_match('/\b' . preg_quote($w2, '/') . '\b/i', $eLower);

            if (($inC1 && $inE2) || ($inC2 && $inE1)) {
                $antonymCues[] = "{$w1} vs {$w2}";
            }
        }

        $polarityMismatch = (!empty($antonymCues)) ||
            (count($claimNegations) > 0 && count($evidenceNegations) === 0 && !preg_match("/\b(why doesn't|why can't|without)\b/i", $cLower)) ||
            (count($claimNegations) === 0 && count($evidenceNegations) > 0);

        return [
            'claim_negations' => array_unique($claimNegations),
            'evidence_negations' => array_unique($evidenceNegations),
            'comparatives' => array_unique($claimComparatives),
            'antonyms' => array_unique($antonymCues),
            'polarity_mismatch_detected' => $polarityMismatch
        ];
    }

    /**
     * N3: Claim Predicate Decomposition (Single Technical Claim)
     */
    public static function decomposeClaimPredicates(string $claim): array {
        $clean = trim($claim);

        if (preg_match('/^(?:why does|why is|how does|does|can|what makes)\s+([a-z0-9_\-:\(\)]+)\s+(.+?)(?:\?|$)/i', $clean, $m)) {
            $entity = trim($m[1]);
            $rest = trim($m[2]);

            $constraintParts = preg_split('/\s+(upon|after|before|rather than|instead of|regardless of|within|across)\s+/i', $rest, 2, PREG_SPLIT_DELIM_CAPTURE);
            if (count($constraintParts) === 3) {
                return [
                    'entity' => $entity,
                    'attribute_or_action' => trim($constraintParts[0]),
                    'relation' => trim($constraintParts[1]),
                    'constraint_or_value' => trim($constraintParts[2]),
                    'raw_predicates' => [
                        "{$entity} " . trim($constraintParts[0]),
                        "{$entity} " . trim($constraintParts[1]) . " " . trim($constraintParts[2])
                    ]
                ];
            }

            return [
                'entity' => $entity,
                'attribute_or_action' => $rest,
                'relation' => 'asserts',
                'constraint_or_value' => 'true',
                'raw_predicates' => ["{$entity} {$rest}"]
            ];
        }

        return [
            'entity' => 'SUBJECT',
            'attribute_or_action' => $clean,
            'relation' => 'asserts',
            'constraint_or_value' => 'true',
            'raw_predicates' => [$clean]
        ];
    }

    /**
     * Build Prompt Variants P0 through P4
     */
    public static function buildPrompt(string $premise, string $hypothesis, string $promptMode, array $polarityInfo = []): string {
        switch ($promptMode) {
            case 'P1':
                return <<<PROMPT
EVIDENCE CONTEXT:
"{$premise}"

STUDENT CLAIM:
"{$hypothesis}"

TASK:
Determine whether the EVIDENCE CONTEXT directly supports (ENTAILMENT), contradicts (CONTRADICTION), or does not contain enough facts to verify (NEUTRAL) the STUDENT CLAIM.
Definitions:
- ENTAILMENT: The claim is confirmed by the evidence, even if phrased differently, descriptively, or indirectly.
- CONTRADICTION: The claim asserts a property, default, behavior, or constraint that conflicts with or is incompatible with the evidence.
- NEUTRAL: The evidence does not address the specific assertion.

JSON ONLY: {"label":"ENTAILMENT"|"CONTRADICTION"|"NEUTRAL","confidence":0.0-1.0,"rationale":"concise reasoning"}
PROMPT;

            case 'P2':
                $negList = !empty($polarityInfo['claim_negations']) ? implode(', ', $polarityInfo['claim_negations']) : 'none';
                $compList = !empty($polarityInfo['comparatives']) ? implode(', ', $polarityInfo['comparatives']) : 'none';
                $antList = !empty($polarityInfo['antonyms']) ? implode(', ', $polarityInfo['antonyms']) : 'none';
                $mismatchStr = ($polarityInfo['polarity_mismatch_detected'] ?? false) ? 'YES (Potential polarity inversion or opposite term)' : 'NO';

                return <<<PROMPT
EVIDENCE CONTEXT:
"{$premise}"

STUDENT CLAIM:
"{$hypothesis}"

POLARITY AND COMPARATIVE ANALYSIS:
- Negations in claim: {$negList}
- Comparative terms: {$compList}
- Antonym / Opposite conflicts: {$antList}
- Polarity inversion risk: {$mismatchStr}

TASK:
Evaluate if the STUDENT CLAIM is ENTAILMENT, CONTRADICTION, or NEUTRAL strictly against the EVIDENCE CONTEXT.
If the claim inverts direction, timing, or constraints (e.g. before vs after, 1D vs 2D, permits vs forbids), classify as CONTRADICTION.
If the claim describes the actual mechanism or rules accurately, classify as ENTAILMENT.
If not addressed, classify as NEUTRAL.

JSON ONLY: {"label":"ENTAILMENT"|"CONTRADICTION"|"NEUTRAL","confidence":0.0-1.0,"rationale":"concise reasoning"}
PROMPT;

            case 'P3':
                $demos = self::FEW_SHOT_DEMONSTRATIONS;
                return <<<PROMPT
You are a strict technical verification judge for a web development curriculum.

REFERENCE DEMONSTRATIONS:
{$demos}

NEW CASE TO EVALUATE:
EVIDENCE CONTEXT:
"{$premise}"

STUDENT CLAIM:
"{$hypothesis}"

TASK:
Following the reference demonstrations above, determine if the STUDENT CLAIM is ENTAILMENT, CONTRADICTION, or NEUTRAL relative to the EVIDENCE CONTEXT.
JSON ONLY: {"label":"ENTAILMENT"|"CONTRADICTION"|"NEUTRAL","confidence":0.0-1.0,"rationale":"concise reasoning"}
PROMPT;

            case 'P4':
                $demos = self::FEW_SHOT_DEMONSTRATIONS;
                $negList = !empty($polarityInfo['claim_negations']) ? implode(', ', $polarityInfo['claim_negations']) : 'none';
                $compList = !empty($polarityInfo['comparatives']) ? implode(', ', $polarityInfo['comparatives']) : 'none';
                $antList = !empty($polarityInfo['antonyms']) ? implode(', ', $polarityInfo['antonyms']) : 'none';
                $mismatchStr = ($polarityInfo['polarity_mismatch_detected'] ?? false) ? 'YES (Potential polarity inversion)' : 'NO';

                return <<<PROMPT
You are a strict technical verification judge for a web development curriculum.

REFERENCE DEMONSTRATIONS:
{$demos}

POLARITY ANALYSIS:
- Negation cues: {$negList}
- Comparative cues: {$compList}
- Antonym cues: {$antList}
- Polarity inversion risk: {$mismatchStr}

NEW CASE TO EVALUATE:
EVIDENCE CONTEXT:
"{$premise}"

STUDENT CLAIM:
"{$hypothesis}"

TASK:
Following the demonstrations and polarity analysis, determine whether the STUDENT CLAIM is ENTAILMENT, CONTRADICTION, or NEUTRAL relative to the EVIDENCE CONTEXT.
JSON ONLY: {"label":"ENTAILMENT"|"CONTRADICTION"|"NEUTRAL","confidence":0.0-1.0,"rationale":"concise reasoning"}
PROMPT;

            case 'P4_neutral':
                $demos = self::FEW_SHOT_DEMONSTRATIONS;
                $negList = !empty($polarityInfo['claim_negations']) ? implode(', ', $polarityInfo['claim_negations']) : 'none';
                $compList = !empty($polarityInfo['comparatives']) ? implode(', ', $polarityInfo['comparatives']) : 'none';
                $antList = !empty($polarityInfo['antonyms']) ? implode(', ', $polarityInfo['antonyms']) : 'none';
                $mismatchStr = ($polarityInfo['polarity_mismatch_detected'] ?? false) ? 'YES (Potential polarity inversion)' : 'NO';

                return <<<PROMPT
You are a strict technical verification judge for a web development curriculum.

REFERENCE DEMONSTRATIONS:
{$demos}

POLARITY ANALYSIS:
- Negation cues: {$negList}
- Comparative cues: {$compList}
- Antonym cues: {$antList}
- Polarity inversion risk: {$mismatchStr}

NEW CASE TO EVALUATE:
EVIDENCE CONTEXT:
"{$premise}"

STUDENT CLAIM:
"{$hypothesis}"

TASK:
Following the demonstrations and polarity analysis, determine whether the STUDENT CLAIM is ENTAILMENT, CONTRADICTION, or NEUTRAL relative to the EVIDENCE CONTEXT.
EPISTEMIC DIRECTIVE: If the claim asserts a subjective preference, normative recommendation, or superiority claim that is not explicitly established as an absolute rule or standard convention in the evidence context, classify as NEUTRAL.
JSON ONLY: {"label":"ENTAILMENT"|"CONTRADICTION"|"NEUTRAL","confidence":0.0-1.0,"rationale":"concise reasoning"}
PROMPT;

            case 'P0':
            default:
                return <<<PROMPT
Curriculum Fact: "{$premise}"
Student Claim: "{$hypothesis}"
Task: Evaluate if the Student Claim is ENTAILMENT, CONTRADICTION, or NEUTRAL strictly against the Curriculum Fact.
Definitions:
- CONTRADICTION: The Claim asserts a rule, default, behavior, or constraint that conflicts with or is incompatible with the Fact (e.g. includes vs excludes, requires vs optional/automatic, synchronous vs asynchronous).
- ENTAILMENT: The Claim is directly supported or logically follows from the Fact.
- NEUTRAL: The Fact does not confirm or refute the Claim.
JSON only: {"label":"CONTRADICTION"|"ENTAILMENT"|"NEUTRAL","confidence":0.0-1.0}
PROMPT;
        }
    }

    /**
     * Unified Verify Entrypoint for EXP-0036
     */
    public static function verify(string $query, array $retrievedChunks, array $runtimeOptions = []): array {
        $mode = $runtimeOptions['mode'] ?? 'N0';

        if ($mode === 'N0') {
            return RagIntentClauseVerifier::verify($query, $retrievedChunks, ['mode' => 'G6']);
        }

        $promptMode = 'P0';
        $usePolarity = in_array($mode, ['N2', 'N5', 'N7'], true);
        $useDecomposition = in_array($mode, ['N3', 'N6', 'N7'], true);

        if ($mode === 'N1') $promptMode = 'P1';
        elseif ($mode === 'N2') $promptMode = 'P2';
        elseif ($mode === 'N3') $promptMode = 'P1';
        elseif ($mode === 'N4') $promptMode = 'P3';
        elseif ($mode === 'N5') $promptMode = 'P2';
        elseif ($mode === 'N6') $promptMode = 'P1';
        elseif ($mode === 'N7') $promptMode = 'P4';

        $intentData = RagIntentClauseVerifier::classifyIntent($query);
        $intent = $intentData['intent'];
        $features = $intentData['features'];
        $thresh = RagIntentClauseVerifier::getThresholdForIntent($intent, $features);

        $clauses = RagIntentClauseVerifier::detectAndSplitClauses($query);
        $clauseGrounding = RagIntentClauseVerifier::evaluateClauseEvidence($clauses, $retrievedChunks, $thresh);

        if (count($clauses) > 1) {
            $clauseResults = [];
            $hasAnyRefuted = false;
            $hasAnyNotEstablished = false;
            $allSupported = true;
            $refutationReason = null;
            $refutationCitation = null;

            foreach ($clauses as $c) {
                $cText = $c['clause_text'];
                $cRes = self::verifySingleClause($cText, $retrievedChunks, $thresh, $promptMode, $usePolarity, $useDecomposition, $runtimeOptions);
                $cStatus = $cRes['status'];
                $clauseResults[] = [
                    'clause' => $cText,
                    'status' => $cStatus,
                    'reason' => $cRes['decision_reason'] ?? '',
                    'confidence' => $cRes['confidence'] ?? 0.0
                ];

                if ($cStatus === RagPremiseVerifier::STATUS_REFUTED) {
                    $hasAnyRefuted = true;
                    if ($refutationReason === null) {
                        $refutationReason = $cRes['refutation'] ?? $cRes['decision_reason'];
                        $refutationCitation = $cRes['citation'] ?? null;
                    }
                } elseif ($cStatus === RagPremiseVerifier::STATUS_NOT_ESTABLISHED) {
                    $hasAnyNotEstablished = true;
                    $allSupported = false;
                } elseif ($cStatus !== RagPremiseVerifier::STATUS_SUPPORTED) {
                    $allSupported = false;
                }
            }

            if ($hasAnyRefuted) {
                $finalStatus = RagPremiseVerifier::STATUS_REFUTED;
                $finalReason = "At least one constituent proposition in compound premise was refuted: {$refutationReason}";
                $finalConf = 0.95;
            } elseif ($allSupported && !$hasAnyNotEstablished) {
                $finalStatus = RagPremiseVerifier::STATUS_SUPPORTED;
                $finalReason = 'All constituent propositions in compound premise were verified and supported by curriculum evidence';
                $finalConf = 0.85;
            } else {
                $finalStatus = RagPremiseVerifier::STATUS_NOT_ESTABLISHED;
                $finalReason = 'Compound premise contains unverified or insufficiently established sub-propositions';
                $finalConf = 0.0;
            }

            return [
                'has_presupposition' => true,
                'status' => $finalStatus,
                'confidence' => $finalConf,
                'evidence_used' => true,
                'claim' => $query,
                'refutation' => $hasAnyRefuted ? $refutationReason : null,
                'citation' => $hasAnyRefuted ? $refutationCitation : null,
                'decision_tier' => RagPremiseVerifier::TIER_2_NLI,
                'decision_reason' => $finalReason,
                'intent_diagnostics' => ['intent' => $intent, 'dynamic_threshold' => $thresh],
                'clause_diagnostics' => $clauseGrounding,
                'decomposed_clause_results' => $clauseResults
            ];
        }

        return self::verifySingleClause($query, $retrievedChunks, $thresh, $promptMode, $usePolarity, $useDecomposition, $runtimeOptions);
    }

    private static function verifySingleClause(string $query, array $retrievedChunks, float $thresh, string $promptMode, bool $usePolarity, bool $useDecomposition, array $runtimeOptions): array {
        $opts = $runtimeOptions;
        $opts['ablation_mode'] = 'E4';
        $opts['evidence_gate_threshold'] = $thresh;

        $topChunk = $retrievedChunks[0] ?? null;
        $evidenceText = '';
        if ($topChunk) {
            $evidenceText = ($topChunk['title'] ?? '') . ': ' . ($topChunk['content'] ?? '');
        }

        $polarityInfo = $usePolarity ? self::extractPolarityCues($query, $evidenceText) : [];

        if ($usePolarity && ($polarityInfo['polarity_mismatch_detected'] ?? false) && !empty($polarityInfo['antonyms'])) {
            foreach ($polarityInfo['antonyms'] as $pair) {
                return [
                    'has_presupposition' => true,
                    'status' => RagPremiseVerifier::STATUS_REFUTED,
                    'confidence' => 0.95,
                    'evidence_used' => true,
                    'claim' => $query,
                    'refutation' => "Direct semantic opposition detected via polarity pre-processing ({$pair})",
                    'citation' => $topChunk['citation'] ?? ($topChunk['title'] ?? 'Curriculum Passage'),
                    'decision_tier' => RagPremiseVerifier::TIER_1,
                    'decision_reason' => "Polarity inversion established: {$pair}",
                    'polarity_diagnostics' => $polarityInfo
                ];
            }
        }

        if ($useDecomposition) {
            $preds = self::decomposeClaimPredicates($query);
            if (count($preds['raw_predicates']) > 1) {
                $allPredsSupported = true;
                foreach ($preds['raw_predicates'] as $p) {
                    $pRes = RagPremiseVerifier::verify($p, $retrievedChunks, $opts);
                    if ($pRes['status'] === RagPremiseVerifier::STATUS_REFUTED) {
                        return $pRes;
                    }
                    if ($pRes['status'] !== RagPremiseVerifier::STATUS_SUPPORTED) {
                        $allPredsSupported = false;
                    }
                }
                if ($allPredsSupported) {
                    return [
                        'has_presupposition' => true,
                        'status' => RagPremiseVerifier::STATUS_SUPPORTED,
                        'confidence' => 0.90,
                        'evidence_used' => true,
                        'claim' => $query,
                        'refutation' => null,
                        'citation' => $topChunk['citation'] ?? null,
                        'decision_tier' => RagPremiseVerifier::TIER_2_NLI,
                        'decision_reason' => 'All decomposed atomic claim predicates independently verified',
                        'predicate_diagnostics' => $preds
                    ];
                }
            }
        }

        $opts['prompt_mode'] = $promptMode;
        $res = RagPremiseVerifier::verify($query, $retrievedChunks, $opts);
        if ($usePolarity) {
            $res['polarity_diagnostics'] = $polarityInfo;
        }
        return $res;
    }
}
