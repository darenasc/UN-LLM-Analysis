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
