import { useCallback, useRef, useState } from "react";

export interface Citation {
  doc: string;
  section: string;
  url: string | null;
  snippet: string;
}

export interface AskState {
  status: "idle" | "streaming" | "done" | "error";
  answer: string;
  citations: Citation[];
  disclaimer: string | null;
  error: string | null;
}

const INITIAL: AskState = {
  status: "idle",
  answer: "",
  citations: [],
  disclaimer: null,
  error: null,
};

/**
 * Streams an answer from POST /api/ask.
 *
 * The endpoint returns Server-Sent Events: `citation` events (emitted first),
 * `token` events (the streamed answer), and a final `done` event carrying the
 * server-appended disclaimer. We read the response body as a stream and parse
 * the SSE frames by hand (EventSource only supports GET, and we POST a body).
 */
export function useAsk() {
  const [state, setState] = useState<AskState>(INITIAL);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => setState(INITIAL), []);

  const ask = useCallback(async (question: string, jurisdiction = "MD") => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ ...INITIAL, status: "streaming" });

    try {
      const resp = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, jurisdiction }),
        signal: controller.signal,
      });
      if (!resp.ok || !resp.body) {
        throw new Error(`Request failed (${resp.status})`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      // SSE frames are separated by a blank line; each frame has `event:` and
      // `data:` lines. Parse incrementally as chunks arrive.
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

        let sep: number;
        while ((sep = buffer.indexOf("\n\n")) !== -1) {
          const frame = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          handleFrame(frame, setState);
        }
      }
      // Flush any trailing frame that arrived without a final blank-line
      // separator before the stream closed (common for short, fast responses
      // like the grounding refusal — otherwise the last event is dropped).
      buffer += decoder.decode();
      if (buffer.trim()) {
        for (const frame of buffer.split("\n\n")) {
          if (frame.trim()) handleFrame(frame, setState);
        }
      }
      setState((s) => (s.status === "streaming" ? { ...s, status: "done" } : s));
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setState((s) => ({ ...s, status: "error", error: (err as Error).message }));
    }
  }, []);

  return { ...state, ask, reset };
}

function handleFrame(frame: string, setState: React.Dispatch<React.SetStateAction<AskState>>) {
  let event = "message";
  let data = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return;

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(data);
  } catch {
    return;
  }

  if (event === "token") {
    setState((s) => ({ ...s, answer: s.answer + (payload.text as string) }));
  } else if (event === "citation") {
    setState((s) => ({
      ...s,
      citations: [...s.citations, payload as unknown as Citation],
    }));
  } else if (event === "done") {
    setState((s) => ({ ...s, status: "done", disclaimer: payload.disclaimer as string }));
  }
}
