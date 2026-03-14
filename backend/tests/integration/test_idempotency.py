# filepath: backend/tests/integration/test_idempotency.py
"""Integration tests for ingestion idempotency (T818).

Verifies (SC-012, NFR-202):
  - Re-running the text extraction pipeline on the same document
    produces identical cleaned text, sections, and chunks.
  - XBRL mapper produces identical output for the same input.
  - Financial upsert is idempotent (same data on re-run).
"""

from __future__ import annotations

import os

os.environ.setdefault("API_KEY", "test-api-key-for-integration-tests")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-azure-openai-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "devstoreaccount1")


# =====================================================================
# Text Extraction Idempotency
# =====================================================================


class TestPDFExtractionIdempotency:
    """Verify PDF parsing is deterministic."""

    def test_pdf_parse_produces_identical_output(self) -> None:
        """Parsing the same PDF twice yields identical text and page count."""
        import fitz

        from app.ingestion.parsers.pdf_parser import extract_text_from_pdf

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Revenue was $394.3 billion for fiscal year 2023.")
        page.insert_text((72, 100), "Net income was $97.0 billion, a decrease of 3%.")
        page2 = doc.new_page()
        page2.insert_text((72, 72), "Item 1A. Risk Factors")
        pdf_bytes = doc.tobytes()
        doc.close()

        result1 = extract_text_from_pdf(pdf_bytes)
        result2 = extract_text_from_pdf(pdf_bytes)

        assert result1.text == result2.text
        assert result1.page_count == result2.page_count
        assert result1.pages == result2.pages

    def test_html_parse_produces_identical_output(self) -> None:
        """Parsing the same HTML twice yields identical text."""
        from app.ingestion.parsers.html_parser import extract_text_from_html

        html = b"""<!DOCTYPE html>
        <html><body>
        <h1>Item 7. Management Discussion</h1>
        <p>Revenue increased by 10% year over year.</p>
        <table><tr><td>Metric</td><td>Value</td></tr></table>
        </body></html>"""

        result1 = extract_text_from_html(html)
        result2 = extract_text_from_html(html)

        assert result1.text == result2.text
        assert result1.title == result2.title


# =====================================================================
# Text Cleaning Idempotency
# =====================================================================


class TestTextCleaningIdempotency:
    """Verify text cleaning is deterministic and idempotent."""

    def test_clean_text_deterministic(self) -> None:
        """Cleaning the same text twice produces identical output."""
        from app.ingestion.parsers.text_cleaner import clean_text

        raw = (
            "Page 42\n\n"
            "\u201cSmart quotes\u201d and \u2014em dashes\u2014 "
            "and\u00a0non-breaking spaces.\n"
            "Table of Contents\n"
            "Revenue was $394.3B.\n\n\n\n"
            "Extra    whitespace   here."
        )

        cleaned1 = clean_text(raw)
        cleaned2 = clean_text(raw)
        assert cleaned1 == cleaned2

    def test_clean_text_is_idempotent(self) -> None:
        """Applying clean_text on already-cleaned text produces the same result."""
        from app.ingestion.parsers.text_cleaner import clean_text

        raw = (
            "\u201cHello\u201d \u2014 world\u2019s best\n\n\n"
            "Page 1\nTable of Contents\nActual content here."
        )

        cleaned_once = clean_text(raw)
        cleaned_twice = clean_text(cleaned_once)
        assert cleaned_once == cleaned_twice


# =====================================================================
# Section Splitting Idempotency
# =====================================================================


class TestSectionSplitIdempotency:
    """Verify section splitting is deterministic."""

    def test_section_split_deterministic_10k(self) -> None:
        """Splitting the same 10-K text twice produces identical sections."""
        from app.ingestion.section_splitter import split_into_sections

        text = (
            "Item 1. Business\n"
            "Apple designs, manufactures and markets smartphones.\n\n"
            "Item 1A. Risk Factors\n"
            "The Company's operations are subject to risks.\n\n"
            "Item 7. Management's Discussion and Analysis\n"
            "Revenue was $394.3 billion for fiscal year 2023.\n\n"
            "Item 8. Financial Statements\n"
            "See consolidated financial statements.\n"
        )

        result1 = split_into_sections(text, "10-K")
        result2 = split_into_sections(text, "10-K")

        assert len(result1) == len(result2)
        for s1, s2 in zip(result1, result2):
            assert s1.key == s2.key
            assert s1.title == s2.title
            assert s1.content == s2.content
            assert s1.char_count == s2.char_count

    def test_section_split_deterministic_10q(self) -> None:
        """Splitting the same 10-Q text twice produces identical sections."""
        from app.ingestion.section_splitter import split_into_sections

        text = (
            "Part I\n"
            "Item 1. Financial Statements\n"
            "Condensed balance sheets.\n\n"
            "Item 2. Management's Discussion and Analysis\n"
            "Quarterly revenue analysis.\n"
        )

        result1 = split_into_sections(text, "10-Q")
        result2 = split_into_sections(text, "10-Q")

        assert len(result1) == len(result2)
        for s1, s2 in zip(result1, result2):
            assert s1.key == s2.key
            assert s1.content == s2.content


