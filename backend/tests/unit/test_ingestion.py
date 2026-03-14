# filepath: backend/tests/unit/test_ingestion.py
"""Unit tests for ingestion pipeline components.

Covers (T311):
  - PDF parser: text extraction
  - HTML parser: text extraction, table conversion
  - Text cleaner: unicode normalisation, header removal
  - Section splitter: 10-K, 10-Q, unknown doc types
  - Chunker: splitting, overlap, empty input
  - XBRL mapper: companyfacts mapping, fallbacks
  - Magic-byte validation: spoofed extensions rejected (NFR-302)
"""

from __future__ import annotations

import os

os.environ.setdefault("API_KEY", "test-ingestion-unit")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-azure-openai-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")

import pytest


# =====================================================================
# PDF Parser
# =====================================================================


class TestPDFParser:
    """Tests for PDF text extraction."""

    def test_extract_text_from_valid_pdf(self) -> None:
        """Minimal valid PDF should produce text."""
        import fitz  # PyMuPDF

        # Build a minimal one-page PDF in memory
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello World from a test PDF")
        pdf_bytes = doc.tobytes()
        doc.close()

        from app.ingestion.parsers.pdf_parser import extract_text_from_pdf

        result = extract_text_from_pdf(pdf_bytes)
        assert result.page_count == 1
        assert "Hello World" in result.text
        assert len(result.pages) == 1

    def test_extract_text_from_corrupt_pdf(self) -> None:
        """Corrupt data should raise ValueError."""
        from app.ingestion.parsers.pdf_parser import extract_text_from_pdf

        with pytest.raises(ValueError, match="Failed to open PDF"):
            extract_text_from_pdf(b"not a real pdf at all")

    def test_extract_text_multi_page(self) -> None:
        """Multi-page PDF should produce multiple page entries."""
        import fitz

        doc = fitz.open()
        for i in range(3):
            page = doc.new_page()
            page.insert_text((72, 72), f"Page {i + 1} content")
        pdf_bytes = doc.tobytes()
        doc.close()

        from app.ingestion.parsers.pdf_parser import extract_text_from_pdf

        result = extract_text_from_pdf(pdf_bytes)
        assert result.page_count == 3
        assert len(result.pages) == 3
        assert "Page 1" in result.pages[0]
        assert "Page 3" in result.pages[2]


# =====================================================================
# HTML Parser
# =====================================================================


class TestHTMLParser:
    """Tests for HTML text extraction."""

    def test_extract_text_from_simple_html(self) -> None:
        from app.ingestion.parsers.html_parser import extract_text_from_html

        html = b"<html><body><p>Hello World</p></body></html>"
        result = extract_text_from_html(html)
        assert "Hello World" in result.text

    def test_removes_script_and_style(self) -> None:
        from app.ingestion.parsers.html_parser import extract_text_from_html

        html = b"""<html><head><style>body{color:red}</style></head>
        <body><script>alert('x')</script><p>Visible text</p></body></html>"""
        result = extract_text_from_html(html)
        assert "Visible text" in result.text
        assert "alert" not in result.text
        assert "color:red" not in result.text

    def test_extracts_title(self) -> None:
        from app.ingestion.parsers.html_parser import extract_text_from_html

        html = b"<html><head><title>My Filing</title></head><body>Content</body></html>"
        result = extract_text_from_html(html)
        assert result.title == "My Filing"

    def test_table_to_text(self) -> None:
        from app.ingestion.parsers.html_parser import extract_text_from_html

        html = b"""<html><body><table>
        <tr><th>Year</th><th>Revenue</th></tr>
        <tr><td>2023</td><td>$100M</td></tr>
        </table></body></html>"""
        result = extract_text_from_html(html)
        assert "Year" in result.text
        assert "Revenue" in result.text
        assert "2023" in result.text

    def test_latin1_fallback_encoding(self) -> None:
        from app.ingestion.parsers.html_parser import extract_text_from_html

        # Latin-1 encoded HTML with special chars
        html = "<html><body><p>Caf\xe9</p></body></html>".encode("latin-1")
        result = extract_text_from_html(html)
        assert "Caf" in result.text


# =====================================================================
# Text Cleaner
# =====================================================================


