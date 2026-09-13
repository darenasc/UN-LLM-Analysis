from dataclasses import asdict
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import un_llm_analysis.extractor as extractor


@pytest.mark.parametrize(
    "markdown_text, expected",
    [("A test string", False), ("** **", False), ("**A test string**", True)],
    ids=[
        "not-bold",
        "empty-bold",
        "fully-bold",
    ],
)
def test_is_fully_bold(markdown_text, expected):

    result = extractor._is_fully_bold(markdown_text)

    assert result is expected


@pytest.mark.parametrize(
    "markdown_line, expected",
    [
        ("**Bold line.**", "Bold line."),
        ("* List item", "List item"),
        ("[Anchor text](URL)", "Anchor text"),
    ],
    ids=[
        "bold-line",
        "list-item",
        "link-with-anchor-text",
    ],
)
def test_markdown_to_text(markdown_line, expected):

    result = extractor._markdown_to_text(markdown_line)

    assert result == expected


@pytest.mark.parametrize(
    "html, expected_markdown_lines",
    [
        (
            '<p><span><strong>SECTION TITLE </strong></span></p><p class="nbps-detected"><span>Section text. &nbsp;</span></p>',
            ["**SECTION TITLE**", "Section text."],
        ),
        (
            "<ul><li>List line-1.</li> <li>List line-2.</li></ul>",
            ["* List line-1.", "* List line-2."],
        ),
        (
            "<p>First line.<br>Second line.</p>",
            ["First line.", "Second line."],
        ),
        ("<p> </p><p></p> <p> </p>", []),
    ],
    ids=[
        "section-title-and-text",
        "list-items",
        "hard-line-breaks",
        "empty-lines",
    ],
)
def test_extract_hard_lines(html, expected_markdown_lines, monkeypatch):

    monkeypatch.setattr(extractor, "_markdown_to_text", lambda _: None)
    monkeypatch.setattr(extractor, "_is_fully_bold", lambda _: None)
    result = extractor._extract_hard_lines(html)

    assert len(result) == len(expected_markdown_lines)

    result_markdown_lines = [line.markdown for line in result]
    assert result_markdown_lines == expected_markdown_lines


def make_hard_line(
    text: str,
    fully_bold: bool = False,
    markdown: str = "",
) -> extractor.HardLine:
    return extractor.HardLine(
        text=text,
        markdown=markdown,
        fully_bold=fully_bold,
    )


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
    "line, fully_bold, expected",
    [
        ("SECTION TITLE", True, True),
        ("SECTION TITLE", False, False),
        ("Section Title", True, False),
        ("2026-08-25", True, False),
    ],
    ids=[
        "valid-title",
        "not-bold",
        "too-much-lowercase",
        "no-cased-characters",
    ],
)
def test_is_section_title_candidate(line, fully_bold, expected):

    input_line = make_hard_line(line, fully_bold=fully_bold)

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


def test_extract_briefing_with_real_fixture():

    fixtures_dir = Path(__file__).parent / "fixtures"

    result = extractor.extract_briefing(fixtures_dir / "briefing_2026-08-25.json")

    expected = json.loads(
        (fixtures_dir / "extracted_briefing_2026-08-25.json").read_text(encoding="utf-8")
    )

    expected["sections"] = tuple(expected["sections"])

    assert asdict(result) == expected
