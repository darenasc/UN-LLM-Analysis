import sqlite3

import pandas as pd

from un_llm_analysis.database import (
    get_sentiment_results_between_dates,
)


def get_existing_sentiment_analysis(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
    model_name: str,
) -> pd.DataFrame:
    """Check whether successful analysis results exist for a model
    within the requested date range.

    Args:
        conn: SQLite database connection.
        start_date: Requested start date (YYYY-MM-DD).
        end_date: Requested end date (YYYY-MM-DD).
        model_name: Name of the model to check.

    Returns:
        A DataFrame containing matching analysis summaries,
        or an empty DataFrame if no matching analysis exists.
    """
    results = get_sentiment_results_between_dates(
        conn=conn,
        start_date=start_date,
        end_date=end_date,
    )

    if results.empty:
        return pd.DataFrame(
            columns=[
                "analysis_id",
                "model_name",
                "min_date",
                "max_date",
                "total_sections",
            ]
        )

    # Keep successful analysis results.
    successful_results = results[results["status"] == "success"]

    if successful_results.empty:
        return pd.DataFrame(
            columns=[
                "analysis_id",
                "model_name",
                "min_date",
                "max_date",
                "total_sections",
            ]
        )

    # Group by analysis_id and model_name.
    date_summary = (
        successful_results.groupby(["analysis_id", "model_name"])
        .agg(
            min_date=("briefing_date", "min"),
            max_date=("briefing_date", "max"),
            total_sections=("section_id", "count"),
        )
        .reset_index()
        .sort_values(["model_name", "analysis_id"])
    )

    # Match the requested model and exact date range.
    matching_results = date_summary[
        (date_summary["model_name"] == model_name)
        & (date_summary["min_date"] == start_date)
        & (date_summary["max_date"] == end_date)
    ].copy()

    if not matching_results.empty:
        print(
            f"Analysis already exists for {start_date} to {end_date} "
            f"using model '{model_name}'."
        )
        return matching_results

    print(
        f"No matching analysis found for {start_date} to {end_date} "
        f"using model '{model_name}'."
    )

    return matching_results
