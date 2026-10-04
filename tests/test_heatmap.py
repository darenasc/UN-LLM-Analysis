from pathlib import Path
import re
import sqlite3
import sys
import tempfile

import pandas as pd

from un_llm_analysis.config import BRIEFINGS_DB_PATH, COUNTRY_CSV_PATH

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from un_llm_analysis.heatmap import (
    build_search_dict,
    clean_alternative_names,
    compile_search_pattern,
    count_mentions_in_section,
    create_bokeh_heatmap,
    get_countries_data,
    process_sections_to_heatmap,
    save_heatmap_to_db,
)


def test_countries_csv_exists(csv_path=COUNTRY_CSV_PATH):
    """Test that countries reference CSV exists."""
    assert csv_path.exists(), "Countries CSV not found"


def test_countries_csv_has_correct_structure(csv_path=COUNTRY_CSV_PATH):
    """Test that CSV has correct columns."""
    df = pd.read_csv(csv_path)
    assert list(df.columns) == ["code", "name", "alternative_names"]
    assert len(df) > 100


def test_countries_csv_data_is_clean(csv_path=COUNTRY_CSV_PATH):
    """Test that CSV data is valid (allows empty codes)."""
    df = pd.read_csv(csv_path)

    # Code column can have NaN (for countries without ISO codes)
    # But name and alternative_names should not have NaN
    assert not df["name"].isnull().any()
    assert not df["alternative_names"].isnull().any()


def test_known_countries_exist(csv_path=COUNTRY_CSV_PATH):
    """Test that known countries are in the CSV."""
    df = pd.read_csv(csv_path)
    expected_countries = ["Germany", "France", "United States", "United Kingdom"]
    for country in expected_countries:
        assert country in df["name"].values


def test_loads_countries_csv(csv_path=COUNTRY_CSV_PATH):
    """Test that function loads CSV and returns DataFrame."""
    result = get_countries_data(csv_path)

    assert isinstance(result, pd.DataFrame)
    assert len(result) > 0


def test_clean_alternative_names():
    """Test that function filters problematic terms and handles NaN."""
    assert clean_alternative_names("Deutschland|AND|France") == "Deutschland|France"
    assert clean_alternative_names(pd.NA) == ""
    assert clean_alternative_names("Valid Name") == "Valid Name"


def test_build_search_dict():
    """Test basic functionality."""
    df = pd.DataFrame(
        {"code": ["DE"], "name": ["Germany"], "alternative_names": ["Bundesrepublik Deutschland"]}
    )

    result = build_search_dict(df)
    assert result["germany"] == "DE"
    assert result["bundesrepublik deutschland"] == "DE"


def test_compile_search_pattern():
    """Test that regex pattern matches terms case-insensitively with word boundaries."""
    search_dict = {"germany": "DE", "deutschland": "DE"}
    pattern = compile_search_pattern(search_dict)

    # Returns compiled pattern
    assert isinstance(pattern, re.Pattern)

    # Matches case-insensitively
    assert pattern.findall("Germany and Deutschland") == ["Germany", "Deutschland"]
    assert pattern.findall("GERMANY DEUTSCHLAND") == ["GERMANY", "DEUTSCHLAND"]

    # Respects word boundaries (doesn't match "german" in "germany")
    assert pattern.findall("german") == []


def test_count_mentions_in_section():
    """Test that mentions are counted and aggregated by country code."""
    text = "Germany and Deutschland visited France"
    search_dict = {"germany": "DE", "deutschland": "DE", "france": "FR"}
    pattern = compile_search_pattern(search_dict)

    result = count_mentions_in_section(text, search_dict, pattern)

    # Aggregates multiple terms mapping to same code
    assert result["DE"] == 2  # Germany and Deutschland
    assert result["FR"] == 1  # France

    # Returns empty dict if no matches
    assert count_mentions_in_section("xyz", search_dict, pattern) == {}


