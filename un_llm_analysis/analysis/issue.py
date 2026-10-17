"""Module to extract relevant ISSUEs for the sections of the briefings and insert them into the database."""

from typing import Literal

import pandas as pd
import pendulum
import plotly.express as px

SELECTED_ISSUES = {
    "ISSUE-1": "Israel-Palestine conflict, Gaza and the Occupied Palestinian Territory",
    "ISSUE-2": "War in Ukraine and its direct security and humanitarian consequences",
    "ISSUE-3": "Sudan conflict, political process and humanitarian crisis",
    "ISSUE-4": "Democratic Republic of the Congo conflict and humanitarian crisis",
    "ISSUE-5": "Yemen conflict and humanitarian crisis",
    "ISSUE-6": "South Sudan conflict, peace process and humanitarian crisis",
    "ISSUE-7": "Syria conflict and humanitarian crisis",
    "ISSUE-8": "Haiti political, security and humanitarian crisis",
    "ISSUE-9": "Afghanistan political and humanitarian crisis",
    "ISSUE-10": "Myanmar conflict and Rohingya crisis",
    "ISSUE-11": "Central African Republic conflict and political transition",
    "ISSUE-12": "Lebanon political and humanitarian crisis and Israel-Lebanon hostilities",
    "ISSUE-13": "Ethiopia conflict and humanitarian crisis",
    "ISSUE-14": "Libya political transition and insecurity",
    "ISSUE-15": "Sahel and Lake Chad Basin conflict and insecurity",
    "ISSUE-16": "Somalia conflict and humanitarian crisis",
    "ISSUE-17": "Climate change and long-term environmental issues",
    "ISSUE-18": "Natural disasters and acute emergency response",
    "ISSUE-19": "Global health, disease outbreaks and vaccination",
    "ISSUE-20": "Food security, hunger and malnutrition as a primary or cross-country issue",
    "ISSUE-21": "Refugees, displacement and migration as a primary or cross-border issue",
    "ISSUE-22": "Human rights, gender equality and child protection as a primary or cross-country issue",
    "ISSUE-23": "Sustainable development and development financing",
    "ISSUE-24": "Disarmament, arms control and non-proliferation",
}

PlotLevel = Literal["day", "week", "month", "year"]


def get_issue_text(issues: dict = SELECTED_ISSUES) -> str:
    """Generate text with the selected issues to pass to the prompt.

    Returns:
        str: Text with all selected issue descriptions.
    """
    issue_text = ""
    for issue, description in issues.items():
        issue_text += f"* {issue} {description}\n"

    return issue_text.strip()


def calculate_issue_stats(
    section_data: pd.DataFrame,
    issue_data: pd.DataFrame,
    level: PlotLevel = "month",
) -> pd.DataFrame:
    """Calculate issue lengths, frequencies, and proportions by time period."""
    section_df = section_data.copy()
    issue_df = issue_data.copy()

    section_df[level] = section_df["briefing_id"].apply(
        lambda x: pendulum.from_format(str(x), "YYYYMMDD").start_of(level).format("YYYY-MM-DD")
    )

    issue_df[level] = issue_df["briefing_id"].apply(
        lambda x: pendulum.from_format(str(x), "YYYYMMDD").start_of(level).format("YYYY-MM-DD")
    )

    # Store the length of each section
    section_df["section_length"] = section_df["section_text"].str.len()

    # Calculate the total section length in each time period.
    total_length = (
        section_df.groupby(level)["section_length"].sum().reset_index(name="total_length")
    )

    # Attach section lengths to the issue records.
    issue_sections = issue_df.merge(
        section_df[["section_id", "section_length"]],
        on="section_id",
        how="left",
    )

    # Calculate the section length and frequency for each issue and period.
    issue_summary = (
        issue_sections.groupby([level, "issue"])
        .agg(
            issue_length=("section_length", "sum"),
            frequency=("section_id", "nunique"),
        )
        .reset_index()
    )

    # Build a grid of observed time periods and selected issues.
    issues = list(SELECTED_ISSUES.keys())
    periods = sorted(section_df[level].unique())

    issue_period_grid = pd.MultiIndex.from_product(
        [periods, issues],
        names=[level, "issue"],
    ).to_frame(index=False)

    # Attach period totals and issue statistics to the grid.
    issue_stats = issue_period_grid.merge(
        total_length,
        on=level,
        how="left",
    )

    issue_stats = issue_stats.merge(
        issue_summary,
        on=[level, "issue"],
        how="left",
    )

    issue_stats = issue_stats.fillna(
        {"issue_length": 0, "frequency": 0, "total_length": 0}
    ).astype({"issue_length": int, "frequency": int, "total_length": int})

    issue_stats["proportion"] = (issue_stats["issue_length"] / issue_stats["total_length"]).fillna(
        0
    )

    # Convert period labels to datetime after all merges.
    issue_stats[level] = pd.to_datetime(issue_stats[level], format="%Y-%m-%d")

    return issue_stats


def calculate_issue_counts(issue_data: pd.DataFrame) -> pd.DataFrame:
    """Calculate issue_counts from issue_data"""
    issue_counts = (
        issue_data["issue"]
        .value_counts()
        .reset_index(name="total_counts")
        .sort_values(by="total_counts", ascending=False)
    )

    return issue_counts
