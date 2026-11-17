from contextlib import nullcontext
from unittest.mock import MagicMock, Mock

import pandas as pd
import pytest

import un_llm_analysis.analysis.issue as issue
from un_llm_analysis.analysis.issue import (
    calculate_issue_counts,
    calculate_issue_stats,
    get_issue_data,
    get_issue_text,
    get_section_data,
    map_issue_to_sections,
)
from un_llm_analysis.database import (
    Section,
    get_issue_by_section_id,
)


def test_get_issue_text():
    issues = {"ISSUE-1": "First issue", "ISSUE-2": "Second issue"}

    assert get_issue_text(issues) == ("* ISSUE-1 First issue\n* ISSUE-2 Second issue")


def test_get_section_data(conn, monkeypatch):
    section = Section(
        title="CLIMATE",
        text="Climate change",
        section_id=2026082501,
        briefing_id=20260825,
        section_order=1,
    )

    monkeypatch.setattr(issue, "get_sections_between_dates", Mock(return_value=[section]))

    result = get_section_data(conn=conn, start_date="2026-08-01", end_date="2026-08-30")

    assert len(result) == 1
    assert result.iloc[0]["section_title"] == "CLIMATE"
    assert result.iloc[0]["section_text"] == "Climate change"


def test_get_issue_data(conn, monkeypatch):
    data = pd.DataFrame(
        {
            "briefing_id": [20260915, 20260916, 20260917],
            "model": ["qwen3.5:4b", "other", "qwen3.5:4b"],
            "issue": ["ISSUE-1", "ISSUE-2", "ISSUE-3"],
        }
    )

    monkeypatch.setattr(issue, "get_issues_between_dates", Mock(return_value=data))

    result = get_issue_data(
        conn=conn,
        model="qwen3.5:4b",
        issues=["ISSUE-1"],
        start_date="2026-09-01",
        end_date="2026-09-30",
    )

    assert len(result) == 1
    assert result.iloc[0]["issue"] == "ISSUE-1"
    assert result.iloc[0]["date"] == pd.Timestamp("2026-09-15")


def test_calculate_issue_stats():
    section_data = pd.DataFrame(
        [
            (2026090101, 20260901, "section_text-1"),
            (2026090201, 20260902, "section_text-2"),
            (2026090202, 20260902, "section_text-3"),
        ],
        columns=["section_id", "briefing_id", "section_text"],
    )
    issue_data = pd.DataFrame(
        [
            (2026090101, 20260901, "ISSUE-1"),
            (2026090201, 20260902, "ISSUE-1"),
        ],
        columns=["section_id", "briefing_id", "issue"],
    )

    result = calculate_issue_stats(section_data, issue_data, level="month")

    assert result.shape == (24, 6)
    assert result.columns.tolist() == [
        "month",
        "issue",
        "total_length",
        "issue_length",
        "frequency",
        "proportion",
    ]
    assert result["month"].eq(pd.Timestamp("2026-09-01")).all()
    assert not result.isna().any().any()


def test_calculate_issue_counts():
    issue_data = pd.DataFrame({"issue": ["ISSUE-2", "ISSUE-1", "ISSUE-1"]})

    result = calculate_issue_counts(issue_data)

    assert result.to_dict("records") == [
        {"issue": "ISSUE-1", "total_counts": 2},
        {"issue": "ISSUE-2", "total_counts": 1},
    ]


@pytest.mark.parametrize(
    "input_text, expected",
    [
        ('["ISSUE-17"]', ["ISSUE-17"]),
        ('["ISSUE-17", "INVALID", 123]', ["ISSUE-17"]),
        ('["INVALID"]', []),
        ('{"ISSUE-17": 1}', None),
        ("invalid syntax", None),
        ("[]", []),
    ],
)
def test_parse_issue_response(input_text, expected):
    assert issue._parse_issue_response(input_text) == expected


def test_mlflow_run(monkeypatch):
    monkeypatch.setattr(
        issue.mlflow,
        "start_run",
        Mock(return_value=nullcontext()),
    )
    log_params = Mock()
    monkeypatch.setattr(issue.mlflow, "log_params", log_params)

    with issue._mlflow_run("llama3.2", {"temperature": 0}):
        pass

    log_params.assert_called_once_with({"model": "llama3.2", "temperature": 0})


def test_tag_section_trace(monkeypatch):
    monkeypatch.setattr(
        issue.mlflow,
        "get_last_active_trace_id",
        Mock(return_value="trace-01"),
    )
    monkeypatch.setattr(
        issue.mlflow,
        "flush_trace_async_logging",
        Mock(),
    )

    set_trace_tag = Mock()
    monkeypatch.setattr(issue.mlflow, "set_trace_tag", set_trace_tag)

    issue._tag_section_trace(2026082501)

    set_trace_tag.assert_called_once_with("trace-01", "section_id", "2026082501")


def test_get_issues_from_llm():
    client = Mock()
    response = client.chat.completions.create.return_value
    response.choices = [Mock(message=Mock(content='["ISSUE-17"]'))]
    response.created = 1788220800

    issues, created_at = issue._get_issues_from_llm(
        client=client,
        model="test-model",
        prompt="Test prompt",
        generation_params={},
    )

    assert issues == ["ISSUE-17"]
    assert created_at == "2026-09-01T00:00:00+00:00"


@pytest.mark.parametrize("issues", [["ISSUE-17"], [], None])
def test_map_issue_to_sections(conn, monkeypatch, issues):
    # GIVEN a connection with certain sections
    # Model to be used exists
    monkeypatch.setattr(issue, "_check_ollama_model_exists", Mock(return_value=True))

    # Mock get_section_data
    monkeypatch.setattr(
        issue,
        "get_section_data",
        Mock(
            return_value=pd.DataFrame(
                [
                    {
                        "briefing_id": 20260825,
                        "section_id": 2026082501,
                        "section_title": "CLIMATE",
                        "section_text": "Climate change",
                    }
                ]
            )
        ),
    )

    # Mock _create_ollama_client
    monkeypatch.setattr(issue, "_create_ollama_client", lambda: MagicMock())

    # Mock _get_issues_from_llm to return a predefined issue and created_at timestamp
    mock_get_issues_from_llm = Mock(return_value=(issues, "2026-09-01T00:00:00+00:00"))
    monkeypatch.setattr(issue, "_get_issues_from_llm", mock_get_issues_from_llm)

    # WHEN mapping issues to sections
    map_issue_to_sections(
        conn=conn,
        start_date="2026-08-01",
        end_date="2026-08-30",
        model="qwen3.5:4b",
    )

    # THEN llm is called and the issue is assigned to the section
    result = get_issue_by_section_id(conn=conn, section_id=2026082501, model="qwen3.5:4b")

    assert mock_get_issues_from_llm.call_count == 1
    assert result == (issues or [])

    # Only test skip-existing behavior when an issue was stored
    if not issues:
        return

    # Mock logger.info to check if it was called
    mock_logger_info = Mock()
    monkeypatch.setattr(issue.logger, "info", mock_logger_info)

    # WHEN mapping issues to sections again
    map_issue_to_sections(
        conn=conn,
        start_date="2026-08-01",
        end_date="2026-08-30",
        model="qwen3.5:4b",
    )

    # THEN skipping without calling llm and logger.info is called
    assert mock_get_issues_from_llm.call_count == 1  # No additional call
    mock_logger_info.assert_called_once()
