// filepath: frontend/src/lib/sse-client.ts
/**
 * SSE client for streaming chat responses (T708).
 *
 * Parses the event stream from POST /api/v1/companies/{id}/chat
 * and calls typed callbacks for each event kind.
 */

export interface SSECallbacks {
  onSession?: (data: { session_id: string; title: string }) => void;
  onSources?: (data: { sources: ChatSourceEvent[] }) => void;
  onToken?: (data: { token: string }) => void;
  onDone?: (data: { message_id: string; token_count: number }) => void;
  onError?: (data: { error: string; message: string }) => void;
  onConnectionError?: (error: Error) => void;
}

export interface ChatSourceEvent {
  chunk_id: string;
  doc_type: string;
  fiscal_year: number;
  section_title?: string;
  score: number;
  text_preview?: string;
}

/**
 * Send a chat message and stream the response via SSE.
 *
 * Returns an AbortController so the caller can cancel the stream.
 */
export function streamChat(
  companyId: string,
  body: {
    message: string;
    session_id?: string;
    retrieval_config?: Record<string, unknown>;
  },
  callbacks: SSECallbacks,
): AbortController {
  const controller = new AbortController();
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const apiKey = process.env.NEXT_PUBLIC_API_KEY ?? "";
  const url = `${baseUrl}/api/v1/companies/${companyId}/chat`;

  fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
      Accept: "text/event-stream",
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const text = await response.text().catch(() => "Unknown error");
        callbacks.onError?.({
          error: `HTTP ${response.status}`,
          message: text,
        });
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onError?.({
          error: "No reader",
          message: "Response body is not readable",
        });
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        let currentEvent = "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            const raw = line.slice(5).trim();
            if (!raw) continue;

            try {
              const data = JSON.parse(raw);
              switch (currentEvent) {
                case "session":
                  callbacks.onSession?.(data);
                  break;
                case "sources":
                  callbacks.onSources?.(data);
                  break;
                case "token":
                  callbacks.onToken?.(data);
                  break;
                case "done":
                  callbacks.onDone?.(data);
                  break;
                case "error":
                  callbacks.onError?.(data);
                  break;
              }
            } catch {
              // Ignore malformed JSON lines
            }
            currentEvent = "";
          } else if (line.trim() === "") {
            currentEvent = "";
          }
        }
      }
    })
    .catch((err: Error) => {
      if (err.name === "AbortError") return;
      callbacks.onConnectionError?.(err);
    });

  return controller;
}
