<?php
// EduConnect LMS - Safety Boundary & Prompt Injection Defense (Production)
// Detects out-of-domain queries, fabricated APIs, admin requests, and injection attacks

class RagSafetyBoundary {
    // Unsupported technologies outside curriculum
    private static array $unsupportedTechnologies = [
        'vue' => ['/\bvue(\.js)?\b/i'],
        'angular' => ['/\bangular\b/i', '/\brxjs\b/i'],
        'nextjs' => ['/\bnext(\.js|js)\b/i', '/\bserver\s+components?\b/i'],
        'svelte' => ['/\bsvelte\b/i'],
        'flutter' => ['/\bflutter\b/i', '/\bdart\b/i'],
        'react_native' => ['/\breact\s+native\b/i'],
        'redux' => ['/\bredux\b/i'],
        'django' => ['/\bdjango\b/i'],
        'flask' => ['/\bflask\b/i'],
        'fastapi' => ['/\bfastapi\b/i'],
        'spring_boot' => ['/\bspring(\s*boot)?\b/i'],
        'laravel' => ['/\blaravel\b/i'],
        'rust' => ['/\brust\b/i', '/\bcargo\b/i'],
        'golang' => ['/\bgo(lang)?\b/i', '/\bgoroutines?\b/i'],
        'java' => ['/\bjava\b/i', '/\bjvm\b/i'],
        'mongodb' => ['/\bmongo(db)?\b/i'],
        'redis' => ['/\bredis\b/i'],
        'graphql' => ['/\bgraphql\b/i'],
        'docker' => ['/\bdocker\b/i'],
        'kubernetes' => ['/\bkubernetes\b/i', '/\bk8s\b/i'],
        'aws_cloud' => ['/\baws\b/i', '/\blambda\b/i', '/\bazure\b/i', '/\bgcp\b/i'],
        'blockchain' => ['/\bblockchain\b/i', '/\bbitcoin\b/i', '/\bethereum\b/i', '/\bsolidity\b/i'],
        'ai_ml' => ['/\bpytorch\b/i', '/\btensorflow\b/i', '/\bmachine\s+learning\b/i', '/\bdeep\s+learning\b/i']
    ];

    private static array $administrativePatterns = [
        '/\b(admin.*password|database\s+password|root\s+password|ssh.*key|credentials?)\b/i',
        '/\b(tuition\s+refund|refund\s+polic)\b/i',
        '/\b(change\s+my\s+grade|hack\s+the\s+portal)\b/i'
    ];

    private static array $fabricatedFeaturePatterns = [
        '/\busequantum\b/i', '/\bautorouter\b/i', '/\bmulti-dimensional-flex\b/i',
        '/\buseeffectsync\b/i', '/\bpromise\.allstrict\b/i', '/\bexpress\.autocluster\b/i',
        '/\bobject\.deepfreezeall\b/i', '/\busestate\.forcesync\b/i',
        '/\bdisplay:\s*(hologram|infinite)\b/i', '/\bhtml6\b/i'
    ];

    public static function detectUnsupportedTechnology(string $query): ?array {
        foreach (self::$unsupportedTechnologies as $techKey => $patterns) {
            foreach ($patterns as $pat) {
                if (preg_match($pat, $query, $matches)) {
                    return ['technology' => $techKey, 'matched' => $matches[0]];
                }
            }
        }
        return null;
    }

    public static function detectAdministrativeQuery(string $query): ?string {
        foreach (self::$administrativePatterns as $pat) {
            if (preg_match($pat, $query, $matches)) return $matches[0];
        }
        return null;
    }

    public static function detectFabricatedFeature(string $query): ?string {
        foreach (self::$fabricatedFeaturePatterns as $pat) {
            if (preg_match($pat, $query, $matches)) return $matches[0];
        }
        return null;
    }

    /**
     * Detect prompt injection attacks across 8 attack vectors
     */
    public static function detectInjectionPayload(string $query): ?array {
        $patterns = [
            'instruction_override' => '/\b(ignore\s+(?:all\s+)?(?:previous\s+)?instructions|disregard.*instructions|system\s+override|forget.*previous.*instructions)\b/i',
            'system_prompt_extraction' => '/\b(print.*system\s+prompt|repeat.*words.*above|reveal.*hidden.*prompt|output.*system.*instructions)\b/i',
            'tool_invocation' => '/\b(call\s+tool|execute\s+function|trigger\s+tool|call_tool|use_tool|run_command)\b/i',
            'fake_developer_messages' => '/(\[DEVELOPER\s+NOTICE|ADMINISTRATIVE\s+ALERT|<developer_instruction>|\[SYSTEM\s+INSTRUCTION\])/',
            'role_confusion' => '/\b(you\s+are\s+no\s+longer.*educonnect|you\s+are\s+now\s+dan|roleplay.*unrestricted)\b/i',
            'delimiter_escape' => '/(END\s+OF\s+SYSTEM\s+PROMPT|<\/student_query>|<\/curriculum_evidence>)/i',
            'database_dump' => '/\b(UNION\s+SELECT|DROP\s+TABLE|SELECT.*FROM\s+users)\b/i',
            'multilingual_override' => '/(忽略所有|Игнорируй все|ignorez toutes|ignora todas)/i'
        ];

        foreach ($patterns as $type => $pat) {
            if (preg_match($pat, $query, $m)) {
                return ['type' => $type, 'match' => $m[0]];
            }
        }

        // Base64 encoded payload detection
        if (preg_match_all('/\b([A-Za-z0-9+\/]{16,}={0,2})\b/', $query, $b64Matches)) {
            foreach ($b64Matches[1] as $cand) {
                $decoded = @base64_decode($cand, true);
                if ($decoded && strlen($decoded) > 8 && preg_match('/\b(ignore|system.*prompt|override|password|pwned)\b/i', $decoded)) {
                    return ['type' => 'base64_encoded_override', 'match' => $cand];
                }
            }
        }
        return null;
    }

    /**
     * Comprehensive Safety Boundary Evaluation
     */
    public static function evaluate(string $query): array {
        $q = trim($query);

        if ($inj = self::detectInjectionPayload($q)) {
            return ['action' => 'ABSTAIN', 'reason' => "Injection attack blocked: {$inj['type']}"];
        }
        if ($admin = self::detectAdministrativeQuery($q)) {
            return ['action' => 'ABSTAIN', 'reason' => "Administrative request outside curriculum: {$admin}"];
        }
        if ($fab = self::detectFabricatedFeature($q)) {
            return ['action' => 'ABSTAIN', 'reason' => "Fabricated feature: {$fab}"];
        }
        if ($tech = self::detectUnsupportedTechnology($q)) {
            return ['action' => 'ABSTAIN', 'reason' => "Unsupported technology: {$tech['technology']}"];
        }

        return ['action' => 'PROCEED', 'reason' => 'Within curriculum boundaries'];
    }
}
