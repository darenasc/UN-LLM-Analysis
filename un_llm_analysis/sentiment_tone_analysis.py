"""
UN Briefings - Sentiment & Tone Analysis

RESPONSIBILITY
--------------
This file contains the SENTIMENT/TONE analysis logic only.

Database responsibilities belong to:
    un_llm_analysis/database.py

The database.py module should contain:
    - database/table creation
    - database connection
    - SELECT queries for source sections
    - INSERT queries for analysis_run
    - INSERT queries for sentiment_analysis
    - queries used to find completed sections

This module accesses those functions through imports.

IMPORTANT
---------
The function names imported below are an interface between the two modules.
If your database.py uses different names, change only the import block and
the small adapter functions in Section 2.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import re
import time

import ollama
from tqdm.auto import tqdm

from un_llm_analysis.database import (
    count_successful_sections,
    get_analysis_run,
    get_completed_section_ids,
    get_db_connection,
    get_latest_analysis_run,
    get_sections_for_sentiment_analysis,
    insert_into_analysis_run,
    insert_sentiment_analysis,
)

# ============================================================
# 1. ACCESS THE DATABASE LAYER
# ============================================================
#
# database.py owns the SQL.
# This file does NOT contain CREATE TABLE or INSERT SQL.
#
# These are the functions that database.py should expose.
#
# Example project structure:
#
# un_llm_analysis/
#     __init__.py
#     database.py
#     sentiment_tone_analysis.py
#
# ============================================================


# ============================================================
# 2. ANALYSIS CONFIGURATION
# ============================================================

MODEL_NAME = "llama3.2"

TEMPERATURE = 0
NUM_PREDICT = 50
KEEP_ALIVE = "10m"

MAX_WORKERS = 2
COMMIT_BATCH_SIZE = 20

ANALYSIS_NAME = "UN briefing sentiment and tone analysis"
PROMPT_VERSION = "v1.2"


SENTIMENT_CATEGORIES = {
    "Positive",
    "Neutral",
    "Negative",
}


TONE_CATEGORIES = {
    "Diplomatic",
    "Concerned",
    "Critical",
    "Urgent",
    "Optimistic",
    "Neutral/Informational",
    "Constructive",
}


ANALYSIS_PROMPT = """
Analyze the following UN briefing section.

Classify its sentiment as exactly one of:

- Positive
- Neutral
- Negative

Classify its primary tone as exactly one of:

- Diplomatic
- Concerned
- Critical
- Urgent
- Optimistic
- Neutral/Informational
- Constructive

Return ONLY this JSON structure:

{"sentiment": "<sentiment>", "tone": "<tone>"}

Do not provide explanations.
Do not provide additional fields.

Text:

__SECTION_TEXT__
""".strip()


# ============================================================
# 3. GENERAL HELPERS
# ============================================================


def utc_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def build_prompt(text: str) -> str:
    """Insert a section's text into the analysis prompt."""
    return ANALYSIS_PROMPT.replace(
        "__SECTION_TEXT__",
        str(text),
    )


# ============================================================
# 4. MODEL RESPONSE VALIDATION
# ============================================================


def parse_and_validate(raw_response: str) -> dict:
    """
    Parse Ollama JSON and make sure sentiment/tone are valid.
    """

    raw_response = raw_response.strip()

    # Remove accidental markdown fences.
    raw_response = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        raw_response,
        flags=re.IGNORECASE,
    ).strip()

    result = json.loads(raw_response)

    expected_keys = {"sentiment", "tone"}

    if set(result.keys()) != expected_keys:
        raise ValueError(f"Unexpected JSON fields: {list(result.keys())}")

    sentiment = result["sentiment"]
    tone = result["tone"]

    if sentiment not in SENTIMENT_CATEGORIES:
        raise ValueError(f"Invalid sentiment: {sentiment}")

    if tone not in TONE_CATEGORIES:
        raise ValueError(f"Invalid tone: {tone}")

    return result


# ============================================================
# 5. SENTIMENT + TONE MODEL LOGIC
# ============================================================


def analyze_section(text: str):
    """
    Send one UN briefing section to Ollama.

    Returns:
        sentiment,
        tone,
        status,
        error_message
    """

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": build_prompt(text),
                }
            ],
            format="json",
            options={
                "temperature": TEMPERATURE,
                "num_predict": NUM_PREDICT,
            },
            keep_alive=KEEP_ALIVE,
        )

        result = parse_and_validate(response["message"]["content"])

        return (
            result["sentiment"],
            result["tone"],
            "success",
            None,
        )

    except Exception as exc:

        return (
            None,
            None,
            "error",
            f"{type(exc).__name__}: {exc}",
        )


# ============================================================
# 6. PROCESS ONE DATABASE ROW
# ============================================================


def process_row(row, analysis_id: int) -> dict:
    """
    Analyze one section.

    Database INSERT is NOT performed here.
    The result is returned to the main thread.
    """

    sentiment, tone, status, error = analyze_section(row["section_text"])

    return {
        "analysis_id": analysis_id,
        "briefing_id": int(row["briefing_id"]),
        "section_id": int(row["section_id"]),
        "briefing_date": row.get("briefing_date"),
        "sentiment": sentiment,
        "tone": tone,
        "status": status,
        "error_message": error,
        "created_at": utc_now(),
    }


# ============================================================
# 7. TEST ONE SECTION
# ============================================================


def test_model(df) -> None:
    """
    Test Ollama before processing the complete database.
    """

    if df.empty:
        raise ValueError("No sections were returned from the database.")

    first_row = df.iloc[0]

    print("Testing first section...")
    print(
        "section_id:",
        first_row["section_id"],
    )

    sentiment, tone, status, error = analyze_section(first_row["section_text"])

    print("Sentiment:", sentiment)
    print("Tone:", tone)
    print("Status:", status)
    print("Error:", error)

    if status != "success":
        raise RuntimeError(f"Ollama test failed: {error}")


