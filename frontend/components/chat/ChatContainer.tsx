"use client";

import { useEffect, useRef, useState } from "react";
import { useChatStream } from "@/hooks/useChatStream";
import { EmptyState } from "@/components/chat/EmptyState";
import { TickerInput } from "@/components/chat/TickerInput";
import { MessageList, type ChatMessage } from "@/components/chat/MessageList";

export function ChatContainer() {
  const { state, stageHistory, submit, reset } = useChatStream();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [ticker, setTicker] = useState("");
  const [question, setQuestion] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, state]);

  // Derive an in-flight assistant message from the live stream state so the
  // UI can show progress + partial tokens without us having to mutate the
  // history on every event.
  const inflight: ChatMessage | null =
    state.kind === "streaming"
      ? {
          id: "inflight",
          role: "assistant",
          ticker,
          status: "streaming",
          stages: stageHistory,
          partial: state.partial,
          currentStage: state.stage,
          currentStageMessage: state.message,
          citations: [],
        }
      : null;

  // When the stream finishes, append the final answer to history.
  if (
    state.kind === "done" &&
    !messages.some((m) => m.id === finalKey(ticker, question, state.answer))
  ) {
    const final: ChatMessage = {
      id: finalKey(ticker, question, state.answer),
      role: "assistant",
      ticker,
      status: "done",
      answer: state.answer,
      citations: state.citations,
      timings_ms: state.timings_ms,
    };
    setMessages((m) => [...m, final]);
    reset();
  }

  if (state.kind === "error" && !messages.some((m) => m.id === errorKey(state))) {
    const err: ChatMessage = {
      id: errorKey(state),
      role: "assistant",
      ticker,
      status: "error",
      errorCode: state.code,
      errorMessage: state.message,
      citations: [],
    };
    setMessages((m) => [...m, err]);
    reset();
  }

  const isStreaming = state.kind === "streaming";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const t = ticker.trim().toUpperCase();
    const q = question.trim();
    if (!t || !q) return;

    setMessages((m) => [
      ...m,
      {
        id: `u-${Date.now()}`,
        role: "user",
        ticker: t,
        question: q,
        citations: [],
      },
    ]);
    submit({ ticker: t, question: q });
    setQuestion("");
  }

  return (
    <div className="flex h-full flex-col rounded-2xl border border-base-300 bg-base-200/50 backdrop-blur">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 && !inflight ? (
          <EmptyState onPick={(t, q) => { setTicker(t); setQuestion(q); }} />
        ) : (
          <MessageList
            messages={inflight ? [...messages, inflight] : messages}
          />
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-2 border-t border-base-300 bg-base-200/80 p-4 sm:flex-row sm:items-stretch"
      >
        <TickerInput value={ticker} onChange={setTicker} />
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about risks, revenue, strategy, anything in the filings..."
          className="input input-bordered flex-1"
          disabled={isStreaming}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={isStreaming || !ticker.trim() || !question.trim()}
        >
          {isStreaming ? "Working..." : "Ask"}
        </button>
      </form>
    </div>
  );
}

function finalKey(ticker: string, question: string, answer: string) {
  return `a-${ticker}-${question.length}-${answer.length}`;
}

function errorKey(s: { code: string; message: string }) {
  return `e-${s.code}-${s.message.length}`;
}
