"""Extract structured information from UN noon briefing records.

The module defines data structures for the extraction process and parses
briefing JSON records, extracting speaker and section information from
available HTML.

Extracted data:
    - `briefing_date`
    - `url`
    - `status`
    - `http_status`
    - `error`
    - `downloaded_at`
    - `speaker_name`
    - `speaker_role`
    - `sections`
    - `full_text`
"""

from dataclasses import dataclass
import json
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from un_llm_analysis.scraper import FetchStatus


@dataclass(frozen=True)
class ExtractedSection:
    """A titled section extracted from a briefing."""

    title: str
    text: str


@dataclass(frozen=True)
class ExtractedContent:
    """Structured content extracted from briefing HTML."""

    speaker_name: str | None
    speaker_role: str | None
    sections: tuple[ExtractedSection, ...]

    # Complete normalized text retained as a fallback.
    full_text: str


@dataclass(frozen=True)
class ExtractedBriefing:
    """A briefing record with its metadata and extracted content."""

    briefing_date: str
    url: str
    status: FetchStatus
    http_status: int | None
    error: str | None
    downloaded_at: str
    speaker_name: str | None
    speaker_role: str | None
    sections: tuple[ExtractedSection, ...]
    full_text: str | None


@dataclass(frozen=True)
class HardLine:
    """A nonempty line separated by an explicit HTML boundary such as <br>, <p>, or <li>."""

    text: str
    fully_bold: bool
    fully_underlined: bool


_TEXT_TRANSLATION = str.maketrans(
    {
        # Space-like characters -> regular space
        "\u00a0": " ",  # NO-BREAK SPACE
        "\u202f": " ",  # NARROW NO-BREAK SPACE
        "\u2002": " ",  # EN SPACE
        "\u2003": " ",  # EM SPACE
        "\u2007": " ",  # FIGURE SPACE
        "\u2009": " ",  # THIN SPACE
        # Invisible formatting characters -> remove
        "\u200b": None,  # ZERO WIDTH SPACE
        "\u00ad": None,  # SOFT HYPHEN
        "\ufeff": None,  # ZERO WIDTH NO-BREAK SPACE / BOM
        "\u2060": None,  # WORD JOINER
    }
)


def _normalize_text(text: str) -> str:
    """Normalize text by replacing certain Unicode characters.

    Args:
        text (str): Original text to normalize.

    Returns:
        str: Normalized text with specific Unicode characters replaced or removed.
    """

    return text.translate(_TEXT_TRANSLATION)


def _extract_hard_lines(html: str) -> list[HardLine]:
    """Split a briefing HTML into hard lines

    Args:
        html (str): Original inner HTML of a briefing.

    Returns:
        list[HardLine]: Structured hard lines extracted from the HTML.
    """

    BLOCK_TAGS = {
        "p",
        "div",
        "li",
        "ul",
        "ol",
        "blockquote",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "section",
        "article",
        "header",
        "footer",
        "main",
        "hr",
    }

    FORMAT_TAGS = {
        "strong": "bold",
        "b": "bold",
        "u": "underline",
        "ins": "underline",
    }

    hard_lines: list[HardLine] = []
    fragments: list[tuple[str, frozenset[str]]] = []

    def fully_formatted(format_: str) -> bool:
        """Check whether all text fragments use the specified format, ignoring symbol-only fragments."""
        text_fragments = [formats for part, formats in fragments if any(c.isalnum() for c in part)]

        if not text_fragments:
            return False

        return all(format_ in formats for formats in text_fragments)

    def flush_line() -> None:
        """Convert accumulated fragments into a hard line and reset the buffer."""
        text = " ".join("".join(part for part, _ in fragments).split())
        if text:
            hard_lines.append(
                HardLine(
                    text=text,
                    fully_bold=fully_formatted("bold"),
                    fully_underlined=fully_formatted("underline"),
                )
            )
        fragments.clear()

    def visit(node: Tag | NavigableString, formats: frozenset[str] = frozenset()) -> None:
        """Recursively process an HTML node, tracking line boundaries and bold/underlined text."""
        if isinstance(node, Comment):
            return

        if isinstance(node, NavigableString):
            fragments.append((_normalize_text(str(node)), formats))
            return

        if node.name in {"script", "style"}:
            return

        if node.name == "br":
            flush_line()
            return

        is_block = node.name in BLOCK_TAGS
        if is_block:
            flush_line()

        format_ = FORMAT_TAGS.get(node.name)
        if format_:
            formats = formats | {format_}

        for child in node.children:
            visit(child, formats)

        if is_block:
            flush_line()

    soup = BeautifulSoup(html, "html.parser")
    visit(soup)
    flush_line()

    return hard_lines


