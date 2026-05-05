// Mirrors backend/src/alpharag/api/schemas/*.py.
// Keep this in sync when those change.

export interface Citation {
  marker: string; // "c1", "c2", ...
  chunk_id: string;
  section_id: string;
  ticker: string;
  filing_id: string;
  filing: string;
  section: string;
  snippet: string;
  source_url: string;
  char_start: number;
  char_end: number;
}

export interface QueryAnswer {
  answer: string;
  citations: Citation[];
  timings_ms: Record<string, number>;
}

export type StageName =
  | "resolving"
  | "cache_hit"
  | "fetching"
  | "parsing"
  | "chunking"
  | "embedding"
  | "persisting"
  | "retrieving"
  | "generating"
  | "done"
  | "error";

export interface StageEvent {
  stage: StageName;
  message: string;
  data?: Record<string, unknown>;
}

export interface TokenEvent {
  text: string;
}

export interface ErrorEvent {
  code: string;
  message: string;
}

// Friendly labels rendered in IngestionProgress.
export const STAGE_LABELS: Record<StageName, string> = {
  resolving: "Looking up company",
  cache_hit: "Filings already loaded",
  fetching: "Downloading filings from SEC",
  parsing: "Parsing filings into sections",
  chunking: "Splitting into searchable chunks",
  embedding: "Creating embeddings",
  persisting: "Saving to database",
  retrieving: "Searching filings",
  generating: "Writing the answer",
  done: "Done",
  error: "Something went wrong",
};

// Order used to render the stage timeline.
export const STAGE_ORDER: StageName[] = [
  "resolving",
  "fetching",
  "parsing",
  "chunking",
  "embedding",
  "persisting",
  "retrieving",
  "generating",
];
