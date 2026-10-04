"""Script to populate country_mentions table from existing sections.

This script reads all sections from the database, counts country mentions
in each section using country data from Wikipedia, and stores the counts
in the country_mentions table.
"""

import argparse
import sqlite3

from loguru import logger
import pandas as pd

from un_llm_analysis.config import BRIEFINGS_DB, get_country_data
from un_llm_analysis.database import (
    delete_country_mentions_by_section,
    get_db_connection,
    insert_country_mentions,
)


def _count_country_mentions(section_text: str, country_row: pd.Series) -> int:
    """Count mentions of a country in section text.

    A country is mentioned if its code, name, or any alternative name appears.
    Counts the total number of times any of the country's names appear.

    Args:
        section_text (str): Text content of the section.
        country_row (pd.Series): Row from country DataFrame.

    Returns:
        int: Total number of mentions of any country name variant.
    """
    search_terms = [
        country_row["code"],
        country_row["name"],
    ]
    # Add alternative names
    if pd.notna(country_row["alternative_names"]):
        search_terms.extend(country_row["alternative_names"].split("|"))

    total_count = 0
    for term in search_terms:
        # Count how many times this specific term appears
        term_lower = term.lower()
        section_lower = section_text.lower()
        count = section_lower.count(term_lower)
        total_count += count

    return total_count


def populate_country_mentions_for_all_sections(
    conn: sqlite3.Connection, countries_df: pd.DataFrame, overwrite: bool = False
) -> None:
    """Populate country_mentions table for all sections.

    Args:
        conn (sqlite3.Connection): Database connection.
        countries_df (pd.DataFrame): DataFrame with country data.
        overwrite (bool): Whether to overwrite existing mentions. Defaults to False.
    """
    # Get all sections
    cursor = conn.cursor()
    cursor.execute("SELECT section_id, briefing_id, section_order, title, text FROM section")
    sections = cursor.fetchall()
    cursor.close()

    logger.info(f"Processing {len(sections)} sections")

    for section in sections:
        section_id = section["section_id"]
        section_text = section["text"]

        # Delete existing mentions if overwrite
        if overwrite:
            delete_country_mentions_by_section(conn, section_id)

        # Count mentions for each country
        for _, country in countries_df.iterrows():
            count = _count_country_mentions(section_text, country)
            if count > 0:
                insert_country_mentions(
                    conn,
                    section_id,
                    country["code"],
                    country["name"],
                    count,
                )

    logger.info("Country mentions populated successfully")


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Populate country_mentions table from existing sections."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing country mentions instead of skipping them.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(BRIEFINGS_DB),
        help="Path to the database file.",
    )
    args = parser.parse_args()

    logger.info("Starting country mentions population")

    # Fetch country data from config
    countries_data = get_country_data()
    countries_df = pd.DataFrame(countries_data, columns=["code", "name", "alternative_names"])
    logger.info(f"Loaded {len(countries_df)} countries")

    # Connect to database
    with get_db_connection(args.db_path) as conn:
        populate_country_mentions_for_all_sections(conn, countries_df, overwrite=args.overwrite)

    logger.info("Country mentions population complete")


if __name__ == "__main__":
    main()
