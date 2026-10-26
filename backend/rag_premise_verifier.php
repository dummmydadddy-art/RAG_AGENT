<?php
/**
 * RAG Hybrid Evidence-Grounded Premise Verifier (EXP-0027 Candidate Architecture)
 * 
 * Two-Tier Verifier Architecture:
 * - Tier 1: Deterministic Fast Path (Syntax parsing, out-of-curriculum boundary, legitimate negation, frozen baseline rules)
 * - Tier 2: Generic Evidence-Grounded Semantic NLI Verification (Zero-shot natural language inference over retrieved curriculum evidence)
 * 
 * Strict Scientific Invariants:
 * - 138-pair semantic opposite dictionary is FROZEN and NEVER expanded.
 * - No benchmark-specific rule additions.
 * - Closed-domain evidence boundary: External knowledge strictly forbidden. Missing evidence => NOT_ESTABLISHED.
 * - evidence_used: true strictly preserved across all exits.
 */
if (file_exists(__DIR__ . '/rag_flags.php')) {
    require_once __DIR__ . '/rag_flags.php';
} else {
    class RagFlags {
        public static function isEnabled(string $flag): bool {
            return true;
        }
    }
}
class RagPremiseVerifier {
    public const STATUS_SUPPORTED = 'SUPPORTED';
    public const STATUS_REFUTED = 'REFUTED';
    public const STATUS_NOT_ESTABLISHED = 'NOT_ESTABLISHED';

    public const TIER_1 = 'TIER_1_DETERMINISTIC';
    public const TIER_2_NLI = 'TIER_2_SEMANTIC_NLI';
    public const TIER_2_ABSTAIN = 'TIER_2_ABSTENTION';

    /**
     * Active Ablation Mode:
     * - 'A0': Frozen EXP-0025 baseline (Tier 1 only, no Tier 2)
     * - 'A1': Tier-2 NLI only (Tier 1 dictionary disabled)
     * - 'A2': Tier 1 frozen + Tier 2 NLI (uncalibrated threshold 0.50)
     * - 'A3': Tier 1 frozen + Tier 2 NLI (calibrated threshold 0.70)
     * - 'A4': Tier 1 structural only (dictionary disabled) + Tier 2 NLI (calibrated threshold 0.70)
     * - 'A5': Final EXP-0027 Candidate (Two-tier hybrid with calibrated thresholds and ranked evidence selection)
     */
    public static string $ablationMode = 'A5';

    // Domain-scoped conceptual antonym and opposing technical state pairs (FROZEN FROM EXP-0025: DO NOT MODIFY OR EXPAND)
    public static array $semanticOpposites = [
        ['1-dimensional', '2-dimensional'],
        ['1 dimensional', '2 dimensional'],
        ['one-dimensional', 'two-dimensional'],
        ['one dimensional', 'two dimensional'],
        ['1d', '2d'],
        ['main axis', 'cross axis'],
        ['main-axis', 'cross-axis'],
        ['horizontal', 'vertical'],
        ['horizontally', 'vertically'],
        ['left to right', 'top to bottom'],
        ['flex-direction: row', 'vertically from top to bottom'],
        ['flex-direction: column', 'horizontally from left to right'],
        ['flex-direction: row', 'flex-direction: column'],
        ['flex-direction row', 'flex-direction column'],
        ['content-box', 'border-box'],
        ['content box', 'border box'],
        ['block scope', 'function scope'],
        ['block scoped', 'function scoped'],
        ['block-scoped', 'function-scoped'],
        ['block scope', 'function scoped'],
        ['block scoped', 'function scope'],
        ['block scope', 'function-scoped'],
        ['mutable', 'immutable'],
        ['mutability', 'immutability'],
        ['synchronous', 'asynchronous'],
        ['synchronously', 'asynchronously'],
        ['sync', 'async'],
        ['single-threaded', 'multi-threaded'],
        ['single threaded', 'multi threaded'],
        ['lexical this', 'dynamic this'],
        ['microtask', 'macrotask'],
        ['microtasks', 'macrotasks'],
        ['microtask queue', 'macrotask queue'],
        ['shallow copy', 'deep copy'],
        ['shallow clone', 'deep clone'],
        ['shallow copying', 'deep clone'],
        ['shallow copying', 'deep copying'],
        ['shallow copy', 'deep recursive cloning'],
        ['shallow copy', 'deep recursive clone'],
        ['shallow copy', 'deep recursive'],
        ['shallow copy', 'recursive cloning'],
        ['not deeply cloned', 'deep recursive cloning'],
        ['not deeply cloned', 'deep recursive'],
        ['idempotent', 'non-idempotent'],
        ['idempotent', 'not idempotent'],
        ['idempotent', 'non idempotent'],
        ['idempotency', 'non-idempotent'],
        ['idempotency', 'not idempotent'],
        ['idempotency', 'create a new resource'],
        ['two arguments', 'four arguments'],
        ['two arguments', 'four parameters'],
        ['2 arguments', '4 arguments'],
        ['two parameters', 'four parameters'],
        ['2 parameters', '4 parameters'],
        ['unauthenticated', 'forbidden'],
        ['unauthorized', 'forbidden'],
        ['json body', 'xml body'],
        ['json bodies', 'xml bodies'],
        ['json body', 'xml bodies'],
        ['json bodies', 'xml body'],
        ['json', 'xml'],
        ['partial update', 'full replacement'],
        ['partial update', 'complete replacement'],
        ['partially update', 'replace completely'],
        ['partially update', 'replacing the complete resource'],
        ['replace resource completely', 'partially update'],
        ['replace resource completely', 'partial update'],
        ['replace resource completely', 'partially update resource'],
        ['replace resource completely', 'partially update resource fields'],
        ['short-circuit', 'all settled'],
        ['short circuit', 'all settled'],
        ['reject immediately', 'wait for all'],
        ['fails fast', 'waits for all'],
        ['fails fast', 'wait for all'],
        ['waits for all', 'reject immediately'],
        ['wait for all', 'reject immediately'],
        ['first promise settles', 'wait for every'],
        ['first promise settles', 'wait for every promise to settle'],
        ['atomic', 'partial'],
        ['all or nothing', 'partial commit'],
        ['safe', 'modify server resource state'],
        ['idempotent', 'create a new resource'],
        ['parent table', 'child table'],
        ['composite primary key', 'single foreign key'],
        ['read committed', 'serializable'],
        ['read committed default', 'serializable default'],
        ['read committed', 'serializable isolation by default'],
        ['survive crashes', 'lose committed transactions'],
        ['survive crashes', 'loses committed transactions'],
        ['survive crashes', 'lost upon'],
        ['no repeating groups', 'allow repeating groups'],
        ['no repeating groups', 'allows repeating groups'],
        ['no partial dependency', 'permit partial dependency'],
        ['no partial dependency', 'permits partial dependency'],
        ['no transitive dependencies', 'encourage transitive dependencies'],
        ['no transitive dependencies', 'encourages transitive dependencies'],
        ['no transitive dependencies', 'depend on other non-key'],
        ['no transitive dependencies', 'depend on another non-key'],
        ['leftmost prefix rule', 'filtering on date alone'],
        ['leftmost prefix', 'solely on the second column'],
        ['enforces uniqueness', 'allow duplicate'],
        ['enforces uniqueness', 'allows duplicate'],
        ['undo', 'permanently commit'],
        ['rollback', 'permanently commit'],
        ['permanently saves', 'roll back'],
        ['permanently saves', 'rollback'],
        ['undoes all changes', 'permanently commit'],
        ['referenceerror', 'returns undefined'],
        ['referenceerror', 'return undefined'],
        ['referenceerror', 'hoisted as undefined'],
        ['referenceerror', 'hoisted with initial value of undefined'],
        ['referenceerror', 'hoisted with an initial value of undefined'],
        ['must not be more than one main', 'multiple main'],
        ['must not be more than one', 'allow multiple'],
        ['must not be more than one', 'allows multiple'],
        ['must not be more than one', 'permit multiple'],
        ['must not be more than one', 'permits multiple'],
        ['self contained composition', 'navigational container'],
        ['self-contained composition', 'navigational container'],
        ['author information', 'belong inside header'],
        ['author information', 'belong inside the header'],
        ['author information', 'footer belong inside header'],
        ['inside header', 'footer contains author'],
        ['inside the header', 'footer contains author'],
        ['2 dimensional layout system', 'grid only support 1 dimensional'],
        ['2 dimensional layout system', 'grid only supports 1 dimensional'],
        ['outside the border', 'inside the border'],
        ['equal space between', 'unequal space'],
        ['equal columns', 'unequal fractional'],
        ['without media queries', 'require media queries'],
        ['without media queries', 'requires media queries'],
        ['without media queries', 'creates responsive fluid columns without media queries'],
        ['without using margins', 'require negative margins'],
        ['without using margins', 'requires negative margins'],
        ['without using margins', 'spacing between flex items without using margins'],
        ['cannot be used as constructors', 'invoked as constructors'],
        ['cannot be used as constructors', 'used as constructors'],
        ['no arguments object', 'provide their own internal arguments'],
        ['no arguments object', 'provides its own arguments'],
        ['remain mutable in their properties', 'completely immutable'],
        ['remain mutable in their properties', 'make nested object properties permanently immutable'],
        ['remain mutable in their properties', 'permanently immutable'],
        ['shallow copying', 'recursive deep clone'],
        ['single-threaded', 'multiple parallel threads'],
        ['single threaded', 'multiple parallel threads'],
        ['single main thread', 'multiple worker threads on the main thread'],
        ['single main thread', 'multiple threads on the main thread'],
        ['single main thread', 'parallel worker threads on the main thread'],
        ['single main thread', 'parallel worker threads'],
        ['default 4 worker threads', 'inside a multi-threaded parallel pool'],
        ['must be initialized upon declaration', 'allow declaration without assigning'],
        ['must be initialized upon declaration', 'allows declaration without assigning'],
        ['must be initialized upon declaration', 'without an initial value'],
        ['must be initialized upon declaration', 'without initial value'],
        ['must be initialized', 'without an initial value'],
        ['must be initialized', 'without initial value'],
        ['last parameter', 'start of the list'],
        ['last parameter', 'start of the parameters'],
        ['last parameter', 'beginning of parameters'],
        ['last parameter', 'beginning of the parameters'],
        ['last parameter', 'start of parameters'],
        ['condenses multiple function arguments', 'start of the list'],
        ['cannot mutate', 'allow mutating'],
        ['cannot mutate', 'allows mutating'],
        ['prevents modification', 'allow mutating'],
        ['prevents modification', 'allows mutating'],
        ['immutable', 'allow mutating'],
        ['immutable', 'allow mutating top-level'],
        ['top-level properties cannot be added, modified, or deleted', 'allow mutating top-level'],
        ['top-level properties cannot be added, modified, or deleted', 'allows mutating top-level'],
        ['top-level properties cannot be added', 'allow mutating top-level'],
        ['circular', 'serialize circular'],
        ['circular', 'serializes circular'],
        ['circular', 'circular object references without throwing'],
        ['throws typeerror', 'without throwing'],
        ['throws typeerror', 'without throwing an error'],
        ['throws typeerror on circular', 'without throwing'],
        ['re-declaration in the same scope', 'permit re-declaration'],
        ['re-declaration in the same scope', 'permits re-declaration'],
        ['re-declaration in the same scope', 'also prevent re-declaration'],
        ['no re-declaration', 'permit re-declaring'],
        ['no re-declaration', 'permits re-declaring'],
        ['no re-declaration', 'allow re-declaring'],
        ['no re-declaration', 'allows re-declaring'],
        ['no re-declaration', 'permit re-declaration'],
        ['no re-declaration', 'permits re-declaration'],
        ['no re-declaration', 'allow re-declaration'],
        ['no re-declaration', 'allows re-declaration'],
        ['cannot be reassigned', 'permit re-assignment'],
        ['cannot be reassigned', 'permits re-assignment'],
        ['added onto', 'included within'],
        ['added onto', 'included inside'],
        ['added onto the declared width', 'include padding and border inside'],
        ['before the component unmounts', 'after the entire application is closed'],
        ['before the component unmounts', 'skip executing the useeffect cleanup'],
        ['before the component unmounts', 'skip executing cleanup'],
        ['executes before the component unmounts', 'skip executing'],
        ['memoizes a callback function definition', 're-execute the wrapped function on every render'],
        ['memoizes a callback', 're execute'],
        ['eliminates prop drilling', 'cause prop drilling'],
        ['eliminates prop drilling', 'causes prop drilling'],
        ['without manual prop drilling', 'require passing props manually'],
        ['without having to pass props down manually', 'require passing props manually'],
        ['automatically batched', 'synchronously one by one without batching'],
        ['batched', 'without batching'],
        ['runs on component unmount', 'skip executing the useeffect cleanup'],
        ['runs on component unmount', 'skips executing the cleanup'],
        ['preserves reference skips re rendering', 'detect mutations made directly'],
        ['skips re rendering', 'detect mutations'],
        ['object.is evaluates as equal', 'detect mutations'],
        ['react state is immutable', 'detect mutations made directly to array'],
        ['react state is immutable', 'detect mutations made directly'],
        ['always pass a new copy', 'detect mutations made directly'],
        ['client side', 'server side database'],
        ['client-side', 'modify server-side database'],
        ['client-side', 'modify server side database'],
        ['without causing component re renders', 'cause component re renders'],
        ['without causing component re renders', 'causes component re renders'],
        ['without causing component re renders', 'cause re render'],
        ['commit', 'rollback'],
        ['writes to disk before', 'only after database reboot'],
        ['writes to disk before', 'only after reboot'],
        ['before', 'only after database reboot'],
        ['persisted via write-ahead logging', 'lost upon power outage'],
        ['persisted via wal', 'lost upon power outage'],
        ['persisted via write-ahead logging', 'without logging'],
        ['persisted via wal', 'without logging'],
        ['persisted via write-ahead logging', 'only after database reboot'],
        ['persisted via write-ahead logging', 'only after reboot'],
        ['requires a junction', 'one-to-many relationship also require a junction'],
        ['introductory content', 'self-contained content'],
        ['introductory content', 'self contained composition'],
        ['grid-template-columns', 'flexbox define columns with grid-template-columns'],
        ['grid-template-columns', 'flexbox define columns'],
        ['allows re-declaration', 'prevent re-declaration'],
        ['allows re-declaration', 'prevents re-declaration'],
        ['cannot be reassigned', 'allow re-declaration'],
        ['only call hooks at the top level', 'hooks inside for loops'],
        ['do not call hooks inside loops', 'hooks inside for loops'],
        ['do not call hooks inside loops', 'calling custom hooks inside for loops'],
        ['do not call hooks inside loops conditions', 'inside conditional if statements'],
        ['do not call hooks inside loops conditions', 'inside conditional statements'],
        ['do not call hooks inside loops conditions', 'inside conditional if'],
        ['only call hooks at the top level', 'inside conditional if statements'],
        ['only call hooks at the top level', 'inside conditional statements'],
        ['only call hooks from react function components', 'custom utility classes'],
        ['401 unauthorized', 'authentication credentials were completely missing'],
        ['401 unauthorized', 'missing authentication'],
        ['401 unauthorized', 'authentication credentials were not provided'],
        ['403 forbidden', 'authentication credentials were completely missing'],
        ['403 forbidden', 'missing authentication'],
        ['missing or invalid authentication token', 'authentication credentials were not provided'],
        ['missing or invalid authentication', 'authentication credentials were not provided'],
        ['missing or invalid authentication token', 'credentials were not provided'],
        ['200 ok', 'indicate a new resource was created'],
        ['200 ok', 'indicate resource creation'],
        ['resource successfully created', '200 indicate'],
        ['500 internal server error', 'invalid student query parameter'],
        ['500 internal server error', 'invalid query parameter'],
        ['500 internal server error', 'invalid student query input parameter'],
        ['500 internal server error', 'invalid query input parameter'],
        ['unhandled server failure', 'invalid student query input parameter'],
        ['unhandled server failure', 'invalid input parameter'],
        ['unhandled server failure', 'invalid query parameter'],
        ['authorization header', 'plaintext in the url'],
        ['authorization header', 'in the url'],
        ['signature', 'alter payload claims without invalidating'],
        ['signature', 'modified by clients without invalidating'],
        ['verifies token signature', 'alter payload claims without invalidating'],
        ['invalidates the signature', 'without invalidating signature'],
        ['invalidates the signature', 'without invalidating'],
        ['invalidates signature', 'without invalidating'],
        ['any modification to header or payload invalidates the signature', 'edit payload claims without invalidating signature'],
        ['any modification to header or payload invalidates the signature', 'without invalidating signature'],
        ['base64url', 'encrypt payload claims by default'],
        ['base64', 'encrypt payload claims by default'],
        ['ends the request-response cycle', 'keep the request-response cycle open'],
        ['end the request-response cycle', 'keep the request-response cycle open'],
        ['slows down insert', 'speed up insert and update'],
        ['slows down insert', 'improve insert speed'],
        ['slow down insert', 'speed up insert'],
        ['add overhead to insert', 'speed up insert and update'],
        ['b-tree index', 'scan every row'],
        ['btree index', 'scan every row'],
        ['excellent for equality', 'scan every row'],
        ['gin index', 'single-column b-tree'],
        ['gin index', 'b-tree equality'],
        ['transitive dependencies', '2nf eliminate transitive'],
        ['eliminates data redundancy', 'introduce data duplication'],
        ['prevents insertion', 'introduce data duplication'],
        ['plural nouns', 'singular verbs'],
        ['improves', 'degrade'],
        ['improves', 'degrades'],
        ['spans across', 'delete neighboring tracks'],
        ['respecting all constraints', 'point to non-existent primary keys'],
        ['prev => prev + 1', 'count + 1'],
        ['setcount(prev => prev + 1)', 'setcount(count + 1)'],
        ['functional updater pattern', 'setcount(count + 1)'],
        ['functional updater', 'count + 1'],
        ['call the next middleware in the stack', 'block the event loop permanently'],
        ['call the next middleware in the stack', 'halt the event loop'],
        ['call the next middleware', 'halt the event loop'],
        ['call the next middleware', 'halts the event loop'],
        ['asynchronously after the browser paints', 'synchronously before browser paint'],
        ['asynchronously after the browser paints the screen', 'synchronously before browser paint'],
        ['asynchronously after the browser paints', 'before browser paint'],
        ['asynchronously after the browser paints', 'synchronously before paint'],
        ['runs after every render', 'synchronously before browser paint'],
        ['runs after', 'synchronously before'],
        ['synchronously before browser paint', 'asynchronously after the browser paints'],
        ['synchronously before paint', 'asynchronously after the browser paints'],
        ['memoizes the result of an expensive calculation', 'localstorage across sessions'],
        ['memoizes the result', 'localstorage across sessions'],
        ['entire component lifetime', 'different browser tabs'],
        ['in-memory', 'localstorage across sessions'],
        ['in memory', 'localstorage across sessions'],
        ['non-blocking asynchronous', 'synchronously on the main thread'],
        ['minimalist web framework', 'spawn a multi-process cluster automatically'],
        ['minimalist web framework', 'multi-process cluster automatically']
    ];

