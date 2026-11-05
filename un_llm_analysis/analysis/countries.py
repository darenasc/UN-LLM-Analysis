"""Countries module with functions to download data about conutries and flags"""

import ast
from io import StringIO
from pathlib import Path
import sqlite3
from typing import Literal

from bs4 import BeautifulSoup
import curl_cffi
import geopandas as gpd  # type: ignore
from loguru import logger
import pandas as pd
import plotly.express as px  # type: ignore
import requests
from tqdm import tqdm

from un_llm_analysis.config import APP_DIR, FLAGS_DIR
from un_llm_analysis.database import (
    _check_country_section_exists,
    check_country_section_model_exists,
    get_briefings_between_dates,
    insert_into_country,
)
from un_llm_analysis.prompts import COUNTRY_MENTION_PROMPT, run_model_prompt

HeatmapLevel = Literal["date", "week", "month", "year"]


def create_heatmap(
    df_country: pd.DataFrame, level: HeatmapLevel = "month", color_map="viridis"
):  # pragma: no cover
    """Return a heatmap figure.

    Args:
        df_country (pd.DataFrame): Data to plot
        level (Literal["day", "week", "month", "year"], optional): Level of
            aggregation of the data. Defaults to "month".

    Returns:
        Figure: plotly figure.
    """
    x = (
        df_country[[level, "country"]]
        .value_counts()
        .reset_index()
        .pivot(index=level, columns=["country"])
        .fillna(0)
        .reset_index()[level]
        .to_list()
    )

    y = sorted(df_country["country"].unique())
    short_labels = [label[:15] + "..." if len(label) > 15 else label for label in y]

    z = (
        df_country[[level, "country"]]
        .value_counts()
        .reset_index()
        .pivot(index=level, columns=["country"])
        .fillna(0)
        .reset_index()
        .T.values[1:]
    )
    fig = px.imshow(
        z,
        text_auto=True,
        aspect="auto",
        labels=dict(x="Date", y="Country", color="Mentions"),
        x=x,
        # y=y,
        y=short_labels,
        color_continuous_scale=color_map,
    )
    fig.update_layout(
        autosize=False,
        # width=1700,
        height=25 * len(y),
        template="plotly_dark",
    )

    fig.update_layout(yaxis={"dtick": 1})
    return fig


def _get_country_polygons(df_country: pd.DataFrame) -> gpd.GeoDataFrame:  # pragma: no cover
    """Return polygons of the countries in the dataframe to plot them in a map.

    Args:
        df_country (pd.DataFrame): Countries with mentions.

    Returns:
        gpd.GeoDataFrame: GeoDataFrame with polygons of the countries.
    """
    geo_data = gpd.read_file(Path(APP_DIR / "static" / "ne_110m_admin_0_countries.zip"))
    gdf_map = geo_data[["NAME", "ADM0_A3", "geometry"]].merge(
        df_country[["iso_3"]].value_counts().rename("Mentions").reset_index(),
        how="right",
        left_on="ADM0_A3",
        right_on="iso_3",
    )
    return gdf_map


def _get_wikipedia_country_data(
    file_path: Path = APP_DIR / "static" / "wikipedia_country_data.csv",
) -> pd.DataFrame:
    """Return DataFrame with wikipedia data of countries including:
    "country, iso_2, iso_3, wikipedia_link"

    Country data: https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes

    Args:
        file_path (Path, optional): Path to file. Defaults to
            APP_DIR/"static"/"wikipedia_country_data.csv".

    Returns:
        pd.DataFrame: Country list with name, ISO codes and wikipedia link.
    """
    if not file_path.exists():
        _download_wikipedia_country_data(output_path=file_path)

    df = pd.read_csv(file_path)
    return df


def _download_wikipedia_country_data(
    output_path: Path = APP_DIR / "static" / "wikipedia_country_data.csv", overwrite: bool = False
) -> Path:  # pragma: no cover
    """Download wikipedia table from
    https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes

    Args:
        output_path (Path, optional): Path to store the wikipedia table.
            Defaults to APP_DIR/"static"/"wikipedia_country_data.csv".
        overwrite (bool): Whether or not to overwrite an existing file.
            Default to False.

    Returns:
        Path: Path where the wikipedia table is stored.
    """
    if not overwrite and output_path.exists():
        return output_path

    url_list_countries = "https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes"
    response = curl_cffi.get(url_list_countries, impersonate="chrome")
    soup = BeautifulSoup(response.text, "html.parser")

    data = []
    table = soup.find("table")
    links = table.find_all("a")  # type: ignore
    for link in links:
        if (
            "/ISO" not in link.get("href")  # type: ignore
            and len(link.text.strip()) > 3
            and link.get("href").startswith("https://en.")  # type: ignore
        ):
            data.append((link.text.strip(), link.get("href")))

    df_wikipedia_links = pd.DataFrame(data, columns=["country", "wikipedia_link"])

    tables_wikipedia = pd.read_html(StringIO(response.text))
    tables_wikipedia[0].columns = tables_wikipedia[0].columns.droplevel(0)  # type: ignore
    df_wikipedia_codes = tables_wikipedia[0][["ISO 3166[1] name[5]", "A-2 [5]", "A-3 [5]"]]
    df_wikipedia_codes.columns = ["country", "iso_2", "iso_3"]  # type: ignore

    df_wikipedia = df_wikipedia_codes.merge(df_wikipedia_links, on="country", how="left")
    df_wikipedia["country"] = df_wikipedia["country"].apply(lambda x: x.split("[")[0].strip())
    df_wikipedia["country"] = df_wikipedia["country"].apply(lambda x: x.split("(")[0].strip())
    df_wikipedia.to_csv(output_path, index=False)
    return output_path


