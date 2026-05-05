"""HTML -> sections parser for SEC 10-K and 10-Q filings.

Strategy:
1. Strip scripts, styles, and tables (tables are out of scope for v1; we log
   the count so the UI can warn the user).
2. Extract text while preserving paragraph breaks.
3. Find Item anchors (`Item 1`, `Item 1A`, `Item 7`, etc.) using a regex
   tuned for both 10-K and 10-Q numbering conventions. SEC formats vary
   wildly across filers and years; this regex is intentionally permissive.
4. Slice the text between consecutive Item anchors. The first chunk before
   any Item anchor is dropped (it's usually the cover page, which is mostly
   tables and boilerplate).
5. If no anchors are found (very old or unusual filings), return one
   "Document" section containing the whole text. The caller can decide
   whether to fail or proceed.

We deliberately do NOT use heavy parsers like `unstructured` -- they're
slow and add 100MB of dependencies. selectolax is ~5x faster than
BeautifulSoup for our use case.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from selectolax.parser import HTMLParser

from alpharag.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ParsedSection:
    item_code: str | None  # e.g. "Item 1A"; None for whole-document fallback
    title: str  # e.g. "Item 1A. Risk Factors"
    char_start: int
    char_end: int
    text: str


@dataclass(frozen=True, slots=True)
class ParsedFiling:
    sections: list[ParsedSection]
    full_text: str
    table_count: int
    is_fallback: bool  # True if no Item anchors were found


# Match Item anchors permissively. Examples we want to match:
#   "Item 1.", "ITEM 1A.", "Item 7A. Quantitative...", "Item 1A: Risk Factors"
# Anchored to start-of-line-ish (after optional whitespace) with Item then a
# digit-letter combo. Captures the item code (e.g. "1A") for keying.
ITEM_PATTERN = re.compile(
    r"(?im)^\s{0,4}item\s+(\d{1,2}[A-Z]?)\.?\s*[:\.\-]?\s*([^\n]{0,120})$"
)

# Common known titles for 10-K items, used to make titles nicer when the
# source line is just "Item 1A." with no descriptive text on the same line.
KNOWN_ITEM_TITLES: dict[str, str] = {
    "1": "Business",
    "1A": "Risk Factors",
    "1B": "Unresolved Staff Comments",
    "2": "Properties",
    "3": "Legal Proceedings",
    "4": "Mine Safety Disclosures",
    "5": "Market for Registrant's Common Equity",
    "6": "Selected Financial Data",
    "7": "Management's Discussion and Analysis",
    "7A": "Quantitative and Qualitative Disclosures About Market Risk",
    "8": "Financial Statements and Supplementary Data",
    "9": "Changes in and Disagreements With Accountants",
    "9A": "Controls and Procedures",
    "9B": "Other Information",
    "10": "Directors, Executive Officers and Corporate Governance",
    "11": "Executive Compensation",
    "12": "Security Ownership of Certain Beneficial Owners",
    "13": "Certain Relationships and Related Transactions",
    "14": "Principal Accountant Fees and Services",
    "15": "Exhibits and Financial Statement Schedules",
}

# Items we keep for retrieval. Cover-page boilerplate (Item 5 of 10-K, etc.)
# adds noise without much value for an MVP focused on substantive analysis.
KEEP_ITEMS: set[str] = {"1", "1A", "2", "3", "7", "7A", "8", "9A"}


class FilingParser:
    def parse(self, html: str) -> ParsedFiling:
        text, table_count = self._html_to_text(html)
        anchors = self._find_item_anchors(text)
        if not anchors:
            logger.warning("parser_fallback_no_items_found", text_len=len(text))
            return ParsedFiling(
                sections=[
                    ParsedSection(
                        item_code=None,
                        title="Document",
                        char_start=0,
                        char_end=len(text),
                        text=text,
                    )
                ],
                full_text=text,
                table_count=table_count,
                is_fallback=True,
            )

        sections: list[ParsedSection] = []
        for i, (item_code, title, anchor_start) in enumerate(anchors):
            section_end = (
                anchors[i + 1][2] if i + 1 < len(anchors) else len(text)
            )
            body = text[anchor_start:section_end].strip()
            if not body or len(body) < 200:
                # Too short to be the real section -- often a TOC entry.
                continue
            if item_code not in KEEP_ITEMS:
                continue
            sections.append(
                ParsedSection(
                    item_code=f"Item {item_code}",
                    title=self._make_title(item_code, title),
                    char_start=anchor_start,
                    char_end=section_end,
                    text=body,
                )
            )

        # Deduplicate by item_code, keeping the LAST (and longest) occurrence.
        # Filings typically have a TOC entry and a body entry for each item;
        # the body is later and longer.
        by_code: dict[str, ParsedSection] = {}
        for s in sections:
            existing = by_code.get(s.item_code or "")
            if existing is None or len(s.text) > len(existing.text):
                by_code[s.item_code or ""] = s
        deduped = sorted(by_code.values(), key=lambda s: s.char_start)

        if not deduped:
            logger.warning(
                "parser_no_sections_after_filter",
                anchor_count=len(anchors),
                text_len=len(text),
            )
            return ParsedFiling(
                sections=[
                    ParsedSection(
                        item_code=None,
                        title="Document",
                        char_start=0,
                        char_end=len(text),
                        text=text,
                    )
                ],
                full_text=text,
                table_count=table_count,
                is_fallback=True,
            )

        return ParsedFiling(
            sections=deduped,
            full_text=text,
            table_count=table_count,
            is_fallback=False,
        )

    @staticmethod
    def _html_to_text(html: str) -> tuple[str, int]:
        tree = HTMLParser(html)
        # Strip noise
        for sel in ("script", "style", "noscript"):
            for n in tree.css(sel):
                n.decompose()
        # Count and strip tables (out of scope for v1)
        table_nodes = tree.css("table")
        table_count = len(table_nodes)
        for n in table_nodes:
            n.decompose()

        text = tree.text(separator="\n")
        # Collapse runs of whitespace within lines but preserve newlines.
        text = re.sub(r"[ \t\xa0]+", " ", text)
        # Collapse 3+ blank lines into 2.
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        return text, table_count

    @staticmethod
    def _find_item_anchors(text: str) -> list[tuple[str, str, int]]:
        """Returns list of (item_code_normalized, title_part, char_start)."""
        anchors: list[tuple[str, str, int]] = []
        for m in ITEM_PATTERN.finditer(text):
            code = m.group(1).upper()
            title_part = (m.group(2) or "").strip().rstrip(".:- ")
            anchors.append((code, title_part, m.start()))
        return anchors

    @staticmethod
    def _make_title(item_code: str, title_from_html: str) -> str:
        title = title_from_html.strip()
        if not title or len(title) < 4:
            title = KNOWN_ITEM_TITLES.get(item_code, "")
        if title:
            return f"Item {item_code}. {title}"
        return f"Item {item_code}"
