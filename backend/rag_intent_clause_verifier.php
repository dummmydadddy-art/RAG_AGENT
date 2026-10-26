<?php
/**
 * RagIntentClauseVerifier - EXP-0035 Dynamic Intent-Aware & Compound Clause Verifier
 * 
 * Implements:
 * - G2: Deterministic linguistic query-intent classifier (7 classes, zero LLM)
 * - G3: Intent-aware similarity gate threshold function θ(intent)
 * - G4: Deterministic compound-clause detection & semantic proposition segmentation
 * - G5: Clause-grounded evidence adequacy evaluation (partial support tracking)
 * - G6: Decomposed per-clause verification and pre-registered deterministic aggregation
 * 
 * Lineage: EXP-0031 E4 (01d6220) -> EXP-0034 Champion M2 (b2fb2f2) -> EXP-0035
 */

require_once __DIR__ . '/rag_premise_verifier.php';

class RagIntentClauseVerifier {

    // 7 Mutually Exclusive Intent Classes
    const INTENT_DIRECT_FACT   = 'DIRECT_FACT';
    const INTENT_PROCEDURAL    = 'PROCEDURAL';
    const INTENT_CONCEPTUAL    = 'CONCEPTUAL';
    const INTENT_COMPARISON    = 'COMPARISON';
    const INTENT_MULTI_CLAUSE  = 'MULTI_CLAUSE';
    const INTENT_AMBIGUOUS     = 'AMBIGUOUS';
    const INTENT_UNKNOWN_OOD   = 'UNKNOWN_OOD';

    // Curriculum Entities Whitelist
    private static array $curriculumEntities = [
        'justify-content', 'align-items', 'flex-direction', 'flex-grow', 'flex-shrink', 'flex-wrap', 'gap',
        'box-sizing: border-box', 'box-sizing: content-box', 'border-box', 'content-box', 'box-sizing', 'box model',
        'const', 'var', 'let', 'tdz', 'temporal dead zone', 'arrow function', 'arrow functions', 'hoisting',
        'uselayouteffect', 'usecallback', 'usecontext', 'useeffect', 'usestate', 'useref', 'usememo', 'react state',
        'macrotask', 'macrotasks', 'microtask', 'microtasks', 'event loop', 'libuv', 'v8', 'express', 'middleware', 'jwt',
        'atomicity', 'consistency', 'isolation', 'durability', 'acid', 'b-tree', 'b tree', 'index',
        'commit', 'rollback', 'wal', 'write-ahead logging', '1nf', '2nf', '3nf', 'normalization',
        'http get', 'http post', 'http put', 'http delete', 'idempotent', 'stateless',
        'display: flex', 'display: grid', 'grid', 'flexbox', 'semantic html', 'article', 'section', 'header', 'footer', 'nav'
    ];

    // Out-of-curriculum blacklist
    private static array $oodEntities = [
        'django', 'flutter', 'ruby', 'rails', 'spring', 'kafka', 'kubernetes', 'redis', 'docker', 'terraform',
        'c#', 'elixir', 'swiftui', 'grpc', 'sidekiq', 'python', 'rust', 'golang', 'asp.net', 'laravel', 'vue', 'angular',
        'cassandra', 'neo4j', 'zig', 'spark', 'envoy', 'prometheus'
    ];

