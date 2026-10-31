/**
 * Server-Sent Events (SSE) Client via Fetch & ReadableStream
 * Consumes POST /api/chat event streams with full control over payload, headers, and cancellation.
 */

export async function streamChatCompletion({
  message,
  conversationId,
  onToken,
  onTelemetry,
  onDone,
  onError,
  abortSignal,
}) {
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
        model: 'stem-coder-expert:latest',
      }),
      signal: abortSignal,
    });

    if (!response.ok) {
      let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errJson = await response.json();
        if (errJson && errJson.detail) errorDetail = errJson.detail;
      } catch (_) {}
      throw new Error(errorDetail);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete line fragment for next chunk

      let currentEvent = 'token'; // Default event type

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
          currentEvent = 'token'; // Reset after event block separator
          continue;
        }

        if (trimmed.startsWith('event:')) {
          currentEvent = trimmed.slice(6).trim();
        } else if (trimmed.startsWith('data:')) {
          const rawData = trimmed.slice(5).trim();
          try {
            const data = JSON.parse(rawData);

            if (currentEvent === 'token') {
              if (onToken) onToken(data.chunk !== undefined ? data.chunk : data);
            } else if (currentEvent === 'telemetry' || currentEvent.startsWith('telemetry_')) {
              if (onTelemetry) onTelemetry(currentEvent, data);
            } else if (currentEvent === 'done') {
              if (onDone) onDone(data);
            } else if (currentEvent === 'error') {
              if (onError) onError(data.error || data.detail || 'An error occurred during generation');
            } else if (currentEvent === 'metadata') {
              // Metadata like conversation_id
              if (data.conversation_id && onDone) {
                // Keep track if needed
              }
            }
          } catch (e) {
            // If data is plain text rather than JSON
            if (currentEvent === 'token') {
              if (onToken) onToken(rawData);
            }
          }
        }
      }
    }

    // Flush any remaining stream completion
    if (onDone) onDone({ status: 'completed' });

  } catch (err) {
    if (err.name === 'AbortError') {
      console.log('Stream generation aborted by user.');
      if (onDone) onDone({ status: 'aborted' });
    } else {
      console.error('SSE Stream Error:', err);
      if (onError) onError(err.message || 'Stream connection failed');
    }
  }
}
