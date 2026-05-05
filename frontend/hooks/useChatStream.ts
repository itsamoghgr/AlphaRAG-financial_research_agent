"use client";

import { useCallback, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/api";
import { postSSE } from "@/lib/sse";
import type {
  Citation,
  QueryAnswer,
  StageEvent,
  StageName,
} from "@/lib/types";

export type ChatStreamState =
  | { kind: "idle" }
  | { kind: "streaming"; stage: StageName; message: string; partial: string }
  | {
      kind: "done";
      answer: string;
      citations: Citation[];
      timings_ms: Record<string, number>;
    }
  | { kind: "error"; code: string; message: string };

export interface SubmitArgs {
  ticker: string;
  question: string;
  refresh?: boolean;
}

export function useChatStream() {
  const [state, setState] = useState<ChatStreamState>({ kind: "idle" });
  const [stageHistory, setStageHistory] = useState<StageEvent[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState({ kind: "idle" });
    setStageHistory([]);
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const submit = useCallback(async (args: SubmitArgs) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStageHistory([]);
    setState({
      kind: "streaming",
      stage: "resolving",
      message: "Looking up company",
      partial: "",
    });

    let partial = "";

    await postSSE(
      `${API_BASE_URL}/api/query`,
      {
        body: {
          ticker: args.ticker.trim().toUpperCase(),
          question: args.question.trim(),
          refresh: args.refresh ?? false,
        },
        signal: controller.signal,
      },
      {
        onEvent(eventName, data) {
          try {
            if (eventName === "token") {
              const parsed = JSON.parse(data) as { text: string };
              partial += parsed.text;
              setState((prev) =>
                prev.kind === "streaming"
                  ? { ...prev, partial }
                  : prev,
              );
              return;
            }

            if (eventName === "done") {
              const final = JSON.parse(data) as QueryAnswer;
              setState({
                kind: "done",
                answer: final.answer,
                citations: final.citations,
                timings_ms: final.timings_ms,
              });
              return;
            }

            if (eventName === "error") {
              const err = JSON.parse(data) as {
                code: string;
                message: string;
              };
              setState({ kind: "error", code: err.code, message: err.message });
              return;
            }

            // Stage event: the event name IS the stage, body has message + extras.
            const parsed = JSON.parse(data) as {
              message: string;
              [k: string]: unknown;
            };
            const stage = eventName as StageName;
            setStageHistory((h) => [
              ...h,
              { stage, message: parsed.message, data: parsed },
            ]);
            setState((prev) =>
              prev.kind === "streaming"
                ? { ...prev, stage, message: parsed.message }
                : { kind: "streaming", stage, message: parsed.message, partial },
            );
          } catch (e) {
            console.warn("Failed to parse SSE event", eventName, data, e);
          }
        },
        onError(err) {
          if ((err as Error)?.name === "AbortError") return;
          setState({
            kind: "error",
            code: "stream_error",
            message: (err as Error)?.message ?? "Streaming connection lost",
          });
        },
        onClose() {
          // No-op: terminal state was already set by 'done' or 'error'.
        },
      },
    );
  }, []);

  return { state, stageHistory, submit, cancel, reset };
}