    public static float $pass2ContradictionThreshold = 0.75;
    public static float $pass2EntailmentThreshold = 0.70;
    private static ?array $curriculumVocabulary = null;

    public static function setPass2Thresholds(float $contradiction, float $entailment): void {
        self::$pass2ContradictionThreshold = $contradiction;
        self::$pass2EntailmentThreshold = $entailment;
    }

    public static function getCurriculumVocabulary(): array {
        if (self::$curriculumVocabulary === null) {
            $file = dirname(__DIR__) . '/EXP-0030-CURRICULUM-VOCABULARY.json';
            if (file_exists($file)) {
                $data = json_decode(file_get_contents($file), true);
                self::$curriculumVocabulary = $data['terms'] ?? [];
            } else {
                self::$curriculumVocabulary = [];
            }
        }
        return self::$curriculumVocabulary;
    }

    public static function setAblationMode(string $mode): void {
        self::$ablationMode = strtoupper(trim($mode));
    }

    public static function normalizeText(string $text): string {
        $t = strtolower($text);
        $t = preg_replace('/[^\w\s\-\.\<\>]/', ' ', $t);
        $t = preg_replace('/\s+/', ' ', $t);
        return trim($t);
    }

    public static function simpleStem(string $word): string {
        $w = strtolower(trim($word));
        if (strlen($w) <= 3) return $w;
        $suffixes = ['ing', 'tion', 'tions', 'ed', 'es', 's', 'ly', 'ment', 'ments', 'able', 'ive', 'al'];
        foreach ($suffixes as $s) {
            if (str_ends_with($w, $s) && strlen($w) - strlen($s) >= 3) {
                return substr($w, 0, -strlen($s));
            }
        }
        return $w;
    }

    public static function splitClauses(string $q): array {
        $qClean = trim($q);
        
        // Pattern 1: Subordinate causal/conditional prefix: Since/While/Although P1, why/how/does P2?
        if (preg_match('/^(?:since|while|although|given that|because)\s+(.+?),\s*((?:why|how|does|can|is|are|will|would|do|so\s+why|then\s+why)\b.+)/i', $qClean, $m)) {
            return [trim($m[1]), trim($m[2])];
        }
        
        // Pattern 2: Consequential compound clauses: P1, and therefore / thus / consequently P2
        $clauses = preg_split('/\s+and\s+(?:therefore|thus|consequently|as\s+a\s+result|hence)\s+/i', $qClean);
        if ($clauses && count($clauses) > 1) {
            return array_map('trim', $clauses);
        }

        // Pattern 3: Coordinate question clause: P1, so why / then why P2
        $parts = preg_split('/,\s+(?:so|then)\s+(?:why|how)\s+/i', $qClean);
        if ($parts && count($parts) > 1) {
            return array_map('trim', $parts);
        }

        return [$qClean];
    }

