from datetime import datetime

from logos import CORRELAID_LOGO  # type: ignore
import plotly.express as px  # type: ignore
import streamlit as st

from un_llm_analysis.database import (
    get_db_connection,
    get_min_max_dates_with_table,
    get_sentiment_models,
    get_sentiment_results_between_dates,
)

st.logo(
    CORRELAID_LOGO,
    link="https://mentoring.correlaid.org",
    size="large",
)

st.title("Sentiment and tone analysis in Briefings")

conn = get_db_connection()
min_date, max_date = get_min_max_dates_with_table(conn=conn, table="sentiment_analysis")
if min_date == "" and max_date == "":
    st.warning(
        "No Sentiment and tone analysis data. You can populate the sentiment_analysis table using the code in `notebooks/sentiment_analysis/sentiment_analysis_tone1.2_fixed.ipynb`."
    )

st.sidebar.caption(
    f"Suggested Sentiment and tone analysis date range between: `{min_date}` and `{max_date}`"
)
start_date = st.sidebar.date_input("Start date", min_date or datetime.now())
end_date = st.sidebar.date_input("End date", max_date or datetime.now())
analysis_type = st.sidebar.selectbox(
    "Select analysis type",
    ["Sentiment", "Tone"],
)


def create_analysis_plot(
    model: str,
    start_date: str,
    end_date: str,
    analysis_type: str = "sentiment",
):
    """Create a sentiment or tone distribution bar chart.

    Args:
        model: Model name used for the analysis.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        analysis_type: Either 'sentiment' or 'tone'.

    Returns:
        Plotly figure, or an empty dictionary if no data exists.
    """
    # Configure the column and category order.
    configurations = {
        "sentiment": {
            "column": "sentiment",
            "categories": ["Positive", "Neutral", "Negative"],
            "label": "Sentiment",
        },
        "tone": {
            "column": "tone",
            "categories": [
                "Diplomatic",
                "Concerned",
                "Critical",
                "Urgent",
                "Optimistic",
                "Neutral/Informational",
                "Constructive",
            ],
            "label": "Tone",
        },
    }

    analysis_type = analysis_type.lower()

    if analysis_type not in configurations:
        raise ValueError("analysis_type must be 'sentiment' or 'tone'")

    config = configurations[analysis_type]

    # Fetch results using the existing database function.
    conn = get_db_connection()

    df = get_sentiment_results_between_dates(
        conn=conn,
        start_date=start_date,
        end_date=end_date,
    )

    if df.empty:
        return {}

    # Filter results for the selected model.
    df = df[df["model_name"] == model].copy()

    if df.empty:
        return {}

    column = config["column"]
    categories = config["categories"]
    label = config["label"]

    # Count sections for each category.
    df_plot = (
        df[column]
        .dropna()
        .value_counts()
        .reindex(categories, fill_value=0)
        .rename_axis(label)
        .reset_index(name="count")
    )

    # Create the vertical bar chart.
    fig = px.bar(
        df_plot,
        x=label,
        y="count",
        labels={
            label: label,
            "count": "Number of Sections",
        },
        category_orders={label: categories},
        title=f"{label} Distribution — {model}",
    )

    fig.update_layout(
        xaxis_title=label,
        yaxis_title="Number of Sections",
    )

    fig.update_xaxes(tickangle=30 if analysis_type == "tone" else 0)

    return fig


models_sentiment = get_sentiment_models(conn=conn)

model_choice = st.sidebar.selectbox(
    "Model",
    models_sentiment,
)

fig = create_analysis_plot(
    model=str(model_choice),
    start_date=start_date.strftime("%Y-%m-%d"),
    end_date=end_date.strftime("%Y-%m-%d"),
    analysis_type=analysis_type,
)
if fig:
    st.plotly_chart(fig)
else:
    st.warning(
        f"No sentiment and tone analysis data between `{start_date.strftime("%Y-%m-%d")}` and `{end_date.strftime("%Y-%m-%d")}`"
    )

# Reference note: This code is adapted from the SDG Mentions page (app/pages/02_SDG_Mentions.py) to create a similar functionality for sentiment and tone analysis. The structure and logic are inspired by the original code,
# but it has been modified to suit the specific requirements of sentiment and tone analysis
