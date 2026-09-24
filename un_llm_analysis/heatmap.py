import sqlite3
import re
from pathlib import Path
from typing import Dict
from collections import Counter
from loguru import logger
import pandas as pd
import numpy as np
import curl_cffi
from bs4 import BeautifulSoup
from bokeh.plotting import figure, output_file, save
from bokeh.models import HoverTool, ColumnDataSource, ColorBar, LinearColorMapper
from bokeh.palettes import Viridis256
from bokeh.transform import transform


def get_countries_from_wikipedia() -> pd.DataFrame:
    """
    Scrape country data from Wikipedia.
    
    Fetches country codes, official names, and alternative names from the
    Wikipedia List of alternative country names page.
    
    Returns:
        DataFrame with columns:
            - code: ISO 3166-1 alpha-3 country code
            - name: Official country name
            - alternative_names: Pipe-separated alternative names
    
    Raises:
        Exception: If Wikipedia page cannot be reached or parsed
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
    
    Queries the database to retrieve section text along with briefing dates,
    then parses dates and extracts month periods for temporal analysis.
    
    Args:
        db_path: Path to SQLite database file
    
    Returns:
        DataFrame with columns:
            - section_id: Unique section identifier
            - text: Section content text
            - month: Month period (pd.Period) for grouping
    
    Raises:
        sqlite3.OperationalError: If database cannot be opened or query fails
    """
    conn = sqlite3.connect(db_path)

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
    conn.close()

    # Parse date and extract month
    sections_df['briefing_date'] = pd.to_datetime(sections_df['briefing_date'])
    sections_df['month'] = sections_df['briefing_date'].dt.to_period('M')

    return sections_df[['section_id', 'text', 'month']]

def clean_alternative_names(alt_names_str: str) -> str:
    """
    Remove problematic abbreviations from alternative names.
    
    Filters out single-letter or short abbreviations that are common English
    words (e.g., AND, OR, PNG, USA) to prevent false positive matches.
    
    Args:
        alt_names_str: Pipe-separated string of alternative names
    
    Returns:
        Cleaned pipe-separated string with problematic entries removed
    """
    if pd.isna(alt_names_str):
        return ""
    
    alt_names = alt_names_str.split("|")
    problematic = {'png', 'and', 'or', 'usa'}
    alt_names = [
        name for name in alt_names 
        if name.strip().lower() not in problematic
    ]
    
    return "|".join(alt_names)

def build_search_dict(country_df: pd.DataFrame) -> Dict[str, str]:
    """
    Build mapping of search terms to country codes.
    
    Creates a dictionary where keys are country names/alternative names
    (lowercase) and values are country codes. Only matches full country names,
    not country codes, to avoid false positives.
    
    Args:
        country_df: DataFrame with columns ['code', 'name', 'alternative_names']
    
    Returns:
        Dictionary mapping lowercase search terms to country codes (ISO 3166-1 alpha-3)
    
    Example:
        >>> df = pd.DataFrame({
        ...     'code': ['DE', 'US'],
        ...     'name': ['Germany', 'United States'],
        ...     'alternative_names': ['Bundesrepublik Deutschland', '']
        ... })
        >>> d = build_search_dict(df)
        >>> d['germany']
        'DE'
    """
    search_dict = {}

    for _, row in country_df.iterrows():
        code = row['code'].strip() if pd.notna(row['code']) else ""
        name = row['name'].strip() if pd.notna(row['name']) else ""
        alt_names = row['alternative_names'].split("|") if pd.notna(row['alternative_names']) else []

        country_key = code if code else name

        # Only match full country names and alternatives - skip codes
        if name:
            search_dict[name.lower()] = country_key
        
        # Only include alternatives with alphanumeric content
        for alt in alt_names:
            alt = alt.strip().lower()
            if alt and any(c.isalnum() for c in alt):  # Skip punctuation-only entries
                search_dict[alt] = country_key

    return search_dict