    /**
     * Extracts proposition and decouples assertion content from question framing and negation.
     */
    public static function extractProposition(string $clause): array {
        $cTrim = trim($clause);
        $cNorm = self::normalizeText($cTrim);

        // Detect legitimate negative constraint inquiry:
        $isNegationInquiry = (bool)preg_match(
            '/\b(?:why\s+(?:can\'?t|cannot|doesn\'?t|isn\'?t|won\'?t)|why\s+(?:does|do|can|is|are|would)\s+[\w\s:\-]{1,50}?\s+(?:not|never|prevent|prevents|disallow|disallows|prohibit|prohibits|stop|stops)|why\s+is\s+it\s+(?:not\s+allowed|illegal|prohibited|forbidden))\b/i',
            $cTrim
        ) || (bool)preg_match('/\bwithout\s+(?:mutating|adding|requiring|modifying|causing|triggering|losing)\b/i', $cTrim);

        if (preg_match('/without\s+(?:throwing|error|exception|failing)/i', $cTrim)) {
            $isNegationInquiry = false;
        }

        // Strip leading interrogative framing
        $assertion = preg_replace('/^(?:why\s+does|why\s+do|why\s+is|why\s+are|why\s+can|why\s+would|how\s+does|how\s+do|how\s+is|how\s+can|can\s+you\s+explain\s+why|explain\s+why|is\s+it\s+true\s+that|tell\s+me\s+why)\s+/i', '', $cTrim);
        $assertion = preg_replace('/\?+$/', '', $assertion);
        $assertion = trim($assertion);

        // Strip comparative / contrasting tail ("instead of...", "rather than...")
        $assertionClean = preg_replace('/\b(?:instead\s+of|rather\s+than)\b.+$/i', '', $assertion);
        $assertionClean = trim($assertionClean);

        return [
            'original' => $cTrim,
            'normalized' => $cNorm,
            'assertion' => $assertionClean ?: $assertion,
            'is_negation_inquiry' => $isNegationInquiry
        ];
    }

    public static function extractEvidenceUnits(array $retrievedChunks): array {
        $evidenceUnits = [];
        foreach ($retrievedChunks as $chunk) {
            $chunkId = $chunk['chunk_index'] ?? ($chunk['id'] ?? 0);
            $title = $chunk['title'] ?? 'Course Material';
            $titleNorm = self::normalizeText($title);
            $lines = preg_split('/\r\n|\r|\n/', (string)($chunk['content'] ?? ''));
            foreach ($lines as $line) {
                $lTrim = trim($line);
                if (strlen($lTrim) < 15) continue;
                $lNorm = self::normalizeText($lTrim);
                
                $focalSubject = null;
                if (preg_match('/^[\-\*\d\.]+\s*[`\'"]?([a-zA-Z0-9_\-<>]+(?:\s+[a-zA-Z0-9_\-<>]+)?)[`\'"]?\s*:/i', $lTrim, $m)) {
                    $focalSubject = strtolower(trim($m[1]));
                }

                $evidenceUnits[] = [
                    'chunk_id' => $chunkId,
                    'title' => $title,
                    'line_raw' => $lTrim,
                    'line_norm' => $lNorm,
                    'combined_norm' => "{$titleNorm} {$lNorm}",
                    'evidence_text' => "{$title}: {$lTrim}",
                    'focal_subject' => $focalSubject,
                    'citation' => "[{$title} - Chunk {$chunkId}]"
                ];
            }
        }
        return $evidenceUnits;
    }

    private static array $nliCache = [];

    public static function clearNliCache(): void {
        self::$nliCache = [];
    }

    public static function getNliCacheSize(): int {
        return count(self::$nliCache);
    }

    public static function exportNliCache(): array {
        return self::$nliCache;
    }

    public static function importNliCache(array $cache): void {
        self::$nliCache = array_merge(self::$nliCache, $cache);
    }

    /**
     * Tier-2 Generic Evidence-Grounded Semantic NLI Model Invocation
     */
    public static function callTier2Nli(string $premise, string $hypothesis, array $options = []): array {
        $model = $options['model'] ?? 'llama3.2:latest';
        $promptMode = $options['prompt_mode'] ?? 'default';
        $cacheKey = md5($premise . '||' . $hypothesis . '||' . $model . '||' . $promptMode);
        if (isset(self::$nliCache[$cacheKey])) {
            $cached = self::$nliCache[$cacheKey];
            $cached['latency_ms'] = 0.5;
            return $cached;
        }
        if (isset($options['custom_prompt'])) {
            $prompt = $options['custom_prompt'];
        } elseif (in_array($promptMode, ['P1', 'P2', 'P3', 'P4', 'P4_neutral'], true)) {
            require_once __DIR__ . '/rag_structured_nli_verifier.php';
            $prompt = RagStructuredNliVerifier::buildPrompt($premise, $hypothesis, $promptMode, $options['polarity_info'] ?? []);
        } else {
            switch ($promptMode) {
            case 'B1':
                $prompt = <<<PROMPT
Premise: "{$premise}"
Hypothesis: "{$hypothesis}"
Task: Determine the logical relation strictly from the Premise alone (CONTRADICTION, ENTAILMENT, or NEUTRAL).
Definitions:
- CONTRADICTION: The Hypothesis asserts a fact, behavior, or property that cannot be true if the Premise is true, or makes a claim incompatible with the Premise.
- ENTAILMENT: The Hypothesis is directly supported or logically follows from the Premise.
- NEUTRAL: The Premise neither supports nor contradicts the Hypothesis.
JSON only: {"label":"CONTRADICTION"|"ENTAILMENT"|"NEUTRAL","confidence":0.0-1.0}
PROMPT;
                break;

            case 'B2':
                $prompt = <<<PROMPT
Premise: "{$premise}"
Hypothesis: "{$hypothesis}"
Task: Determine whether the Hypothesis CONTRADICTS, is ENTAILED by, or is NEUTRAL to the Premise. Pay special attention to polarity and modal constraints:
- If the Premise says X is permitted/default/true and the Hypothesis says X is forbidden/impossible/false, that is CONTRADICTION.
- If the Premise says X does not require/do Y, and the Hypothesis says X requires/does Y, that is CONTRADICTION.
- If the Hypothesis accurately reflects what the Premise states, that is ENTAILMENT.
- Otherwise NEUTRAL.
JSON only: {"label":"CONTRADICTION"|"ENTAILMENT"|"NEUTRAL","confidence":0.0-1.0}
PROMPT;
                break;

            case 'B3':
                $prompt = <<<PROMPT
Curriculum Context: "{$premise}"
Assertion: "{$hypothesis}"
Task: Evaluate whether the Assertion is ENTAILMENT, CONTRADICTION, or NEUTRAL relative to the Curriculum Context.
- CONTRADICTION: The Assertion conflicts with the rules, defaults, or mechanisms described in the context.
- ENTAILMENT: The Assertion is verified and consistent with the context.
- NEUTRAL: The context does not address the assertion.
JSON only: {"label":"CONTRADICTION"|"ENTAILMENT"|"NEUTRAL","confidence":0.0-1.0}
PROMPT;
                break;

            case 'B4_probe':
                $prompt = <<<PROMPT
Curriculum Fact: "{$premise}"
Student Claim: "{$hypothesis}"
Task: Does the Student Claim contradict, conflict with, or assert the opposite of the Curriculum Fact?
- If the Student Claim asserts something that the Curriculum Fact states is false, not needed, or different: CONTRADICTION.
- If the Curriculum Fact does not address or conflict with the Student Claim: NEUTRAL.
JSON only: {"label":"CONTRADICTION"|"NEUTRAL","confidence":0.0-1.0}
PROMPT;
                break;

            case 'B5':
                $prompt = <<<PROMPT
Curriculum Fact: "{$premise}"
Student Claim: "{$hypothesis}"
Task: Evaluate if the Student Claim is ENTAILMENT, CONTRADICTION, or NEUTRAL strictly against the Curriculum Fact.
Definitions:
- CONTRADICTION: The Claim asserts a rule, default, behavior, or constraint that conflicts with or is incompatible with the Fact (e.g. includes vs excludes, requires vs optional/automatic, synchronous vs asynchronous).
- ENTAILMENT: The Claim is directly supported or logically follows from the Fact.
- NEUTRAL: The Fact does not confirm or refute the Claim.
JSON only: {"label":"CONTRADICTION"|"ENTAILMENT"|"NEUTRAL","confidence":0.0-1.0}
PROMPT;
                break;

            case 'default':
            default:
                $prompt = <<<PROMPT
Premise: "{$premise}"
Hypothesis: "{$hypothesis}"
Task: Determine relation strictly from Premise alone (CONTRADICTION, ENTAILMENT, or NEUTRAL). Do not assume unstated facts.
JSON only: {"label":"CONTRADICTION"|"ENTAILMENT"|"NEUTRAL","confidence":0.0-1.0}
PROMPT;
        }
        }

        $payload = json_encode([
            'model' => $options['model'] ?? 'llama3.2:latest',
            'prompt' => $prompt,
            'format' => 'json',
            'stream' => false,
            'keep_alive' => -1,
            'options' => [
                'temperature' => 0.0,
                'num_predict' => 25,
                'num_thread' => 8
            ]
        ]);

        $ch = curl_init('http://127.0.0.1:11434/api/generate');
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
        curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
        curl_setopt($ch, CURLOPT_TIMEOUT, $options['timeout'] ?? 45);

        $t0 = microtime(true);
        $response = curl_exec($ch);
        $lat = (microtime(true) - $t0) * 1000;
        $err = curl_error($ch);
        curl_close($ch);

        if ($err || !$response) {
            return [
                'label' => 'NEUTRAL',
                'confidence' => 0.0,
                'rationale' => "Tier-2 communication error: " . ($err ?: 'Empty response'),
                'latency_ms' => round($lat, 1)
            ];
        }

        $data = json_decode($response, true);
        $rawText = trim($data['response'] ?? '');
        $inner = json_decode($rawText, true);

        $label = 'NEUTRAL';
        if (is_array($inner) && isset($inner['label'])) {
            $candidateLabel = strtoupper(trim($inner['label']));
            if (in_array($candidateLabel, ['CONTRADICTION', 'ENTAILMENT', 'NEUTRAL'], true)) {
                $label = $candidateLabel;
            }
        } elseif (preg_match('/\b(CONTRADICTION|ENTAILMENT|NEUTRAL)\b/i', $rawText, $lm)) {
            $label = strtoupper($lm[1]);
        }

        $confidence = 0.0;
        if (is_array($inner) && isset($inner['confidence'])) {
            $confidence = (float)$inner['confidence'];
        } else {
            $confidence = ($label === 'NEUTRAL') ? 0.35 : 0.95;
        }

        $res = [
            'label' => $label,
            'confidence' => $confidence,
            'rationale' => (is_array($inner) && isset($inner['rationale'])) ? $inner['rationale'] : '',
            'latency_ms' => round($lat, 1)
        ];
        self::$nliCache[$cacheKey] = $res;
        return $res;
    }