def test_process_sections_to_heatmap():
    """Test that heatmap data is aggregated correctly by month and country."""
    sections = pd.DataFrame(
        {
            "text": ["Germany and France", "Deutschland", "France France"],
            "month": [
                pd.Period("2024-01", "M"),
                pd.Period("2024-01", "M"),
                pd.Period("2024-02", "M"),
            ],
        }
    )
    countries = pd.DataFrame(
        {
            "code": ["DE", "FR"],
            "name": ["Germany", "France"],
            "alternative_names": ["Deutschland", ""],
        }
    )

    result = process_sections_to_heatmap(sections, countries)

    # Check structure
    assert list(result.columns) == ["month", "country_code", "count"]

    # Check aggregation
    de_2024_01 = result[(result["month"] == "2024-01") & (result["country_code"] == "DE")]
    assert de_2024_01["count"].values[0] == 2  # Germany + Deutschland


def test_create_bokeh_heatmap(tmp_path):
    """Test that heatmap HTML file is created."""
    heatmap_df = pd.DataFrame(
        {"month": ["2024-01", "2024-01"], "country_code": ["DE", "FR"], "count": [5, 3]}
    )

    output_path = tmp_path / "test_heatmap.html"
    create_bokeh_heatmap(heatmap_df, output_path=str(output_path), top_n=5)

    assert output_path.exists()
    assert output_path.stat().st_size > 0


@pytest.fixture
def sample_heatmap_df():
    """Create sample heatmap dataframe."""
    return pd.DataFrame(
        {
            "month": ["2024-01", "2024-01", "2024-02", "2024-02"],
            "country_code": ["USA", "CHN", "USA", "RUS"],
            "count": [42, 28, 35, 19],
        }
    )


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup
    db_path.unlink(missing_ok=True)


def test_save_heatmap_creates_table(temp_db, sample_heatmap_df):
    """Test that function creates table with correct schema."""
    save_heatmap_to_db(sample_heatmap_df, temp_db)

    # Read back and verify
    conn = sqlite3.connect(temp_db)
    result_df = pd.read_sql_query("SELECT * FROM country_mention_heatmap", conn)
    conn.close()

    assert len(result_df) == 4
    assert list(result_df.columns) == ["month", "country_code", "count"]


def test_save_heatmap_data_integrity(temp_db, sample_heatmap_df):
    """Test that data is saved correctly without modification."""
    save_heatmap_to_db(sample_heatmap_df, temp_db)

    conn = sqlite3.connect(temp_db)
    result_df = pd.read_sql_query("SELECT * FROM country_mention_heatmap", conn)
    conn.close()

    # Check specific values
    assert result_df[result_df["country_code"] == "USA"]["count"].tolist() == [42, 35]
    assert result_df[result_df["country_code"] == "CHN"]["count"].iloc[0] == 28


def test_append_behavior(temp_db, sample_heatmap_df):
    """Test that calling twice appends, not replaces."""
    # First save
    save_heatmap_to_db(sample_heatmap_df, temp_db)

    # Second save with different data
    new_df = pd.DataFrame({"month": ["2024-03"], "country_code": ["GBR"], "count": [15]})
    save_heatmap_to_db(new_df, temp_db)

    # Verify both sets are in the database
    conn = sqlite3.connect(temp_db)
    result_df = pd.read_sql_query("SELECT * FROM country_mention_heatmap", conn)
    conn.close()

    assert len(result_df) == 5  # 4 original + 1 new
    assert "GBR" in result_df["country_code"].values
    assert "USA" in result_df["country_code"].values


def test_save_empty_dataframe(temp_db):
    """Test behavior with empty dataframe."""
    empty_df = pd.DataFrame({"month": [], "country_code": [], "count": []})

    # Should not raise an error
    save_heatmap_to_db(empty_df, temp_db)

    conn = sqlite3.connect(temp_db)
    result_df = pd.read_sql_query("SELECT * FROM country_mention_heatmap", conn)
    conn.close()

    assert len(result_df) == 0


def test_save_large_dataset(temp_db):
    """Test with larger dataset."""
    large_df = pd.DataFrame(
        {
            "month": ["2024-01"] * 100,
            "country_code": [f"C{i:03d}" for i in range(100)],
            "count": list(range(1, 101)),
        }
    )

    save_heatmap_to_db(large_df, temp_db)

    conn = sqlite3.connect(temp_db)
    result_df = pd.read_sql_query("SELECT * FROM country_mention_heatmap", conn)
    conn.close()

    assert len(result_df) == 100
    assert result_df["count"].sum() == sum(range(1, 101))


if __name__ == "__main__":
    pytest.main([__file__])
