"use client";

import { useEffect, useState } from "react";
import { fetchSection, type SectionContent } from "@/lib/api";
import type { Citation } from "@/lib/types";

interface Props {
  citation: Citation | null;
  onClose: () => void;
}

export function FilingViewer({ citation, onClose }: Props) {
  const [section, setSection] = useState<SectionContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!citation) {
      setSection(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchSection(citation.filing_id, citation.section_id)
      .then((s) => {
        if (!cancelled) setSection(s);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [citation]);

  if (!citation) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-3xl flex-col rounded-2xl border border-base-300 bg-base-100 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between border-b border-base-300 px-5 py-4">
          <div>
            <div className="text-xs font-mono text-primary">
              {citation.ticker}
            </div>
            <div className="mt-0.5 text-sm">
              {citation.filing} &middot; {citation.section}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={citation.source_url}
              target="_blank"
              rel="noreferrer"
              className="btn btn-xs"
            >
              View on SEC.gov
            </a>
            <button
              type="button"
              className="btn btn-xs btn-ghost"
              onClick={onClose}
              aria-label="Close"
            >
              Close
            </button>
          </div>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4 text-sm leading-relaxed">
          {loading ? (
            <div className="flex items-center gap-2 text-base-content/60">
              <span className="loading loading-spinner loading-sm" />
              Loading section...
            </div>
          ) : error ? (
            <div className="text-error">
              Could not load this section: {error}
              <p className="mt-2 text-base-content/70">
                The cited snippet is shown below. You can also open the full
                filing on SEC.gov above.
              </p>
              <blockquote className="mt-3 border-l-4 border-primary/60 pl-3 italic">
                {citation.snippet}
              </blockquote>
            </div>
          ) : section ? (
            <SectionWithHighlight section={section} citation={citation} />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function SectionWithHighlight({
  section,
  citation,
}: {
  section: SectionContent;
  citation: Citation;
}) {
  // Highlight the cited substring within the section text.
  const start = Math.max(0, citation.char_start - section.char_start);
  const end = Math.min(
    section.text.length,
    citation.char_end - section.char_start,
  );
  if (end <= start) {
    return <pre className="whitespace-pre-wrap font-sans">{section.text}</pre>;
  }
  const before = section.text.slice(0, start);
  const middle = section.text.slice(start, end);
  const after = section.text.slice(end);
  return (
    <pre className="whitespace-pre-wrap font-sans">
      {before}
      <mark className="rounded bg-primary/20 px-0.5 text-base-content">
        {middle}
      </mark>
      {after}
    </pre>
  );
}