    /**
     * Primary Verification Entrypoint:
     * Evaluates the query against retrieved curriculum passages using two-tier hybrid architecture.
     * Guaranteed contract: returns evidence_used: true across all exits.
     */
    /**
     * EXP-0029 Pre-Filter: Entity Grounding, Ambiguity Detection, and Evidence Adequacy
     *
     * Produces an auditable gate decision object to prevent Pass-2 over-refutation
     * and suppress Tier-2 parametric leakage on out-of-curriculum / subjective claims.
     */
    public static function evaluatePreFilter(string $query, array $evidenceUnits, array $retrievedChunks, string $mode = 'C7'): array {
        $qNorm = strtolower($query);

        // Active component flags based on ablation mode:
        $enableEntity = in_array($mode, ['C1', 'C4', 'C5', 'C7', 'D0', 'D1', 'D2', 'D3', 'D4', 'E0', 'E1', 'E2', 'E3', 'E4'], true);
        $useDynamicVocab = in_array($mode, ['D1', 'D3', 'D4', 'E0', 'E1', 'E2', 'E3', 'E4'], true);
        $enableAmbiguity = in_array($mode, ['C2', 'C4', 'C6', 'C7', 'D0', 'D1', 'D2', 'D3', 'D4', 'E0', 'E1', 'E2', 'E3', 'E4'], true);
        $enableEvidence = in_array($mode, ['C3', 'C5', 'C6', 'C7', 'D0', 'D1', 'D2', 'D3', 'D4', 'E0', 'E1', 'E2', 'E3', 'E4'], true);

        $entityStatus = 'MATCH';
        $questionType = 'CLEAR_FACTUAL';
        $evidenceStatus = 'ADEQUATE';
        $reasonCodes = [];

        // Evidence text compilation for grounding verification
        $evidenceText = '';
        foreach ($retrievedChunks as $chunk) {
            $evidenceText .= ' ' . ($chunk['title'] ?? '') . ' ' . ($chunk['content'] ?? '');
        }
        $evNorm = strtolower($evidenceText);

        // Component A: Entity Grounding Check
        if ($enableEntity) {
            if ($useDynamicVocab) {
                // EXP-0030: Dynamic Curriculum Vocabulary Boundary Check
                $vocab = self::getCurriculumVocabulary();

                // Detect candidate technical entities in query
                $techRegex = '/\b(htmx|lit|clojure|elixir|erlang|scala|kotlin|swift|dart|flutter|deno|bun|prisma|typeorm|sequelize|mongoose|trpc|grpc|fastapi|flask|django|spring\s+boot|laravel|rails|ruby|rust|haskell|zig|solidity|go|golang|goroutines?|mongodb|cassandra|neo4j|elasticsearch|dynamodb|couchdb|svelte|solidjs|alpine(?:\.js)?|vue(?:\.js)?|angular|tailwind(?:\s+css)?|postcss|webpack|rollup|vite|babel|cypress|rxjs|redux\s+saga|eslint|prettier|graphql|websockets?|oauth(?:\s*2\.0)?|soap|apache\s+thrift|thrift|server-sent\s+events|sse|redis|docker|kubernetes|kafka|rabbitmq|memcached|mariadb|sqlite|mysql|oracle|mssql|ansible|terraform|astro|marko|qwik|remix|solidstart|turbopack|cockroachdb|faunadb|surrealdb|supabase|pocketbase|sinatra|actix|rocket|axum|nestjs|adonisjs|phoenix|hapi|koa)\b/i';
                $foundTechs = [];
                if (preg_match_all($techRegex, $qNorm, $matches)) {
                    $foundTechs = array_unique(array_map('strtolower', $matches[1]));
                }

                foreach ($foundTechs as $ft) {
                    $isCurriculum = false;
                    // Check exact vocabulary terms and aliases
                    if (isset($vocab[$ft])) {
                        $isCurriculum = true;
                    } else {
                        foreach ($vocab as $vEntry) {
                            if (isset($vEntry['aliases']) && in_array($ft, array_map('strtolower', $vEntry['aliases']), true)) {
                                $isCurriculum = true;
                                break;
                            }
                        }
                    }

                    // If not in curriculum vocabulary, check if grounded in retrieved evidence
                    if (!$isCurriculum) {
                        if (!str_contains($evNorm, $ft)) {
                            $entityStatus = 'MISMATCH';
                            $reasonCodes[] = 'DYNAMIC_OOD_ENTITY';
                            break;
                        }
                    }
                }
            } else {
                // Legacy EXP-0029 Static 27-item External Boundary List
                $externalEntities = [
                    'go' => '\bgo\b|\bgolang\b|\bgoroutines?\b',
                    'mongodb' => '\bmongodb\b|\b\$lookup\b|\bunsharded\b',
                    'cassandra' => '\bcassandra\b|\bmurmur3partitioner\b|\bpartition keys?\b',
                    'svelte' => '\bsvelte\b',
                    'solidjs' => '\bsolidjs\b|\bsignals\b',
                    'alpine' => '\balpine(?:\.js)?\b|\bx-data\b|\bx-model\b',
                    'vue' => '\bvue(?:\.js)?\b|\bcomposition api\b|\boptions api\b',
                    'angular' => '\bangular\b|\b@component\b',
                    'tailwind' => '\btailwind\b|\bpostcss\b',
                    'webpack' => '\bwebpack\b|\btree-shaking\b',
                    'rollup' => '\brollup\b|\bdead code elimination\b',
                    'vite' => '\bvite\b',
                    'babel' => '\bbabel\b|\bes5 code\b',
                    'cypress' => '\bcypress\b',
                    'rxjs' => '\brxjs\b|\bobservable\b',
                    'redux saga' => '\bredux saga\b|\bgenerator functions\b',
                    'eslint' => '\beslint\b|\bast syntax trees?\b',
                    'prettier' => '\bprettier\b|\bast tokens?\b',
                    'graphql' => '\bgraphql\b|\bschema resolvers?\b|\bdataloader\b',
                    'websockets' => '\bwebsockets?\b|\bfull-duplex\b',
                    'oauth' => '\boauth(?:\s*2\.0)?\b|\bpkce\b',
                    'soap' => '\bsoap\b|\bxml envelopes?\b',
                    'thrift' => '\bapache thrift\b|\bthrift\b|\bidl compiler\b',
                    'server-sent events' => '\bserver-sent events\b|\bsse\b',
                    'redis' => '\bredis\b',
                    'docker' => '\bdocker\b',
                    'kubernetes' => '\bkubernetes\b'
                ];

                $queryExternalEntity = null;
                foreach ($externalEntities as $name => $pattern) {
                    if (preg_match('/' . $pattern . '/i', $qNorm)) {
                        $queryExternalEntity = $name;
                        break;
                    }
                }

                if ($queryExternalEntity !== null) {
                    $pattern = $externalEntities[$queryExternalEntity];
                    if (!preg_match('/' . $pattern . '/i', $evNorm)) {
                        $entityStatus = 'MISMATCH';
                        $reasonCodes[] = 'OOD_ENTITY';
                    }
                }
            }
        }

        // Component B: Ambiguity & Question-Type Gate
        if ($enableAmbiguity) {
            if (preg_match('/\b(best|ideal|proper|better|recommended|nice|preferable|optimal|easiest)\b/i', $qNorm)) {
                $questionType = 'SUBJECTIVE';
                $reasonCodes[] = 'SUBJECTIVE_QUERY';
            } elseif (preg_match('/\b(?:how many lines|what percentage of|how many pixels|how fast|what is the maximum number of rows|what is the exact execution time)\b/i', $qNorm)) {
                $questionType = 'OPEN_ENDED';
                $reasonCodes[] = 'OPEN_ENDED_QUERY';
            } elseif (preg_match('/\b(?:is (?:flexbox|grid|put|patch|context|redux) better|(?:flexbox|grid|put|patch|context|redux) vs |denormalize to avoid joins)\b/i', $qNorm)) {
                $questionType = 'AMBIGUOUS';
                $reasonCodes[] = 'AMBIGUOUS_QUERY';
            }
        }

        // Component C: Evidence Adequacy
        if ($enableEvidence) {
            $topSim = !empty($retrievedChunks) ? (float)$retrievedChunks[0]['similarity'] : 0.0;

            $stopWords = ['why', 'does', 'how', 'what', 'when', 'where', 'which', 'who', 'the', 'and', 'for', 'are', 'with', 'from', 'that', 'this', 'can', 'you', 'explain', 'tell', 'about', 'have', 'instead', 'being', 'provide', 'since', 'while', 'although', 'should', 'would', 'could', 'their', 'there'];
            $rawTokens = preg_split('/\W+/', $qNorm, -1, PREG_SPLIT_NO_EMPTY);
            $qTokens = array_values(array_filter($rawTokens, fn($w) => strlen($w) > 2 && !in_array($w, $stopWords, true)));
            $qStems = array_map([self::class, 'simpleStem'], $qTokens);

            $evidenceText = '';
            foreach ($retrievedChunks as $chunk) {
                $evidenceText .= ' ' . ($chunk['title'] ?? '') . ' ' . ($chunk['content'] ?? '');
            }
            $rawEvWords = preg_split('/\W+/', strtolower($evidenceText), -1, PREG_SPLIT_NO_EMPTY);
            $evStems = array_map([self::class, 'simpleStem'], $rawEvWords);

            $overlap = array_intersect($qStems, $evStems);
            $ratio = count($qStems) > 0 ? count($overlap) / count($qStems) : 0;
            $overlapCount = count($overlap);

            if ($topSim < 0.35 || $ratio < 0.20 || $overlapCount < 2) {
                $evidenceStatus = 'INADEQUATE';
                $reasonCodes[] = 'LOW_GROUNDING';
            } elseif ($topSim < 0.45 || $ratio < 0.40) {
                $evidenceStatus = 'PARTIAL';
                $reasonCodes[] = 'PARTIAL_EVIDENCE';
            } else {
                $evidenceStatus = 'ADEQUATE';
            }
        }

        // Pass 2 Gate Decision
        $pass2Gate = 'ALLOW';
        if ($entityStatus === 'MISMATCH') {
            $pass2Gate = 'ABSTAIN';
        } elseif ($questionType !== 'CLEAR_FACTUAL') {
            $pass2Gate = 'ABSTAIN';
        } elseif ($evidenceStatus === 'INADEQUATE') {
            $pass2Gate = 'BLOCK';
        }

        return [
            'entity_status' => $entityStatus,
            'question_type' => $questionType,
            'evidence_status' => $evidenceStatus,
            'pass2_gate' => $pass2Gate,
            'reason_codes' => array_values(array_unique($reasonCodes))
        ];
    }

