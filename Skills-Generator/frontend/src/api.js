/* ==========================================================================
   API helpers — JSON requests and Server-Sent Event streams (POST)
   ========================================================================== */

export class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}

async function errorFrom(res) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = Array.isArray(err.detail) ? err.detail.map((d) => d.msg).join(", ") : err.detail;
    return new ApiError(detail || `Request failed (${res.status})`, res.status);
}

export async function api(path, opts = {}) {
    const res = await fetch(`/api${path}`, {
        headers: { "Content-Type": "application/json" },
        ...opts,
    });
    if (!res.ok) throw await errorFrom(res);
    return res.json();
}

/**
 * POST to an SSE endpoint and call onEvent(event) for every `data:` message.
 * Resolves with the final "done" event; rejects on an "error" event.
 * (EventSource can't POST a body, so this reads the stream by hand.)
 */
export async function streamSSE(path, body, onEvent) {
    const res = await fetch(`/api${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(body ?? {}),
    });
    if (!res.ok) throw await errorFrom(res);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let final = null;

    const handle = (chunk) => {
        const data = chunk
            .split("\n")
            .filter((l) => l.startsWith("data:"))
            .map((l) => l.slice(5).trimStart())
            .join("\n");
        if (!data) return;
        const event = JSON.parse(data);
        if (event.type === "error") throw new ApiError(event.detail, event.status);
        if (event.type === "done") final = event;
        onEvent?.(event);
    };

    for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
            handle(buffer.slice(0, idx));
            buffer = buffer.slice(idx + 2);
        }
    }
    if (buffer.trim()) handle(buffer);
    if (!final) throw new ApiError("The server closed the stream before finishing", 502);
    return final;
}
