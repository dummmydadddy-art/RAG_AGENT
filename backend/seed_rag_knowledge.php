<?php
// EduConnect LMS - Seed RAG Knowledge Base
// Ingests authentic, structured course notes for the 5 curriculum modules into the vector store.

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/rag_service.php';

echo "=== EduConnect LMS RAG Knowledge Base Seeder ===\n";

// Fetch existing materials from Supabase to associate chunks correctly
$materialsRes = supabaseSelect('materials', 'id, title, course_id, batch_id');
$materials = $materialsRes['data'] ?? [];
$materialsByTitle = [];
foreach ($materials as $m) {
    $materialsByTitle[$m['title']] = $m;
}

$curriculum = [
    [
        'title' => 'HTML & CSS Fundamentals',
        'course_name' => 'Full Stack Web Development',
        'default_mat_id' => 'ea1f3b17-0657-4ee2-b155-c56b775dd25e',
        'content' => <<<EOT
HTML5 SEMANTIC ELEMENTS:
Semantic HTML elements clearly describe their meaning to both the browser and the developer. Key structural elements include:
- <header>: Represents introductory content or a set of navigational links.
- <nav>: Defines a set of major navigation links.
- <main>: Specifies the main, unique content of the document. There must not be more than one <main> element in a document.
- <article>: Represents a self-contained composition (e.g., blog post, forum post, product card) that is independently distributable.
- <section>: Represents a standalone section of functionality or thematic grouping of content.
- <footer>: Contains author information, copyright, or footer links.
Using semantic tags improves SEO, screen-reader accessibility (A11y), and code maintainability over generic <div> tags.

CSS BOX MODEL:
Every HTML element in a document tree is formatted as a rectangular box. The CSS box model consists of four distinct layers from inside out:
1. Content: The actual text, image, or media content of the box. Controlled via width and height.
2. Padding: Transparent area clearing space around the content inside the border.
3. Border: A border surrounding the padding and content (e.g., border: 1px solid #ccc).
4. Margin: Transparent space outside the border separating the element from neighboring elements.
By default, box-sizing is content-box, meaning padding and border are added onto the specified width. Modern web development universally recommends:
* { box-sizing: border-box; }
This ensures padding and borders are included within the element's total declared width and height.

CSS FLEXBOX LAYOUT GUIDE:
Flexbox (Flexible Box Layout) is a 1-dimensional layout model designed for distributing space along a single axis (row or column).
Core container properties:
- display: flex (initiates the flex formatting context).
- flex-direction: row (default, left to right) | column (top to bottom) | row-reverse | column-reverse.
- justify-content: Controls alignment along the Main Axis: flex-start, flex-end, center, space-between (equal space between items), space-around, space-evenly.
- align-items: Controls alignment along the Cross Axis: stretch (default), center, flex-start, flex-end, baseline.
- flex-wrap: nowrap (default) | wrap | wrap-reverse. Allows items to break into multiple lines.
- gap: Defines spacing between flex items without using margins (e.g., gap: 1rem).
Core child properties:
- flex-grow: Defines the ability for a flex item to grow if necessary (default 0).
- flex-shrink: Defines the ability for a flex item to shrink if necessary (default 1).
- flex-basis: The default size of an element before the remaining space is distributed (e.g., flex-basis: 250px). Shorthand: flex: 1 1 auto.

CSS GRID SYSTEM:
CSS Grid is a 2-dimensional layout system designed for both columns and rows simultaneously.
- display: grid: Activates grid container.
- grid-template-columns: Defines track sizes for columns (e.g., repeat(3, 1fr) creates 3 equal columns; repeat(auto-fit, minmax(280px, 1fr)) creates responsive fluid columns without media queries).
- grid-template-rows: Defines track sizes for rows.
- gap: Sets spacing between grid cells (e.g., gap: 24px).
- grid-column / grid-row: Specifies an item's start and end line positions (e.g., grid-column: span 2 spans across two columns).
EOT
    ],

    [
        'title' => 'JavaScript ES6+ Deep Dive',
        'course_name' => 'Full Stack Web Development',
        'default_mat_id' => 'c254cc49-47b8-455f-bc9e-bc834c0276fe',
        'content' => <<<EOT
VARIABLE DECLARATIONS & SCOPING:
ES6 introduced `let` and `const` to replace `var`:
- var: Function-scoped, hoisted with an initial value of undefined, and allows re-declaration. This often caused subtle bugs.
- let: Block-scoped (confined within { }), hoisted into the Temporal Dead Zone (TDZ) where accessing it before declaration throws a ReferenceError. Allows re-assignment but not re-declaration in the same scope.
- const: Block-scoped, also TDZ hoisted. Must be initialized upon declaration and cannot be reassigned. However, objects and arrays declared with const remain mutable in their properties and elements.

ARROW FUNCTIONS & LEXICAL THIS:
Arrow functions provide concise syntax: `const add = (a, b) => a + b;`
Key differences from regular functions:
1. Lexical `this`: Arrow functions do not bind their own `this`; they inherit `this` from the enclosing lexical execution context. This eliminates the need for `.bind(this)` or `const self = this` in callbacks.
2. No `arguments` object: Use rest parameters `(...args)` instead.
3. Cannot be used as constructors: Invoking an arrow function with `new` throws a TypeError.

DESTRUCTURING, SPREAD & REST OPERATORS:
- Object Destructuring: `const { name, age, role = 'student' } = user;` extracts properties into local variables with optional defaults.
- Array Destructuring: `const [first, second, ...rest] = items;`
- Spread Operator (`...`): Expands an iterable into individual elements. Used for shallow copying (`const copy = { ...original };`) and merging (`const merged = [...arr1, ...arr2];`).
- Rest Parameters (`...args`): Condenses multiple function arguments into a true Array object inside the function body.

ASYNCHRONOUS JAVASCRIPT & PROMISES:
JavaScript is single-threaded and uses an event loop with a Call Stack, Web APIs, Task Queue (Macrotasks: setTimeout, setInterval), and Microtask Queue (Promises, queueMicrotask). Microtasks always take priority over macrotasks.
A Promise represents an asynchronous operation with three states: pending, fulfilled, or rejected.
Example promise creation:
```javascript
const fetchData = () => new Promise((resolve, reject) => {
  setTimeout(() => resolve({ id: 1, name: "Arjun" }), 500);
});
```
Async/Await Syntax:
Built on top of Promises, `async/await` allows asynchronous code to be written sequentially:
```javascript
async function loadStudent() {
  try {
    const student = await fetchData();
    console.log("Loaded:", student.name);
  } catch (error) {
    console.error("Fetch failed:", error.message);
  }
}
```
Promise Utilities:
- Promise.all([p1, p2]): Fails fast if any promise rejects; returns array of results when all resolve.
- Promise.allSettled([p1, p2]): Waits for all promises to settle regardless of outcome.
- Promise.race([p1, p2]): Resolves or rejects as soon as the first promise settles.
EOT
    ],

    [
        'title' => 'React Hooks Tutorial',
        'course_name' => 'Full Stack Web Development',
        'default_mat_id' => 'abc6db98-3d75-40ea-b988-f1e8a7497bba',
        'content' => <<<EOT
REACT HOOKS OVERVIEW & RULES:
Hooks allow functional components to utilize state and lifecycle features without writing class components.
Rules of Hooks:
1. Only call Hooks at the top level of your component. Do not call Hooks inside loops, conditions, or nested functions.
2. Only call Hooks from React function components or custom Hooks.

USESTATE HOOK:
`const [state, setState] = useState(initialValue);`
- When updating state based on previous state, always use the functional updater pattern:
  `setCount(prev => prev + 1);`
- State updates in React 18 are batched automatically across event handlers, promises, and timeouts.
- React state is immutable: always pass a new copy of arrays or objects (`setItems([...items, newItem])`).

USEEFFECT HOOK:
Performs side effects (data fetching, DOM mutations, subscriptions) in function components.
`useEffect(() => { ... return () => cleanup(); }, [dependencies]);`
- No dependency array `useEffect(() => {})`: Runs after EVERY render.
- Empty array `useEffect(() => {}, [])`: Runs ONCE after initial mount.
- With dependencies `useEffect(() => {}, [userId])`: Runs after mount and when any dependency value changes by shallow comparison (Object.is).
- Cleanup function: Returned function executes before the component unmounts and before each re-execution of the effect to clear subscriptions, abort network controllers, or remove event listeners.

USECONTEXT & STATE PROPAGATION:
Enables sharing global state (user profile, theme, auth token) across components without manual prop drilling.
1. Create context: `const AuthContext = createContext(null);`
2. Provide context: `<AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>`
3. Consume context: `const { user } = useContext(AuthContext);`

PERFORMANCE HOOKS: USEMEMO & USECALLBACK:
- useMemo: Memoizes the result of an expensive calculation:
  `const filteredList = useMemo(() => items.filter(heavyCheck), [items]);`
- useCallback: Memoizes a callback function definition between renders, preventing unnecessary child re-renders when passing callbacks to React.memo components:
  `const handleClick = useCallback(() => { doSomething(id); }, [id]);`

USEREF HOOK:
Returns a mutable ref object whose `.current` property persists across the entire component lifetime without triggering a re-render when changed:
1. Referencing DOM elements: `<input ref={inputRef} />` -> `inputRef.current.focus();`
2. Storing mutable values: Timer IDs, previous state values, render counts.
EOT
    ],

    [
        'title' => 'Node.js & Express REST API Notes',
        'course_name' => 'Full Stack Web Development',
        'default_mat_id' => '5d1923d4-d240-4348-8ee3-29c512a8e752',
        'content' => <<<EOT
NODE.JS ARCHITECTURE & EVENT LOOP:
Node.js is an asynchronous, event-driven JavaScript runtime built on Chrome's V8 engine and Libuv.
Key components:
- Single Main Thread executes JavaScript code sequentially.
- Libuv provides a thread pool (default 4 worker threads) to handle non-blocking asynchronous I/O operations like file system reads, DNS lookups, and crypto hashing.
- The Event Loop continuously checks phases: Timers (setTimeout) -> Pending Callbacks -> Idle/Prepare -> Poll (I/O) -> Check (setImmediate) -> Close Callbacks.
Avoid CPU-intensive operations (heavy loops, synchronous encryption) on the main thread to prevent blocking event handling.

EXPRESS.JS CORE CONCEPTS:
Express is a fast, unopinionated minimalist web framework for Node.js.
Basic structure:
```javascript
const express = require('express');
const app = express();
app.use(express.json()); // Built-in middleware to parse incoming JSON bodies
```

MIDDLEWARE IN EXPRESS:
Middleware functions are functions that have access to the request object (`req`), response object (`res`), and the next middleware function (`next`).
Capabilities:
1. Execute arbitrary code (logging, rate limiting).
2. Make changes to the request and response objects (`req.user = decodedToken`).
3. End the request-response cycle (`res.status(401).json({ error: 'Unauthorized' })`).
4. Call the next middleware in the stack (`next()`).
Error-handling middleware must declare four parameters: `app.use((err, req, res, next) => { ... })`.

RESTFUL API DESIGN PRINCIPLES:
- Resource-oriented URLs using plural nouns: `/api/students`, `/api/courses`, `/api/materials`.
- HTTP Verbs indicate actions:
  - GET: Retrieve resource(s). Must be idempotent and safe.
  - POST: Create a new resource.
  - PUT: Replace resource completely.
  - PATCH: Partially update resource fields.
  - DELETE: Remove resource.
- Standard HTTP Status Codes:
  - 200 OK: Successful request.
  - 201 Created: Resource successfully created.
  - 400 Bad Request: Invalid input or missing parameters.
  - 401 Unauthorized: Missing or invalid authentication token.
  - 403 Forbidden: Authenticated user lacks permission for this action.
  - 404 Not Found: Requested resource does not exist.
  - 500 Internal Server Error: Unhandled server failure.

JWT (JSON WEB TOKEN) AUTHENTICATION:
A compact, URL-safe means of representing claims between parties.
Structure: Header.Payload.Signature (Base64Url-encoded).
Authentication flow:
1. Student submits credentials (email/password).
2. Server validates credentials and signs token with private secret:
   `const token = jwt.sign({ id: student.id, role: 'STUDENT' }, SECRET, { expiresIn: '7d' });`
3. Client stores token and sends it in the Authorization header: `Bearer <token>`.
4. Auth middleware verifies token signature on protected endpoints.
EOT
    ],

    [
        'title' => 'PostgreSQL Database Design',
        'course_name' => 'Full Stack Web Development',
        'default_mat_id' => 'd4e9dcd2-3b77-4e67-afa5-2d04001d09d0',
        'content' => <<<EOT
RELATIONAL DATABASE MODELING:
A relational database organizes data into tables (relations) with rows (tuples) and columns (attributes).
Relationship types:
- One-to-One (1:1): e.g., Student to StudentProfile. Stored by placing a UNIQUE foreign key in one of the tables.
- One-to-Many (1:N): e.g., Course to Batches. Foreign key is placed in the child table (batches table has course_id references courses(id)).
- Many-to-Many (M:N): e.g., Students to Batches. Requires a junction (associative) table with composite primary key or foreign keys (student_batches table with student_id and batch_id).

DATABASE NORMALIZATION FORMS:
Normalization eliminates data redundancy and prevents insertion, update, and deletion anomalies.
1. First Normal Form (1NF):
   - Each column contains atomic (indivisible) values.
   - Each record is uniquely identified by a primary key.
   - No repeating groups of columns.
2. Second Normal Form (2NF):
   - Meets 1NF.
   - All non-key attributes must be fully functionally dependent on the entire primary key (eliminates partial dependency in composite primary keys).
3. Third Normal Form (3NF):
   - Meets 2NF.
   - No transitive dependencies: non-key attributes must depend directly on the primary key, not on another non-key attribute.

INDEXING STRATEGIES & PERFORMANCE:
An index is a separate data structure (typically a B-tree in PostgreSQL) that allows fast lookups without scanning every row in a table.
Types of indexes:
- B-Tree Index: Default index. Excellent for equality (`=`), range queries (`<`, `<=`, `>`, `>=`), and sorting (`ORDER BY`).
- Unique Index: Enforces uniqueness constraint while indexing (`CREATE UNIQUE INDEX ...`).
- Composite Index: Indexes multiple columns together. Column order matters (Leftmost prefix rule: an index on (course_id, date) supports queries on course_id alone, but not date alone).
- Inverted/GIN Index: Used for JSONB, full-text search, and array containment.
- Vector Index (IVFFlat/HNSW): Used in pgvector for high-dimensional approximate nearest neighbor searches using cosine or L2 distance.
Index tradeoffs: Indexes speed up SELECT queries but add overhead to INSERT, UPDATE, and DELETE operations, and consume disk space.

ACID TRANSACTIONS:
A transaction is a sequence of SQL statements executed as a single unit of work.
- Atomicity: All operations succeed, or all are rolled back. No partial changes (`COMMIT` or `ROLLBACK`).
- Consistency: Data transitions from one valid state to another, respecting all constraints, foreign keys, and triggers.
- Isolation: Concurrent transactions do not interfere with each other. Isolation levels: Read Uncommitted, Read Committed (Postgres default), Repeatable Read, Serializable.
- Durability: Once a transaction commits, its changes survive crashes and power failures (persisted via Write-Ahead Logging / WAL).
EOT
    ]
];

$totalIngested = 0;
$totalChunks = 0;

foreach ($curriculum as $item) {
    $title = $item['title'];
    $mat = $materialsByTitle[$title] ?? null;
    $matId = $mat['id'] ?? $item['default_mat_id'];
    $courseId = $mat['course_id'] ?? '8e561fd8-744a-4845-a577-140bd4389346';
    $batchId = $mat['batch_id'] ?? '9421c760-14bc-4687-82ec-ab02effc833f';

    echo "\nProcessing: [{$title}]...\n";
    $result = RagService::ingestMaterial(
        $matId,
        $title,
        $item['content'],
        $courseId,
        $batchId,
        ['course_name' => $item['course_name']]
    );

    if ($result['success']) {
        echo "  -> OK: {$result['indexed_chunks']}/{$result['total_chunks']} chunks embedded and indexed.\n";
        $totalIngested++;
        $totalChunks += $result['indexed_chunks'];
    } else {
        echo "  -> FAILED to ingest {$title}\n";
    }
}

echo "\n============================================\n";
echo "RAG Seeding Complete!\n";
echo "Modules indexed: {$totalIngested}\n";
echo "Total chunks created: {$totalChunks}\n";
$stats = RagService::getStats();
echo "Active stats: " . json_encode($stats, JSON_PRETTY_PRINT) . "\n";

$sbCheck = supabaseSelect('document_chunks', 'id');
if ($sbCheck['success']) {
    $sbCount = count($sbCheck['data'] ?? []);
    echo "Supabase Cloud: {$sbCount} chunks verified in document_chunks table.\n";
} else {
    echo "Supabase Cloud Notice: " . ($sbCheck['error'] ?? 'Table not found') . "\n";
    echo "-> Remember to run database/rag_migration.sql in the Supabase SQL editor if not done yet.\n";
}
echo "============================================\n";