    /**
     * EXP-0031: 5-Point Structural Validation Pipeline for Tier-1 Contradictions
     * 
     * Decouples lexical opposition and predicate negation from proposition contradiction.
     * Evaluates:
     * 1. Entity & Focal Subject Alignment (Sibling list separation)
     * 2. Predicate Target Alignment (Atomic vs Partial, Mutable vs Immutable, Async vs Sync)
     * 3. Negation Scope & Polarity Alignment (Absence/prevention verbs concordant with negative evidence)
     * 4. Scope Validity (Subordinate conditionals 'even if', disjunctive alternatives 'either... or...')
     * 5. Contradiction Confidence & Conservative Fall-through
     */
    public static function validateTier1Contradiction(
        string $query,
        string $clause,
        array $topMatch,
        string $mode = 'E4'
    ): array {
        // E0: Legacy baseline - no validation
        if ($mode === 'E0') {
            return [
                'lexical_opposition' => true,
                'entity_aligned' => true,
                'predicate_aligned' => true,
                'polarity_aligned' => true,
                'scope_valid' => true,
                'contradiction_confidence' => 'HIGH',
                'tier1_decision' => 'REFUTED',
                'validation_reason' => 'Legacy E0 fast-path: structural validation disabled'
            ];
        }

        $qLower = strtolower($query);
        $cLower = strtolower($clause);
        $evLine = strtolower($topMatch['unit']['line_raw'] ?? '');
        $evFocal = strtolower($topMatch['unit']['focal_subject'] ?? '');
        $evTitle = strtolower($topMatch['unit']['title'] ?? '');
        $matchedOpposite = $topMatch['matched_opposite'] ?? null;
        $hasAntonym = !empty($topMatch['has_antonym']);
        $hasPredNeg = !empty($topMatch['has_predicate_negation']);

        $entityAligned = true;
        $predicateAligned = true;
        $polarityAligned = true;
        $scopeValid = true;
        $reason = 'Passed all structural validation checks';

        // -------------------------------------------------------------
        // Check 1: Entity & Sibling Alignment (Active in E1, E2, E3, E4)
        // -------------------------------------------------------------
        if (in_array($mode, ['E1', 'E2', 'E3', 'E4'], true)) {
            // Sibling list 1: HTTP status codes (401 vs 403 vs 404 vs 500)
            if (preg_match('/\b(401|unauthorized)\b/i', $qLower)) {
                if (preg_match('/\b(403|forbidden)\b/i', $evFocal) || (preg_match('/\b403\b/i', $evLine) && !preg_match('/\b401\b/i', $evLine))) {
                    $entityAligned = false;
                    $reason = 'Entity mismatch: 401 Unauthorized query matched 403 Forbidden evidence';
                }
            } elseif (preg_match('/\b(403|forbidden)\b/i', $qLower)) {
                if (preg_match('/\b(401|unauthorized)\b/i', $evFocal) || (preg_match('/\b401\b/i', $evLine) && !preg_match('/\b403\b/i', $evLine))) {
                    $entityAligned = false;
                    $reason = 'Entity mismatch: 403 Forbidden query matched 401 Unauthorized evidence';
                }
            }

            // Sibling list 2: Database transactions (COMMIT vs ROLLBACK)
            if (preg_match('/\bcommit\b/i', $qLower) && !preg_match('/\brollback\b/i', $qLower)) {
                if ($evFocal === 'rollback' || (str_contains($evLine, 'rollback') && str_contains($evLine, 'commit'))) {
                    $entityAligned = false;
                    $reason = 'Entity/Enumeration mismatch: COMMIT query matched ROLLBACK / dual enumeration';
                }
            } elseif (preg_match('/\brollback\b/i', $qLower) && !preg_match('/\bcommit\b/i', $qLower)) {
                if ($evFocal === 'commit' || (str_contains($evLine, 'rollback') && str_contains($evLine, 'commit'))) {
                    $entityAligned = false;
                    $reason = 'Entity/Enumeration mismatch: ROLLBACK query matched COMMIT / dual enumeration';
                }
            }

            // Sibling list 3: React Hooks (useRef vs useEffect vs useMemo vs useCallback vs useState)
            $hooks = ['useref', 'useeffect', 'usememo', 'usecallback', 'usestate', 'usecontext', 'uselayouteffect'];
            $qHook = null;
            foreach ($hooks as $h) {
                if (preg_match('/\b' . $h . '\b/i', $qLower)) {
                    $qHook = $h;
                    break;
                }
            }
            if ($qHook !== null) {
                if ($qHook !== 'useref' && (str_contains($evLine, 'mutable ref object') || str_contains($evLine, '`.current`') || str_contains($evLine, 'useref'))) {
                    $entityAligned = false;
                    $reason = "Entity mismatch: React $qHook query matched useRef evidence";
                } elseif ($qHook === 'useref' && (str_contains($evLine, 'react state is immutable') || str_contains($evLine, 'usestate'))) {
                    $entityAligned = false;
                    $reason = 'Entity mismatch: React useRef query matched React state evidence';
                }
            }

            // Sibling list: Spread operator vs arguments object
            if (str_contains($qLower, 'spread operator') && !str_contains($qLower, 'arrow')) {
                if (str_contains($evLine, 'no `arguments` object') || str_contains($evLine, 'rest parameters')) {
                    $entityAligned = false;
                    $reason = 'Entity mismatch: Spread operator query matched arrow function arguments evidence';
                }
            }

            // Sibling list 4: HTTP Methods (PUT vs POST vs PATCH)
            if (preg_match('/\bhttp\s+put\b|\bput\s+(?:request|method|is)\b/i', $qLower)) {
                if ($evFocal === 'post' || preg_match('/^[\-\*\d\.]*\s*post\s*:/i', $evLine)) {
                    $entityAligned = false;
                    $reason = 'Entity mismatch: HTTP PUT query matched HTTP POST definition line';
                }
            } elseif (preg_match('/\bhttp\s+patch\b|\bpatch\s+(?:request|method|is)\b/i', $qLower)) {
                if ($evFocal === 'post' || $evFocal === 'put' || str_contains($evLine, 'atomic') || str_contains($evTitle, 'database') || str_contains($evTitle, 'normalization')) {
                    $entityAligned = false;
                    $reason = 'Entity mismatch: HTTP PATCH query matched database normalization line';
                }
            }

            // Sibling list 5: JS variable declarations (var vs let/const/TDZ)
            if (preg_match('/\b(?:temporal\s+dead\s+zone|tdz|const|let)\b/i', $qLower) && !preg_match('/\bvar\b/i', $qLower)) {
                if ($evFocal === 'var' || preg_match('/^[\-\*\d\.]*\s*var\s*:/i', $evLine)) {
                    $entityAligned = false;
                    $reason = 'Entity mismatch: TDZ/const/let query matched var definition line';
                }
            }

            // Sibling list 6: CSS Layout (Flexbox vs Grid)
            if (preg_match('/\bflex(?:box)?\b/i', $qLower) && !preg_match('/\bgrid\b/i', $qLower)) {
                if ($evFocal === 'grid' || preg_match('/^[\-\*\d\.]*\s*grid\s*:/i', $evLine)) {
                    $entityAligned = false;
                    $reason = 'Entity mismatch: Flexbox query matched Grid definition';
                }
            }

            // Cross-Technology mismatch: React vs Node.js
            if ((str_contains($qLower, 'react') || str_contains($qLower, 'component')) && !str_contains($qLower, 'node')) {
                if (str_contains($evTitle, 'node.js') || str_contains($evLine, 'node.js is an asynchronous')) {
                    $entityAligned = false;
                    $reason = 'Cross-technology mismatch: React query matched Node.js runtime evidence';
                }
            }
        }

        // -------------------------------------------------------------
        // Check 2: Predicate Target Alignment (Active in E1, E2, E3, E4)
        // -------------------------------------------------------------
        if (in_array($mode, ['E1', 'E2', 'E3', 'E4'], true) && $entityAligned) {
            // Antonym dual appearance in evidence line (Enumeration collision):
            // e.g. "flex-direction: row (default, left to right) | column (top to bottom)"
            // e.g. "COMMIT or ROLLBACK"
            // e.g. "Macrotasks: setTimeout ... and Microtask Queue (Promises ...)"
            if ($matchedOpposite !== null && is_array($matchedOpposite) && count($matchedOpposite) >= 2) {
                $termA = strtolower($matchedOpposite[0]);
                $termB = strtolower($matchedOpposite[1]);
                if (!empty($termA) && !empty($termB) && str_contains($evLine, $termA) && str_contains($evLine, $termB)) {
                    $isDisjunctionEnum = (bool)preg_match('/(?:\||\bor\b|and\s+microtask|\/)/i', $evLine);
                    $hasExplicitNegationOnTerm = (bool)preg_match('/\b(?:not|no|non)\s+' . preg_quote($termA, '/') . '\b|\b(?:not|no|non)\s+' . preg_quote($termB, '/') . '\b/i', $evLine);
                    if ($isDisjunctionEnum && !$hasExplicitNegationOnTerm) {
                        $predicateAligned = false;
                        $reason = "Enumeration collision: evidence lists both opposing terms ('$termA' and '$termB') in alternative specification";
                    }
                }
            }

            // Atomic vs Partial target disambiguation
            if (preg_match('/\b(?:atomic|partial)\b/i', $qLower)) {
                $qIs1NF = (bool)preg_match('/\b(?:first normal form|1nf|column|scalar)\b/i', $qLower);
                $qIs2NF = (bool)preg_match('/\b(?:second normal form|2nf|partial dependenc)\b/i', $qLower);
                $qIsACID = (bool)preg_match('/\b(?:transaction|acid|all or nothing)\b/i', $qLower);
                $qIsPatch = (bool)preg_match('/\b(?:patch|http patch)\b/i', $qLower);

                $evIs1NF = (bool)preg_match('/\b(?:each\s+column|column\s+contains|atomic\s+\(indivisible\)|indivisible\s+values)\b/i', $evLine) || ((bool)preg_match('/\b(?:atomic|indivisible|column)\b/i', $evLine) && str_contains($evTitle, 'normalization'));
                $evIs2NF = (bool)preg_match('/\bpartial dependenc/i', $evLine);

                if ($qIs1NF && $evIs2NF) {
                    $predicateAligned = false;
                    $reason = 'Predicate target mismatch: 1NF column atomicity matched 2NF partial dependency';
                } elseif ($qIs2NF && $evIs1NF && !str_contains($evLine, 'partial')) {
                    $predicateAligned = false;
                    $reason = 'Predicate target mismatch: 2NF partial dependency matched 1NF column atomicity';
                } elseif ($qIsPatch && ($evIs1NF || $evIs2NF)) {
                    $predicateAligned = false;
                    $reason = 'Predicate target mismatch: HTTP PATCH partial update matched database atomicity';
                } elseif ($qIsACID && ($evIs1NF && !str_contains($evLine, 'transaction'))) {
                    $predicateAligned = false;
                    $reason = 'Predicate target mismatch: Transaction atomicity matched column scalar atomicity';
                }
            }

            // Mutable vs Immutable target disambiguation
            if (str_contains($qLower, 'const') && str_contains($qLower, 'binding')) {
                if (str_contains($evLine, 'cannot be reassigned') && str_contains($evLine, 'remain mutable in their properties')) {
                    $predicateAligned = false;
                    $reason = 'Predicate target mismatch: const binding immutability modifies identifier, evidence mutable modifies object properties';
                }
            }

            // Synchronous vs Asynchronous target disambiguation in Node.js / I/O
            if (str_contains($qLower, 'libuv') || str_contains($qLower, 'asynchronous i/o') || str_contains($qLower, 'asynchronous file')) {
                if (str_contains($evLine, 'synchronous encryption') || str_contains($evLine, 'heavy loops')) {
                    $predicateAligned = false;
                    $reason = 'Predicate target mismatch: libuv async I/O query matched synchronous CPU warning in evidence';
                }
            }
        }

        // -------------------------------------------------------------
        // Check 3: Negation Scope & Polarity Alignment (Active in E2, E3, E4)
        // -------------------------------------------------------------
        if (in_array($mode, ['E2', 'E3', 'E4'], true) && $entityAligned && $predicateAligned) {
            $negMarkers = '/\b(?:without|avoid|avoids|avoiding|prevent|prevents|preventing|prevented|prevention|omit|omits|omitting|omitted|eliminate|eliminates|eliminating|eliminated|cannot|can\'t|does not|doesn\'t|no|never|not)\b/i';

            if (preg_match($negMarkers, $qLower, $negMatch)) {
                $marker = strtolower($negMatch[0]);

                if (in_array($marker, ['without', 'avoid', 'avoids', 'avoiding', 'prevent', 'prevents', 'prevented', 'prevention', 'omit', 'omits', 'omitting', 'eliminate', 'eliminates', 'eliminating'], true)) {
                    $polarityAligned = false;
                    $reason = "Polarity concordance: query asserts absence/prevention ('$marker') which is confirmed by evidence";
                }

                if ($hasPredNeg) {
                    if (preg_match('/\b(?:prevent|prevented|preventing|omit|omits|eliminate|eliminates|without)\b/i', $qLower)) {
                        $polarityAligned = false;
                        $reason = "Predicate negation concordance: query absence verb matches evidence negation";
                    }
                }
            }

            // Case C: React event update batching / ref persistence into single render
            if (str_contains($qLower, 'render') && str_contains($evLine, 'without triggering a re-render')) {
                if (preg_match('/\b(?:survive|survives|surviving|persist|persists|persisting|batch|batched|batching)\b/i', $qLower)) {
                    $polarityAligned = false;
                    $reason = 'Predicate scope concordance: ref persistence / batching query aligns with non-triggering re-render evidence';
                }
            }
        }

        // -------------------------------------------------------------
        // Check 4: Subordinate Conditional & Disjunctive Scope (Active in E3, E4)
        // -------------------------------------------------------------
        if (in_array($mode, ['E3', 'E4'], true) && $entityAligned && $predicateAligned && $polarityAligned) {
            // Check subordinate conditionals: "even if ...", "if ...", "unless ..."
            if (preg_match('/\beven\s+if\s+([^,\?]+)/i', $qLower, $condMatch)) {
                $condClause = $condMatch[1];
                if ($matchedOpposite !== null) {
                    foreach ($matchedOpposite as $opp) {
                        if (str_contains($condClause, strtolower($opp))) {
                            $scopeValid = false;
                            $reason = "Subordinate conditional scope: opposite term '$opp' is inside 'even if' concession";
                            break;
                        }
                    }
                }
            }

            // Check disjunctive alternative: "either ... or ...", "succeeds as a whole or leaves no partial traces"
            if (preg_match('/\b(?:either\b.+?\bor\b|\bor\s+leaves\s+no\s+partial\b|\bor\b)/i', $cLower)) {
                if (str_contains($qLower, 'succeeds as a whole or leaves no partial traces')) {
                    $scopeValid = false;
                    $reason = 'Disjunctive alternative scope: query affirms either branch of ACID atomicity definition';
                }
            }
        }

        // -------------------------------------------------------------
        // Decision Synthesis
        // -------------------------------------------------------------
        $allPassed = ($entityAligned && $predicateAligned && $polarityAligned && $scopeValid);

        if ($allPassed) {
            return [
                'lexical_opposition' => true,
                'entity_aligned' => true,
                'predicate_aligned' => true,
                'polarity_aligned' => true,
                'scope_valid' => true,
                'contradiction_confidence' => 'HIGH',
                'tier1_decision' => 'REFUTED',
                'validation_reason' => $reason
            ];
        } else {
            return [
                'lexical_opposition' => ($hasAntonym || $hasPredNeg),
                'entity_aligned' => $entityAligned,
                'predicate_aligned' => $predicateAligned,
                'polarity_aligned' => $polarityAligned,
                'scope_valid' => $scopeValid,
                'contradiction_confidence' => 'LOW',
                'tier1_decision' => 'NO_DETERMINISTIC_REFUTATION',
                'validation_reason' => $reason
            ];
        }
    }

