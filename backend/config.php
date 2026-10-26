<?php
// RAG Agent Configuration — Template
// Fill in your own values or configure environment variables.
// ⚠️ Do not commit real keys or credentials to a public repository.

ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

// Load deployment variables
$APP_NAME = "RAG-Agent";
$APP_ENV = "production";

// Supabase Configuration
$SUPABASE_PROJECT_URL = getenv("SUPABASE_PROJECT_URL") ?: "https://YOUR_PROJECT_ID.supabase.co";
$SUPABASE_URL = getenv("SUPABASE_URL") ?: "https://YOUR_PROJECT_ID.supabase.co/rest/v1/";
$SUPABASE_ANON_KEY = getenv("SUPABASE_ANON_KEY") ?: "YOUR_SUPABASE_ANON_KEY";
$SUPABASE_SERVICE_ROLE_KEY = getenv("SUPABASE_SERVICE_ROLE_KEY") ?: "";

// Service-to-service API key (for external integrations)
$SERVICE_API_KEY = getenv("LMS_SERVICE_API_KEY") ?: "YOUR_SERVICE_API_KEY";

// Ollama AI Configuration
$OLLAMA_BASE_URL = getenv("OLLAMA_BASE_URL") ?: "http://localhost:11434";
$OLLAMA_EMBED_MODEL = getenv("OLLAMA_EMBED_MODEL") ?: "nomic-embed-text";
$OLLAMA_CHAT_MODEL = getenv("OLLAMA_CHAT_MODEL") ?: "llama3.2:latest";

// Helper headers
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With, apikey");
header("Content-Type: application/json; charset=UTF-8");

// Handle CORS preflight request
if (isset($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}