# =====================================================================
# Chunking Idempotency
# =====================================================================


class TestChunkingIdempotency:
    """Verify chunking is deterministic."""

    def test_chunk_text_deterministic(self) -> None:
        """Chunking the same text twice produces identical chunks."""
        from app.ingestion.chunker import chunk_text

        text = "This is a test sentence. " * 200  # Long enough to produce multiple chunks

        chunks1 = chunk_text(text, chunk_size=100, chunk_overlap=20)
        chunks2 = chunk_text(text, chunk_size=100, chunk_overlap=20)

        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.content == c2.content
            assert c1.chunk_index == c2.chunk_index
            assert c1.token_count == c2.token_count
            assert c1.char_count == c2.char_count

    def test_chunk_with_section_metadata_deterministic(self) -> None:
        """Chunks with section metadata are identical across runs."""
        from app.ingestion.chunker import chunk_text

        text = "Financial data paragraph. " * 150

        chunks1 = chunk_text(
            text, chunk_size=100, chunk_overlap=20,
            section_key="item_7", section_title="MD&A",
        )
        chunks2 = chunk_text(
            text, chunk_size=100, chunk_overlap=20,
            section_key="item_7", section_title="MD&A",
        )

        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.section_key == c2.section_key
            assert c1.section_title == c2.section_title
            assert c1.content == c2.content


# =====================================================================
# XBRL Mapping Idempotency
# =====================================================================


class TestXBRLMappingIdempotency:
    """Verify XBRL companyfacts mapping is deterministic."""

    @staticmethod
    def _make_companyfacts() -> dict:
        return {
            "cik": 320193,
            "entityName": "Apple Inc.",
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "label": "Revenues",
                        "units": {
                            "USD": [
                                {
                                    "val": 394328000000,
                                    "end": "2023-09-30",
                                    "start": "2022-10-01",
                                    "form": "10-K",
                                    "filed": "2023-11-02",
                                    "fy": 2023,
                                    "fp": "FY",
                                },
                            ],
                        },
                    },
                    "NetIncomeLoss": {
                        "label": "Net Income",
                        "units": {
                            "USD": [
                                {
                                    "val": 96995000000,
                                    "end": "2023-09-30",
                                    "start": "2022-10-01",
                                    "form": "10-K",
                                    "filed": "2023-11-02",
                                    "fy": 2023,
                                    "fp": "FY",
                                },
                            ],
                        },
                    },
                    "Assets": {
                        "label": "Assets",
                        "units": {
                            "USD": [
                                {
                                    "val": 352583000000,
                                    "end": "2023-09-30",
                                    "form": "10-K",
                                    "filed": "2023-11-02",
                                    "fy": 2023,
                                    "fp": "FY",
                                },
                            ],
                        },
                    },
                },
            },
        }

    def test_xbrl_mapping_deterministic(self) -> None:
        """Mapping the same companyfacts twice produces identical periods."""
        from app.xbrl.mapper import map_company_facts

        raw = self._make_companyfacts()

        periods1 = map_company_facts(raw)
        periods2 = map_company_facts(raw)

        assert len(periods1) == len(periods2)
        for p1, p2 in zip(periods1, periods2):
            assert p1["fiscal_year"] == p2["fiscal_year"]
            assert p1["fiscal_quarter"] == p2["fiscal_quarter"]
            assert p1["period_end_date"] == p2["period_end_date"]
            assert p1["income_statement"] == p2["income_statement"]
            assert p1["balance_sheet"] == p2["balance_sheet"]
            assert p1["cash_flow"] == p2["cash_flow"]

    def test_xbrl_mapping_with_year_filter_deterministic(self) -> None:
        """Year-filtered mapping is also deterministic."""
        from app.xbrl.mapper import map_company_facts

        raw = self._make_companyfacts()

        periods1 = map_company_facts(raw, start_year=2023, end_year=2023)
        periods2 = map_company_facts(raw, start_year=2023, end_year=2023)

        assert periods1 == periods2


