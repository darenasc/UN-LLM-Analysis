from dataclasses import asdict
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import un_llm_analysis.extractor as extractor


def test_normalize_text():
    assert extractor._normalize_text("a\u00a0\u202f\u2002\u2003\u2007\u2009b") == "a      b"

    assert extractor._normalize_text("a\u200b\u00ad\ufeff\u2060b") == "ab"


def make_hard_line(
    text: str,
    fully_bold: bool = False,
    fully_underlined: bool = False,
) -> extractor.HardLine:
    return extractor.HardLine(
        text=text,
        fully_bold=fully_bold,
        fully_underlined=fully_underlined,
    )


@pytest.mark.parametrize(
    "html, expected_lines",
    [
        (
            "<p><span><strong>SECTION TITLE</strong></span></p>"
            "<p>Section text.</p>"
            "<p><strong>Bold part.</strong> Normal part.</p>",
            [
                ("SECTION TITLE", True),
                ("Section text.", False),
                ("Bold part. Normal part.", False),
            ],
        ),
        (
            "<ul><li>List line-1.</li><li>List line-2.</li></ul>",
            [
                ("List line-1.", False),
                ("List line-2.", False),
            ],
        ),
        (
            "<p><strong>First<br>Second</strong></p>",
            [
                ("First", True),
                ("Second", True),
            ],
        ),
        (
            "<p>Before <!-- comment -->"
            "<script>ignored script</script>"
            "<style>ignored style</style>"
            "after.</p>",
            [
                ("Before after.", False),
            ],
        ),
        (
            "<p> </p><p></p><p>   </p>",
            [],
        ),
    ],
    ids=[
        "paragraphs-and-bold-state",
        "list-items",
        "hard-line-break-in-bold",
        "ignored-nodes",
        "empty-lines",
    ],
)
def test_extract_hard_lines(html, expected_lines):

    result = extractor._extract_hard_lines(html)

    expected = [make_hard_line(text, fully_bold=bold) for text, bold in expected_lines]

    assert result == expected


def test_extract_hard_lines_underlined():
    html = "<p><u>UNDERLINED TITLE</u></p>"

    result = extractor._extract_hard_lines(html)

    assert result == [
        make_hard_line(
            "UNDERLINED TITLE",
            fully_bold=False,
            fully_underlined=True,
        )
    ]


@pytest.mark.parametrize(
    "lines, expected_name, expected_role",
    [
        (
            ["HIGHLIGHTS OF THE NOON BRIEFING", "BY SPEAKER NAME,", "SPOKESMAN ROLE"],
            "SPEAKER NAME",
            "SPOKESMAN ROLE",
        ),
        (
            ["HIGHLIGHTS OF THE NOON BRIEFING BY SPEAKER NAME", "SECTION TITLE"],
            "SPEAKER NAME",
            None,
        ),
        (
            [
                "HIGHLIGHTS OF THE NOON BRIEFING BY",
                "SPEAKER NAME,",
                "SPOKESMAN ROLE",
            ],
            "SPEAKER NAME",
            "SPOKESMAN ROLE",
        ),
        (["HIGHLIGHTS OF THE NOON BRIEFING", "SECTION TITLE", "Section text."], None, None),
        (["SECTION TITLE", "Section text."], None, None),
        (["HIGHLIGHTS OF THE NOON BRIEFING", "BY", ","], None, None),
    ],
    ids=[
        "speaker-name-and-role",
        "speaker-name-without-role",
        "by-at-line-end",
        "briefing-header-without-by",
        "no-briefing-header",
        "no-speaker-after-by",
    ],
)
def test_extract_speaker(lines, expected_name, expected_role):

    make_hard_lines = [make_hard_line(line) for line in lines]

    result = extractor._extract_speaker(make_hard_lines)
    assert result == (expected_name, expected_role)


@pytest.mark.parametrize(
    "line, fully_bold, fully_underlined, expected",
    [
        ("Section Title", True, False, True),
        ("Section Title", False, True, True),
        ("SECTION TITLE", False, False, True),
        ("Section Title", False, False, False),
        ("2026-08-25", False, False, False),
    ],
    ids=[
        "fully-bold",
        "fully-underlined",
        "mostly-uppercase",
        "too-much-lowercase",
        "no-cased-characters",
    ],
)
def test_is_section_title_candidate(line, fully_bold, fully_underlined, expected):

    input_line = make_hard_line(line, fully_bold=fully_bold, fully_underlined=fully_underlined)

    result = extractor._is_section_title_candidate(input_line)

    assert result is expected


def test_extract_sections_regular_case(monkeypatch):

    hard_lines = [
        make_hard_line(text="SECTION A"),
        make_hard_line(text="First paragraph."),
        make_hard_line(text="Second paragraph."),
        make_hard_line(text="SECTION B"),
        make_hard_line(text="Another paragraph."),
    ]

    monkeypatch.setattr(
        extractor,
        "_is_section_title_candidate",
        lambda line: line.text.startswith("SECTION"),
    )

    result = extractor._extract_sections(hard_lines)

    assert result == (
        extractor.ExtractedSection(
            title="SECTION A",
            text="First paragraph.\nSecond paragraph.",
        ),
        extractor.ExtractedSection(
            title="SECTION B",
            text="Another paragraph.",
        ),
    )


