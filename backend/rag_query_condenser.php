<?php
// EduConnect LMS - Conversational Query Condenser (Production)
// Resolves pronouns and anaphora in follow-up questions using curriculum entity detection

class RagQueryCondenser {
    // Technical curriculum entities mapped to canonical forms
    private static array $curriculumEntities = [
        'tdz' => ['canonical' => 'Temporal Dead Zone (TDZ)', 'patterns' => ['/\btdz\b/i', '/\btemporal\s+dead\s+zone\b/i']],
        'const_let' => ['canonical' => 'let and const declarations', 'patterns' => ['/\bconst\b/i', '/\blet\b/i', '/\bvar\b/i']],
        'arrow_functions' => ['canonical' => 'arrow functions and lexical this', 'patterns' => ['/\barrow\s+functions?\b/i']],
        'closure' => ['canonical' => 'JavaScript closures', 'patterns' => ['/\bclosures?\b/i']],
        'promise' => ['canonical' => 'JavaScript Promises and async/await', 'patterns' => ['/\bpromises?\b/i', '/\basync\s*\/\s*await\b/i']],
        'react_hooks' => ['canonical' => 'React Hooks', 'patterns' => ['/\breact\s+hooks?\b/i']],
        'useeffect' => ['canonical' => 'React useEffect hook', 'patterns' => ['/\buseeffect\b/i', '/\bcleanup\s+function\b/i']],
        'usestate' => ['canonical' => 'React useState hook', 'patterns' => ['/\busestate\b/i']],
        'useref' => ['canonical' => 'React useRef hook', 'patterns' => ['/\buseref\b/i']],
        'usecontext' => ['canonical' => 'React useContext hook', 'patterns' => ['/\busecontext\b/i']],
        'usememo' => ['canonical' => 'React useMemo and useCallback', 'patterns' => ['/\busememo\b/i', '/\busecallback\b/i']],
        'flexbox' => ['canonical' => 'CSS Flexbox layout', 'patterns' => ['/\bflexbox\b/i', '/\bjustify-content\b/i']],
        'grid' => ['canonical' => 'CSS Grid layout', 'patterns' => ['/\bcss\s+grid\b/i']],
        'box_sizing' => ['canonical' => 'CSS box-sizing border-box', 'patterns' => ['/\bbox-sizing\b/i', '/\bborder-box\b/i']],
        'express_middleware' => ['canonical' => 'Express middleware pipeline', 'patterns' => ['/\bmiddleware\b/i', '/\bnext\(\)\b/i']],
        'jwt_auth' => ['canonical' => 'JWT authentication in Express', 'patterns' => ['/\bjwt\b/i']],
        'event_loop' => ['canonical' => 'Node.js event loop and libuv', 'patterns' => ['/\bevent\s+loop\b/i', '/\blibuv\b/i']],
        'normalization_3nf' => ['canonical' => 'Database Normalization and 3NF', 'patterns' => ['/\b3nf\b/i', '/\bnormalization\b/i']],
        'btree_index' => ['canonical' => 'PostgreSQL B-tree indexing', 'patterns' => ['/\bb-tree\b/i', '/\bindex(es|ing)?\b/i']],
        'acid' => ['canonical' => 'PostgreSQL ACID transactions', 'patterns' => ['/\bacid\b/i', '/\btransactions?\b/i']]
    ];

    private static array $anaphoraPatterns = [
        '/\b(it|this|that|they|them|its)\b/i',
        '/\b(this|that)\s+(hook|function|method|property|element|feature|concept)\b/i',
        '/\b(how\s+does\s+its|does\s+it|can\s+it|why\s+does\s+it)\b/i',
        '/\b(what\s+about\s+it|show\s+me\s+an\s+example)\b/i'
    ];

    public static function isSelfContained(string $query): bool {
        $q = trim($query);
        // Topic shift = self-contained
        if (preg_match('/\b(switch.*topics?|moving\s+on|different\s+topic|new\s+topic)\b/i', $q)) return true;
        // Check for anaphora
        foreach (self::$anaphoraPatterns as $pat) {
            if (preg_match($pat, $q)) return false;
        }
        $words = preg_split('/\s+/', $q);
        return count($words) >= 3 || strlen($q) > 25;
    }

    public static function detectEntityFromText(string $text): ?array {
        $found = null;
        $highestScore = 0;
        foreach (self::$curriculumEntities as $key => $meta) {
            $score = 0;
            foreach ($meta['patterns'] as $pat) {
                if (preg_match_all($pat, $text, $matches)) $score += count($matches[0]) * 3;
            }
            if ($score > $highestScore) {
                $highestScore = $score;
                $found = ['key' => $key, 'canonical' => $meta['canonical']];
            }
        }
        return $found;
    }

    public static function resolveConversationalEntity(string $query, array $history): ?array {
        if (empty($history)) return null;
        // Scan reverse chronological
        foreach (array_reverse($history) as $turn) {
            $content = is_array($turn) ? (($turn['content'] ?? '') . ' ' . ($turn['question'] ?? '')) : (string)$turn;
            $ent = self::detectEntityFromText($content);
            if ($ent) return $ent;
        }
        return null;
    }

    /**
     * Condense a follow-up query by resolving pronouns to curriculum entities
     */
    public static function condense(string $query, array $history): array {
        $cleanQ = trim($query);
        if (empty($history) || empty($cleanQ)) {
            return ['condensed_query' => $cleanQ, 'original_query' => $cleanQ, 'rewritten' => false, 'entity' => null];
        }
        if (self::isSelfContained($cleanQ)) {
            return ['condensed_query' => $cleanQ, 'original_query' => $cleanQ, 'rewritten' => false, 'entity' => null];
        }

        $targetEntity = self::resolveConversationalEntity($cleanQ, $history);
        if (!$targetEntity) {
            return ['condensed_query' => $cleanQ, 'original_query' => $cleanQ, 'rewritten' => false, 'entity' => null];
        }

        $entityName = $targetEntity['canonical'];
        $rewritten = $cleanQ;

        // Pattern-based pronoun replacement
        $replacements = [
            '/^does\s+(it|this)\s+/i' => "Does {$entityName} ",
            '/^can\s+(it|this)\s+/i' => "Can {$entityName} ",
            '/^why\s+does\s+(it|this)\b/i' => "Why does {$entityName}",
            '/^how\s+does\s+(it|this)\b/i' => "How does {$entityName}",
            '/^what\s+happens\s+when\s+(it|this)\b/i' => "What happens when {$entityName}",
            '/^show\s+me\s+an\s+example/i' => "Example of {$entityName}",
            '/\b(this|that)\s+(hook|function|method|element|concept)\b/i' => $entityName,
        ];

        $matched = false;
        foreach ($replacements as $pat => $rep) {
            if (preg_match($pat, $rewritten)) {
                $rewritten = preg_replace($pat, $rep, $rewritten);
                $matched = true;
                break;
            }
        }

        if (!$matched) {
            if (preg_match('/\b(it|this|that)\b/i', $rewritten)) {
                $rewritten = preg_replace('/\b(it|this|that)\b/i', $entityName, $rewritten, 1);
            } else {
                $rewritten = "{$entityName}: {$cleanQ}";
            }
        }

        return [
            'condensed_query' => trim($rewritten),
            'original_query' => $cleanQ,
            'rewritten' => true,
            'entity' => $entityName
        ];
    }
}