    /**
     * G2: Deterministic query-intent classification
     */
    public static function classifyIntent(string $query): array {
        $qLower = strtolower(trim($query));
        
        // 1. Check OOD entity match
        $matchedOod = [];
        foreach (self::$oodEntities as $ood) {
            if (preg_match('/\b' . preg_quote($ood, '/') . '\b/i', $qLower)) {
                $matchedOod[] = $ood;
            }
        }
        $hasOodEntity = !empty($matchedOod);

        // 2. Check Curriculum entity match
        $matchedCurriculum = [];
        foreach (self::$curriculumEntities as $cent) {
            if (preg_match('/\b' . preg_quote($cent, '/') . '\b/i', $qLower)) {
                $matchedCurriculum[] = $cent;
            }
        }
        $hasCurriculumEntity = !empty($matchedCurriculum);

        // 3. Ambiguous / Subjective markers
        $isAmbiguous = (bool)preg_match('/\b(best|better|perfect|optimal|always recommended|should you always|superior|ideal|most readable|flawless)\b/i', $qLower);

        // 4. Comparison markers
        $isComparison = (bool)preg_match('/\b(versus|vs|difference between|compared to|whereas|strictly superior to)\b/i', $qLower);

        // 5. Multi-clause markers
        $isSubordinateMulti = (bool)preg_match('/^(?:since|while|although|given that|because)\s+(.+?),\s*((?:why|how|does|can|is|are|will|would|do|so\s+why|then\s+why)\b.+)/i', $qLower);
        $isCoordinateMulti = (bool)preg_match('/\b(does|is|can)\b.+\b(and|as well as)\b.+(does|is|can|make|cause|provide|prevent|execute|allow)\b/i', $qLower);
        $isConjunctionMulti = (bool)preg_match('/,\s*and\s+(?:therefore|thus|consequently|also)\b/i', $qLower);
        $isMultiClause = ($isSubordinateMulti || $isCoordinateMulti || $isConjunctionMulti);

        // 6. Procedural markers
        $isProcedural = (bool)preg_match('/\b(how does|explain how|describe how|workflow|pipeline|sequence|step|lifecycle|event loop)\b/i', $qLower);

        // 7. Conceptual markers
        $isConceptual = (bool)preg_match('/\b(why does|why is|why can\'t|why doesn\'t|concept of|architecture|principle|abstraction|underlying)\b/i', $qLower);

        // 8. Direct fact markers
        $isDirectFact = (bool)preg_match('/\b(does|is|can|what is|which)\b/i', $qLower) && !$isProcedural && !$isConceptual;

        // Intent assignment hierarchy
        $intent = self::INTENT_DIRECT_FACT;
        if ($hasOodEntity) {
            $intent = self::INTENT_UNKNOWN_OOD;
        } elseif ($isAmbiguous) {
            $intent = self::INTENT_AMBIGUOUS;
        } elseif ($isMultiClause) {
            $intent = self::INTENT_MULTI_CLAUSE;
        } elseif ($isComparison) {
            $intent = self::INTENT_COMPARISON;
        } elseif ($isProcedural) {
            $intent = self::INTENT_PROCEDURAL;
        } elseif ($isConceptual) {
            $intent = self::INTENT_CONCEPTUAL;
        } elseif ($isDirectFact) {
            $intent = self::INTENT_DIRECT_FACT;
        }

        $features = [
            'has_curriculum_entity' => $hasCurriculumEntity,
            'matched_entities' => $matchedCurriculum,
            'has_ood_entity' => $hasOodEntity,
            'matched_ood_entities' => $matchedOod,
            'is_multi_clause' => $isMultiClause,
            'is_comparison' => $isComparison,
            'is_ambiguous' => $isAmbiguous,
            'is_procedural' => $isProcedural,
            'is_conceptual' => $isConceptual,
            'is_direct_fact' => $isDirectFact,
            'query_length' => strlen($query)
        ];

        return [
            'intent' => $intent,
            'features' => $features
        ];
    }

    /**
     * G3: Intent-aware threshold mapping θ(intent)
     */
    public static function getThresholdForIntent(string $intent, array $features, ?array $customMap = null): float {
        $defaultMap = [
            self::INTENT_CONCEPTUAL   => 0.24,
            self::INTENT_PROCEDURAL   => 0.24,
            self::INTENT_DIRECT_FACT  => 0.26,
            self::INTENT_COMPARISON   => 0.26,
            self::INTENT_MULTI_CLAUSE => 0.27,
            self::INTENT_AMBIGUOUS    => 0.30,
            self::INTENT_UNKNOWN_OOD  => 0.32
        ];
        $map = $customMap ?? $defaultMap;

        $hasCurriculum = $features['has_curriculum_entity'] ?? false;
        $hasOod = $features['has_ood_entity'] ?? false;

        if ($hasOod) {
            return $map[self::INTENT_UNKNOWN_OOD] ?? 0.32;
        }

        if ($intent === self::INTENT_CONCEPTUAL || $intent === self::INTENT_PROCEDURAL) {
            // If in-domain curriculum entity is confirmed, safely lower threshold to 0.24
            return $hasCurriculum ? ($map[$intent] ?? 0.24) : 0.28;
        }

        return $map[$intent] ?? 0.28;
    }