def _extract_speaker(hard_lines: list[HardLine]) -> tuple[str | None, str | None]:
    """Extract the speaker's name and role from the briefing lines.

    Args:
        hard_lines (list[HardLine]): Hard lines extracted from the briefing.

    Returns:
        tuple[str | None, str | None]: The speaker's name and role.
    """

    title_str = "HIGHLIGHTS OF THE NOON BRIEFING"
    by_str = "BY "
    role_words = [
        "SPOKESMAN",
        "SPOKESWOMAN",
        "SPOKESPERSON",
        # Below are common misspellings found in the data.
        "SPOKESPESMAN",
    ]

    for i, hard_line in enumerate(hard_lines):
        if title_str not in hard_line.text.upper():
            continue

        # Add a space before each newline to handle a line ending in "BY".
        header = " \n".join(line.text.strip() for line in hard_lines[i : i + 3])

        title_start = header.upper().find(title_str)
        remaining = header[title_start + len(title_str) :]

        # Remove separators between the title and "BY ".
        remaining = remaining.lstrip(" ,\r\n\t")

        if not remaining.upper().startswith(by_str):
            return None, None

        cleaned = remaining[len(by_str) :].replace(",", "\n")
        parts = [part.strip() for part in cleaned.splitlines() if part.strip()]

        if not parts:
            return None, None

        speaker_name = parts[0]
        speaker_role = (
            parts[1]
            if len(parts) >= 2 and any(word in parts[1].upper() for word in role_words)
            else None
        )

        return speaker_name, speaker_role

    return None, None


def _is_section_title_candidate(line: HardLine) -> bool:
    """Check whether a hard line looks like a section title.

    Args:
        line (HardLine): A HardLine object to check.

    Returns:
        bool: Whether it's a section title.
    """

    MAX_LOWERCASE_RATIO = 0.25

    if line.fully_bold or line.fully_underlined:
        return True

    num_lowercase = sum(char.islower() for char in line.text)
    num_uppercase = sum(char.isupper() for char in line.text)
    num_cased_chars = num_lowercase + num_uppercase

    if num_cased_chars == 0:
        return False

    lowercase_ratio = num_lowercase / num_cased_chars

    return lowercase_ratio < MAX_LOWERCASE_RATIO


def _extract_sections(hard_lines: list[HardLine]) -> tuple[ExtractedSection, ...]:
    """Extract sections from the briefing lines.

    Args:
        hard_lines (list[HardLine]): Hard lines extracted from the briefing.

    Returns:
        tuple[ExtractedSection, ...]: Sections extracted from the hard lines.
    """

    extracted_sections: list[ExtractedSection] = []
    i = 0

    while i < len(hard_lines) - 1:
        current_is_title_candidate = _is_section_title_candidate(hard_lines[i])
        next_is_title_candidate = _is_section_title_candidate(hard_lines[i + 1])

        # This may treat a few irregular header lines as section titles (an accepted limitation).
        found_section = current_is_title_candidate and not next_is_title_candidate

        if not found_section:
            i += 1
            continue

        section_title = hard_lines[i].text
        section_text_lines = [hard_lines[i + 1].text]

        j = i + 2
        while j < len(hard_lines) and not _is_section_title_candidate(hard_lines[j]):
            section_text_lines.append(hard_lines[j].text)
            j += 1

        extracted_sections.append(
            ExtractedSection(title=section_title, text="\n".join(section_text_lines))
        )

        i = j

    return tuple(extracted_sections)


def extract_html(html: str) -> ExtractedContent:
    """Extract and parse content from a briefing's HTML

    Args:
        html (str): Original inner HTML of a briefing.

    Returns:
        ExtractedContent: Structured content extracted from the HTML.
    """

    hard_lines = _extract_hard_lines(html)
    speaker_name, speaker_role = _extract_speaker(hard_lines)
    sections = _extract_sections(hard_lines)
    full_text = "\n".join(line.text for line in hard_lines)

    return ExtractedContent(
        speaker_name=speaker_name,
        speaker_role=speaker_role,
        sections=sections,
        full_text=full_text,
    )


def extract_briefing(file_path: Path) -> ExtractedBriefing:
    """Extract a structured briefing from a briefing's JSON file

    Args:
        file_path (Path): Path to the briefing JSON file.

    Returns:
        ExtractedBriefing: Briefing record parsed from the JSON file.
    """

    with file_path.open("r", encoding="utf-8") as file:
        record = json.load(file)

    if record["status"] != "available":
        return ExtractedBriefing(
            briefing_date=record["date"],
            url=record["url"],
            status=record["status"],
            http_status=record["http_status"],
            error=record["error"],
            downloaded_at=record["downloaded_at"],
            speaker_name=None,
            speaker_role=None,
            sections=(),
            full_text=None,
        )

    extracted_content = extract_html(record["html"])

    return ExtractedBriefing(
        briefing_date=record["date"],
        url=record["url"],
        status=record["status"],
        http_status=record["http_status"],
        error=record["error"],
        downloaded_at=record["downloaded_at"],
        speaker_name=extracted_content.speaker_name,
        speaker_role=extracted_content.speaker_role,
        sections=extracted_content.sections,
        full_text=extracted_content.full_text,
    )
