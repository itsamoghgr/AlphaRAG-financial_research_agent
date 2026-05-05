"use client";

import type { Citation, StageEvent, StageName } from "@/lib/types";
import { UserMessage } from "@/components/chat/UserMessage";
import { AssistantMessage } from "@/components/chat/AssistantMessage";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  ticker: string;
  question?: string;
  status?: "streaming" | "done" | "error";
  stages?: StageEvent[];
  partial?: string;
  currentStage?: StageName;
  currentStageMessage?: string;
  answer?: string;
  citations: Citation[];
  timings_ms?: Record<string, number>;
  errorCode?: string;
  errorMessage?: string;
}

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      {messages.map((m) =>
        m.role === "user" ? (
          <UserMessage key={m.id} message={m} />
        ) : (
          <AssistantMessage key={m.id} message={m} />
        ),
      )}
    </div>
  );
}