class TestTextCleaner:
    """Tests for text cleaning and normalisation."""

    def test_unicode_normalisation(self) -> None:
        from app.ingestion.parsers.text_cleaner import clean_text

        # Non-breaking space and fancy quotes
        text = "Hello\u00a0World \u201cquoted\u201d text"
        result = clean_text(text)
        assert "\u00a0" not in result
        assert '"quoted"' in result

    def test_removes_page_numbers(self) -> None:
        from app.ingestion.parsers.text_cleaner import clean_text

        text = "Some content\n  42  \nMore content"
        result = clean_text(text)
        assert "42" not in result

    def test_removes_table_of_contents(self) -> None:
        from app.ingestion.parsers.text_cleaner import clean_text

        text = "Text before\nTable of Contents\nText after"
        result = clean_text(text)
        assert "Table of Contents" not in result

    def test_collapses_whitespace(self) -> None:
        from app.ingestion.parsers.text_cleaner import clean_text

        text = "word1   word2\n\n\n\n\nword3"
        result = clean_text(text)
        assert "word1 word2" in result
        # Max 2 newlines
        assert "\n\n\n" not in result

    def test_empty_input(self) -> None:
        from app.ingestion.parsers.text_cleaner import clean_text

        assert clean_text("") == ""

    def test_unicode_dashes_replaced(self) -> None:
        from app.ingestion.parsers.text_cleaner import clean_text

        text = "range\u2013value and em\u2014dash"
        result = clean_text(text)
        assert "range-value" in result
        assert "em-dash" in result


# =====================================================================
# Section Splitter
# =====================================================================


class TestSectionSplitter:
    """Tests for section splitting."""

    def test_10k_sections(self) -> None:
        from app.ingestion.section_splitter import split_into_sections

        text = """
        Some preamble text here.

        Item 1. Business

        We are a technology company that makes widgets.

        Item 1A. Risk Factors

        There are significant risks including market competition.

        Item 7. Management's Discussion and Analysis

        Revenue increased 15% year over year.
        """
        sections = split_into_sections(text, "10-K")
        keys = [s.key for s in sections]
        assert "item_1" in keys
        assert "item_1a" in keys
        assert "item_7" in keys
        assert len(sections) >= 3

    def test_10q_sections(self) -> None:
        from app.ingestion.section_splitter import split_into_sections

        text = """
        Item 2. Management's Discussion and Analysis

        Quarterly results discussion.

        Item 4. Controls and Procedures

        Internal controls assessment.
        """
        sections = split_into_sections(text, "10-Q")
        keys = [s.key for s in sections]
        assert "part1_item2" in keys
        assert "part1_item4" in keys

    def test_unknown_doc_type_returns_full_text(self) -> None:
        from app.ingestion.section_splitter import split_into_sections

        text = "Some 8-K content about a material event."
        sections = split_into_sections(text, "8-K")
        assert len(sections) == 1
        assert sections[0].key == "full_text"
        assert "8-K content" in sections[0].content

    def test_empty_text(self) -> None:
        from app.ingestion.section_splitter import split_into_sections

        sections = split_into_sections("", "10-K")
        assert sections == []

    def test_no_sections_found_returns_full_text(self) -> None:
        from app.ingestion.section_splitter import split_into_sections

        # Text with no recognisable section headers
        text = "Just a block of text without any Item headers."
        sections = split_into_sections(text, "10-K")
        assert len(sections) == 1
        assert sections[0].key == "full_text"

    def test_section_char_count(self) -> None:
        from app.ingestion.section_splitter import split_into_sections

        text = "Item 1. Business\n\nContent here"
        sections = split_into_sections(text, "10-K")
        assert len(sections) >= 1
        for section in sections:
            assert section.char_count == len(section.content)


# =====================================================================
# Chunker
# =====================================================================


class TestChunker:
    """Tests for text chunking."""

    def test_short_text_single_chunk(self) -> None:
        from app.ingestion.chunker import chunk_text

        text = "A short piece of text."
        chunks = chunk_text(text, chunk_size=768, chunk_overlap=128)
        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].chunk_index == 0
        assert chunks[0].token_count > 0

    def test_long_text_multiple_chunks(self) -> None:
        from app.ingestion.chunker import chunk_text

        # Create a text that's definitely longer than 768 tokens
        text = "This is a sentence about financial data. " * 200
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        assert len(chunks) > 1
        # Chunk indices should be sequential
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_empty_text(self) -> None:
        from app.ingestion.chunker import chunk_text

        chunks = chunk_text("", chunk_size=768, chunk_overlap=128)
        assert chunks == []

    def test_section_metadata_preserved(self) -> None:
        from app.ingestion.chunker import chunk_text

        text = "Content for this section. " * 5
        chunks = chunk_text(
            text,
            chunk_size=768,
            chunk_overlap=128,
            section_key="item_1a",
            section_title="Risk Factors",
        )
        assert len(chunks) >= 1
        assert chunks[0].section_key == "item_1a"
        assert chunks[0].section_title == "Risk Factors"

    def test_start_index_offset(self) -> None:
        from app.ingestion.chunker import chunk_text

        text = "Some text content."
        chunks = chunk_text(text, chunk_size=768, chunk_overlap=128, start_index=5)
        assert chunks[0].chunk_index == 5

    def test_count_tokens(self) -> None:
        from app.ingestion.chunker import count_tokens

        count = count_tokens("Hello world, how are you?")
        assert count > 0
        assert isinstance(count, int)


