# filepath: backend/app/ingestion/section_splitter.py
"""Section splitter for SEC 10-K and 10-Q filings.

Uses regex patterns to identify standard sections (Items) in
SEC filings and splits the full text into named sections.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Section:
    """A section extracted from a filing document."""

    key: str
    title: str
    content: str
    start_pos: int = 0
    end_pos: int = 0
    char_count: int = 0

    def __post_init__(self) -> None:
        self.char_count = len(self.content)


# ── 10-K Section definitions ────────────────────────────────────

_10K_SECTIONS: list[tuple[str, str, re.Pattern]] = [
    ("item_1", "Business", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+1\.?\s*[-—:]?\s*(?:Business|BUSINESS)",
        re.MULTILINE,
    )),
    ("item_1a", "Risk Factors", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+1A\.?\s*[-—:]?\s*(?:Risk\s+Factors|RISK\s+FACTORS)",
        re.MULTILINE,
    )),
    ("item_1b", "Unresolved Staff Comments", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+1B\.?\s*[-—:]?\s*(?:Unresolved|UNRESOLVED)",
        re.MULTILINE,
    )),
    ("item_1c", "Cybersecurity", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+1C\.?\s*[-—:]?\s*(?:Cybersecurity|CYBERSECURITY)",
        re.MULTILINE,
    )),
    ("item_2", "Properties", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+2\.?\s*[-—:]?\s*(?:Properties|PROPERTIES)",
        re.MULTILINE,
    )),
    ("item_3", "Legal Proceedings", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+3\.?\s*[-—:]?\s*(?:Legal|LEGAL)",
        re.MULTILINE,
    )),
    ("item_5", "Market for Registrant's Common Equity", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+5\.?\s*[-—:]?\s*(?:Market|MARKET)",
        re.MULTILINE,
    )),
    ("item_6", "Selected Financial Data", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+6\.?\s*[-—:]?\s*(?:Selected|SELECTED|\[Reserved\]|\[RESERVED\])",
        re.MULTILINE,
    )),
    ("item_7", "Management's Discussion and Analysis", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+7\.?\s*[-—:]?\s*(?:Management|MANAGEMENT)",
        re.MULTILINE,
    )),
    ("item_7a", "Quantitative and Qualitative Disclosures About Market Risk", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+7A\.?\s*[-—:]?\s*(?:Quantitative|QUANTITATIVE)",
        re.MULTILINE,
    )),
    ("item_8", "Financial Statements and Supplementary Data", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+8\.?\s*[-—:]?\s*(?:Financial\s+Statements|FINANCIAL\s+STATEMENTS)",
        re.MULTILINE,
    )),
    ("item_9a", "Controls and Procedures", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+9A\.?\s*[-—:]?\s*(?:Controls|CONTROLS)",
        re.MULTILINE,
    )),
]

# ── 10-Q Section definitions ────────────────────────────────────

_10Q_SECTIONS: list[tuple[str, str, re.Pattern]] = [
    ("part1_item1", "Financial Statements", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+1\.?\s*[-—:]?\s*(?:Financial\s+Statements|FINANCIAL\s+STATEMENTS)",
        re.MULTILINE,
    )),
    ("part1_item2", "Management's Discussion and Analysis", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+2\.?\s*[-—:]?\s*(?:Management|MANAGEMENT)",
        re.MULTILINE,
    )),
    ("part1_item3", "Quantitative and Qualitative Disclosures", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+3\.?\s*[-—:]?\s*(?:Quantitative|QUANTITATIVE)",
        re.MULTILINE,
    )),
    ("part1_item4", "Controls and Procedures", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+4\.?\s*[-—:]?\s*(?:Controls|CONTROLS)",
        re.MULTILINE,
    )),
    ("part2_item1", "Legal Proceedings", re.compile(
        r"(?:^|\n)\s*(?:PART|Part)\s+II.*(?:ITEM|Item)\s+1\.?\s*[-—:]?\s*(?:Legal|LEGAL)",
        re.MULTILINE,
    )),
    ("part2_item1a", "Risk Factors", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+1A\.?\s*[-—:]?\s*(?:Risk\s+Factors|RISK\s+FACTORS)",
        re.MULTILINE,
    )),
    ("part2_item6", "Exhibits", re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s+6\.?\s*[-—:]?\s*(?:Exhibits|EXHIBITS)",
        re.MULTILINE,
    )),
]


def split_into_sections(
    text: str,
    doc_type: str,
) -> list[Section]:
    """Split filing text into sections based on document type.

    Args:
        text: Full filing text (already cleaned).
        doc_type: Filing type ("10-K", "10-Q", or other).

    Returns:
        List of Section objects. If no sections are found,
        returns a single "full_text" section with the entire content.
    """
    if not text.strip():
        return []

    if doc_type in ("10-K", "TEN_K"):
        patterns = _10K_SECTIONS
    elif doc_type in ("10-Q", "TEN_Q"):
        patterns = _10Q_SECTIONS
    else:
        # For other filing types, return the full text as one section
        return [
            Section(
                key="full_text",
                title="Full Document",
                content=text,
                start_pos=0,
                end_pos=len(text),
            )
        ]

    # Find all section start positions
    matches: list[tuple[str, str, int]] = []
    for key, title, pattern in patterns:
        match = pattern.search(text)
        if match:
            matches.append((key, title, match.start()))

    if not matches:
        logger.warning(
            "No sections found in document",
            doc_type=doc_type,
            text_length=len(text),
        )
        return [
            Section(
                key="full_text",
                title="Full Document",
                content=text,
                start_pos=0,
                end_pos=len(text),
            )
        ]

    # Sort by position
    matches.sort(key=lambda m: m[2])

    # Build sections from consecutive matches
    sections: list[Section] = []
    for i, (key, title, start) in enumerate(matches):
        end = matches[i + 1][2] if i + 1 < len(matches) else len(text)

        content = text[start:end].strip()
        if content:
            sections.append(
                Section(
                    key=key,
                    title=title,
                    content=content,
                    start_pos=start,
                    end_pos=end,
                )
            )

    logger.info(
        "Document split into sections",
        doc_type=doc_type,
        section_count=len(sections),
        section_keys=[s.key for s in sections],
    )

    return sections
