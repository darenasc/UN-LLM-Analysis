from dataclasses import dataclass
from datetime import date, datetime

from path import Path


@dataclass(frozen=True)
class ExtractedSection:
    title: str
    text: str


@dataclass(frozen=True)
class ExtractedContent:
    speaker_name: str
    speaker_role: str
    preface_text: str
    sections: tuple[ExtractedSection, ...]


@dataclass(frozen=True)
class ExtractedBriefing:
    briefing_date: date
    url: str
    downloaded_at: datetime
    speaker_name: str
    speaker_role: str
    preface_text: str
    sections: tuple[ExtractedSection, ...]


def extract_html(html: str) -> ExtractedContent:
    """Extract and parse content from a briefing's HTML

    Args:
        html (str): Original inner HTML of a briefing.

    Returns:
        ExtractedContent: Structured content extracted from the HTML.
    """


def extract_briefing(file_path: Path) -> ExtractedBriefing:
    """Extract a structured briefing from a briefing's JSON file

    Args:
        file_path (Path): Path to the briefing JSON file.

    Returns:
        ExtractedBriefing: Structured briefing data extracted from the JSON file.
    """
