"use client";

import type { Citation } from "@/lib/types";

export function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <details className="mt-4 text-xs text-base-content/70">
      <summary className="cursor-pointer select-none">
        {citations.length} source{citations.length === 1 ? "" : "s"}
      </summary>
      <ol className="mt-2 list-decimal space-y-2 pl-5">
        {citations.map((c) => (
          <li key={c.chunk_id}>
            <span className="font-mono text-primary">[{c.marker}]</span>{" "}
            <span className="text-base-content/80">
              {c.ticker} · {c.filing} · {c.section}
            </span>
            <div className="mt-0.5 line-clamp-2 italic">{c.snippet}</div>
            <a
              href={c.source_url}
              target="_blank"
              rel="noreferrer"
              className="link link-hover text-primary"
            >
              Source
            </a>
          </li>
        ))}
      </ol>
    </details>
  );
}
