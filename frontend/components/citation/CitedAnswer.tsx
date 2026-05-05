"use client";

import type { Citation } from "@/lib/types";
import { CitationChip } from "@/components/citation/CitationChip";

interface Props {
  answer: string;
  citations: Citation[];
}

// Replaces every [cN] marker in the answer with an interactive chip.
// Falls back gracefully if a marker doesn't have a matching citation.
export function CitedAnswer({ answer, citations }: Props) {
  const byMarker = new Map(citations.map((c) => [c.marker, c]));
  const parts: Array<string | Citation> = [];
  const re = /\[(c\d+)\]/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(answer)) !== null) {
    if (match.index > lastIndex) {
      parts.push(answer.slice(lastIndex, match.index));
    }
    const cit = byMarker.get(match[1]);
    if (cit) {
      parts.push(cit);
    } else {
      parts.push(match[0]);
    }
    lastIndex = re.lastIndex;
  }
  if (lastIndex < answer.length) {
    parts.push(answer.slice(lastIndex));
  }

  return (
    <div className="whitespace-pre-wrap text-sm leading-relaxed">
      {parts.map((p, i) =>
        typeof p === "string" ? (
          <span key={i}>{p}</span>
        ) : (
          <CitationChip key={i} citation={p} />
        ),
      )}
    </div>
  );
}
