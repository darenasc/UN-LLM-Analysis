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
