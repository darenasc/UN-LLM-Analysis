from datetime import datetime

from logos import CORRELAID_LOGO  # type: ignore
import pandas as pd
import plotly.express as px  # type: ignore
import streamlit as st

from un_llm_analysis.analysis.issue import (
    SELECTED_ISSUES,
    PlotLevel,
    calculate_issue_counts,
    calculate_issue_stats,
)
from un_llm_analysis.config import BRIEFINGS_DB_PATH
from un_llm_analysis.database import (
    get_db_connection,
    get_issues_between_dates,
    get_min_max_dates_with_table,
    get_models,
    get_sections_between_dates,
)

st.logo(
    CORRELAID_LOGO,
    link="https://mentoring.correlaid.org",
    size="large",
)

st.title("Issue Proportion in Briefings")

conn = get_db_connection()
min_date, max_date = get_min_max_dates_with_table(conn=conn, table="issue")
if min_date == "" and max_date == "":
    st.warning(
        "No ISSUE data. You can populate the issue table using the code in `notebooks/issue_analysis/02_issue_proportion_in_briefings.ipynb`."
    )

st.sidebar.caption(f"Suggested ISSUE date range between: `{min_date}` and `{max_date}`")
start_date = st.sidebar.date_input("Start date", min_date or datetime.now())
end_date = st.sidebar.date_input("End date", max_date or datetime.now())


def get_data(model: str, issues: list[str], start_date: str, end_date: str):
    # Get the data in the database within the specified date range
    with get_db_connection(BRIEFINGS_DB_PATH) as conn:
        sections = get_sections_between_dates(conn=conn, start_date=start_date, end_date=end_date)

    # Get the section data from the briefings and store it in a DataFrame
    section_data = pd.DataFrame(
        [
            {
                "section_id": section.section_id,
                "briefing_id": section.briefing_id,
                "section_title": section.title,
                "section_text": section.text,
            }
            for section in sections
        ],
        columns=["section_id", "briefing_id", "section_title", "section_text"],
    )

    with get_db_connection() as conn:
        issue_data = get_issues_between_dates(conn=conn, start_date=start_date, end_date=end_date)

    issue_data = issue_data[(issue_data["model"] == model) & (issue_data["issue"].isin(issues))]
    issue_data["date"] = pd.to_datetime(issue_data["briefing_id"].astype(str), format="%Y%m%d")

    return section_data, issue_data


def create_plot(
    section_data: pd.DataFrame,
    issue_data: pd.DataFrame,
    start_date: str,
    end_date: str,
    level: PlotLevel = "month",
):
    """Returns figures of analysis results for a given date range.

    Args:
        model (str): Model used to extract relevant ISSUEs.
        start_date (str): Start date with ISSUEs.
        end_date (str): End date with ISSUEs.

    Returns:
        Figure: Plotly figure.
    """

    issue_stats = calculate_issue_stats(
        section_data=section_data,
        issue_data=issue_data,
        level=level,
    )

    issue_counts = calculate_issue_counts(issue_data)

    fig_1 = px.line(
        issue_stats,
        x=level,
        y="frequency",
        color="issue",
        markers=False,
        title=f"Frequency of Issues in UN Briefings between {start_date} and {end_date}",
    )

    fig_2 = px.line(
        issue_stats,
        x=level,
        y="issue_length",
        color="issue",
        markers=False,
        title=f"Total Length of Sections for each Issue in UN Briefings between {start_date} and {end_date}",
    )

    fig_3 = px.line(
        issue_stats,
        x=level,
        y="proportion",
        color="issue",
        markers=False,
        title=f"Proportion of Text for each Issue in UN Briefings between {start_date} and {end_date}",
    )

    fig_4 = px.bar(
        issue_counts,
        x="total_counts",
        y="issue",
        orientation="h",
        title=f"Total Counts of Issues in UN Briefings between {start_date} and {end_date}",
    )

    fig_4.update_yaxes(
        dtick=1,
        automargin=True,
        autorange="reversed",
    )

    return [fig_1, fig_2, fig_3, fig_4]


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


models = get_models(conn=conn, table="issue")
model_choice = st.sidebar.selectbox(
    "Model",
    models,
)

all_issues = list(SELECTED_ISSUES.keys())

issue_choice = st.sidebar.multiselect("Issues", all_issues, default=all_issues, select_all=True)

section_data, issue_data = get_data(
    model=model_choice,
    issues=issue_choice,
    start_date=start_date.strftime("%Y-%m-%d"),
    end_date=end_date.strftime("%Y-%m-%d"),
)

level_choice = st.sidebar.pills(
    "Plot by", options=["day", "week", "month", "year"], default="month"
)

figs = create_plot(
    section_data=section_data,
    issue_data=issue_data,
    start_date=start_date.strftime("%Y-%m-%d"),
    end_date=end_date.strftime("%Y-%m-%d"),
    level=level_choice,
)

if figs:
    for fig in figs:
        st.plotly_chart(fig)
else:
    st.warning(
        f"No ISSUE data between `{start_date.strftime("%Y-%m-%d")}` and `{end_date.strftime("%Y-%m-%d")}`"
    )

st.markdown(formulate_issue_text())