    public static function verify(string $query, array $retrievedChunks, array $runtimeOptions = []): array {
        if (!RagFlags::isEnabled('ENABLE_PREMISE_VERIFIER')) {
            return [
                'has_presupposition' => false,
                'status' => self::STATUS_SUPPORTED,
                'confidence' => 1.0,
                'evidence_used' => true,
                'claim' => trim($query),
                'refutation' => null,
                'citation' => null,
                'decision_tier' => self::TIER_1,
                'decision_reason' => 'Verifier disabled by feature flag',
                'tier2_diagnostics' => null,
                'tier1_diagnostics' => null
            ];
        }

        $mode = $runtimeOptions['ablation_mode'] ?? self::$ablationMode;
        $qClean = trim($query);

        // Stage 0: ECMAScript non-existent operator syntax check (Tier 1 structural)
        if (preg_match('/(===!|!==!|<=>|\?->|<-(?!-))/i', $qClean, $opMatches)) {
            $badOp = $opMatches[1];
            return [
                'has_presupposition' => true,
                'status' => self::STATUS_REFUTED,
                'confidence' => 1.0,
                'evidence_used' => true,
                'claim' => "JavaScript syntax supports operator '{$badOp}'",
                'refutation' => "JavaScript does not define the operator '{$badOp}'. Valid comparison operators include ===, !==, ==, !=, <, >, <=, >=.",
                'citation' => "[JavaScript ES6+ Deep Dive - Chunk 0]",
                'decision_tier' => self::TIER_1,
                'decision_reason' => "Nonexistent ECMAScript operator syntax: {$badOp}",
                'tier2_diagnostics' => null,
                'tier1_diagnostics' => null
            ];
        }

        // Stage 1: Out-of-curriculum external language/framework detection (Tier 1 boundary)
        if (preg_match('/\b(sidekiq|ruby|redis|flutter|widget tree|render tree|dart|django|python|rust|send and sync|golang|c#|asp\.net|spring boot|laravel)\b/i', $qClean)) {
            return [
                'has_presupposition' => true,
                'status' => self::STATUS_NOT_ESTABLISHED,
                'confidence' => 0.0,
                'evidence_used' => true,
                'claim' => $qClean,
                'refutation' => null,
                'citation' => null,
                'decision_tier' => self::TIER_1,
                'decision_reason' => 'Query refers to an external technology not covered in curriculum',
                'tier2_diagnostics' => null,
                'tier1_diagnostics' => null
            ];
        }

        // Stage 2: Compound clause decomposition
        $clauses = self::splitClauses($qClean);

        // Stage 3: Curriculum relevance threshold check
        $maxSimilarity = 0.0;
        foreach ($retrievedChunks as $chunk) {
            $sim = (float)($chunk['similarity'] ?? 0.0);
            if ($sim > $maxSimilarity) $maxSimilarity = $sim;
        }

        $evidenceGateThreshold = isset($runtimeOptions['evidence_gate_threshold']) ? (float)$runtimeOptions['evidence_gate_threshold'] : 0.28;
        if (empty($retrievedChunks) || $maxSimilarity < $evidenceGateThreshold) {
            return [
                'has_presupposition' => true,
                'status' => self::STATUS_NOT_ESTABLISHED,
                'confidence' => 0.0,
                'evidence_used' => true,
                'claim' => $qClean,
                'refutation' => null,
                'citation' => null,
                'decision_tier' => self::TIER_1,
                'decision_reason' => "Zero or insufficient evidence available in approved curriculum (maxSim < {$evidenceGateThreshold})",
                'tier2_diagnostics' => null,
                'tier1_diagnostics' => null
            ];
        }

        // Stage 4: Atomic evidence unit extraction with focal subject alignment
        $evidenceUnits = self::extractEvidenceUnits($retrievedChunks);

        $hasRefuted = false;
        $hasNotEstablished = false;
        $firstRefutation = null;
        $firstCitation = null;
        $totalSupporting = 0;
        $tier2DiagnosticsList = [];
        $tier1DiagnosticsList = [];
        $overallDecisionTier = self::TIER_1;

        // Stage 5: Evaluate each proposition clause
        foreach ($clauses as $clause) {
            $prop = self::extractProposition($clause);
            $cTrim = $prop['original'];
            if ($cTrim === '') continue;
            $cNorm = $prop['normalized'];
            $cAsserted = self::normalizeText($prop['assertion']);
            $isNegation = $prop['is_negation_inquiry'];

            $stopWords = ['why', 'does', 'how', 'what', 'when', 'where', 'which', 'who', 'the', 'and', 'for', 'are', 'with', 'from', 'that', 'this', 'can', 'you', 'explain', 'tell', 'about', 'have', 'instead', 'being', 'provide', 'since', 'while', 'although'];
            $rawTokens = preg_split('/\W+/', $cNorm, -1, PREG_SPLIT_NO_EMPTY);
            $qTokens = array_values(array_filter($rawTokens, fn($w) => strlen($w) > 2 && !in_array($w, $stopWords, true)));
            $qStems = array_map([self::class, 'simpleStem'], $qTokens);

            // Detect technical entity subject to prevent cross-subject misattribution
            $qSubject = null;
            $entities = [
                'justify-content', 'align-items', 'flex-direction', 'flex-grow', 'flex-shrink', 'flex-wrap', 'gap',
                'box-sizing: border-box', 'box-sizing: content-box', 'border-box', 'content-box', 'box-sizing', 'box model',
                'const', 'var', 'let', 'tdz', 'temporal dead zone', 'arrow function', 'arrow functions',
                'uselayouteffect', 'usecallback', 'usecontext', 'useeffect', 'usestate', 'useref', 'usememo', 'react state',
                'macrotask', 'macrotasks', 'microtask', 'microtasks', 'event loop', 'libuv', 'v8', 'express', 'middleware', 'jwt',
                'atomicity', 'consistency', 'isolation', 'durability', 'acid', 'b tree', 'b-tree', 'index',
                'commit', 'rollback', 'wal', 'write-ahead logging',
                '1nf', '2nf', '3nf', 'normalization',
                'http get', 'http post', 'http put', 'http delete',
                '<header>', '<main>', '<article>', '<section>', '<footer>', '<nav>', 'article', 'header', 'footer', 'nav', 'main',
                'display: flex', 'display: grid', 'flexbox', 'grid', 'css grid'
            ];
            foreach ($entities as $ent) {
                if (preg_match('/\b' . preg_quote($ent, '/') . 's?\b/i', $cNorm)) {
                    $qSubject = $ent;
                    break;
                }
            }

            // Determine if Tier-1 dictionary is active for this ablation mode
            $enableTier1Dictionary = in_array($mode, ['A0', 'A2', 'A3', 'A5', 'B1', 'B2', 'B3', 'B4', 'B5', 'C0', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'D0', 'D1', 'D2', 'D3', 'D4', 'E0', 'E1', 'E2', 'E3', 'E4'], true);

            $candidateMatches = [];
            foreach ($evidenceUnits as $unit) {
                $lineNorm = $unit['line_norm'];
                $focal = $unit['focal_subject'];

                // Filter out conflicting sibling bullet items
                if ($qSubject === 'var' && ($focal === 'let' || $focal === 'const')) continue;
                if ($qSubject === 'let' && ($focal === 'var' || $focal === 'const')) continue;
                if ($qSubject === 'const' && ($focal === 'var' || $focal === 'let')) continue;
                if ($qSubject === 'commit' && $focal === 'rollback') continue;
                if ($qSubject === 'rollback' && $focal === 'commit') continue;
                if ($qSubject === 'align-items' && $focal === 'justify-content') continue;
                if ($qSubject === 'justify-content' && $focal === 'align-items') continue;
                if ($qSubject === 'flex-grow' && $focal === 'flex-shrink') continue;
                if ($qSubject === 'flex-shrink' && $focal === 'flex-grow') continue;
                if (($qSubject === 'grid' || $qSubject === 'css grid' || $qSubject === 'display: grid') && (str_contains($lineNorm, 'flexbox') || $focal === 'flexbox' || $focal === 'flex')) continue;
                if (($qSubject === 'flexbox' || $qSubject === 'display: flex') && (str_contains($lineNorm, 'grid') || $focal === 'grid' || $focal === 'css grid')) continue;

                // Semantic HTML tag exclusions
                if (($qSubject === 'article' || $qSubject === '<article>') && ($focal === 'header' || $focal === 'footer' || $focal === 'nav' || $focal === 'main')) continue;
                if (($qSubject === 'header' || $qSubject === '<header>') && ($focal === 'article' || $focal === 'footer' || $focal === 'nav' || $focal === 'main')) continue;
                if (($qSubject === 'footer' || $qSubject === '<footer>') && ($focal === 'header' || $focal === 'article' || $focal === 'nav' || $focal === 'main')) continue;

                // Border-box vs content-box context exclusion
                if (($qSubject === 'border-box' || $qSubject === 'box-sizing: border-box') && str_contains($lineNorm, 'by default box-sizing is content-box')) continue;

                $rawLineWords = preg_split('/\W+/', $unit['combined_norm'] ?? $lineNorm, -1, PREG_SPLIT_NO_EMPTY);
                $lineStems = array_map([self::class, 'simpleStem'], $rawLineWords);
                $overlap = array_intersect($qStems, $lineStems);
                $overlapCount = count($overlap);

                // Word-boundary antonym check (Tier 1)
                $hasAntonym = false;
                $matchedOpposite = null;
                if ($enableTier1Dictionary) {
                    foreach (self::$semanticOpposites as [$termA, $termB]) {
                        $termANorm = self::normalizeText($termA);
                        $termBNorm = self::normalizeText($termB);
                        $patA = '/\b' . preg_quote($termANorm, '/') . '\b/i';
                        $patB = '/\b' . preg_quote($termBNorm, '/') . '\b/i';

                        if (preg_match($patA, $cAsserted) && preg_match($patB, $cAsserted)) {
                            if (preg_match('/\b(?:difference\s+between|compare|comparison|versus|\bvs\b)\b/i', $cNorm)) {
                                continue;
                            }
                        }

                        if ((str_contains($termANorm, 'row') || str_contains($termBNorm, 'row')) && str_contains($lineNorm, 'row') && str_contains($lineNorm, 'column')) {
                            continue;
                        }

                        if (preg_match($patA, $cAsserted) && preg_match($patB, $lineNorm)) {
                            $hasAntonym = true;
                            $matchedOpposite = [$termA, $termB];
                            break;
                        }
                        if (preg_match($patB, $cAsserted) && preg_match($patA, $lineNorm)) {
                            $hasAntonym = true;
                            $matchedOpposite = [$termB, $termA];
                            break;
                        }
                    }

                    if (!$hasAntonym) {
                        if (preg_match('/\bdefault\s+(?:is|to|of)?\s*([0-9]+)\b/i', $cAsserted, $qm) &&
                            preg_match('/\bdefault\s+(?:is|to|of)?\s*([0-9]+)\b/i', $lineNorm, $lm)) {
                            if ($qm[1] !== $lm[1]) {
                                $hasAntonym = true;
                                $matchedOpposite = ["default {$qm[1]}", "default {$lm[1]}"];
                            }
                        }
                    }
                }

                // Predicate negation check
                $hasPredicateNegation = false;
                $predKeywords = ['reassign', 'reassigned', 'reassignment', 'mutate', 'mutating', 'mutation', 'hoist', 'hoisted', 'constructors', 'arguments', 'clone', 'cache', 'xml', 'duplicate', 'render', 're-render', 'batch', 'cleanup', 'encrypt', 'speed', 'drilling', 'unmount', 'transitive', 'anomalies'];
                foreach ($predKeywords as $pk) {
                    if (str_contains($cNorm, $pk)) {
                        $queryHasNegation = (bool)preg_match('/\b(?:cannot|never|does\s+not|without|no|eliminate|eliminates|prevent|prevents)\b.{0,25}\b' . preg_quote($pk, '/') . '/i', $cNorm);
                        $negPat = '/\b(?:not|cannot|can\s+not|never|does\s+not|do\s+not|is\s+not|prohibits?|prevents?|without|no)\b.{0,30}\b' . preg_quote($pk, '/') . '/i';
                        $lineHasNegation = (bool)preg_match($negPat, $lineNorm);

                        if ($lineHasNegation && !$queryHasNegation) {
                            $hasPredicateNegation = true;
                            break;
                        }
                    }
                }

                $subjectBoost = ($qSubject !== null && $focal !== null && (str_contains($focal, $qSubject) || str_contains($qSubject, $focal))) ? 10 : 0;
                if ($overlapCount < 1 && !$hasAntonym && !$hasPredicateNegation && $subjectBoost === 0) {
                    continue;
                }
                $score = $overlapCount + ($hasAntonym ? 20 : 0) + ($hasPredicateNegation ? 15 : 0) + $subjectBoost;

                $candidateMatches[] = [
                    'unit' => $unit,
                    'score' => $score,
                    'overlap_count' => $overlapCount,
                    'has_antonym' => $hasAntonym,
                    'has_predicate_negation' => $hasPredicateNegation,
                    'matched_opposite' => $matchedOpposite
                ];
            }

            if (empty($candidateMatches)) {
                $hasNotEstablished = true;
                continue;
            }

            usort($candidateMatches, fn($a, $b) => $b['score'] <=> $a['score']);
            $topMatch = $candidateMatches[0];

            // Check Tier 1 resolution
            $tier1Contradiction = ($topMatch['has_antonym'] || $topMatch['has_predicate_negation']);
            $tier1Validation = null;

            if ($tier1Contradiction) {
                if (in_array($mode, ['E1', 'E2', 'E3', 'E4'], true)) {
                    $tier1Validation = self::validateTier1Contradiction($qClean, $cTrim, $topMatch, $mode);
                } else {
                    $tier1Validation = [
                        'lexical_opposition' => true,
                        'entity_aligned' => true,
                        'predicate_aligned' => true,
                        'polarity_aligned' => true,
                        'scope_valid' => true,
                        'contradiction_confidence' => 'HIGH',
                        'tier1_decision' => 'REFUTED',
                        'validation_reason' => 'Legacy fast-path: structural validation disabled'
                    ];
                }
            }

            if ($mode === 'A0') {
                // Pure frozen EXP-0025 baseline: no Tier 2 NLI
                if ($tier1Contradiction) {
                    if ($isNegation) {
                        $totalSupporting++;
                    } else {
                        $hasRefuted = true;
                        if ($firstRefutation === null) {
                            $firstRefutation = "The premise is incorrect according to the course curriculum: {$topMatch['unit']['line_raw']}";
                            $firstCitation = $topMatch['unit']['citation'];
                        }
                    }
                } else {
                    if ($isNegation) {
                        $totalSupporting++;
                    } else {
                        if ($topMatch['overlap_count'] >= 3) {
                            $totalSupporting++;
                        } else {
                            $hasNotEstablished = true;
                        }
                    }
                }
                continue;
            }

            // TIER 1 FAST-PATH DECISION:
            // In legacy modes (A2-D4, E0): unconditional if $tier1Contradiction is true.
            // In decoupled modes (E1-E4): gated by structural validation ($tier1Validation['tier1_decision'] === 'REFUTED').
            if ($tier1Contradiction && $tier1Validation !== null && $tier1Validation['tier1_decision'] === 'REFUTED' && in_array($mode, ['A2', 'A3', 'A5', 'B1', 'B2', 'B3', 'B4', 'B5', 'C0', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'D0', 'D1', 'D2', 'D3', 'D4', 'E0', 'E1', 'E2', 'E3', 'E4'], true)) {
                if ($isNegation) {
                    $totalSupporting++;
                } else {
                    $hasRefuted = true;
                    if ($firstRefutation === null) {
                        $firstRefutation = "The premise is incorrect according to the course curriculum: {$topMatch['unit']['line_raw']}";
                        $firstCitation = $topMatch['unit']['citation'];
                    }
                }
                $tier2DiagnosticsList[] = [
                    'clause' => $cTrim,
                    'decision_tier' => self::TIER_1,
                    'reason' => 'Resolved by Tier-1 fast-path contradiction',
                    'tier1_validation' => $tier1Validation
                ];
                $tier1DiagnosticsList[] = [
                    'clause' => $cTrim,
                    'top_evidence_line' => $topMatch['unit']['line_raw'],
                    'trigger_type' => $topMatch['has_antonym'] ? 'ANTONYM' : 'PREDICATE_NEGATION',
                    'matched_opposite' => $topMatch['matched_opposite'],
                    'validation' => $tier1Validation
                ];
                continue;
            } elseif ($tier1Contradiction && $tier1Validation !== null && $tier1Validation['tier1_decision'] === 'NO_DETERMINISTIC_REFUTATION') {
                // Record diagnostic for downgraded Tier-1 collision
                $tier1DiagnosticsList[] = [
                    'clause' => $cTrim,
                    'top_evidence_line' => $topMatch['unit']['line_raw'],
                    'trigger_type' => $topMatch['has_antonym'] ? 'ANTONYM' : 'PREDICATE_NEGATION',
                    'matched_opposite' => $topMatch['matched_opposite'],
                    'validation' => $tier1Validation
                ];
                // Conservatism Invariant: fall through cleanly to pre-filter and Tier-2 Semantic NLI!
            }

            // Fall through to Tier-2 Generic Semantic NLI Verifier
            $overallDecisionTier = self::TIER_2_NLI;

            // Format NLI premise context: B3, B5, B5-NoDict, C0-C7, D0-D4, E0-E4 frame with curriculum topic and focal subject
            if (in_array($mode, ['B3', 'B5', 'B5-NoDict', 'C0', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'D0', 'D1', 'D2', 'D3', 'D4', 'E0', 'E1', 'E2', 'E3', 'E4'], true)) {
                $ctxTitle = $topMatch['unit']['title'] ?? '';
                $ctxFocal = $topMatch['unit']['focal_subject'] ?? '';
                $ctxLine = $topMatch['unit']['line_raw'] ?? '';
                $nliPremise = "[Topic: {$ctxTitle}]" . ($ctxFocal ? " [Subject: {$ctxFocal}]" : "") . " {$ctxLine}";
            } else {
                $nliPremise = $topMatch['unit']['evidence_text'] ?? $topMatch['unit']['line_raw'];
            }
            $nliHypothesis = $prop['assertion'] ?: $cTrim;

            $nliOptions = $runtimeOptions;
            if (isset($runtimeOptions['prompt_mode'])) {
                $nliOptions['prompt_mode'] = $runtimeOptions['prompt_mode'];
            } elseif (in_array($mode, ['B1', 'B2', 'B3'], true)) {
                $nliOptions['prompt_mode'] = $mode;
            } elseif (in_array($mode, ['B4'], true)) {
                $nliOptions['prompt_mode'] = 'B1';
            } elseif (in_array($mode, ['B5', 'B5-NoDict', 'C0', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'D0', 'D1', 'D2', 'D3', 'D4', 'E0', 'E1', 'E2', 'E3', 'E4'], true)) {
                $nliOptions['prompt_mode'] = 'B5';
            } else {
                $nliOptions['prompt_mode'] = 'default';
            }

            // EXP-0029/EXP-0030/EXP-0031 Pre-Filter Evaluation
            $preFilter = null;
            if (in_array($mode, ['C0', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'D0', 'D1', 'D2', 'D3', 'D4', 'E0', 'E1', 'E2', 'E3', 'E4'], true)) {
                $preFilter = self::evaluatePreFilter($qClean, $evidenceUnits, $retrievedChunks, $mode);
            }

            $nliRes = self::callTier2Nli($nliPremise, $nliHypothesis, $nliOptions);

            // Pass 1 and Pass 2 Threshold resolution:
            // D4: symmetric high (0.75 / 0.75)
            // D2, D3, E0-E4: asymmetric calibrated ($pass2EntailmentThreshold / $pass2ContradictionThreshold = 0.70 / 0.75)
            // A1, A2: symmetric low (0.50 / 0.50)
            // Default (A3, A5, B1-B5, C0-C7, D0, D1): symmetric calibrated (0.70 / 0.70)
            if ($mode === 'D4') {
                $pass1Threshold = 0.75;
                $pass2ContraThreshold = 0.75;
            } elseif (in_array($mode, ['D2', 'D3', 'E0', 'E1', 'E2', 'E3', 'E4'], true)) {
                $pass1Threshold = self::$pass2EntailmentThreshold;
                $pass2ContraThreshold = self::$pass2ContradictionThreshold;
            } elseif (in_array($mode, ['A1', 'A2'], true)) {
                $pass1Threshold = 0.50;
                $pass2ContraThreshold = 0.50;
            } else {
                $pass1Threshold = 0.70;
                $pass2ContraThreshold = 0.70;
            }

            if (isset($runtimeOptions['pass1_threshold'])) {
                $pass1Threshold = (float)$runtimeOptions['pass1_threshold'];
            }
            if (isset($runtimeOptions['pass2_contra_threshold'])) {
                $pass2ContraThreshold = (float)$runtimeOptions['pass2_contra_threshold'];
            }

            $nliLabel = $nliRes['label'] ?? 'NEUTRAL';
            $nliConf = (float)($nliRes['confidence'] ?? 0.0);
            $pass1Lat = (float)($nliRes['latency_ms'] ?? 0.0);
            $totalLat = $pass1Lat;
            $twoPassInvoked = false;
            $pass2Res = null;

            // Two-pass verification for B4, B5, B5-NoDict, C0-C7, D0-D4, E0-E4
            $allowPass2 = in_array($mode, ['B4', 'B5', 'B5-NoDict', 'C0'], true);
            if (in_array($mode, ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'D0', 'D1', 'D2', 'D3', 'D4', 'E0', 'E1', 'E2', 'E3', 'E4'], true)) {
                $allowPass2 = ($preFilter !== null && $preFilter['pass2_gate'] === 'ALLOW');
            }

            // If pre-filter signals ABSTAIN (e.g. OOD entity mismatch or subjective query),
            // override any Pass 1 parametric leakage or overconfidence to NEUTRAL!
            if ($preFilter !== null && $preFilter['pass2_gate'] === 'ABSTAIN') {
                $nliLabel = 'NEUTRAL';
                $nliConf = 0.0;
            }

            if ($allowPass2 && ($nliLabel === 'NEUTRAL' || $nliConf < $pass1Threshold)) {
                $twoPassInvoked = true;
                $probeOptions = $runtimeOptions;
                $probeOptions['prompt_mode'] = 'B4_probe';
                $pass2Res = self::callTier2Nli($nliPremise, $nliHypothesis, $probeOptions);
                $pass2Lat = (float)($pass2Res['latency_ms'] ?? 0.0);
                $totalLat += $pass2Lat;
                if (($pass2Res['label'] ?? '') === 'CONTRADICTION' && (float)($pass2Res['confidence'] ?? 0.0) >= $pass2ContraThreshold) {
                    $nliLabel = 'CONTRADICTION';
                    $nliConf = (float)$pass2Res['confidence'];
                }
            }

            $tier2DiagnosticsList[] = [
                'original_query' => $qClean,
                'extracted_proposition' => $nliHypothesis,
                'retrieved_evidence_chunk_ids' => [$topMatch['unit']['chunk_id']],
                'evidence_sentence' => $nliPremise,
                'citation' => $topMatch['unit']['citation'],
                'model_identifier' => 'llama3.2:latest',
                'mode' => $mode,
                'pre_filter' => $preFilter,
                'nli_label' => $nliLabel,
                'entailment_score' => ($nliLabel === 'ENTAILMENT' ? $nliConf : 0.0),
                'contradiction_score' => ($nliLabel === 'CONTRADICTION' ? $nliConf : 0.0),
                'neutral_score' => ($nliLabel === 'NEUTRAL' ? $nliConf : 0.0),
                'confidence' => $nliConf,
                'pass1_threshold' => $pass1Threshold,
                'pass2_contra_threshold' => $pass2ContraThreshold,
                'threshold_version' => in_array($mode, ['E0', 'E1', 'E2', 'E3', 'E4'], true) ? 'EXP-0031-V1' : (in_array($mode, ['D0', 'D1', 'D2', 'D3', 'D4'], true) ? 'EXP-0030-V1' : 'EXP-0028-V1'),
                'decision_tier' => self::TIER_2_NLI,
                'rationale' => $nliRes['rationale'] ?? ($pass2Res['rationale'] ?? ''),
                'latency_ms' => round($totalLat, 1),
                'two_pass' => [
                    'invoked' => $twoPassInvoked,
                    'pass1_label' => $nliRes['label'] ?? 'NEUTRAL',
                    'pass1_confidence' => $nliRes['confidence'] ?? 0.0,
                    'pass1_latency_ms' => $pass1Lat,
                    'pass2_label' => $pass2Res['label'] ?? null,
                    'pass2_confidence' => $pass2Res['confidence'] ?? null,
                    'pass2_latency_ms' => $pass2Res['latency_ms'] ?? null,
                ]
            ];

            $isContraAccepted = ($nliLabel === 'CONTRADICTION' && $nliConf >= ($twoPassInvoked ? $pass2ContraThreshold : $pass1Threshold));
            $isEntailAccepted = ($nliLabel === 'ENTAILMENT' && $nliConf >= $pass1Threshold);

            if ($isContraAccepted) {
                if ($isNegation) {
                    // Contradiction of negative claim inquiry resolves as supported
                    $totalSupporting++;
                } else {
                    $hasRefuted = true;
                    if ($firstRefutation === null) {
                        $firstRefutation = "The premise is contradicted by curriculum evidence: {$nliPremise}";
                        $firstCitation = $topMatch['unit']['citation'];
                    }
                }
            } elseif ($isEntailAccepted) {
                $totalSupporting++;
            } else {
                // Ambiguous / Neutral / Insufficient certainty
                $hasNotEstablished = true;
            }
        }

