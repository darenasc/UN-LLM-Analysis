from datetime import date

from logos import CORRELAID_LOGO  # type: ignore
import streamlit as st
from streamlit_folium import st_folium  # type: ignore

from un_llm_analysis.analysis.countries import _get_country_polygons, create_heatmap
from un_llm_analysis.database import (
    get_briefing_id_from_date,
    get_country_mentions_by_date,
    get_db_connection,
    get_min_max_dates_with_table,
    get_models,
)

st.logo(
    CORRELAID_LOGO,
    link="https://mentoring.correlaid.org",
    size="large",
)

st.title("Country Mentions")


conn = get_db_connection()
min_date, max_date = get_min_max_dates_with_table(conn=conn, table="country")
if min_date == "" and max_date == "":
    st.warning(
        "No country mention data. You can populate the sdg table using the code in `notebooks/country_data_generation/01_country_mentions.ipynb`."
    )
    st.stop()

st.sidebar.caption(f"Suggested SDG date range between: `{min_date}` and `{max_date}`")
start_date = st.sidebar.date_input("Start date", min_date or date.today())
end_date = st.sidebar.date_input("End date", max_date or date.today())

models = get_models(conn=conn, table="country")
model_choice = st.sidebar.selectbox(
    "Model",
    models,
)

heatmap_level = st.sidebar.pills(
    "Heatmap by", options=["date", "week", "month", "year"], default="month"
)

df_country = get_country_mentions_by_date(
    conn=conn, model=model_choice, start_date=min_date, end_date=max_date
)
countries = sorted(
    df_country[
        (df_country["briefing_id"] >= get_briefing_id_from_date(str(start_date)))
        & (df_country["briefing_id"] <= get_briefing_id_from_date(str(end_date)))
    ]["country"].unique()
)
country_selection = st.sidebar.multiselect(
    "Countries", countries, default=countries, select_all=True
)
color_selection = st.sidebar.selectbox(
    "Color",
    [
        "viridis",
        "plasma",
        "inferno",
        "magma",
        "cividis",
        "YlOrBr",
        "YlOrRd",
        "YlGnBu",
        "YlGn",
        "gray",
    ],
    0,
)

gdf_map = _get_country_polygons(
    df_country[
        (df_country["briefing_id"] >= get_briefing_id_from_date(str(start_date)))
        & (df_country["briefing_id"] <= get_briefing_id_from_date(str(end_date)))
        & (df_country["country"].isin(country_selection))
    ]
)

m = gdf_map.explore(column="Mentions", tooltip=["NAME", "Mentions"], cmap=color_selection)  # type: ignore
container_map = st.container(border=True)
with container_map:
    st_folium(m, use_container_width=True, height=350)
    st.caption(
        f"Country mentions data between {date.fromisoformat(str(df_country.briefing_id.min())).isoformat()} and {date.fromisoformat(str(df_country.briefing_id.max())).isoformat()}"
    )

fig_heatmap = create_heatmap(
    df_country=df_country[
        (df_country["briefing_id"] >= get_briefing_id_from_date(str(start_date)))
        & (df_country["briefing_id"] <= get_briefing_id_from_date(str(end_date)))
        & (df_country["country"].isin(country_selection))
    ],
    level=heatmap_level,  # type: ignore
    color_map=color_selection,
)
# figure_container = st.container(width=2000)
# with figure_container:
st.plotly_chart(
    fig_heatmap,
    width="content",
)