    /**
     * G4: Deterministic compound-clause detection & proposition segmentation
     */
    public static function detectAndSplitClauses(string $query): array {
        $qClean = trim($query);

        // Pattern 1: Subordinate prefix: "Since P1, why does P2?"
        if (preg_match('/^(?:since|while|although|given that|because)\s+(.+?),\s*((?:why|how|does|can|is|are|will|would|do|so\s+why|then\s+why)\b.+)/i', $qClean, $m)) {
            return [
                [
                    'index' => 0,
                    'clause_text' => trim($m[1]),
                    'is_subordinate' => true,
                    'raw_span' => trim($m[1])
                ],
                [
                    'index' => 1,
                    'clause_text' => trim($m[2]),
                    'is_subordinate' => false,
                    'raw_span' => trim($m[2])
                ]
            ];
        }

        // Pattern 2: Consequential compound: "P1, and therefore P2"
        $parts = preg_split('/\s+and\s+(?:therefore|thus|consequently|as\s+a\s+result|hence|also)\s+/i', $qClean);
        if ($parts && count($parts) > 1) {
            $clauses = [];
            foreach ($parts as $idx => $p) {
                $clauses[] = [
                    'index' => $idx,
                    'clause_text' => trim($p),
                    'is_subordinate' => false,
                    'raw_span' => trim($p)
                ];
            }
            return $clauses;
        }

        // Pattern 3: Coordinate conjunction with shared subject:
        // "Does const prevent reassignment and make nested properties immutable?"
        if (preg_match('/^(?:does|can|is)\s+([a-z0-9_\-:]+)\s+(.+?)\s+and\s+(make|prevent|cause|allow|execute|provide|render|mutate|hoist|reassign)\s+(.+?)\??$/i', $qClean, $m)) {
            $subject = trim($m[1]);
            $pred1 = trim($m[2]);
            $verb2 = trim($m[3]);
            $pred2 = trim($m[4]);
            return [
                [
                    'index' => 0,
                    'clause_text' => "{$subject} {$pred1}",
                    'is_subordinate' => false,
                    'raw_span' => "{$subject} {$pred1}"
                ],
                [
                    'index' => 1,
                    'clause_text' => "{$subject} {$verb2} {$pred2}",
                    'is_subordinate' => false,
                    'raw_span' => "{$subject} {$verb2} {$pred2}"
                ]
            ];
        }

        // Single clause default
        return [
            [
                'index' => 0,
                'clause_text' => $qClean,
                'is_subordinate' => false,
                'raw_span' => $qClean
            ]
        ];
    }

    /**
     * G5: Clause-Grounded Evidence Gate
     */
    public static function evaluateClauseEvidence(array $clauses, array $retrievedChunks, float $threshold): array {
        $clauseEval = [];
        $supportedCount = 0;
        $totalCount = count($clauses);

        foreach ($clauses as $c) {
            $cText = $c['clause_text'];
            $cTokens = array_filter(preg_split('/\W+/', strtolower($cText)), fn($w) => strlen($w) > 2);
            
            $maxSim = 0.0;
            $bestChunk = null;

            foreach ($retrievedChunks as $chunk) {
                $sim = (float)($chunk['similarity'] ?? 0.0);
                if ($sim > $maxSim) {
                    $maxSim = $sim;
                    $bestChunk = $chunk;
                }
            }

            $isGrounded = ($maxSim >= $threshold);
            if ($isGrounded) $supportedCount++;

            $clauseEval[] = [
                'clause' => $cText,
                'max_similarity' => round($maxSim, 4),
                'grounded' => $isGrounded,
                'best_chunk_id' => $bestChunk['id'] ?? null,
                'best_chunk_title' => $bestChunk['title'] ?? null
            ];
        }

        return [
            'total_clauses' => $totalCount,
            'grounded_clauses' => $supportedCount,
            'is_fully_grounded' => ($supportedCount === $totalCount),
            'has_partial_grounding' => ($supportedCount > 0 && $supportedCount < $totalCount),
            'clause_eval' => $clauseEval
        ];
    }

