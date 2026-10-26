<?php
// LMS Supabase Database Helper

require_once 'config.php';

function supabaseRequest($method, $path, $body = null, $headers = []) {
    global $SUPABASE_URL, $SUPABASE_SERVICE_ROLE_KEY;

    static $ch = null;
    if ($ch === null) {
        $ch = curl_init();
    } else {
        curl_reset($ch);
    }

    $url = rtrim($SUPABASE_URL, '/') . '/' . ltrim($path, '/');

    $defaultHeaders = [
        "apikey: " . $SUPABASE_SERVICE_ROLE_KEY,
        "Authorization: Bearer " . $SUPABASE_SERVICE_ROLE_KEY,
        "Content-Type: application/json"
    ];

    $mergedHeaders = array_merge($defaultHeaders, $headers);

    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $mergedHeaders);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false); // For local environments
    curl_setopt($ch, CURLOPT_TIMEOUT, 10); // 10 seconds execution timeout
    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 5); // 5 seconds connection timeout
    curl_setopt($ch, CURLOPT_HTTP_VERSION, CURL_HTTP_VERSION_1_1); // Force HTTP/1.1 for connection reuse

    if ($body !== null) {
        $jsonBody = is_string($body) ? $body : json_encode($body);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $jsonBody);
    }

    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);


    if ($error) {
        return [
            'success' => false,
            'error' => 'cURL Error: ' . $error,
            'status' => $httpCode
        ];
    }

    $decoded = json_decode($response, true);
    $isSuccess = ($httpCode >= 200 && $httpCode < 300);

    return [
        'success' => $isSuccess,
        'status' => $httpCode,
        'data' => $isSuccess ? $decoded : null,
        'error' => !$isSuccess ? ($decoded['message'] ?? $response) : null,
        'hint' => !$isSuccess ? ($decoded['hint'] ?? '') : null
    ];
}

function buildQueryString($params) {
    if (empty($params)) return '';
    $queryParts = [];
    foreach ($params as $key => $val) {
        // If val already contains an operator (e.g. eq., ilike., in.), use it directly.
        // Otherwise, default to eq.
        if (is_string($val) && strpos($val, '.') !== false) {
            $queryParts[] = urlencode($key) . '=' . urlencode($val);
        } else {
            $queryParts[] = urlencode($key) . '=eq.' . urlencode($val);
        }
    }
    return implode('&', $queryParts);
}

function supabaseSelect($table, $select = '*', $params = [], $single = false) {
    $path = $table . '?select=' . urlencode($select);
    $queryString = buildQueryString($params);
    if ($queryString) {
        $path .= '&' . $queryString;
    }

    $headers = [];
    if ($single) {
        // PostgREST return single object format
        $headers[] = "Accept: application/vnd.pgrst.object+json";
    }

    return supabaseRequest('GET', $path, null, $headers);
}

function supabaseInsert($table, $data) {
    $headers = [
        "Prefer: return=representation"
    ];
    return supabaseRequest('POST', $table, $data, $headers);
}

function supabaseUpdate($table, $data, $params = []) {
    $queryString = buildQueryString($params);
    $path = $table;
    if ($queryString) {
        $path .= '?' . $queryString;
    }
    
    $headers = [
        "Prefer: return=representation"
    ];
    return supabaseRequest('PATCH', $path, $data, $headers);
}

function supabaseDelete($table, $params = []) {
    $queryString = buildQueryString($params);
    $path = $table;
    if ($queryString) {
        $path .= '?' . $queryString;
    }
    return supabaseRequest('DELETE', $path);
}

function supabaseRPC($functionName, $params = []) {
    $path = 'rpc/' . $functionName;
    $headers = [
        "Prefer: return=representation"
    ];
    return supabaseRequest('POST', $path, $params, $headers);
}
