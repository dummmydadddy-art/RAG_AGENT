# EduConnect LMS & n8n Telegram Bot Integration: Complete Changelog & Architecture Guide

This document summarizes all issues encountered, root causes identified, architectural fixes, workflow corrections, and backend code modifications implemented during the setup of the **EduConnect LMS Telegram AI Chatbot** powered by **n8n** and **Ollama**.

---

## Table of Contents
1. [Overview & Architecture Flow](#1-overview--architecture-flow)
2. [Summary of Issues & Solutions](#2-summary-of-issues--solutions)
3. [Backend Code Changes (PHP)](#3-backend-code-changes-php)
   - [3.1 Authentication & Service Key Support](#31-authentication--service-key-support)
   - [3.2 Service Account Handling for Attendance, Fees & Materials](#32-service-account-handling-for-attendance-fees--materials)
   - [3.3 Server Interface & Network Binding](#33-server-interface--network-binding)
4. [n8n Workflow Fixes & Adjustments](#4-n8n-workflow-fixes--adjustments)
   - [4.1 Resolving `chat_id is empty`](#41-resolving-chat_id-is-empty)
   - [4.2 Environment Variable Access (`$env`)](#42-environment-variable-access-env)
   - [4.3 Telegram Markdown Parse Mode Errors](#43-telegram-markdown-parse-mode-errors)
   - [4.4 Publishing vs Manual Test Execution](#44-publishing-vs-manual-test-execution)
5. [Ollama AI Performance & Latency Recommendations](#5-ollama-ai-performance--latency-recommendations)
6. [Step-by-Step Running & Testing Guide](#6-step-by-step-running--testing-guide)

---

## 1. Overview & Architecture Flow

The Telegram bot connects students to the EduConnect LMS backend using an n8n workflow and local Ollama LLMs:

```
[Telegram User]
       │ (Message / Mobile Number)
       ▼
[Telegram Trigger (n8n)]
       │
[Normalize Telegram Message]
       │
[Resolve Student Identity] ──(Not Linked)──► [Needs Mobile?] ──► [Ask for Mobile]
       │ (Linked or Phone Provided)
       ▼
[Lookup Student (PHP API: /api/users/students)]
       │
[Store Mapping in n8n Static Data]
       │
[Build Session Context]
       │
[Intent Router (Ollama)] ───► Classifies into: attendance, fees, quiz, support
       │
[Route to Specialist (Switch)]
  ├── attendance ──► [GET /api/attendance?student_id=...] ──► [Attendance Specialist] ──► [Attendance Finalize]
  ├── fees       ──► [GET /api/fees?student_id=...]       ──► [Fees Specialist]       ──► [Fees Finalize]
  ├── quiz       ──► [GET /api/materials?student_id=...]  ──► [Quiz Specialist]       ──► [Quiz Finalize]
  └── support    ──► [Prepare Support Context]            ──► [Support Specialist]    ──► [Create Support Ticket (POST /api/notifications)] ──► [Build Support Final]
       │
       ▼
[Send Telegram Reply] ──► [Telegram User]
```

---

## 2. Summary of Issues & Solutions

| # | Issue / Error Message | Root Cause | Solution Implemented |
|---|---|---|---|
| **1** | `Telegram Trigger: Because of limitations in Telegram Trigger, n8n can't listen for test executions...` | Telegram only permits **one active webhook per bot token**. An active/published workflow locks the webhook. | Deactivate the workflow before clicking "Test Workflow", or **Publish** it and test live from Telegram. |
| **2** | `Problem in node ‘Lookup Student...’ access to env vars denied` | n8n blocks access to `$env.*` inside workflow expressions by default for security (`N8N_BLOCK_ENV_ACCESS_IN_NODE=true`). | Configured `X-Service-Key` header with `lms-n8n-service-key-2026` directly (or set `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`). |
| **3** | `Lookup Student: The service refused the connection - perhaps it is offline` | PHP server was bound only to `localhost:8000` / `[::1]:8000`. Docker container (`host.docker.internal`) was rejected. | Changed PHP server binding to `0.0.0.0:8000` in `start-backend.ps1` to accept connections across container networks. |
| **4** | `Intent Router (Ollama): access to env vars denied` | `$env.OLLAMA_ROUTER_MODEL` and `$env.OLLAMA_SPECIALIST_MODEL` were blocked by n8n. | Replaced `$env` expressions in Ollama JSON bodies with explicit model names (e.g. `"llama3.2:latest"` or `"llama3.2:1b"`). |
| **5** | `Send Telegram Reply: Bad Request: chat_id is empty` | Ollama HTTP response payload overwrote the node item context; `d.chatId` was undefined in Finalize nodes. | Modified Finalize Code nodes to read `chatId` from preceding `Prepare ... Context` nodes instead of Ollama response. |
| **6** | `Workflow succeeded but reply did not come on Telegram` | Telegram API rejected messages due to strict Markdown parsing when LLM output contained unescaped characters (`_`, `*`, `[`, etc.). | Removed Markdown parse mode from `Send Telegram Reply` (or switched to plain text/HTML). |
| **7** | `Get Attendance Data: 401 Unauthorized: No token provided` | `index.php` routes were using `verifyToken()` (JWT only) and ignored `X-Service-Key`. | Changed authentication checks on attendance, fees, materials, and notification endpoints to use `verifyTokenOrApiKey()`. |
| **8** | `Get Attendance Data: 400 Bad Request: batch_id required for list` | Backend treated service account (`ROLE_SERVICE`) as an admin/teacher, which required a `batch_id` parameter instead of `student_id`. | Added dedicated `elseif ($user['role'] === 'SERVICE' && !empty($_GET['student_id']))` handlers across endpoints. |

---

## 3. Backend Code Changes (PHP)

File modified: [`d:\Collage project\Learning Management System\backend\index.php`](file:///d:/Collage%20project/Learning%20Management%20System/backend/index.php)

### 3.1 Authentication & Service Key Support
Updated the following routes to call `verifyTokenOrApiKey()` instead of `verifyToken()` or `requireRole(...)`:

1. **`GET /api/attendance`** (Line ~822)
2. **`GET /api/materials`** (Line ~887)
3. **`GET /api/fees`** (Line ~1402)
4. **`POST /api/notifications`** (Line ~1749)

### 3.2 Service Account Handling for Attendance, Fees & Materials

#### A. Attendance Endpoint (`GET /api/attendance`)
```php
case ($route === '/api/attendance' && $method === 'GET'):
    $user = verifyTokenOrApiKey();
    $batchId = $_GET['batch_id'] ?? '';
    $date = $_GET['date'] ?? '';

    if ($user['role'] === 'STUDENT') {
        $res = supabaseSelect('attendance', '*, batches(batch_name)', ['student_id' => $user['id']]);
        echo json_encode(['success' => true, 'attendance' => $res['data'] ?: []]);
    } elseif ($user['role'] === 'SERVICE' && !empty($_GET['student_id'])) {
        // n8n service account: look up attendance by student_id query param
        $res = supabaseSelect('attendance', '*, batches(batch_name)', ['student_id' => $_GET['student_id']]);
        echo json_encode(['success' => true, 'attendance' => $res['data'] ?: []]);
    } else {
        if (empty($batchId)) {
            http_response_code(400);
            echo json_encode(['success' => false, 'error' => 'batch_id required for list']);
            break;
        }
        $params = ['batch_id' => $batchId];
        if (!empty($date)) {
            $params['date'] = $date;
        }
        $res = supabaseSelect('attendance', '*, students(full_name)', $params);
        echo json_encode(['success' => true, 'attendance' => $res['data'] ?: []]);
    }
    break;
```

#### B. Study Materials Endpoint (`GET /api/materials`)
```php
case ($route === '/api/materials' && $method === 'GET'):
    $user = verifyTokenOrApiKey();
    if ($user['role'] === 'STUDENT') {
        $res = supabaseSelect('materials', '*, courses(course_name), batches!inner(batch_name, student_batches!inner(student_id))', [
            'batches.student_batches.student_id' => $user['id']
        ]);
        if ($res['success'] && !empty($res['data'])) {
            foreach ($res['data'] as &$m) {
                if (isset($m['batches']['student_batches'])) {
                    unset($m['batches']['student_batches']);
                }
            }
        }
        echo json_encode(['success' => $res['success'], 'materials' => $res['data'] ?: [], 'error' => $res['error']]);
    } elseif ($user['role'] === 'SERVICE' && !empty($_GET['student_id'])) {
        // n8n service account: look up materials by student_id query param
        $res = supabaseSelect('materials', '*, courses(course_name), batches!inner(batch_name, student_batches!inner(student_id))', [
            'batches.student_batches.student_id' => $_GET['student_id']
        ]);
        if ($res['success'] && !empty($res['data'])) {
            foreach ($res['data'] as &$m) {
                if (isset($m['batches']['student_batches'])) {
                    unset($m['batches']['student_batches']);
                }
            }
        }
        echo json_encode(['success' => $res['success'], 'materials' => $res['data'] ?: [], 'error' => $res['error']]);
    } else {
        $batchId = $_GET['batch_id'] ?? '';
        $params = [];
        if (!empty($batchId)) {
            $params['batch_id'] = $batchId;
        }
        $res = supabaseSelect('materials', '*, courses(course_name), batches(batch_name)', $params);
        echo json_encode(['success' => true, 'materials' => $res['data'] ?: []]);
    }
    break;
```

#### C. Fees & Payments Endpoint (`GET /api/fees`)
```php
case ($route === '/api/fees' && $method === 'GET'):
    $user = verifyTokenOrApiKey();
    if ($user['role'] === 'STUDENT') {
        $ledger = supabaseSelect('fee_records', '*', ['student_id' => $user['id']], true);
        $txns = supabaseSelect('payment_transactions', '*', ['student_id' => $user['id']]);
        echo json_encode([
            'success' => true,
            'ledger' => $ledger['data'] ?: null,
            'transactions' => $txns['data'] ?: []
        ]);
    } elseif ($user['role'] === 'SERVICE' && !empty($_GET['student_id'])) {
        // n8n service account: look up fees by student_id query param
        $sid = $_GET['student_id'];
        $ledger = supabaseSelect('fee_records', '*', ['student_id' => $sid], true);
        $txns = supabaseSelect('payment_transactions', '*', ['student_id' => $sid]);
        echo json_encode([
            'success' => true,
            'ledger' => $ledger['data'] ?: null,
            'transactions' => $txns['data'] ?: []
        ]);
    } else {
        // Admin and Teacher view all fees
        $ledger = supabaseSelect('fee_records', '*, students(full_name)');
        $txns = supabaseSelect('payment_transactions', '*, students(full_name)');
        echo json_encode([
            'success' => true,
            'ledgers' => $ledger['data'] ?: [],
            'transactions' => $txns['data'] ?: []
        ]);
    }
    break;
```

### 3.3 Server Interface & Network Binding

To allow Docker containers to communicate with the host PHP server via `host.docker.internal:8000`, the server must bind to `0.0.0.0` instead of `localhost`:

```powershell
cd "d:\Collage project\Learning Management System\backend"
& "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\PHP.PHP.8.3_Microsoft.Winget.Source_8wekyb3d8bbwe\php.exe" -S "0.0.0.0:8000"
```

---

## 4. n8n Workflow Fixes & Adjustments

### 4.1 Resolving `chat_id is empty`

In the Finalize Code nodes, `chatId` is retrieved from the **`Prepare ... Context`** node rather than the Ollama HTTP node:

```javascript
// Example: Attendance Finalize node
const d = $('Attendance Specialist (Ollama)').item.json;
const ctx = $('Prepare Attendance Context').item.json;
return [{
  json: {
    replyText: d.message?.content || d.response || 'Sorry, I could not generate a response.',
    chatId: ctx.chatId
  }
}];
```

Applied identically to:
- `Attendance Finalize`
- `Fees Finalize`
- `Quiz Finalize`
- `Build Support Final`

### 4.2 Environment Variable Access (`$env`)

For each HTTP request communicating with the LMS backend:
- Header Name: `X-Service-Key`
- Header Value: `lms-n8n-service-key-2026`

For Ollama HTTP requests:
- Specified model directly: `"model": "llama3.2:latest"` (or `"llama3.2:1b"`).

### 4.3 Telegram Markdown Parse Mode Errors

In `Send Telegram Reply`:
- Set **Parse Mode** to empty (plain text) or `HTML` to prevent message drops caused by unescaped Markdown symbols in LLM responses.

### 4.4 Publishing vs Manual Test Execution

In newer versions of n8n:
- **Publish** button (top right) activates production webhook mode.
- When **Published**, messages sent to the bot in Telegram trigger executions automatically.
- Live progress and logs can be monitored under the **Executions** tab.

---

## 5. Ollama AI Performance & Latency Recommendations

Because the workflow performs two sequential LLM inferences:
1. **Intent Router**: ~10–30 seconds
2. **Specialist Response**: ~15–60 seconds

To improve latency:
1. **Use lightweight 1B model**:
   ```bash
   ollama pull llama3.2:1b
   ```
   Set `"model": "llama3.2:1b"` in all 5 Ollama nodes.
2. **GPU Acceleration**:
   Verify GPU offloading with `ollama ps`.
3. **Optional Regex-based Routing**:
   Replace the Intent Router LLM call with a JavaScript Code node for instant (<1ms) keyword classification.

---

## 6. Step-by-Step Running & Testing Guide

1. **Start the PHP Backend**:
   ```powershell
   cd "d:\Collage project\Learning Management System\backend"
   & "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\PHP.PHP.8.3_Microsoft.Winget.Source_8wekyb3d8bbwe\php.exe" -S "0.0.0.0:8000"
   ```
2. **Ensure Ollama is Running**:
   ```powershell
   ollama serve
   ```
3. **Ensure n8n is Running & Workflow is Published**:
   - Open n8n interface.
   - Click **Publish** (top-right).
4. **Interact via Telegram Bot**:
   - Send registered phone number to link student identity.
   - Ask for attendance, fee balances, course materials/quizzes, or support.
5. **Monitor Logs**:
   - Check the **Executions** tab in n8n for live execution traces.
