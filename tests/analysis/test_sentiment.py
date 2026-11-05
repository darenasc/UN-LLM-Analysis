import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

from un_llm_analysis.analysis import sentiment
from un_llm_analysis.database import SCHEMA_DB, create_database, get_db_connection


@pytest.fixture
def test_db(tmp_path):
    """Create an isolated temporary database for testing."""

    db_path = tmp_path / "test.db"

    create_database(
        db_path=db_path,
        schema_path=SCHEMA_DB,
    )

    return db_path


def test_get_existing_sentiment_analysis(monkeypatch):
    """Test the existing sentiment analysis function."""

    sample_results = pd.DataFrame(
        [
            {
                "analysis_id": 1,
                "model_name": "llama3.2:latest",
                "briefing_date": "2026-11-01",
                "section_id": 101,
                "status": "success",
            },
            {
                "analysis_id": 1,
                "model_name": "llama3.2:latest",
                "briefing_date": "2026-11-02",
                "section_id": 102,
                "status": "success",
            },
        ]
    )

    monkeypatch.setattr(
        sentiment,
        "get_sentiment_results_between_dates",
        lambda **kwargs: sample_results,
    )

    result = sentiment.get_existing_sentiment_analysis(
        conn=None,
        start_date="2026-11-01",
        end_date="2026-11-02",
        model_name="llama3.2:latest",
    )

    assert not result.empty
    assert result.iloc[0]["analysis_id"] == 1
    assert result.iloc[0]["model_name"] == "llama3.2:latest"
    assert result.iloc[0]["min_date"] == "2026-11-01"
    assert result.iloc[0]["max_date"] == "2026-11-02"
    assert result.iloc[0]["total_sections"] == 2


def test_run_sentiment_analysis(monkeypatch, test_db):
    """Test the main sentiment analysis workflow."""

    # Mock MLflow tracking
    mlflow_run = MagicMock()
    mlflow_run.__enter__ = MagicMock(return_value=mlflow_run)
    mlflow_run.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(
        sentiment.mlflow,
        "set_experiment",
        MagicMock(),
    )
    monkeypatch.setattr(
        sentiment.mlflow,
        "start_run",
        lambda **kwargs: mlflow_run,
    )
    monkeypatch.setattr(
        sentiment,
        "_check_ollama_model_exists",
        lambda model: True,
    )
    monkeypatch.setattr(
        sentiment,
        "run_model_prompt",
        lambda **kwargs: {
            "response": ('{"sentiment": "Neutral", ' '"tone": "Neutral/Informational"}')
        },
    )
    monkeypatch.setattr(
        sentiment,
        "get_existing_sentiment_analysis",
        lambda *args, **kwargs: pd.DataFrame(),
    )
    monkeypatch.setattr(
        sentiment,
        "get_db_connection",
        lambda db_path=None: get_db_connection(test_db),
    )
    monkeypatch.setattr(sentiment.mlflow, "log_params", MagicMock())
    monkeypatch.setattr(sentiment.mlflow, "log_text", MagicMock())
    monkeypatch.setattr(sentiment.mlflow, "log_metrics", MagicMock())

    # Sample briefing section
    section_data = pd.DataFrame(
        [
            {
                "briefing_id": 10,
                "section_id": 101,
                "briefing_date": "2026-11-01",
                "section_text": "The United Nations discussed climate change.",
            }
        ]
    )

    # Execute the function
    result = sentiment.run_sentiment_analysis(
        section_data=section_data,
        start_date="2026-11-01",
        end_date="2026-11-01",
    )

    # Verify the result
    assert result["status"] == "completed"
    assert result["analysis_id"] > 0
    assert result["successful_sections"] == 1
    assert result["failed_sections"] == 0
