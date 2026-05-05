"""Smoke tests for FilingParser. Uses a tiny synthetic filing fixture."""

from __future__ import annotations

from alpharag.ingestion.parser import FilingParser


def _fake_10k_html() -> str:
    return """
    <html><body>
      <p>Cover page boilerplate that should not become a section.</p>
      <h2>Item 1. Business</h2>
      <p>We are a company that does things. """ + ("Lorem ipsum dolor sit amet. " * 50) + """</p>
      <h2>Item 1A. Risk Factors</h2>
      <p>Our business is subject to many risks. """ + ("Risk text. " * 50) + """</p>
      <h2>Item 7. Management's Discussion and Analysis</h2>
      <p>We discuss our results here. """ + ("MD&A text. " * 50) + """</p>
      <table><tr><td>this table should be stripped</td></tr></table>
      <h2>Item 9A. Controls and Procedures</h2>
      <p>Our controls are effective. """ + ("Controls text. " * 50) + """</p>
    </body></html>
    """


def test_parser_splits_into_known_items():
    parsed = FilingParser().parse(_fake_10k_html())
    assert not parsed.is_fallback
    assert parsed.table_count == 1
    item_codes = [s.item_code for s in parsed.sections]
    # We should see Item 1, 1A, 7, 9A (Item 5 etc. are filtered out by KEEP_ITEMS).
    assert "Item 1" in item_codes
    assert "Item 1A" in item_codes
    assert "Item 7" in item_codes
    assert "Item 9A" in item_codes
    # Sections should have non-trivial bodies.
    for s in parsed.sections:
        assert len(s.text) > 200
        assert s.title.startswith("Item")


def test_parser_falls_back_when_no_items():
    html = "<html><body><p>This document has no Item anchors at all. " + ("blah " * 100) + "</p></body></html>"
    parsed = FilingParser().parse(html)
    assert parsed.is_fallback
    assert len(parsed.sections) == 1
    assert parsed.sections[0].title == "Document"


def test_parser_dedupes_toc_versus_body():
    html = """
    <html><body>
      <h2>Item 1A</h2>
      <p>TOC entry, very short.</p>
      <h2>Item 1A. Risk Factors</h2>
      <p>The real body. """ + ("Detailed risk discussion. " * 100) + """</p>
    </body></html>
    """
    parsed = FilingParser().parse(html)
    risk_sections = [s for s in parsed.sections if s.item_code == "Item 1A"]
    assert len(risk_sections) == 1
    assert "Detailed risk discussion." in risk_sections[0].text
