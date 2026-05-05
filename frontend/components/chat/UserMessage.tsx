"use client";

import type { ChatMessage } from "@/components/chat/MessageList";

export function UserMessage({ message }: { message: ChatMessage }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary/15 px-4 py-3">
        <div className="text-xs font-mono text-primary">{message.ticker}</div>
        <div className="mt-1 whitespace-pre-wrap text-sm">
          {message.question}
        </div>
      </div>
    </div>
  );
}
