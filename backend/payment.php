<?php
// Stub for payment functions in standalone RAG engine
function createPayment($studentId, $amount, $paymentMethod) {
    return ['success' => false, 'error' => 'Payment functionality disabled in standalone RAG engine'];
}

function verifyPayment($transactionId, $paymentId, $orderId, $signature) {
    return ['success' => false, 'error' => 'Payment functionality disabled in standalone RAG engine'];
}
