import json
import sqlite3

from loguru import logger
import mlflow
import pandas as pd
from tqdm import tqdm

from un_llm_analysis.database import (
    get_db_connection,
    get_sentiment_results_between_dates,
    insert_into_analysis_run,
    insert_sentiment_analysis,
)
from un_llm_analysis.prompts import (
    SENTIMENT_ANALYSIS_PROMPT,
    VALID_SENTIMENTS,
    VALID_TONES,
    run_model_prompt,
    sentiment_analysis_prompt_version,
)
from un_llm_analysis.utils import _check_ollama_model_exists


## analysis checking
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


## sentiment analysis run


def run_sentiment_analysis(
    section_data: pd.DataFrame,
    start_date: str,
    end_date: str,
    model_name: str = "llama3.2:latest",
    temperature: float = 0,
    overwrite: bool = False,
) -> dict:
    """Run sentiment and tone analysis with MLflow tracking.

    Returns a summary with the results of the analysis with all or some of the
    following fields:
    - "status"
    - "analysis_id"
    - "model"
    - "successful_sections"
    - "failed_sections"
    - "start_date"
    - "end_date"

    Args:
        section_data (pd.DataFrame): Section data from briefings to be analysed.
        start_date (str): Start date of the analysis in format 'YYYY-MM-DD'.
        end_date (str): End date of the analysis in format 'YYYY-MM-DD'.
        model_name (_type_, optional): Name of the LLM to be used with Ollama.
            The model must exists in your local Ollama server.
            Defaults to "llama3.2:latest".
        temperature (float, optional): Temperature to use to query the LLM.
            Defaults to 0. Cero minimises variations in the answers.
        overwrite (bool, optional): Whether or not to overwrite previous results.
            Defaults to False.

    Returns:
        dict: Summary with the results of the analysis.
    """

    # Validate Ollama model before database operations.
    if not _check_ollama_model_exists(model=model_name):
        logger.error(f"Cannot run sentiment analysis. Model '{model_name}' is not available.")

        return {
            "status": "failed",
            "reason": "model_not_available",
            "model": model_name,
        }

    conn = None

    try:
        # Continue with your existing database and analysis logic...

        # Create the database connection.
        conn = get_db_connection()

        # Check whether matching analysis results already exist.
        existing_results = get_existing_sentiment_analysis(
            conn=conn,
            start_date=start_date,
            end_date=end_date,
            model_name=model_name,
        )

        # Skip if matching results already exist.
        if not overwrite and not existing_results.empty:
            logger.info(
                f"Skipping analysis: {model_name} already has results for {start_date} to {end_date}."
            )

            return {
                "status": "skipped",
                "model": model_name,
                "start_date": start_date,
                "end_date": end_date,
            }

        # Check whether briefing sections are available.
        if section_data.empty:
            raise ValueError("No briefing sections available for analysis.")

        logger.info(
            f"Starting sentiment analysis using {model_name} from {start_date} to {end_date}."
        )

        # Create a new analysis run in the database.
        analysis_id = insert_into_analysis_run(
            conn=conn,
            analysis_name="UN briefing sentiment and tone analysis",
            model_name=model_name,
            model_version=model_name,
            ollama_version=None,
            prompt_version=sentiment_analysis_prompt_version,
            prompt=SENTIMENT_ANALYSIS_PROMPT,
            temperature=temperature,
        )

        # Initialize counters.
        success_count = 0
        error_count = 0
        # MLflow configuration
        mlflow.set_tracking_uri("http://127.0.0.1:5000")
        mlflow.set_experiment("sentiment and tone analysis")
        # Start MLflow tracking.
        with mlflow.start_run(run_name=f"{model_name}-{sentiment_analysis_prompt_version}"):
            mlflow.log_params(
                {
                    "model": model_name,
                    "prompt_version": sentiment_analysis_prompt_version,
                    "temperature": temperature,
                    "n_sections": len(section_data),
                    "start_date": start_date,
                    "end_date": end_date,
                    "overwrite": overwrite,
                }
            )

            # Log the prompt template.
            mlflow.log_text(
                SENTIMENT_ANALYSIS_PROMPT,
                "prompts/analysis_prompt.txt",
            )

            # Process each briefing section.
            for _, section in tqdm(
                section_data.iterrows(),
                total=len(section_data),
                desc=f"Classifying with {model_name}",
            ):
                sentiment = None
                tone = None
                status = "error"
                error_message = None

                try:
                    # Handle missing section text.
                    text_value = section.get("section_text")

                    section_text = "" if pd.isna(text_value) else str(text_value).strip()

                    # Check whether section text is available.
                    if not section_text:
                        raise ValueError("Section text is empty.")

                    # Construct the prompt.
                    prompt = SENTIMENT_ANALYSIS_PROMPT.format(
                        text=section_text,
                    )

                    # Call the existing Ollama interface.
                    result = run_model_prompt(
                        model=model_name,
                        prompt=prompt,
                        think=False,
                        temperature=temperature,
                    )

                    # Extract the model response.
                    result_text = result["response"]

                    if not result_text:
                        raise ValueError("The model returned an empty response.")

                    # Parse the JSON response.
                    model_result = json.loads(result_text)

                    if not isinstance(model_result, dict):
                        raise ValueError("Model response must be a JSON object.")

                    # Extract sentiment and tone.
                    sentiment = model_result.get("sentiment")
                    tone = model_result.get("tone")

                    # Validate sentiment.
                    if sentiment not in VALID_SENTIMENTS:
                        raise ValueError(
                            f"Invalid sentiment label: {sentiment!r}. "
                            f"Expected one of "
                            f"{sorted(VALID_SENTIMENTS)}"
                        )

                    # Validate tone.
                    if tone not in VALID_TONES:
                        raise ValueError(
                            f"Invalid tone label: {tone!r}. "
                            f"Expected one of {sorted(VALID_TONES)}"
                        )

                    # Mark the result as successful.
                    status = "success"
                    success_count += 1

                except Exception as exc:
                    # Record errors without stopping the entire loop.
                    error_message = f"{type(exc).__name__}: {exc}"
                    error_count += 1

                    logger.error(
                        f"Analysis failed for section {section.get('section_id')}: {error_message}"
                    )

                # Save each result, including failures.
                insert_sentiment_analysis(
                    conn=conn,
                    analysis_id=analysis_id,
                    briefing_id=int(section.briefing_id),
                    section_id=int(section.section_id),
                    briefing_date=section.get("briefing_date"),
                    sentiment=sentiment,
                    tone=tone,
                    status=status,
                    error_message=error_message,
                )

            # Log final metrics to MLflow.
            mlflow.log_metrics(
                {
                    "successful_sections": success_count,
                    "failed_sections": error_count,
                }
            )

        # Return the analysis summary.
        summary = {
            "status": "completed",
            "analysis_id": analysis_id,
            "model": model_name,
            "successful_sections": success_count,
            "failed_sections": error_count,
        }

        logger.info(
            f"Analysis run {analysis_id} finished: {success_count} successful, {error_count} failed."
        )

        return summary

    finally:
        # Always close the database connection.
        if conn is not None:
            conn.close()
