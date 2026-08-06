import pandas as pd
import pytest
#import pytest-cov

from notebooks.daniel.aggregation import read_csv_parsing_dates, create_wordcloud

@pytest.fixture
def sample_csv(tmp_path):
    # create a small csv for testing
    csv_path = tmp_path/"sample.csv"
    data = pd.DataFrame({
        "date": ["2022-01-15", "2023-06-01", "2024-03-10"],
        "value": [10, 20, 30],
    })
    data.to_csv(csv_path, index=False)
    return csv_path

def test_returns_dataframe(sample_csv):
    # sanity check on the return type. Expect df.
    df = read_csv_parsing_dates(sample_csv)
    assert isinstance(df, pd.DataFrame)


def test_date_column_is_datetime(sample_csv):
    # confirms that parse_dates worked, not just that the column exists
    df = read_csv_parsing_dates(sample_csv)
    assert pd.api.types.is_datetime64_dtype(df["date"])

def test_year_column_created(sample_csv):
    # check whether year column was created
    df = read_csv_parsing_dates(sample_csv)
    assert "year" in df.columns

def test_year_values_correct(sample_csv):
    # check that year values match expected values 2022-2024
    df = read_csv_parsing_dates(sample_csv)
    assert list(df["year"]) == [2022, 2023,2024]

def test_row_count_preserved(sample_csv):
    # check length of generated df is same as expectation = 3. Catches silent data loss.
    df = read_csv_parsing_dates(sample_csv)
    assert len(df) == 3

def test_missing_file_raises_error():
    # Raise FileNotFoundError if try parsing a file that does not exist.
    # Confirms behaviour on bad input.
    with pytest.raises(FileNotFoundError):
        read_csv_parsing_dates("non_existent_file.csv")

def test_missing_date_column_raises_error(tmp_path):
    # Raise ValueError if there is no date column in the csv being read
    #TODO check that this error would be raised by the used version of Pandas
    csv_path = tmp_path / "no_date.csv"
    pd.DataFrame({"value":[1,2,3]}).to_csv(csv_path, index=False)
    with pytest.raises(ValueError):
        read_csv_parsing_dates(csv_path)

