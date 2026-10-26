<?php
// LMS Configuration — TEMPLATE FILE
// Copy this to config.php and fill in your own values.
// ⚠️  Never commit config.php with real keys to a public repo.

ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

$APP_NAME = "LMS";
$APP_ENV  = "production"; // "development" | "production"

// ── Supabase ────────────────────────────────────────────────────────────────
// Get these from: https://supabase.com → Project Settings → API
$SUPABASE_PROJECT_URL      = "https://YOUR_PROJECT_ID.supabase.co";
$SUPABASE_URL              = "https://YOUR_PROJECT_ID.supabase.co/rest/v1/";
$SUPABASE_ANON_KEY         = "YOUR_SUPABASE_ANON_KEY";
$SUPABASE_SERVICE_ROLE_KEY = getenv("SUPABASE_SERVICE_ROLE_KEY") ?: "YOUR_SUPABASE_SERVICE_ROLE_KEY";

// ── Payment Gateway (Razorpay) ───────────────────────────────────────────────
// Get these from: https://dashboard.razorpay.com → Settings → API Keys
$PAYMENT_GATEWAY_KEY    = getenv("PAYMENT_GATEWAY_KEY")    ?: "YOUR_RAZORPAY_KEY_ID";
$PAYMENT_GATEWAY_SECRET = getenv("PAYMENT_GATEWAY_SECRET") ?: "YOUR_RAZORPAY_KEY_SECRET";

// ── Service-to-Service API Key (n8n / Telegram bot) ─────────────────────────
// Used in X-Service-Key header so n8n can call the API without a user JWT.
// Set this to any strong random string — keep it secret.
$SERVICE_API_KEY = getenv("LMS_SERVICE_API_KEY") ?: "YOUR_SERVICE_API_KEY";

// ── Ollama AI (local LLM) ───────────────────────────────────────────────────
// Run Ollama locally: https://ollama.com
// Pull models: ollama pull nomic-embed-text && ollama pull llama3.2
$OLLAMA_BASE_URL    = getenv("OLLAMA_BASE_URL")    ?: "http://localhost:11434";
$OLLAMA_EMBED_MODEL = getenv("OLLAMA_EMBED_MODEL") ?: "nomic-embed-text";
$OLLAMA_CHAT_MODEL  = getenv("OLLAMA_CHAT_MODEL")  ?: "llama3.2:latest";

// ── CORS ────────────────────────────────────────────────────────────────────
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With, apikey");
header("Content-Type: application/json; charset=UTF-8");

if (isset($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}
