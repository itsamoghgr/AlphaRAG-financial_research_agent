import { ChatContainer } from "@/components/chat/ChatContainer";

export default function HomePage() {
  return (
    <main className="mx-auto flex h-screen max-w-5xl flex-col px-4 py-6">
      <header className="mb-4 flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">AlphaRAG</h1>
          <p className="text-sm text-base-content/60">
            Ask questions about any US public company. Answers are grounded in
            SEC filings, with click-through citations.
          </p>
        </div>
        <a
          href="https://www.sec.gov/edgar"
          target="_blank"
          rel="noreferrer"
          className="link link-hover text-xs text-base-content/50"
        >
          Powered by SEC EDGAR
        </a>
      </header>
      <div className="flex-1 min-h-0">
        <ChatContainer />
      </div>
    </main>
  );
}