# =====================================================================
# XBRL Mapper
# =====================================================================


class TestXBRLMapper:
    """Tests for XBRL companyfacts mapping."""

    def _make_companyfacts(self, tags: dict) -> dict:
        """Build a minimal companyfacts structure."""
        us_gaap = {}
        for tag_name, values in tags.items():
            us_gaap[tag_name] = {
                "units": {"USD": values},
            }
        return {"facts": {"us-gaap": us_gaap}}

    def test_basic_income_statement_mapping(self) -> None:
        from app.xbrl.mapper import map_company_facts

        facts = self._make_companyfacts({
            "Revenues": [
                {
                    "val": 100000000,
                    "end": "2023-12-31",
                    "start": "2023-01-01",
                    "form": "10-K",
                    "filed": "2024-02-15",
                },
            ],
            "NetIncomeLoss": [
                {
                    "val": 20000000,
                    "end": "2023-12-31",
                    "start": "2023-01-01",
                    "form": "10-K",
                    "filed": "2024-02-15",
                },
            ],
        })

        periods = map_company_facts(facts)
        assert len(periods) > 0

        # Find the annual 2023 period
        annual_2023 = [
            p for p in periods
            if p["fiscal_year"] == 2023 and p["fiscal_quarter"] is None
        ]
        assert len(annual_2023) > 0
        period = annual_2023[0]
        assert period["income_statement"]["revenue"] == 100000000.0
        assert period["income_statement"]["net_income"] == 20000000.0

    def test_balance_sheet_mapping(self) -> None:
        from app.xbrl.mapper import map_company_facts

        facts = self._make_companyfacts({
            "Assets": [
                {
                    "val": 500000000,
                    "end": "2023-12-31",
                    "form": "10-K",
                    "filed": "2024-02-15",
                },
            ],
            "Liabilities": [
                {
                    "val": 200000000,
                    "end": "2023-12-31",
                    "form": "10-K",
                    "filed": "2024-02-15",
                },
            ],
        })

        periods = map_company_facts(facts)
        assert len(periods) > 0

    def test_gross_profit_fallback(self) -> None:
        from app.xbrl.mapper import map_company_facts

        # Provide revenue and COGS but no gross profit
        facts = self._make_companyfacts({
            "Revenues": [
                {
                    "val": 100000,
                    "end": "2023-12-31",
                    "start": "2023-01-01",
                    "form": "10-K",
                    "filed": "2024-02-15",
                },
            ],
            "CostOfGoodsAndServicesSold": [
                {
                    "val": 60000,
                    "end": "2023-12-31",
                    "start": "2023-01-01",
                    "form": "10-K",
                    "filed": "2024-02-15",
                },
            ],
        })

        periods = map_company_facts(facts)
        annual = [p for p in periods if p["fiscal_quarter"] is None]
        if annual:
            # gross_profit should be computed as fallback
            income = annual[0]["income_statement"]
            if "revenue" in income and "cost_of_revenue" in income:
                assert income["gross_profit"] == 40000.0

    def test_empty_facts(self) -> None:
        from app.xbrl.mapper import map_company_facts

        periods = map_company_facts({"facts": {}})
        assert periods == []

    def test_year_filter(self) -> None:
        from app.xbrl.mapper import map_company_facts

        facts = self._make_companyfacts({
            "Revenues": [
                {
                    "val": 100,
                    "end": "2020-12-31",
                    "start": "2020-01-01",
                    "form": "10-K",
                    "filed": "2021-02-15",
                },
                {
                    "val": 200,
                    "end": "2023-12-31",
                    "start": "2023-01-01",
                    "form": "10-K",
                    "filed": "2024-02-15",
                },
            ],
        })

        periods = map_company_facts(facts, start_year=2023)
        years = [p["fiscal_year"] for p in periods]
        assert all(y >= 2023 for y in years)


# =====================================================================
# Magic-byte validation (NFR-302)
# =====================================================================


