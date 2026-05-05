"use client";

const SAMPLES: Array<{ ticker: string; question: string }> = [
  { ticker: "AAPL", question: "What are the company's key risk factors?" },
  { ticker: "MSFT", question: "How does the company describe its AI strategy?" },
  { ticker: "TSLA", question: "What does management say about production capacity?" },
  { ticker: "NVDA", question: "What customer concentration risks does the company face?" },
];

export function EmptyState({
  onPick,
}: {
  onPick: (ticker: string, question: string) => void;
}) {
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center gap-6 text-center">
      <div>
        <h2 className="text-xl font-medium">Ask about a public company</h2>
        <p className="mt-2 text-sm text-base-content/60">
          Enter a ticker, ask a question, and get an answer grounded in the
          company&apos;s latest 10-K and 10-Q filings, with citations back to
          the source.
        </p>
      </div>
      <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-2">
        {SAMPLES.map((s) => (
          <button
            key={s.ticker + s.question}
            onClick={() => onPick(s.ticker, s.question)}
            className="rounded-lg border border-base-300 bg-base-100/40 px-4 py-3 text-left transition hover:border-primary/50 hover:bg-base-100/70"
          >
            <div className="text-xs font-mono text-primary">{s.ticker}</div>
            <div className="text-sm">{s.question}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
