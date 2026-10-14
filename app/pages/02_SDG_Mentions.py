from datetime import datetime

from logos import CORRELAID_LOGO  # type: ignore
import plotly.express as px  # type: ignore
import streamlit as st

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

st.title("SDG mentions in Briefings")

conn = get_db_connection()
min_date, max_date = get_min_max_dates_with_sdg(conn=conn)
if min_date == "" and max_date == "":
    st.warning(
        "No SDG data. You can populate the sdg table using the code in `notebooks/SDG_mentions_in_briefings.ipynb`."
    )

st.sidebar.caption(f"Suggested SDG date range between: `{min_date}` and `{max_date}`")
start_date = st.sidebar.date_input("Start date", min_date or datetime.now())
end_date = st.sidebar.date_input("End date", max_date or datetime.now())


def create_plot(model: str, start_date: str, end_date: str):
    """Returns a figure with an horizontal bar chart with the SDG counts for a
    given date range.

    Args:
        model (str): Model used to extract SDG mentions.
        start_date (str): Start date with SDGs.
        end_date (str): End date with SDGs.

    Returns:
        Figure: Plotly figure.
    """
    conn = get_db_connection()
    df = get_sdgs_between_dates(conn=conn, start_date=start_date, end_date=end_date)

    if df.shape[0] == 0:
        return {}

    df["order"] = df.sdg.apply(lambda x: int(str(x).replace("SDG", "")))
    df.sort_values(by="order", inplace=True)

    # Prepare and sort data for plot
    df_plot = (
        df[df["model"] == model][["order", "sdg"]]
        .value_counts()
        .reset_index()
        .sort_values("order", ascending=False)
        .set_index("sdg")
        .drop(columns=["order"])
    )

    x = [x[0] for x in df_plot.values.tolist()]  # frequency of each SDG in the sections.
    y = (
        df_plot.index.tolist()
    )  # values from the "sdg" column with values: ["SDG1", "SDG2", ..., "SDG17"]

    fig = px.bar(
        df,
        x=x,
        y=y,
        labels={
            "x": "# of Mentions in Sections",
            "y": "Sustainable Development Goal",
        },
        orientation="h",
        title=f"17SDGs in {len(df.briefing_id.unique())} Daily Briefings between {str(datetime.strptime(str(df.briefing_id.min()), "%Y%m%d"))[:10]} and {str(datetime.strptime(str(df.briefing_id.max()), "%Y%m%d"))[:10]}",
    )
    return fig


models = get_sdg_models(conn=conn)
model_choice = st.sidebar.selectbox(
    "Model",
    models,
)

fig = create_plot(
    model=str(model_choice),
    start_date=start_date.strftime("%Y-%m-%d"),
    end_date=end_date.strftime("%Y-%m-%d"),
)
if fig:
    st.plotly_chart(fig)
else:
    st.warning(
        f"No SDG data between `{start_date.strftime("%Y-%m-%d")}` and `{end_date.strftime("%Y-%m-%d")}`"
    )