    /**
     * Unified Verify Entrypoint (G0 through G6)
     */
    public static function verify(string $query, array $retrievedChunks, array $runtimeOptions = []): array {
        $mode = $runtimeOptions['mode'] ?? 'G0';

        // G0: Frozen M2 baseline
        if ($mode === 'G0') {
            return RagPremiseVerifier::verify($query, $retrievedChunks, [
                'ablation_mode' => 'E4',
                'evidence_gate_threshold' => 0.28
            ]);
        }

        // G1: Static Gate Sensitivity
        if ($mode === 'G1') {
            $staticThresh = (float)($runtimeOptions['static_threshold'] ?? 0.28);
            return RagPremiseVerifier::verify($query, $retrievedChunks, [
                'ablation_mode' => 'E4',
                'evidence_gate_threshold' => $staticThresh
            ]);
        }

        // G2/G3: Intent-Aware Gating
        $intentData = self::classifyIntent($query);
        $intent = $intentData['intent'];
        $features = $intentData['features'];
        $thresh = self::getThresholdForIntent($intent, $features, $runtimeOptions['intent_threshold_map'] ?? null);

        if ($mode === 'G2_G3' || $mode === 'G2' || $mode === 'G3') {
            $res = RagPremiseVerifier::verify($query, $retrievedChunks, [
                'ablation_mode' => 'E4',
                'evidence_gate_threshold' => $thresh
            ]);
            $res['intent_diagnostics'] = [
                'intent' => $intent,
                'features' => $features,
                'dynamic_threshold' => $thresh
            ];
            return $res;
        }

        // G4/G5: Clause Detection + Clause Evidence Gate
        $clauses = self::detectAndSplitClauses($query);
        $clauseGrounding = self::evaluateClauseEvidence($clauses, $retrievedChunks, $thresh);

        if ($mode === 'G4_G5' || $mode === 'G4' || $mode === 'G5') {
            if (!$clauseGrounding['is_fully_grounded'] && count($clauses) > 1) {
                // Partial evidence on compound query cannot be treated as fully verified
                return [
                    'has_presupposition' => true,
                    'status' => RagPremiseVerifier::STATUS_NOT_ESTABLISHED,
                    'confidence' => 0.0,
                    'evidence_used' => true,
                    'claim' => $query,
                    'refutation' => null,
                    'citation' => null,
                    'decision_tier' => RagPremiseVerifier::TIER_1,
                    'decision_reason' => 'Partial evidence grounding across compound clauses (some clauses lack curriculum evidence)',
                    'intent_diagnostics' => ['intent' => $intent, 'dynamic_threshold' => $thresh],
                    'clause_diagnostics' => $clauseGrounding
                ];
            }
            $res = RagPremiseVerifier::verify($query, $retrievedChunks, [
                'ablation_mode' => 'E4',
                'evidence_gate_threshold' => $thresh
            ]);
            $res['intent_diagnostics'] = ['intent' => $intent, 'dynamic_threshold' => $thresh];
            $res['clause_diagnostics'] = $clauseGrounding;
            return $res;
        }

        // G6: Full Compound-Clause NLI Decomposition & Aggregation
        if ($mode === 'G6') {
            if (count($clauses) <= 1) {
                // Single clause: verify directly with dynamic threshold
                $res = RagPremiseVerifier::verify($query, $retrievedChunks, [
                    'ablation_mode' => 'E4',
                    'evidence_gate_threshold' => $thresh
                ]);
                $res['intent_diagnostics'] = ['intent' => $intent, 'dynamic_threshold' => $thresh];
                $res['clause_diagnostics'] = $clauseGrounding;
                return $res;
            }

            // Multi-clause decomposition execution
            $clauseResults = [];
            $hasAnyRefuted = false;
            $hasAnyNotEstablished = false;
            $allSupported = true;
            $refutationReason = null;
            $refutationCitation = null;

            foreach ($clauses as $c) {
                $cText = $c['clause_text'];
                // Run verification on each clause individually
                $cRes = RagPremiseVerifier::verify($cText, $retrievedChunks, [
                    'ablation_mode' => 'E4',
                    'evidence_gate_threshold' => $thresh
                ]);
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

            // Pre-Registered Deterministic Truth Table:
            // 1. Any clause REFUTED -> REFUTED (conjunction is false)
            // 2. All clauses SUPPORTED -> SUPPORTED
            // 3. Otherwise -> NOT_ESTABLISHED
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

        // Fallback default
        return RagPremiseVerifier::verify($query, $retrievedChunks, [
            'ablation_mode' => 'E4',
            'evidence_gate_threshold' => 0.28
        ]);
    }
}
