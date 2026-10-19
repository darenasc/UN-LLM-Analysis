import pandas as pd

from un_llm_analysis.analysis.issue import (
    calculate_issue_counts,
    calculate_issue_stats,
    get_issue_text,
)


def test_get_issue_text():
    issues = {"ISSUE-1": "First issue", "ISSUE-2": "Second issue"}

    assert get_issue_text(issues) == ("* ISSUE-1 First issue\n* ISSUE-2 Second issue")


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
