"""Country mentions heatmap analysis for UN briefing database - Issue #47.

This script is executable: python heatmap_47_clean.py

It performs the following steps:
1. Load country data (from CSV or scrape Wikipedia)
2. Clean alternative names
3. Extract sections from database
4. Count country mentions
5. Export data to CSV
6. Generate interactive Bokeh visualization
"""

from pathlib import Path
import re
import sqlite3
from typing import Dict

from bokeh.models import ColorBar, ColumnDataSource, HoverTool, LinearColorMapper
from bokeh.palettes import Viridis256
from bokeh.plotting import figure, output_file, save
from bokeh.transform import transform
from bs4 import BeautifulSoup
import curl_cffi
from loguru import logger
import numpy as np
import pandas as pd

from un_llm_analysis.config import COUNTRY_CSV_PATH, PROCESSED_DATA_DIR
from un_llm_analysis.database import get_db_connection

# ============================================================================
# FUNCTIONS
# ============================================================================


def get_countries_from_wikipedia() -> pd.DataFrame:
    """
    Scrape country data from Wikipedia.

    Fetches country codes, official names, and alternative names from the
    Wikipedia List of alternative country names page.

    Returns:
        DataFrame with columns: code, name, alternative_names
    """
    url = "https://en.wikipedia.org/wiki/List_of_alternative_country_names"
    response = curl_cffi.get(url, impersonate="chrome")
    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all(class_="wikitable")

    data = []
    for table in tables:
        for row in table.find_all("tr")[1:]:  # Skip header row
            cell_data = row.find_all("td")
            if len(cell_data) == 3:
                code, name, names = cell_data
                country_name = name.find("a")["title"].strip()
                other_names = "|".join(
                    [x.text.strip() for x in names.find_all("b")]
                    + [x.text.strip() for x in names.find_all("i")]
                )
                data.append((code.text.strip(), country_name, other_names))

    return pd.DataFrame(data, columns=["code", "name", "alternative_names"])


def get_countries_data(csv_path: Path | str) -> pd.DataFrame:
    """Load country data from CSV reference file."""
    return pd.read_csv(csv_path)


def get_sections_from_db(db_path: Path | str) -> pd.DataFrame:
    """
    Extract briefing sections from SQLite database.

    Args:
        db_path: Path to SQLite database file

    Returns:
        DataFrame with columns: section_id, text, month (as pd.Period)
    """
    conn = get_db_connection(str(db_path))

    try:
        query = """
        SELECT
            s.section_id,
            s.briefing_id,
            s.text,
            b.briefing_date
        FROM section s
        JOIN briefing b ON s.briefing_id = b.briefing_id
        WHERE s.text IS NOT NULL AND b.briefing_date IS NOT NULL
        """

        sections_df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    # Parse date and extract month
    sections_df["briefing_date"] = pd.to_datetime(sections_df["briefing_date"])
    sections_df["month"] = sections_df["briefing_date"].dt.to_period("M")

    return sections_df[["section_id", "text", "month"]]


def clean_alternative_names(alt_names_str: str) -> str:
    """
    Remove problematic abbreviations from alternative names.

    Filters out: AND, OR, PNG, USA to prevent false positives.
    """
    if pd.isna(alt_names_str):
        return ""

    alt_names = alt_names_str.split("|")
    problematic = {"png", "and", "or", "usa"}
    alt_names = [name for name in alt_names if name.strip().lower() not in problematic]

    return "|".join(alt_names)


def build_search_dict(country_df: pd.DataFrame) -> Dict[str, str]:
    """
    Build mapping of search terms to country codes.

    Key design: Only matches country NAMES/alternatives, not codes.
    This prevents false positives like AND→Andorra.
    """
    search_dict = {}

    for _, row in country_df.iterrows():
        code = row["code"].strip() if pd.notna(row["code"]) else ""
        name = row["name"].strip() if pd.notna(row["name"]) else ""
        alt_names = (
            row["alternative_names"].split("|") if pd.notna(row["alternative_names"]) else []
        )

        country_key = code if code else name

        # Only match full country names - NOT codes
        if name:
            search_dict[name.lower()] = country_key

        # Only include alternatives with alphanumeric content
        for alt in alt_names:
            alt = alt.strip().lower()
            if alt and any(c.isalnum() for c in alt):
                search_dict[alt] = country_key

    return search_dict