def test_extract_sections_uses_last_title_candidates(monkeypatch):

    hard_lines = [
        make_hard_line(text="HEADER ONE"),
        make_hard_line(text="HEADER TWO"),
        make_hard_line(text="SECTION A"),
        make_hard_line(text="First paragraph."),
    ]

    monkeypatch.setattr(
        extractor,
        "_is_section_title_candidate",
        lambda line: line.text.startswith(("HEADER", "SECTION")),
    )

    result = extractor._extract_sections(hard_lines)

    assert result == (
        extractor.ExtractedSection(
            title="SECTION A",
            text="First paragraph.",
        ),
    )


def test_extract_sections_returns_empty_when_no_titles(monkeypatch):

    hard_lines = [
        make_hard_line(text="First paragraph."),
        make_hard_line(text="Second paragraph."),
    ]

    monkeypatch.setattr(
        extractor,
        "_is_section_title_candidate",
        lambda line: False,
    )

    result = extractor._extract_sections(hard_lines)

    assert result == ()


def test_extract_sections_ignores_title_without_content(monkeypatch):

    hard_lines = [
        make_hard_line(text="First paragraph."),
        make_hard_line(text="Second paragraph."),
        make_hard_line(text="SECTION A"),
        make_hard_line(text="SECTION B"),
    ]

    monkeypatch.setattr(
        extractor,
        "_is_section_title_candidate",
        lambda line: line.text.startswith("SECTION"),
    )

    result = extractor._extract_sections(hard_lines)

    assert result == ()


def test_extract_html_builds_extracted_content(monkeypatch):

    html = "<p>original html</p>"

    hard_lines = [
        make_hard_line(text="First paragraph."),
        make_hard_line(text="Second paragraph."),
    ]

    sections = (
        extractor.ExtractedSection(
            title="SECTION TITLE",
            text="Section text.",
        ),
    )

    def fake_extract_hard_lines(value):
        assert value == html
        return hard_lines

    def fake_extract_speaker(value):
        assert value is hard_lines
        return "SPEAKER NAME", "SPOKESMAN ROLE"

    def fake_extract_sections(value):
        assert value is hard_lines
        return sections

    monkeypatch.setattr(extractor, "_extract_hard_lines", fake_extract_hard_lines)
    monkeypatch.setattr(extractor, "_extract_speaker", fake_extract_speaker)
    monkeypatch.setattr(extractor, "_extract_sections", fake_extract_sections)

    result = extractor.extract_html(html)

    assert result == extractor.ExtractedContent(
        speaker_name="SPEAKER NAME",
        speaker_role="SPOKESMAN ROLE",
        sections=sections,
        full_text="First paragraph.\nSecond paragraph.",
    )


def test_extract_briefing_available(monkeypatch, tmp_path):

    record = {
        "date": "2026-08-25",
        "url": "https://example.com/briefing",
        "status": "available",
        "http_status": 200,
        "error": None,
        "downloaded_at": "2026-08-25T12:00:00Z",
        "html": "<p>briefing html</p>",
    }

    file_path = tmp_path / "briefing.json"
    file_path.write_text(json.dumps(record), encoding="utf-8")

    extracted_content = extractor.ExtractedContent(
        speaker_name="SPEAKER NAME",
        speaker_role="SPOKESMAN ROLE",
        sections=(
            extractor.ExtractedSection(
                title="SECTION TITLE",
                text="Section text.",
            ),
        ),
        full_text="Full briefing text.",
    )

    def fake_extract_html(value):
        assert value == record["html"]
        return extracted_content

    monkeypatch.setattr(extractor, "extract_html", fake_extract_html)

    result = extractor.extract_briefing(file_path)

    assert result == extractor.ExtractedBriefing(
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


def test_extract_briefing_unavailable(monkeypatch, tmp_path):

    record = {
        "date": "2026-08-25",
        "url": "https://example.com/briefing",
        "status": "failed",
        "http_status": 500,
        "error": "Error message",
        "downloaded_at": "2026-08-25T12:00:00Z",
        "html": None,
    }

    file_path = tmp_path / "briefing.json"
    file_path.write_text(json.dumps(record), encoding="utf-8")

    mock_extract_html = Mock()
    monkeypatch.setattr(extractor, "extract_html", mock_extract_html)

    result = extractor.extract_briefing(file_path)

    mock_extract_html.assert_not_called()

    assert result == extractor.ExtractedBriefing(
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


@pytest.mark.parametrize(
    "selected_date",
    ["2026-08-25", "2026-06-29", "2026-06-12", "2025-01-28"],
)
def test_extract_briefing_with_real_fixture(selected_date):

    fixtures_dir = Path(__file__).parent / "fixtures"

    result = extractor.extract_briefing(fixtures_dir / f"briefing_{selected_date}.json")

    expected = json.loads(
        (fixtures_dir / f"extracted_briefing_{selected_date}.json").read_text(encoding="utf-8")
    )

    expected["sections"] = tuple(expected["sections"])

    assert asdict(result) == expected
