import pytest

import un_llm_analysis.extractor as extractor


@pytest.mark.parametrize(
    "str, expected",
    [("A test string", False), ("** **", False), ("**A test string**", True)],
)
def test_is_fully_bold(str, expected):

    result = extractor._is_fully_bold(str)

    assert result is expected


@pytest.mark.parametrize(
    "markdown_line, expexted",
    [
        ("**Bold line.**", "Bold line."),
        ("* List item", "List item"),
        ("[Anchor text](URL)", "Anchor text"),
    ],
)
def test_markdown_to_text(markdown_line, expexted):

    result = extractor._markdown_to_text(markdown_line)

    assert result == expexted


@pytest.mark.parametrize(
    "html, expected_markdown",
    [
        (
            '<p><span><strong>Section Title </strong></span></p><p class="nbps-detected"><span>Section text. &nbsp;</span></p>',
            ["**Section Title**", "Section text."],
        ),
        (
            "<p><li>List line-1.</li> <li>List line-2.</li></p>",
            ["- List line-1.", "- List line-2."],
        ),
        ("<p> </p><p></p> <p> </p>", []),
    ],
)
def test_extract_hard_lines(html, expected_markdown, monkeypatch):

    monkeypatch.setattr(extractor, "_markdown_to_text", lambda _: None)
    monkeypatch.setattr(extractor, "_is_fully_bold", lambda _: None)
    result = extractor._extract_hard_lines(html)

    expected_num_of_lines = len(expected_markdown)

    assert len(result) == expected_num_of_lines

    for i in range(expected_num_of_lines):
        assert result[i].markdown == expected_markdown[i]


@pytest.fixture
def fake_hard_line(monkeypatch):
    class FakeHardLine:
        def __init__(self, text, fully_bold=False):
            self.text = text
            self.fully_bold = fully_bold

    monkeypatch.setattr(extractor, "HardLine", FakeHardLine)

    return FakeHardLine


@pytest.mark.parametrize(
    "lines, expected_name, expected_role",
    [
        (
            ["HIGHLIGHTS OF THE NOON BRIEFING", "BY SPEAKER NAME", "SPOKESMAN ROLE"],
            "SPEAKER NAME",
            "SPOKESMAN ROLE",
        ),
        (
            ["HIGHLIGHTS OF THE NOON BRIEFING BY SPEAKER NAME", "SPOKESMAN ROLE"],
            "SPEAKER NAME",
            "SPOKESMAN ROLE",
        ),
        (
            [
                "HIGHLIGHTS OF THE NOON BRIEFING",
                "BY SPEAKER NAME",
                "SECTION TITLE",
                "Section text.",
            ],
            "SPEAKER NAME",
            None,
        ),
        (["HIGHLIGHTS OF THE NOON BRIEFING", "SECTION TITLE", "Section text."], None, None),
    ],
)
def test_extract_speaker(lines, expected_name, expected_role, fake_hard_line):

    fake_hard_lines = [fake_hard_line(line) for line in lines]

    result = extractor._extract_speaker(fake_hard_lines)
    assert result == (expected_name, expected_role)


@pytest.mark.parametrize(
    "line, fully_bold, expected",
    [
        ("SECTION TITLE", True, True),
        ("SECTION TITLE", False, False),
        ("Section Title", True, False),
        ("2026-08-25", True, False),
    ],
)
def test_is_section_title_candidate(fake_hard_line, line, fully_bold, expected):

    input_line = fake_hard_line(line, fully_bold=fully_bold)

    result = extractor._is_section_title_candidate(input_line)

    assert result is expected


def test_extract_sections_regular_case(monkeypatch, fake_hard_line):

    hard_lines = [
        fake_hard_line(text="SECTION A"),
        fake_hard_line(text="First paragraph."),
        fake_hard_line(text="Second paragraph."),
        fake_hard_line(text="SECTION B"),
        fake_hard_line(text="Another paragraph."),
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


def test_extract_sections_uses_last_of_consecutive_title_candidates(monkeypatch, fake_hard_line):

    hard_lines = [
        fake_hard_line(text="HEADER ONE"),
        fake_hard_line(text="HEADER TWO"),
        fake_hard_line(text="SECTION A"),
        fake_hard_line(text="First paragraph."),
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


def test_extract_sections_returns_empty_tuple_when_no_title_candidates(
    monkeypatch, fake_hard_line
):

    hard_lines = [
        fake_hard_line(text="First paragraph."),
        fake_hard_line(text="Second paragraph."),
    ]

    monkeypatch.setattr(
        extractor,
        "_is_section_title_candidate",
        lambda line: False,
    )

    result = extractor._extract_sections(hard_lines)

    assert result == ()


def test_extract_sections_ignores_title_candidate_without_content(monkeypatch, fake_hard_line):

    hard_lines = [
        fake_hard_line(text="First paragraph."),
        fake_hard_line(text="Second paragraph."),
        fake_hard_line(text="SECTION A"),
        fake_hard_line(text="SECTION B"),
    ]

    monkeypatch.setattr(
        extractor,
        "_is_section_title_candidate",
        lambda line: line.text.startswith("SECTION"),
    )

    result = extractor._extract_sections(hard_lines)

    assert result == ()
