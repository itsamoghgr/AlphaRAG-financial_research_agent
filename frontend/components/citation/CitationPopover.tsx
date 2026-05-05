"use client";

import type { Citation } from "@/lib/types";

export function CitationPopover({ citation }: { citation: Citation }) {
  return (
    <div className="absolute bottom-full left-1/2 z-20 mb-2 w-80 -translate-x-1/2 rounded-lg border border-base-300 bg-base-200 p-3 text-left shadow-lg">
      <div className="flex items-center justify-between text-xs text-base-content/60">
        <span>
          {citation.ticker} · {citation.filing}
        </span>
        <span className="opacity-70">{citation.section}</span>
      </div>
      <div className="mt-2 line-clamp-5 text-xs leading-relaxed text-base-content/90">
        {citation.snippet}
      </div>
      <div className="mt-2 text-right">
        <a
          href={citation.source_url}
          target="_blank"
          rel="noreferrer"
          className="link link-primary text-xs"
        >
          Open on SEC.gov
        </a>
      </div>
    </div>
  );
}
