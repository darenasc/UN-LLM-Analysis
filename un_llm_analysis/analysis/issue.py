"""Module to extract relevant ISSUEs for the sections of the briefings and insert them into the database."""

import pandas as pd
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
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Calculate the issue_stats for drawing plots from the section_data and issue_data."""
    section_df = section_data.copy()
    issue_df = issue_data.copy()

    issue_df["date"] = pd.to_datetime(issue_df["briefing_id"].astype(str), format="%Y%m%d")

    # Store the length of each section
    section_df["section_length"] = section_df["section_text"].str.len()

    # Calculate total length of the sections on each date
    total_length = (
        section_df.groupby("briefing_id")["section_length"].sum().reset_index(name="total_length")
    )

    section_df = section_df.merge(total_length, on="briefing_id", how="left")

    # Merge the issue data with the section data to get the section lengths and total lengths for each issue
    issue_sections = issue_df.merge(
        section_df[["section_id", "section_length", "total_length"]], on="section_id", how="left"
    )

    # Calculate the total length of sections for each issue on each date
    issue_length = (
        issue_sections.groupby(["date", "issue"])["section_length"]
        .sum()
        .reset_index(name="issue_length")
    )

    # Calculate the frequency of sections for each issue on each date
    frequency = (
        issue_sections.groupby(["date", "issue"])["section_id"]
        .nunique()
        .reset_index(name="frequency")
    )

    # Build a complete date x issue grid.
    issues = list(SELECTED_ISSUES.keys())

    dates = pd.to_datetime(section_df["briefing_id"].unique(), format="%Y%m%d").sort_values()

    issue_date_grid = pd.MultiIndex.from_product(
        [dates, issues], names=["date", "issue"]
    ).to_frame(index=False)

    # Merge the issue date grid with the issue length and frequency data to get a complete dataset for analysis
    issue_stats = issue_date_grid.merge(
        issue_sections[["date", "total_length"]].drop_duplicates(), on="date", how="left"
    )

    issue_stats = issue_stats.merge(issue_length, on=["date", "issue"], how="left")
    issue_stats = issue_stats.merge(frequency, on=["date", "issue"], how="left")

    issue_stats = issue_stats.fillna(
        {"issue_length": 0, "frequency": 0, "total_length": 0}
    ).astype({"issue_length": int, "frequency": int, "total_length": int})

    issue_stats["proportion"] = (issue_stats["issue_length"] / issue_stats["total_length"]).fillna(
        0
    )

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