def compile_search_pattern(search_dict: Dict[str, str]) -> re.Pattern:
    """
    Compile regex pattern for efficient multi-term matching.
    
    Creates a word-boundary-aware regex pattern from search dictionary keys,
    enabling fast matching of all country names and alternatives in text.
    
    Args:
        search_dict: Dictionary mapping search terms to country codes
    
    Returns:
        Compiled regex pattern object with IGNORECASE flag
    
    Example:
        >>> d = {'germany': 'DE', 'deutschland': 'DE'}
        >>> pattern = compile_search_pattern(d)
        >>> pattern.findall('Germany and Deutschland')
        ['Germany', 'Deutschland']
    """
    pattern = r'\b(' + '|'.join(re.escape(term) for term in search_dict.keys()) + r')\b'
    return re.compile(pattern, re.IGNORECASE)

def count_mentions_in_section(
    section_text: str,
    search_dict: Dict[str, str],
    compiled_regex: re.Pattern
) -> Dict[str, int]:
    """
    Count country mentions in a single section of text.
    
    Finds all regex matches in the provided text and aggregates mention counts
    by country code, accounting for multiple mentions of the same country.
    
    Args:
        section_text: Text content to search
        search_dict: Dictionary mapping search terms to country codes
        compiled_regex: Pre-compiled regex pattern for efficient matching
    
    Returns:
        Dictionary mapping country codes to mention counts in this section
    
    Example:
        >>> text = "Germany and Deutschland"
        >>> d = {'germany': 'DE', 'deutschland': 'DE'}
        >>> pattern = compile_search_pattern(d)
        >>> counts = count_mentions_in_section(text, d, pattern)
        >>> counts['DE']
        2
    """
    counts = {}

    for match in compiled_regex.finditer(section_text):
        matched_term = match.group(1).lower()
        country_key = search_dict[matched_term]
        counts[country_key] = counts.get(country_key, 0) + 1

    return counts

