"""Module to extract relevant ISSUEs for the sections of the briefings and insert them into the database."""

import ast
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import sqlite3
from typing import Literal

from loguru import logger
import mlflow
from openai import OpenAI
import pandas as pd
import pendulum

from un_llm_analysis.config import BRIEFINGS_DB_PATH
from un_llm_analysis.database import (
    get_db_connection,
    get_issue_by_section_id,
    get_issues_between_dates,
    get_sections_between_dates,
    insert_into_issue,
)
from un_llm_analysis.prompts import ISSUE_MAPPING_PROMPT
from un_llm_analysis.utils import _check_ollama_model_exists

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


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float = 0
    seed: int = 42
    reasoning_effort: Literal["none", "low", "medium", "high"] = "none"
    max_completion_tokens: int = 128


def _create_ollama_client(
    base_url: str = "http://localhost:11434/v1",
    api_key: str = "dummy",
) -> OpenAI:
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
    )


def get_issue_text(issues: dict = SELECTED_ISSUES) -> str:
    """Generate text with the selected issues to pass to the prompt.

    Returns:
        str: Text with all selected issue descriptions.
    """
    issue_text = ""
    for issue, description in issues.items():
        issue_text += f"* {issue} {description}\n"

    return issue_text.strip()


def get_section_data(start_date: str, end_date: str) -> pd.DataFrame:
    """Get the section data from the database within the specified date range.
    Args:
        start_date (str): Start date with ISSUEs.
        end_date (str): End date with ISSUEs.
    Returns:
        pd.DataFrame: DataFrame with the section data.
    """
    # Get the data in the database within the specified date range
    with get_db_connection(BRIEFINGS_DB_PATH) as conn:
        sections = get_sections_between_dates(conn=conn, start_date=start_date, end_date=end_date)

    # Get the section data from the briefings and store it in a DataFrame
    section_data = pd.DataFrame(
        [
            {
                "section_id": section.section_id,
                "briefing_id": section.briefing_id,
                "section_title": section.title,
                "section_text": section.text,
            }
            for section in sections
        ],
        columns=["section_id", "briefing_id", "section_title", "section_text"],
    )

    return section_data


def get_issue_data(model: str, issues: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Get the issue data from the database within the specified date range.
    Args:
        model (str): Model used to extract relevant ISSUEs.
        issues (list[str]): List of selected issues to extract.
        start_date (str): Start date with ISSUEs.
        end_date (str): End date with ISSUEs.
    Returns:
        pd.DataFrame: DataFrame with the issue data.
    """
    with get_db_connection() as conn:
        issue_data = get_issues_between_dates(conn=conn, start_date=start_date, end_date=end_date)

    issue_data = issue_data[(issue_data["model"] == model) & (issue_data["issue"].isin(issues))]
    issue_data["date"] = pd.to_datetime(issue_data["briefing_id"].astype(str), format="%Y%m%d")

    return issue_data


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


def _parse_issue_response(issues: str) -> list[str] | None:
    """Parse an LLM response and filter out invalid issues.

    Args:
        issues: Raw text returned by the LLM.

    Returns:
        A list of valid issues, or None if parsing fails.
    """
    try:
        parsed_issues = ast.literal_eval(issues)
    except (ValueError, SyntaxError):
        return None

    if not isinstance(parsed_issues, list):
        return None

    return [
        issue
        for issue in parsed_issues
        if isinstance(issue, str) and issue in SELECTED_ISSUES.keys()
    ]


def map_issue_to_sections(
    start_date: str,
    end_date: str,
    conn: sqlite3.Connection,
    model: str = "qwen3.5:4b",
    prompt: str = ISSUE_MAPPING_PROMPT,
    config: GenerationConfig = GenerationConfig(),
    overwrite: bool = False,
) -> None:
    if not _check_ollama_model_exists(model=model):
        logger.warning(f"Issues cannot be processed using the '{model}' model.")
        return

    section_data = get_section_data(start_date=start_date, end_date=end_date)

    generation_params = asdict(config)

    with _create_ollama_client() as client, mlflow.start_run(run_name=model):
        # Log model-level experiment settings
        mlflow.log_params(
            {
                "model": model,
                **generation_params,
                "n_sections": len(section_data),
            }
        )

        for _, section in section_data.iterrows():

            # Skip already processed sections
            if not overwrite and get_issue_by_section_id(
                conn=conn,
                section_id=section.section_id,
                model=model,
            ):
                logger.info(f"Issue section {section.section_id} by {model} already exists")
                continue

            section_text = f"**{section.section_title}**\n\n" f"{section.section_text}"

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt.format(
                            section_text=section_text,
                            issue_definitions=get_issue_text(SELECTED_ISSUES),
                        ),
                    }
                ],
                **generation_params,
            )

            # Set the section_id as a trace tag
            trace_id = mlflow.get_last_active_trace_id(thread_local=True)
            mlflow.flush_trace_async_logging()
            if trace_id is not None:
                mlflow.set_trace_tag(
                    trace_id,
                    "section_id",
                    str(section.section_id),
                )

            issues = _parse_issue_response(response.choices[0].message.content)

            if not issues:
                logger.warning(f"No issues returned for section {section.section_id}")
                continue

            insert_into_issue(
                conn=conn,
                briefing_id=section.briefing_id,
                section_id=section.section_id,
                issues=issues,
                model=model,
                created_at=datetime.fromtimestamp(response.created, tz=timezone.utc).isoformat(
                    timespec="seconds"
                ),
            )