def _get_country_text(
    wikipedia_data: Path = APP_DIR / "static" / "wikipedia_country_data.csv",
) -> str:
    """Returns a text with a list of countries to be passed to a prompt that
    recorgnise countries in texts.

    Args:
        wikipedia_data (Path, optional): Path to country data from Wikipedia.
            Defaults to APP_DIR/"static"/"wikipedia_country_data.csv".

    Returns:
        str: Text with a list of countries.
    """
    if not wikipedia_data.exists():
        wikipedia_data = _download_wikipedia_country_data()

    df_wikipedia = pd.read_csv(wikipedia_data)

    country_text = ""
    for _, r in df_wikipedia.iterrows():
        country_text += f"- {r['country']}: {r['iso_2']}\n"

    return country_text


def _get_country_data(iso_2: str, df_wikipedia: pd.DataFrame):
    """Returns ["country", "iso_2", "iso_3"] from the wikipedia data.

    Args:
        iso_2 (str): ISO code of two letters.
        df_wikipedia (pd.DataFrame): Dataframe with data from wikipedia.

    Returns:
        list: ["country", "iso_2", "iso_3"].
    """
    if iso_2.upper() in df_wikipedia["iso_2"].to_list():
        return df_wikipedia[df_wikipedia["iso_2"] == iso_2.upper()][
            ["country", "iso_2", "iso_3"]
        ].to_records(index=False)[0]
    else:
        return [None, None, None]


def _download_flag(url: str, output_path: Path) -> None:  # pragma: no cover
    """Download SVG file with the flag of a country.

    Args:
        url (str): URL to download.
        output_path (Path): Path to store the file.
    """
    if output_path.exists():
        return
    response = requests.get(url, timeout=10)
    if response.ok:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response.text)


def _download_flags(output_dir: Path = FLAGS_DIR) -> None:  # pragma: no cover
    """Download all the flags from
    https://raw.githubusercontent.com/amckenna41/iso3166-flags/refs/heads/main/iso3166-flags-metadata/iso3166_1_flag_metadata.csv

    Thanks to https://github.com/amckenna41 that hosts the flags.

    Args:
        output_dir (Path, optional): Path to store the flag files.
            Defaults to FLAGS_DIR.
    """
    url_metadata_flags = "https://raw.githubusercontent.com/amckenna41/iso3166-flags/refs/heads/main/iso3166-flags-metadata/iso3166_1_flag_metadata.csv"
    url_base_flags = (
        "https://raw.githubusercontent.com/amckenna41/iso3166-flags/main/iso3166-1-flags/{}"
    )
    df_flags = pd.read_csv(url_metadata_flags)
    for _, r in tqdm(df_flags.iterrows(), total=df_flags.shape[0]):
        _download_flag(
            url=url_base_flags.format(r["file_name"]), output_path=output_dir / f"{r["file_name"]}"
        )


def _parse_country_response(text):
    result_parsed = None
    text = text.replace("null", "''")
    try:
        result_parsed = ast.literal_eval(text)
    except ValueError:
        logger.error(f"Could not process {text}")
    return result_parsed


def process_country_mentions(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
    model: str = "qwen3.5:4b",
    wikipedia_path: Path = APP_DIR / "static" / "wikipedia_country_data.csv",
    overwrite: bool = False,
):
    """Extract country mentions from sections of the briefings using and LLM.

    It matches the country mention to data from Wikipedia to add ISO codes.

    Args:
        conn (sqlite3.Connection): Database connection.
        start_date (str): Processing start date.
        end_date (str): Processing end date.
        model (str, optional): LLM to use. Defaults to "qwen3.5:4b".
        wikipedia_path (Path, optional): Wikipedia data of counetries.
            Defaults to APP_DIR/"static"/"wikipedia_country_data.csv".
        overwrite (bool, optional): Whether or not to overwrite data.
            Defaults to False.
    """
    df_wikipedia = _get_wikipedia_country_data(file_path=wikipedia_path)
    briefings = get_briefings_between_dates(conn=conn, start_date=start_date, end_date=end_date)
    country_text = _get_country_text(wikipedia_data=wikipedia_path)

    if briefings:
        for briefing in briefings:
            logger.info(f"{briefing.briefing_date} {model}")
            for _, section in enumerate(briefing.sections, start=1):
                if not overwrite and _check_country_section_exists(
                    conn=conn, section_id=section.section_id, model=model
                ):
                    continue
                result = run_model_prompt(
                    model=model,
                    prompt=COUNTRY_MENTION_PROMPT.format(
                        text=section.text, country_text=country_text
                    ),
                    temperature=0,
                )
                result_parsed = _parse_country_response(result["response"])
                if result_parsed:
                    for country_result, iso_2_result in result_parsed:
                        if iso_2_result:
                            country, iso_2, iso_3 = _get_country_data(
                                iso_2=iso_2_result.strip(), df_wikipedia=df_wikipedia
                            )
                            if (
                                country
                                and iso_2
                                and iso_3
                                and not check_country_section_model_exists(
                                    conn=conn,
                                    section_id=section.section_id,
                                    iso_2=iso_2,
                                    model=model,
                                )
                            ):
                                logger.info(
                                    f"{section.section_id=} {country_result=} {country=} {iso_2=}"
                                )
                                insert_into_country(
                                    conn=conn,
                                    briefing_id=section.briefing_id,
                                    section_id=section.section_id,
                                    country=country,
                                    iso_2=iso_2,
                                    iso_3=iso_3,
                                    model=model,
                                    created_at=result["created_at"],
                                )