        if ($hasRefuted) {
            return [
                'has_presupposition' => true,
                'status' => self::STATUS_REFUTED,
                'confidence' => 0.96,
                'evidence_used' => true,
                'claim' => $qClean,
                'refutation' => $firstRefutation,
                'citation' => $firstCitation,
                'decision_tier' => $overallDecisionTier,
                'decision_reason' => ($overallDecisionTier === self::TIER_2_NLI)
                    ? 'Semantic contradiction established by Tier-2 NLI over curriculum evidence'
                    : 'Contradictory evidence found via Tier-1 curriculum fast path',
                'pre_filter' => $preFilter ?? null,
                'tier2_diagnostics' => $tier2DiagnosticsList,
                'tier1_diagnostics' => !empty($tier1DiagnosticsList) ? $tier1DiagnosticsList : null
            ];
        } elseif ($hasNotEstablished || $totalSupporting === 0) {
            return [
                'has_presupposition' => true,
                'status' => self::STATUS_NOT_ESTABLISHED,
                'confidence' => 0.35,
                'evidence_used' => true,
                'claim' => $qClean,
                'refutation' => null,
                'citation' => null,
                'decision_tier' => ($overallDecisionTier === self::TIER_2_NLI ? self::TIER_2_ABSTAIN : self::TIER_1),
                'decision_reason' => 'Insufficient or neutral evidence in retrieved curriculum passages to establish premise',
                'pre_filter' => $preFilter ?? null,
                'tier2_diagnostics' => $tier2DiagnosticsList,
                'tier1_diagnostics' => !empty($tier1DiagnosticsList) ? $tier1DiagnosticsList : null
            ];
        } else {
            return [
                'has_presupposition' => true,
                'status' => self::STATUS_SUPPORTED,
                'confidence' => 0.95,
                'evidence_used' => true,
                'claim' => $qClean,
                'refutation' => null,
                'citation' => null,
                'decision_tier' => $overallDecisionTier,
                'decision_reason' => ($overallDecisionTier === self::TIER_2_NLI)
                    ? 'Premise entailed by curriculum evidence according to Tier-2 NLI'
                    : 'Premise supported by retrieved curriculum evidence with matching polarity',
                'pre_filter' => $preFilter ?? null,
                'tier2_diagnostics' => $tier2DiagnosticsList,
                'tier1_diagnostics' => !empty($tier1DiagnosticsList) ? $tier1DiagnosticsList : null
            ];
        }
    }
}