def compile_search_pattern(search_dict: Dict[str, str]) -> re.Pattern:
    """Compile word-boundary-aware regex pattern for matching."""
    pattern = r"\b(" + "|".join(re.escape(term) for term in search_dict.keys()) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


def count_mentions_in_section(
    section_text: str, search_dict: Dict[str, str], compiled_regex: re.Pattern
) -> Dict[str, int]:
    """Count country mentions in a single section of text."""
    counts = {}

    for match in compiled_regex.finditer(section_text):
        matched_term = match.group(1).lower()
        country_key = search_dict[matched_term]
        counts[country_key] = counts.get(country_key, 0) + 1

    return counts


def process_sections_to_heatmap(
    sections_df: pd.DataFrame, country_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Process all sections and generate heatmap data.

    Returns:
        DataFrame with columns: month, country_code, count
    """
    search_dict = build_search_dict(country_df)
    compiled_regex = compile_search_pattern(search_dict)

    all_country_counts = {}

    for _, row in sections_df.iterrows():
        section_text = row["text"]
        section_month = row["month"]

        # Count mentions for this section
        counts = count_mentions_in_section(section_text, search_dict, compiled_regex)

        # Aggregate by (month, country) key
        for country_code, count in counts.items():
            key = (section_month, country_code)
            all_country_counts[key] = all_country_counts.get(key, 0) + count

    # Convert to DataFrame format
    heatmap_data = [
        {"month": str(month), "country_code": code, "count": count}
        for (month, code), count in all_country_counts.items()
    ]

    return pd.DataFrame(heatmap_data)


def create_bokeh_heatmap(
    heatmap_df: pd.DataFrame, output_path: str = "heatmap.html", top_n: int = 25
) -> None:
    """
    Create interactive Bokeh heatmap visualization.

    Args:
        heatmap_df: DataFrame with columns [month, country_code, count]
        output_path: Path where HTML file will be saved
        top_n: Number of top countries to display
    """
    # Filter to top N countries
    top_countries = heatmap_df.groupby("country_code")["count"].sum().nlargest(top_n).index
    heatmap_df = heatmap_df[heatmap_df["country_code"].isin(top_countries)].copy()
    heatmap_df = heatmap_df.sort_values(["month", "country_code"])

    # Apply log scale for better color distribution
    heatmap_df["count_log"] = np.log1p(heatmap_df["count"])
    max_count_log = heatmap_df["count_log"].max()

    # Set up color mapping
    color_mapper = LinearColorMapper(palette=Viridis256, low=0, high=max_count_log)
    source = ColumnDataSource(heatmap_df)

    # Create figure
    p = figure(
        title=f"Country Mentions Heatmap - Top {top_n} Countries (log scale)",
        x_axis_label="Month",
        y_axis_label="Country",
        x_range=sorted(heatmap_df["month"].unique()),
        y_range=sorted(heatmap_df["country_code"].unique()),
        width=1200,
        height=600 + (top_n * 15),
        toolbar_location="right",
        tools="pan,wheel_zoom,box_zoom,reset,save",
    )

    # Add rectangles (heatmap cells)
    p.rect(
        x="month",
        y="country_code",
        width=0.9,
        height=0.9,
        source=source,
        fill_color=transform("count_log", color_mapper),
        line_color="white",
        line_width=1,
    )

    # Add hover tool
    hover = HoverTool(
        tooltips=[("Month", "@month"), ("Country", "@country_code"), ("Mentions", "@count")]
    )
    p.add_tools(hover)

    # Add color bar
    color_bar = ColorBar(color_mapper=color_mapper, label_standoff=12, title="Mentions (log)")
    p.add_layout(color_bar, "right")

    # Style adjustments
    p.yaxis.major_label_text_font_size = "10pt"
    p.xaxis.major_label_orientation = 0.785  # 45 degrees
    p.grid.visible = False

    # Save to file
    output_file(output_path)
    save(p)
    logger.info(f"Heatmap saved to {output_path}")


def save_heatmap_to_db(heatmap_df: pd.DataFrame, db_path: Path | str) -> None:
    """
    Save heatmap data to SQLite database.

    Appends to table: country_mention_heatmap
    Columns: month, country_code, count
    """
    conn = get_db_connection(str(db_path))

    try:
        heatmap_df.to_sql(
            "country_mention_heatmap",
            conn,
            index=False,
            if_exists="append",  # Changed from "replace"
        )

        conn.commit()
        logger.info(f"✓ Appended {len(heatmap_df)} rows to country_mention_heatmap")
    finally:
        conn.close()


# ============================================================================
# CONFIGURATION
# ============================================================================

# Dev database location
DB_PATH = PROCESSED_DATA_DIR / "database" / "briefings.db"
OUTPUT_DIR = PROCESSED_DATA_DIR / "output"

# Create output directory if needed
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def main() -> None:
    """Main pipeline execution."""
    logger.info("=" * 70)
    logger.info("COUNTRY MENTIONS HEATMAP ANALYSIS - ISSUE #47")
    logger.info("=" * 70)

    # Step 1: Load countries
    logger.info("\nStep 1: Loading countries...")
    if COUNTRY_CSV_PATH.exists():
        country_df = get_countries_data(COUNTRY_CSV_PATH)
        logger.info(f"✓ Loaded {len(country_df)} countries from CSV")
    else:
        logger.info("CSV not found, scraping from Wikipedia...")
        country_df = get_countries_from_wikipedia()
        country_df.to_csv(COUNTRY_CSV_PATH, index=False)
        logger.info(f"✓ Scraped and saved {len(country_df)} countries to CSV")

    # Step 2: Clean alternative names
    logger.info("\nStep 2: Cleaning alternative names...")
    country_df["alternative_names"] = country_df["alternative_names"].apply(
        clean_alternative_names
    )
    logger.info("✓ Done")

    # Step 3: Extract sections from database
    logger.info("\nStep 3: Extracting sections from database...")
    logger.info(f"Database path: {DB_PATH}")
    logger.info(f"Database exists: {DB_PATH.exists()}")

    sections_df = get_sections_from_db(DB_PATH)
    logger.info(f"✓ Loaded {len(sections_df)} sections")

    # Step 4: Process country mentions
    logger.info("\nStep 4: Processing country mentions...")
    heatmap_df = process_sections_to_heatmap(sections_df, country_df)
    logger.info(f"✓ Generated heatmap with {len(heatmap_df)} data points")

    # Step 5: Save to database
    logger.info("\nStep 5: Saving to database...")
    save_heatmap_to_db(heatmap_df, DB_PATH)

    # Step 6: Create visualization
    logger.info("\nStep 6: Creating Bokeh visualization...")
    html_path = OUTPUT_DIR / "heatmap.html"
    create_bokeh_heatmap(heatmap_df, output_path=str(html_path), top_n=25)
    logger.info("✓ Visualization created")

    # Summary statistics
    logger.info("\n" + "=" * 70)
    logger.info("DATA SUMMARY")
    logger.info("=" * 70)

    logger.info("\nDistribution of country mentions:")
    print(heatmap_df.groupby("country_code")["count"].sum().describe())

    total_mentions = heatmap_df["count"].sum()
    top_25_countries = heatmap_df.groupby("country_code")["count"].sum().nlargest(25).index
    top_25_mentions = heatmap_df[heatmap_df["country_code"].isin(top_25_countries)]["count"].sum()
    pct = (top_25_mentions / total_mentions) * 100

    logger.info(f"\nTop 25 countries: {top_25_mentions:,.0f} mentions ({pct:.1f}% of total)")
    logger.info(
        f"Remaining {len(heatmap_df['country_code'].unique()) - 25} countries: "
        f"{total_mentions - top_25_mentions:,.0f} mentions ({100-pct:.1f}%)"
    )

    logger.info("\nTop 10 countries by mentions:")
    top_countries = heatmap_df.groupby("country_code")["count"].sum().nlargest(10)
    print(top_countries)

    logger.info("=" * 70)
    logger.info("Analysis complete! ✓")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
