export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface CompanyStatus {
  ticker: string;
  cik: string | null;
  name: string | null;
  is_cached: boolean;
  last_ingested_at: string | null;
  filings: Array<{
    id: string;
    form_type: string;
    filing_date: string;
    period_of_report: string | null;
    accession_no: string;
    source_url: string;
  }>;
}

export interface SectionContent {
  id: string;
  item_code: string | null;
  title: string;
  text: string;
  char_start: number;
  char_end: number;
}

export async function fetchCompanyStatus(
  ticker: string,
): Promise<CompanyStatus> {
  const r = await fetch(
    `${API_BASE_URL}/api/companies/${encodeURIComponent(ticker)}/status`,
  );
  if (!r.ok) {
    throw new Error(`Status request failed: ${r.status}`);
  }
  return r.json();
}

export async function fetchSection(
  filingId: string,
  sectionId: string,
): Promise<SectionContent> {
  const r = await fetch(
    `${API_BASE_URL}/api/filings/${encodeURIComponent(
      filingId,
    )}/sections/${encodeURIComponent(sectionId)}`,
  );
  if (!r.ok) {
    throw new Error(`Section request failed: ${r.status}`);
  }
  return r.json();
}
