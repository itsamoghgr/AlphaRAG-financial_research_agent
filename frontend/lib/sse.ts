// Tiny streaming SSE client built on top of fetch + ReadableStream.
//
// The browser's built-in EventSource only supports GET, but we POST the
// query body. This helper does the SSE parsing manually and dispatches
// typed events to the supplied handlers.

export interface SSEHandlers {
  onEvent: (eventName: string, data: string) => void;
  onError: (err: unknown) => void;
  onClose: () => void;
}

export interface PostSSEOptions {
  signal?: AbortSignal;
  body: unknown;
  headers?: Record<string, string>;
}

export async function postSSE(
  url: string,
  opts: PostSSEOptions,
  handlers: SSEHandlers,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(opts.headers ?? {}),
      },
      body: JSON.stringify(opts.body),
      signal: opts.signal,
    });
  } catch (err) {
    handlers.onError(err);
    handlers.onClose();
    return;
  }

  if (!response.ok || !response.body) {
    handlers.onError(new Error(`SSE request failed: ${response.status}`));
    handlers.onClose();
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    // Each SSE message is delimited by a blank line. We accumulate bytes
    // into `buffer` and pull out complete messages whenever we see "\n\n".
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sepIndex: number;
      while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, sepIndex);
        buffer = buffer.slice(sepIndex + 2);
        const { eventName, data } = parseSSEMessage(raw);
        if (data !== null) {
          handlers.onEvent(eventName ?? "message", data);
        }
      }
    }
  } catch (err) {
    handlers.onError(err);
  } finally {
    handlers.onClose();
  }
}

function parseSSEMessage(raw: string): {
  eventName: string | null;
  data: string | null;
} {
  let eventName: string | null = null;
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }
  if (dataLines.length === 0) return { eventName, data: null };
  return { eventName, data: dataLines.join("\n") };
}
