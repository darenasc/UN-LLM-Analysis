import pytest

from un_llm_analysis.analysis.sdg import (
    _parse_sdg_response,
    extract_sdg_mentions_from_sections,
    get_sdg_text,
)
from un_llm_analysis.database import get_sdg_by_section_id, insert_into_briefing


@pytest.mark.parametrize(
    "sdgs,expected",
    [
        ("['SDG1', 'SDG2']", ["SDG1", "SDG2"]),
        ("['SDG3', 'SDG4']", ["SDG3", "SDG4"]),
    ],
)
def test__parse_sdg_response(sdgs, expected):
    """Test parsing of SDGs."""
    result = _parse_sdg_response(sdgs=sdgs)
    assert result == expected


@pytest.mark.parametrize(
    "sdgs,expected",
    [
        (
            {"SDG1": "End poverty in all its forms everywhere"},
            "* SDG1 End poverty in all its forms everywhere",
        ),
        (
            {
                "SDG2": "End hunger, achieve food security and improved nutrition and promote sustainable agriculture"
            },
            "* SDG2 End hunger, achieve food security and improved nutrition and promote sustainable agriculture",
        ),
        (
            {"SDG1": "End poverty", "SDG2": "End hunger", "SDG3": "Ensure healthy lives"},
            """* SDG1 End poverty\n* SDG2 End hunger\n* SDG3 Ensure healthy lives""",
        ),
    ],
)
def test_get_sdg_text(sdgs, expected):
    """Test the concatenation of the SDGs."""
    result = get_sdg_text(sdgs=sdgs)
    assert result == expected


@pytest.mark.parametrize(
    "start_date,end_date,model,prompt,overwrite",
    [
        ("2026-08-25", "2026-08-25", "llama3.2", "prompt test", True),
    ],
)
def test_extract_sdg_mentions_from_sections(
    conn, briefing, start_date, end_date, model, prompt, overwrite, mocker
):
    """Test querying SDG mentions in sections without calling Ollama to generate them.
    It iterates over the briefing 14 times but inserts the same data for testing
    ['SDG17']
    """
    insert_into_briefing(conn=conn, briefing=briefing)

    mock_get_briefings_between_dates = mocker.patch(
        "un_llm_analysis.analysis.sdg.get_briefings_between_dates"
    )
    mock_get_briefings_between_dates.return_value = [briefing]

    mock_get_sdg_text = mocker.patch("un_llm_analysis.analysis.sdg.get_sdg_text")
    mock_get_sdg_text.return_value = "SDGs"

    mock__parse_sdg_response = mocker.patch("un_llm_analysis.analysis.sdg._parse_sdg_response")
    mock__parse_sdg_response.return_value = ["SDG17"]

    mock_ollama_generate = mocker.patch("un_llm_analysis.analysis.sdg.ollama.generate")
    mock_ollama_generate.return_value = {"response": "['SDG17']", "created_at": "2026-08-25"}

    extract_sdg_mentions_from_sections(
        start_date=start_date,
        end_date=end_date,
        conn=conn,
        model=model,
        prompt=prompt,
        overwrite=overwrite,
    )
    result = get_sdg_by_section_id(conn=conn, section_id=2026082501, model="llama3.2")
    assert result == ["SDG17"]

    mock_get_briefings_between_dates.assert_called_once_with(
        conn=conn, start_date=start_date, end_date=end_date
    )
    mock_get_sdg_text.assert_called_once_with()
    mock_ollama_generate.assert_called_with(model="llama3.2", prompt="prompt test", think=False)
