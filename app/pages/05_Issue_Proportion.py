from datetime import datetime

from logos import CORRELAID_LOGO  # type: ignore
import pandas as pd
import plotly.express as px  # type: ignore
import streamlit as st

from un_llm_analysis.analysis.issue import SELECTED_ISSUES
from un_llm_analysis.config import BRIEFINGS_DB_PATH
from un_llm_analysis.database import (
    get_briefing_id_from_date,
    get_briefings_between_dates,
    get_db_connection,
    get_issues_between_dates,
    get_min_max_dates_with_sdg,
    get_sdg_models,
)

st.logo(
    CORRELAID_LOGO,
    link="https://mentoring.correlaid.org",
    size="large",
)

st.title("Issue Proportion in Briefings")

conn = get_db_connection()
min_date, max_date = get_min_max_dates_with_sdg(conn=conn)
if min_date == "" and max_date == "":
    st.warning(
        "No ISSUE data. You can populate the issue table using the code in `notebooks/issue_analysis/02_issue_proportion_in_briefings.ipynb`."
    )

st.sidebar.caption(f"Suggested ISSUE date range between: `{min_date}` and `{max_date}`")
start_date = st.sidebar.date_input("Start date", min_date or datetime.now())
end_date = st.sidebar.date_input("End date", max_date or datetime.now())


def create_plot(model: str, start_date: str, end_date: str):
    """Returns figures of analysis results for a given date range.

    Args:
        model (str): Model used to extract relevant ISSUEs.
        start_date (str): Start date with ISSUEs.
        end_date (str): End date with ISSUEs.

    Returns:
        Figure: Plotly figure.
    """
    # Get the data in the database within the specified date range
    with get_db_connection(BRIEFINGS_DB_PATH) as conn:
        briefings = get_briefings_between_dates(conn, start_date, end_date)

    # Get the section data from the briefings and store it in a DataFrame
    rows = []
    for briefing in briefings:
        briefing_id = get_briefing_id_from_date(briefing.briefing_date)
        for i, section in enumerate(briefing.sections, start=1):
            section_id = briefing_id * 100 + i
            rows.append(
                {
                    "section_id": section_id,
                    "briefing_id": briefing_id,
                    "section_title": section.title,
                    "section_text": section.text,
                }
            )

    section_data = pd.DataFrame(rows)

    with get_db_connection() as conn:
        issue_data = get_issues_between_dates(conn=conn, start_date=start_date, end_date=end_date)

    issue_data["date"] = pd.to_datetime(issue_data["briefing_id"].astype(str), format="%Y%m%d")

    # Store the length of each section
    section_df = section_data.copy()
    section_df["section_length"] = section_df["section_text"].str.len()

    # Calculate total length of the sections on each date
    total_length = (
        section_df.groupby("briefing_id")["section_length"].sum().reset_index(name="total_length")
    )

    section_df = section_df.merge(total_length, on="briefing_id", how="left")

    # Merge the issue data with the section data to get the section lengths and total lengths for each issue
    issue_sections = issue_data.merge(
        section_df[["section_id", "section_length", "total_length"]], on="section_id", how="left"
    )

    # Calculate the total length of sections for each issue on each date
    issue_length = (
        issue_sections.groupby(["date", "issue"])["section_length"]
        .sum()
        .reset_index(name="issue_length")
    )

    # Calculate the frequency of sections for each issue on each date
    frequency = (
        issue_sections.groupby(["date", "issue"])["section_id"]
        .nunique()
        .reset_index(name="frequency")
    )

    # Build a complete date x issue grid.
    issues = [f"ISSUE-{i}" for i in range(1, 25)]

    dates = pd.date_range(start_date, end_date, freq="D")

    issue_date_grid = pd.MultiIndex.from_product(
        [dates, issues], names=["date", "issue"]
    ).to_frame(index=False)

    # Merge the issue date grid with the issue length and frequency data to get a complete dataset for analysis

    issue_stats = issue_date_grid.merge(
        issue_sections[["date", "total_length"]].drop_duplicates(), on="date", how="left"
    )

    issue_stats = issue_stats.merge(issue_length, on=["date", "issue"], how="left")

    issue_stats = issue_stats.merge(frequency, on=["date", "issue"], how="left")

    issue_stats = issue_stats.fillna(
        {"issue_length": 0, "frequency": 0, "total_length": 0}
    ).astype({"issue_length": int, "frequency": int, "total_length": int})

    fig_1 = px.line(
        issue_stats,
        x="date",
        y="frequency",
        color="issue",
        markers=False,
        title=f"Frequency of Issues in UN Briefings between {start_date} and {end_date}",
    )

    fig_2 = px.line(
        issue_stats,
        x="date",
        y="issue_length",
        color="issue",
        markers=False,
        title=f"Total Length of Sections for each Issue in UN Briefings between {start_date} and {end_date}",
    )

    issue_stats["proportion"] = (issue_stats["issue_length"] / issue_stats["total_length"]).fillna(
        0
    )

    fig_3 = px.line(
        issue_stats,
        x="date",
        y="proportion",
        color="issue",
        markers=False,
        title=f"Proportion of Text for each Issue in UN Briefings between {start_date} and {end_date}",
    )

    issue_counts = (
        issue_stats.groupby("issue")["frequency"]
        .sum()
        .reset_index(name="total_counts")
        .sort_values(by="total_counts", ascending=False)
    )

    fig = px.bar(
        issue_counts,
        x="total_counts",
        y="issue",
        orientation="h",
        title=f"Total Counts of Issues in UN Briefings between {start_date} and {end_date}",
    )

    fig.update_yaxes(
        dtick=1,
        automargin=True,
        autorange="reversed",
    )

    return [fig_1, fig_2, fig_3, fig]


def formulate_issue_text(issues: dict = SELECTED_ISSUES) -> str:
    """Formulates a text with all issue descriptions.

    Returns:
        str: Text with all issue descriptions.
    """
    issue_text = "The following are the selected issues for analysis:\n\n"
    for issue, description in issues.items():
        issue_text += f"* **{issue}**: {description}\n"

    issue_text += "\n(Refer to [Identifying Issues for Analysis of UN Briefings](https://github.com/darenasc/correlaid-mentoring-project/blob/main/notebooks/issue_analysis/01_identify_issues.ipynb) for details on how the issues used in the subsequent analysis are identified.)"

    return issue_text.strip()


models = get_sdg_models(conn=conn)
model_choice = st.sidebar.selectbox(
    "Model",
    models,
)

figs = create_plot(
    model=str(model_choice),
    start_date=start_date.strftime("%Y-%m-%d"),
    end_date=end_date.strftime("%Y-%m-%d"),
)
if figs:
    for fig in figs:
        st.plotly_chart(fig)
else:
    st.warning(
        f"No ISSUE data between `{start_date.strftime("%Y-%m-%d")}` and `{end_date.strftime("%Y-%m-%d")}`"
    )

st.markdown(formulate_issue_text())
