from datetime import datetime
from pathlib import Path

import geopandas as gpd  # type: ignore
from logos import CORRELAID_LOGO  # type: ignore
import pandas as pd
import plotly.express as px  # type: ignore
import streamlit as st
from streamlit_folium import st_folium  # type: ignore

from un_llm_analysis.database import (
    get_db_connection,
    get_min_max_dates_with_sdg,
    get_sdg_models,
    get_sdgs_between_dates,
)

st.logo(
    CORRELAID_LOGO,
    link="https://mentoring.correlaid.org",
    size="large",
)

st.title("Country Heatmap")


@st.cache_data
def get_geo_data():
    file_path = Path(
        "/Users/darenasc/projects/correlaid/correlaid-mentoring-project/app/static/ne_110m_admin_0_countries.zip"
    )
    geo_data = gpd.read_file(file_path)
    return geo_data


@st.cache_data
def get_country_mentions():
    conn = get_db_connection()
    query = """select briefing_id, section_id, country, iso_2, iso_3, model from country;"""
    with conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        column_names = [x[0] for x in cursor.description]
        cursor.close()

    df_country = pd.DataFrame(rows, columns=column_names)
    return df_country


geo_data = get_geo_data()
df_country = get_country_mentions()

gdf_map = geo_data[["ADM0_A3", "geometry"]].merge(
    df_country[["iso_3"]].value_counts().reset_index(),
    how="right",
    left_on="ADM0_A3",
    right_on="iso_3",
)


m = gdf_map.explore(column="count")
container_map = st.container(border=True)
with container_map:
    st_folium(m, use_container_width=True, height=350)