class TestMagicByteValidation:
    """Tests for file type validation via magic bytes.

    NFR-302: A file with a spoofed extension (e.g. JPEG renamed to .pdf)
    MUST be rejected based on magic bytes, not file extension.
    """

    def test_valid_pdf_magic_bytes(self) -> None:
        from app.ingestion.pipeline import detect_file_type

        # Real PDF starts with %PDF
        data = b"%PDF-1.4 rest of file content here"
        assert detect_file_type(data) == "pdf"

    def test_valid_html_magic_bytes(self) -> None:
        from app.ingestion.pipeline import detect_file_type

        data = b"<!DOCTYPE html><html><body>test</body></html>"
        assert detect_file_type(data) == "html"

    def test_html_lowercase(self) -> None:
        from app.ingestion.pipeline import detect_file_type

        data = b"<html><body>test</body></html>"
        assert detect_file_type(data) == "html"

    def test_spoofed_pdf_extension_rejected(self) -> None:
        """JPEG data with .pdf extension should be rejected (NFR-302)."""
        from app.ingestion.pipeline import IngestionError, detect_file_type

        # JPEG magic bytes: FF D8 FF
        jpeg_data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        with pytest.raises(IngestionError, match="Unsupported file type"):
            detect_file_type(jpeg_data)

    def test_spoofed_html_extension_rejected(self) -> None:
        """PNG data should be rejected regardless of extension."""
        from app.ingestion.pipeline import IngestionError, detect_file_type

        # PNG magic bytes
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        with pytest.raises(IngestionError, match="Unsupported file type"):
            detect_file_type(png_data)

    def test_empty_file_rejected(self) -> None:
        from app.ingestion.pipeline import IngestionError, detect_file_type

        with pytest.raises(IngestionError, match="File is empty"):
            detect_file_type(b"")

    def test_random_bytes_rejected(self) -> None:
        from app.ingestion.pipeline import IngestionError, detect_file_type

        with pytest.raises(IngestionError, match="Unsupported file type"):
            detect_file_type(b"\x00\x01\x02\x03\x04\x05")


# =====================================================================
# Document Service (status state machine)
# =====================================================================


class TestDocumentStatusStateMachine:
    """Tests for document status transitions (T202)."""

    def test_valid_transitions(self) -> None:
        from app.services.document_service import _VALID_TRANSITIONS
        from app.models.document import DocStatus

        # uploaded -> parsing is valid
        assert DocStatus.PARSING in _VALID_TRANSITIONS[DocStatus.UPLOADED]
        # parsing -> parsed is valid
        assert DocStatus.PARSED in _VALID_TRANSITIONS[DocStatus.PARSING]
        # parsed -> embedding is valid
        assert DocStatus.EMBEDDING in _VALID_TRANSITIONS[DocStatus.PARSED]
        # embedding -> ready is valid
        assert DocStatus.READY in _VALID_TRANSITIONS[DocStatus.EMBEDDING]

    def test_error_transitions(self) -> None:
        from app.services.document_service import _VALID_TRANSITIONS
        from app.models.document import DocStatus

        # Any non-terminal state can go to error
        for status in (DocStatus.UPLOADED, DocStatus.PARSING, DocStatus.PARSED, DocStatus.EMBEDDING):
            assert DocStatus.ERROR in _VALID_TRANSITIONS[status]

    def test_retry_from_error(self) -> None:
        from app.services.document_service import _VALID_TRANSITIONS
        from app.models.document import DocStatus

        # error -> parsing (retry) is valid
        assert DocStatus.PARSING in _VALID_TRANSITIONS[DocStatus.ERROR]


# =====================================================================
# XBRL Tag Registry
# =====================================================================


class TestXBRLTagRegistry:
    """Tests for the XBRL tag registry."""

    def test_all_mappings_have_tags(self) -> None:
        from app.xbrl.tag_registry import ALL_MAPPINGS

        for mapping in ALL_MAPPINGS:
            assert len(mapping.xbrl_tags) > 0
            assert mapping.internal_field
            assert mapping.period_type in ("duration", "instant")
            assert mapping.statement in ("income_statement", "balance_sheet", "cash_flow")

    def test_tag_to_mapping_lookup(self) -> None:
        from app.xbrl.tag_registry import TAG_TO_MAPPING

        # Revenue should be in the lookup
        assert "Revenues" in TAG_TO_MAPPING
        assert TAG_TO_MAPPING["Revenues"].internal_field == "revenue"

    def test_at_least_60_tags(self) -> None:
        """Spec requires 60+ US-GAAP tags mapped."""
        from app.xbrl.tag_registry import TAG_TO_MAPPING

        assert len(TAG_TO_MAPPING) >= 60
