from pathlib import Path

import pytest

from un_llm_analysis.analysis.countries import (
    _get_country_data,
    _get_country_text,
    _get_wikipedia_country_data,
    _parse_country_response,
    process_country_mentions,
)
from un_llm_analysis.database import get_country_mentions_by_date, load_briefing_to_db


def test_get_wikipedia_country_data():
    """Test retrieving wikipedia data about countryes."""
    df_result = _get_wikipedia_country_data(
        file_path=Path("tests/fixtures/app/static/wikipedia_country_data.csv")
    )
    assert df_result.shape == (4, 4)


def test_get_country_text():
    """Test generating a list of countries with codes."""
    result = _get_country_text(
        wikipedia_data=Path("tests/fixtures/app/static/wikipedia_country_data.csv")
    )
    assert isinstance(result, str)
    assert "Germany" in result
    assert "CH" in result


@pytest.mark.parametrize(
    "iso_2,country_expected,iso_2_expected,iso_3_expected",
    [
        ("DE", "Germany", "DE", "DEU"),
        ("CL", None, None, None),
        ("CH", "Switzerland", "CH", "CHE"),
    ],
)
def test_get_country_data(
    iso_2, country_expected, iso_2_expected, iso_3_expected, wikipedia_country_data
):
    """Tests retrieving name and codes from the wikipedia country data."""
    country_result, iso_2_result, iso_3_result = _get_country_data(
        iso_2=iso_2, df_wikipedia=wikipedia_country_data
    )
    assert country_result == country_expected
    assert iso_2_result == iso_2_expected
    assert iso_3_result == iso_3_expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("('Germany', 'GE')", ("Germany", "GE")),
        ("('Chile', 'CL')", ("Chile", "CL")),
    ],
)
def test__parse_country_response(text, expected):
    """Tests the parsing of responses from the LLM."""
    result = _parse_country_response(text=text)
    assert result == expected


@pytest.mark.parametrize(
    "start_date,end_date,model,wikipedia_path,overwrite",
    [
        (
            "2026-08-25",
            "2026-08-25",
            "qwen3.5:4b",
            Path("tests/fixtures/app/static/wikipedia_country_data.csv"),
            False,
        )
    ],
)
def test_process_country_mentions(
    conn, start_date, end_date, model, wikipedia_path, overwrite, mocker
):
    """Test extracting country mentions from sections."""
    load_briefing_to_db(
        file_path=Path("tests/fixtures/briefings/2026/2026-08/2026-08-25.json"), conn=conn
    )

    mock_run_model_prompt = mocker.patch("un_llm_analysis.analysis.countries.run_model_prompt")
    mock_run_model_prompt.return_value = {"response": "Model response", "created_at": "2026-10-17"}

    mock__parse_country_response = mocker.patch(
        "un_llm_analysis.analysis.countries._parse_country_response"
    )
    mock__parse_country_response.return_value = [("Germany", "DE")]

    mock_check_country_section_model_exists = mocker.patch(
        "un_llm_analysis.analysis.countries.check_country_section_model_exists"
    )
    mock_check_country_section_model_exists.return_value = False

    process_country_mentions(
        conn=conn,
        start_date=start_date,
        end_date=end_date,
        model=model,
        wikipedia_path=wikipedia_path,
        overwrite=overwrite,
    )

    result = get_country_mentions_by_date(
        conn=conn, model="qwen3.5:4b", start_date=start_date, end_date=end_date
    )
    assert result.shape[0] == 14