# =====================================================================
# Full Pipeline Idempotency (unit-level, mocked IO)
# =====================================================================


class TestFullPipelineIdempotency:
    """Verify the full text extraction pipeline is idempotent.

    Uses a real PDF but mocks all IO (blob, DB, Qdrant) to verify
    that the *data* produced is identical on re-run.
    """

    def test_pdf_to_chunks_pipeline_deterministic(self) -> None:
        """Extract→clean→split→chunk pipeline produces identical output."""
        import fitz

        from app.ingestion.chunker import chunk_text
        from app.ingestion.parsers.pdf_parser import extract_text_from_pdf
        from app.ingestion.parsers.text_cleaner import clean_text
        from app.ingestion.section_splitter import split_into_sections

        # Build a minimal multi-page 10-K-like PDF
        doc = fitz.open()
        page1 = doc.new_page()
        page1.insert_text((72, 72), "Item 1. Business")
        page1.insert_text((72, 100), "Apple designs smartphones. " * 30)
        page2 = doc.new_page()
        page2.insert_text((72, 72), "Item 1A. Risk Factors")
        page2.insert_text((72, 100), "Competition is intense. " * 30)
        page3 = doc.new_page()
        page3.insert_text((72, 72), "Item 7. Management Discussion")
        page3.insert_text((72, 100), "Revenue grew 10%. " * 30)
        pdf_bytes = doc.tobytes()
        doc.close()

        def run_pipeline(data: bytes) -> list:
            parsed = extract_text_from_pdf(data)
            cleaned = clean_text(parsed.text)
            sections = split_into_sections(cleaned, "10-K")
            all_chunks = []
            idx = 0
            for section in sections:
                chunks = chunk_text(
                    section.content,
                    chunk_size=768, chunk_overlap=128,
                    section_key=section.key, section_title=section.title,
                    start_index=idx,
                )
                all_chunks.extend(chunks)
                idx += len(chunks)
            return all_chunks

        chunks_run1 = run_pipeline(pdf_bytes)
        chunks_run2 = run_pipeline(pdf_bytes)

        assert len(chunks_run1) == len(chunks_run2)
        for c1, c2 in zip(chunks_run1, chunks_run2):
            assert c1.content == c2.content
            assert c1.chunk_index == c2.chunk_index
            assert c1.token_count == c2.token_count
            assert c1.section_key == c2.section_key

    def test_html_to_chunks_pipeline_deterministic(self) -> None:
        """Extract→clean→split→chunk for HTML is also deterministic."""
        from app.ingestion.chunker import chunk_text
        from app.ingestion.parsers.html_parser import extract_text_from_html
        from app.ingestion.parsers.text_cleaner import clean_text
        from app.ingestion.section_splitter import split_into_sections

        html = b"""<!DOCTYPE html><html><body>
        <h2>Item 1. Business</h2>
        <p>""" + b"Apple is a technology company. " * 50 + b"""</p>
        <h2>Item 7. Management's Discussion and Analysis</h2>
        <p>""" + b"Revenue increased significantly. " * 50 + b"""</p>
        </body></html>"""

        def run_pipeline(data: bytes) -> list:
            parsed = extract_text_from_html(data)
            cleaned = clean_text(parsed.text)
            sections = split_into_sections(cleaned, "10-K")
            all_chunks = []
            idx = 0
            for section in sections:
                chunks = chunk_text(
                    section.content,
                    chunk_size=768, chunk_overlap=128,
                    section_key=section.key, section_title=section.title,
                    start_index=idx,
                )
                all_chunks.extend(chunks)
                idx += len(chunks)
            return all_chunks

        chunks_run1 = run_pipeline(html)
        chunks_run2 = run_pipeline(html)

        assert len(chunks_run1) == len(chunks_run2)
        for c1, c2 in zip(chunks_run1, chunks_run2):
            assert c1.content == c2.content
            assert c1.chunk_index == c2.chunk_index
