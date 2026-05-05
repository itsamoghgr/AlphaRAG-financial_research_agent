"use client";

import { useState } from "react";
import type { Citation } from "@/lib/types";
import { CitationPopover } from "@/components/citation/CitationPopover";
import { FilingViewer } from "@/components/filing/FilingViewer";

export function CitationChip({ citation }: { citation: Citation }) {
  const [hover, setHover] = useState(false);
  const [open, setOpen] = useState(false);
  const num = citation.marker.replace(/^c/, "");
  return (
    <>
      <span className="relative inline-block">
        <button
          type="button"
          className="citation-chip"
          onMouseEnter={() => setHover(true)}
          onMouseLeave={() => setHover(false)}
          onFocus={() => setHover(true)}
          onBlur={() => setHover(false)}
          onClick={() => setOpen(true)}
          aria-label={`Citation ${num}: ${citation.section}`}
        >
          {num}
        </button>
        {hover ? <CitationPopover citation={citation} /> : null}
      </span>
      {open ? (
        <FilingViewer citation={citation} onClose={() => setOpen(false)} />
      ) : null}
    </>
  );
}