def process_sections_to_heatmap(
    sections_df: pd.DataFrame,
    country_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Process all sections and generate heatmap data.
    
    Iterates through sections, counts country mentions, and aggregates by
    (month, country) pairs to create data suitable for heatmap visualization.
    
    Args:
        sections_df: DataFrame with columns ['section_id', 'text', 'month']
        country_df: DataFrame with columns ['code', 'name', 'alternative_names']
    
    Returns:
        DataFrame with columns:
            - month: Month period as string
            - country_code: ISO 3166-1 alpha-3 country code
            - count: Number of mentions in that month
    
    Example:
        >>> sections = pd.DataFrame({
        ...     'text': ['Germany and France', 'Deutschland rules'],
        ...     'month': [pd.Period('2024-01', 'M')] * 2
        ... })
        >>> countries = pd.DataFrame({
        ...     'code': ['DE', 'FR'],
        ...     'name': ['Germany', 'France'],
        ...     'alternative_names': ['Deutschland', '']
        ... })
        >>> heatmap = process_sections_to_heatmap(sections, countries)
        >>> len(heatmap) > 0
        True
    """
    search_dict = build_search_dict(country_df)
    compiled_regex = compile_search_pattern(search_dict)

    all_country_counts = {}

    for _, row in sections_df.iterrows():
        section_text = row['text']
        section_month = row['month']

        # Count mentions for this section
        counts = count_mentions_in_section(section_text, search_dict, compiled_regex)

        # Aggregate by (month, country) key
        for country_code, count in counts.items():
            key = (section_month, country_code)
            all_country_counts[key] = all_country_counts.get(key, 0) + count

    # Convert to DataFrame format
    heatmap_data = [
        {
            'month': str(month),
            'country_code': code,
            'count': count
        }
        for (month, code), count in all_country_counts.items()
    ]

    return pd.DataFrame(heatmap_data)

def create_bokeh_heatmap(
    heatmap_df: pd.DataFrame,
    output_path: str = 'heatmap.html',
    top_n: int = 25
) -> None:
    """
    Create interactive Bokeh heatmap visualization.
    
    Generates an HTML heatmap showing country mentions over time with:
    - Log-scale color mapping for better visibility
    - Interactive tooltips showing exact mention counts
    - Pan, zoom, and reset tools for exploration
    - Color bar legend
    
    Args:
        heatmap_df: DataFrame with columns ['month', 'country_code', 'count']
        output_path: Path where HTML file will be saved (default: 'heatmap.html')
        top_n: Number of top countries to display (default: 25)
    
    Returns:
        None (saves HTML file as side effect)
    
    Note:
        Uses logarithmic color scale (log1p) to spread color distribution
        across mention counts that may span multiple orders of magnitude.
    """
    # Filter to top N countries
    top_countries = heatmap_df.groupby('country_code')['count'].sum().nlargest(top_n).index
    heatmap_df = heatmap_df[heatmap_df['country_code'].isin(top_countries)].copy()
    heatmap_df = heatmap_df.sort_values(['month', 'country_code'])

    # Apply log scale for better color distribution
    heatmap_df['count_log'] = np.log1p(heatmap_df['count'])
    max_count_log = heatmap_df['count_log'].max()

    # Set up color mapping
    color_mapper = LinearColorMapper(
        palette=Viridis256,
        low=0,
        high=max_count_log
    )
    source = ColumnDataSource(heatmap_df)

    # Create figure
    p = figure(
        title=f"Country Mentions Heatmap - Top {top_n} Countries (log scale)",
        x_axis_label='Month',
        y_axis_label='Country',
        x_range=sorted(heatmap_df['month'].unique()),
        y_range=sorted(heatmap_df['country_code'].unique()),
        width=1200,
        height=600 + (top_n * 15),
        toolbar_location='right',
        tools='pan,wheel_zoom,box_zoom,reset,save'
    )

    # Add rectangles (heatmap cells)
    p.rect(
        x='month',
        y='country_code',
        width=0.9,
        height=0.9,
        source=source,
        fill_color=transform('count_log', color_mapper),
        line_color='white',
        line_width=1
    )

    # Add hover tool
    hover = HoverTool(
        tooltips=[
            ('Month', '@month'),
            ('Country', '@country_code'),
            ('Mentions', '@count')
        ]
    )
    p.add_tools(hover)

    # Add color bar
    color_bar = ColorBar(
        color_mapper=color_mapper,
        label_standoff=12,
        title='Mentions (log)'
    )
    p.add_layout(color_bar, 'right')

    # Style adjustments
    p.yaxis.major_label_text_font_size = "10pt"
    p.xaxis.major_label_orientation = 0.785  # 45 degrees
    p.grid.visible = False

    # Save to file
    output_file(output_path)
    save(p)
    logger.info(f"Heatmap saved to {output_path}")

def log_data_summary(heatmap_df: pd.DataFrame) -> None:
    """
    Print summary statistics about the heatmap data.
    
    Args:
        heatmap_df: DataFrame with columns ['month', 'country_code', 'count']
    """
    logger.info("\n" + "="*70)
    logger.info("DATA SUMMARY")
    logger.info("="*70)
    
    logger.info("\nDistribution of country mentions:")
    logger.info(heatmap_df.groupby('country_code')['count'].sum().describe())

    # Check top 25 coverage
    total_mentions = heatmap_df['count'].sum()
    top_25_countries = heatmap_df.groupby('country_code')['count'].sum().nlargest(25).index
    top_25_mentions = heatmap_df[heatmap_df['country_code'].isin(top_25_countries)]['count'].sum()
    pct = (top_25_mentions / total_mentions) * 100

    logger.info(f"\nTop 25 countries: {top_25_mentions:,.0f} mentions ({pct:.1f}% of total)")
    logger.info(f"Remaining {len(heatmap_df['country_code'].unique()) - 25} countries: "
          f"{total_mentions - top_25_mentions:,.0f} mentions ({100-pct:.1f}%)")

    logger.info("\nTop 10 countries by mentions:")
    top_countries = heatmap_df.groupby('country_code')['count'].sum().nlargest(10)
    logger.info(top_countries)
    logger.info("="*70 + "\n")
# %%
def analyse_country_mentions(
    country_code: str,
    heatmap_df: pd.DataFrame,
    sections_df: pd.DataFrame
) -> None:
    """
    Analyze mentions of a specific country.
    
    Args:
        country_code: ISO 3166-1 alpha-3 country code
        heatmap_df: DataFrame with aggregated mention counts
        sections_df: DataFrame with full section text
    """
    logger.info(f"\nAnalyzing mentions of {country_code}:")
    logger.info("-" * 50)
    
    # Get country name from briefing sections
    country_sections = sections_df[
        sections_df['text'].str.contains(country_code, case=False, na=False)
    ]
    
    if len(country_sections) == 0:
        logger.info(f"No sections found mentioning {country_code}")
        return
    
    total_mentions = heatmap_df[heatmap_df['country_code'] == country_code]['count'].sum()
    logger.info(f"Total mentions: {total_mentions}")
    logger.info(f"Sections containing term: {len(country_sections)}")
    logger.info(f"Average mentions per section: {total_mentions / len(country_sections):.1f}")
    
    # Top months
    by_month = heatmap_df[heatmap_df['country_code'] == country_code].sort_values('count', ascending=False)
    logger.info("\nTop 5 months:")
    logger.info(by_month.head(5)[['month', 'count']])

DB_PATH = Path("data/processed/database/briefings.db")
OUTPUT_DIR = "."
csv_path = Path(OUTPUT_DIR) / 'heatmap_data.csv'


logger.info(f"Database path: {DB_PATH}")
logger.info(f"Database exists: {DB_PATH.exists()}")

logger.info("\n" + "="*70)
logger.info("COUNTRY MENTIONS HEATMAP ANALYSIS - ISSUE #47")
logger.info("="*70 + "\n")

logger.info("Step 1: Fetching countries from Wikipedia...")
country_df = get_countries_from_wikipedia()
logger.info(f"Loaded {len(country_df)} countries")
if Path("data/countries_reference.csv").exists():
    country_df = pd.read_csv("data/countries_reference.csv")
    logger.info(f"Loaded {len(country_df)} countries from CSV")
else:
    logger.info("CSV not found, scraping from Wikipedia...")
    country_df = get_countries_from_wikipedia()
    country_df.to_csv("data/countries_reference.csv", index=False)
    logger.info(f"Loaded {len(country_df)} countries and saved to CSV")

logger.info("\nStep 2: Cleaning alternative names...")
country_df['alternative_names'] = country_df['alternative_names'].apply(clean_alternative_names)
logger.info("Done")

logger.info("\nStep 3: Extracting sections from database...")
sections_df = get_sections_from_db(DB_PATH)
logger.info(f"Loaded {len(sections_df)} sections")

logger.info("\nStep 4: Processing country mentions...")
heatmap_df = process_sections_to_heatmap(sections_df, country_df)
logger.info(f"Generated heatmap with {len(heatmap_df)} data points")

logger.info("\nStep 5: Exporting data...")
csv_path = Path(OUTPUT_DIR) / 'heatmap_data.csv'
heatmap_df.to_csv(csv_path, index=False)
logger.info(f"Exported to {csv_path}")

logger.info("\nStep 6: Creating Bokeh visualization...")
html_path = Path(OUTPUT_DIR) / 'heatmap.html'
create_bokeh_heatmap(heatmap_df, output_path=str(html_path), top_n=25)

log_data_summary(heatmap_df)
logger.info("Analysis complete!")

# Show distribution of mentions
logger.info("Distribution of country mentions:")
logger.info(heatmap_df.groupby('country_code')['count'].sum().describe())

top_countries = heatmap_df.groupby('country_code')['count'].sum().nlargest(10)
logger.info("\nTop 10 countries by mentions:")
logger.info(top_countries)

analyse_country_mentions('ZAF', heatmap_df, sections_df)

country_to_check = 'South Africa'
country_sections = sections_df[sections_df['text'].str.contains(country_to_check, case=False, na=False)]
logger.info(f"Total sections mentioning '{country_to_check}': {len(country_sections)}")

logger.info(f"\nFirst 3 sections mentioning '{country_to_check}':")
for idx, (i, row) in enumerate(country_sections.head(3).iterrows()):
    logger.info(f"\n--- Sample {idx + 1} ---")
    matches = re.finditer(r'.{0,100}' + country_to_check + r'.{0,100}', row['text'], re.IGNORECASE)
    for match in list(matches)[:2]:
        logger.info(match.group(0))