# ============================================================
# 8. FULL DATABASE ANALYSIS
# ============================================================


def run_analysis(
    start_date: str | None = None,
    end_date: str | None = None,
    resume_analysis_id: int | None = None,
):
    """
    Run sentiment/tone analysis for the complete source dataset.

    Database operations are delegated to database.py.
    """

    print("=" * 70)
    print("UN BRIEFINGS - SENTIMENT & TONE ANALYSIS")
    print("=" * 70)

    # --------------------------------------------------------
    # A. Open the existing project database
    # --------------------------------------------------------

    conn = get_db_connection()

    try:

        # ----------------------------------------------------
        # B. Get source sections from database.py
        # ----------------------------------------------------

        df = get_sections_for_sentiment_analysis(
            conn,
            start_date=start_date,
            end_date=end_date,
        )

        if df.empty:
            print("No sections available for analysis.")
            return

        print(f"Source sections: {len(df)}")

        # --------------------------------------------------------
        # C. Find existing incomplete run OR create a new run
        # --------------------------------------------------------

        if resume_analysis_id is not None:

            # Explicit manual resume
            analysis_id = resume_analysis_id

            print(
                "Resuming analysis_id:",
                analysis_id,
            )

        else:

            # Find the latest analysis run
            latest_analysis_id = get_latest_analysis_run(
                conn,
                ANALYSIS_NAME,
            )

            if latest_analysis_id is None:

                # No previous run exists
                analysis_id = insert_into_analysis_run(
                    conn=conn,
                    analysis_name=ANALYSIS_NAME,
                    model_name=MODEL_NAME,
                    model_version="ollama",
                    ollama_version=None,
                    prompt_version=PROMPT_VERSION,
                    prompt=ANALYSIS_PROMPT,
                    temperature=TEMPERATURE,
                )

                print(
                    "Created first analysis_id:",
                    analysis_id,
                )

            else:

                # Check how many sections were successfully analysed
                successful_count = count_successful_sections(
                    conn,
                    latest_analysis_id,
                )

                total_sections = len(df)

                print(f"Latest analysis_id: " f"{latest_analysis_id}")

                print(f"Successful sections: " f"{successful_count}/{total_sections}")

                if successful_count < total_sections:

                    # Previous run is incomplete.
                    # Resume it.
                    analysis_id = latest_analysis_id

                    print("Resuming incomplete " f"analysis_id: {analysis_id}")

                else:

                    # Previous run is completely finished.
                    # Start a NEW analysis run.
                    analysis_id = insert_into_analysis_run(
                        conn=conn,
                        analysis_name=ANALYSIS_NAME,
                        model_name=MODEL_NAME,
                        model_version="ollama",
                        ollama_version=None,
                        prompt_version=PROMPT_VERSION,
                        prompt=ANALYSIS_PROMPT,
                        temperature=TEMPERATURE,
                    )

                    print("Previous analysis is complete.")

                    print(
                        "Created new analysis_id:",
                        analysis_id,
                    )
        # ----------------------------------------------------
        # D. Find sections already successfully analysed
        # ----------------------------------------------------

        completed_ids = get_completed_section_ids(
            conn,
            analysis_id,
        )

        pending_df = df[~df["section_id"].astype(int).isin(completed_ids)].copy()

        print(
            "Already successful:",
            len(completed_ids),
        )

        print(
            "Remaining:",
            len(pending_df),
        )

        if pending_df.empty:
            print("All sections already have " "successful sentiment/tone results.")
            return

        # ----------------------------------------------------
        # E. Process sections with Ollama
        # ----------------------------------------------------

        rows = pending_df.to_dict(orient="records")

        total = len(rows)
        processed = 0

        started = time.time()

        print(f"Starting {total} sections...")

        # Ollama calls happen in worker threads.
        # Database writes remain in the main thread.
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

            for batch_start in range(
                0,
                total,
                COMMIT_BATCH_SIZE,
            ):

                batch = rows[batch_start : batch_start + COMMIT_BATCH_SIZE]

                futures = [
                    executor.submit(
                        process_row,
                        row,
                        analysis_id,
                    )
                    for row in batch
                ]

                results = []

                for future in tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc="Analysing",
                ):

                    results.append(future.result())

                # --------------------------------------------
                # F. Store results through database.py
                # --------------------------------------------

                for result in results:

                    insert_sentiment_analysis(
                        conn=conn,
                        analysis_id=result["analysis_id"],
                        briefing_id=result["briefing_id"],
                        section_id=result["section_id"],
                        briefing_date=result["briefing_date"],
                        sentiment=result["sentiment"],
                        tone=result["tone"],
                        status=result["status"],
                        error_message=result.get("error_message"),
                    )

                # Commit using the database connection.
                conn.commit()

                processed += len(results)

                elapsed = time.time() - started

                rate = processed / elapsed if elapsed > 0 else 0

                remaining = total - processed

                eta = remaining / rate if rate > 0 else 0

                print()
                print(f"Processed " f"{processed}/{total}")

                print(f"Rate: " f"{rate:.2f} sections/sec")

                print(f"Elapsed: " f"{elapsed / 60:.1f} minutes")

                print(f"Estimated remaining: " f"{eta / 60:.1f} minutes")

        print()
        print("=" * 70)
        print("ANALYSIS COMPLETE")
        print("=" * 70)

    finally:

        conn.close()

        print("Database connection closed.")


# ============================================================
# 9. COMMAND-LINE ENTRY POINT
# ============================================================
if __name__ == "__main__":
    run_analysis()
