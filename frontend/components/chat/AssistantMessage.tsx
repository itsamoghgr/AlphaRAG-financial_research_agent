"use client";

import type { ChatMessage } from "@/components/chat/MessageList";
import { IngestionProgress } from "@/components/chat/IngestionProgress";
import { CitationList } from "@/components/citation/CitationList";
import { CitedAnswer } from "@/components/citation/CitedAnswer";

export function AssistantMessage({ message }: { message: ChatMessage }) {
  if (message.status === "error") {
    return (
      <div className="rounded-2xl border border-error/40 bg-error/10 px-4 py-3 text-sm">
        <div className="font-medium text-error">Something went wrong</div>
        <div className="mt-1 text-base-content/70">
          {message.errorMessage}
          {message.errorCode ? (
            <span className="ml-2 text-xs opacity-60">
              ({message.errorCode})
            </span>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl rounded-bl-sm bg-base-100/40 px-4 py-3">
      <div className="mb-2 flex items-center gap-2">
        <div className="text-xs font-mono text-secondary">
          {message.ticker}
        </div>
        {message.timings_ms ? (
          <div className="text-xs text-base-content/40">
            {message.timings_ms.total ?? 0} ms
          </div>
        ) : null}
      </div>

      {message.status === "streaming" && (
        <IngestionProgress
          stages={message.stages ?? []}
          currentStage={message.currentStage}
          currentStageMessage={message.currentStageMessage}
        />
      )}

      {message.status === "streaming" && message.partial ? (
        <div className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">
          {message.partial}
          <span className="ml-1 inline-block h-3 w-2 animate-pulse bg-base-content/50 align-middle" />
        </div>
      ) : null}

      {message.status === "done" && message.answer ? (
        <>
          <CitedAnswer
            answer={message.answer}
            citations={message.citations}
          />
          <CitationList citations={message.citations} />
        </>
      ) : null}
    </div>
  );
}
