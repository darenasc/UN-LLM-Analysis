import zipfile

from logos import CORRELAID_LOGO
import streamlit as st

from un_llm_analysis import database
from un_llm_analysis.config import APP_DIR, BRIEFINGS_DB_PATH

st.logo(
    CORRELAID_LOGO,
    link="https://mentoring.correlaid.org",
    size="large",
)

if "database_init" not in st.session_state:
    if not BRIEFINGS_DB_PATH.exists():
        with zipfile.ZipFile(APP_DIR / "briefings.db.zip", "r") as zip_ref:
            zip_ref.extractall(APP_DIR)

    st.toast("Database connected!", icon="✅")
    st.session_state.database_init = True

st.set_page_config(
    page_title="UN LLM Analysis",
    page_icon="🇺🇳",
    initial_sidebar_state="collapsed",
    layout="centered",
    menu_items={
        "Report a bug": "https://github.com/darenasc/correlaid-mentoring-project/issues",
        "About": """This project downloads and extract information from the [noon briefings](https://www.un.org/sg/en/content/noon-briefing-highlight) of the UN.""",
    },
)


st.title("UN Daily Briefings")
conn = database.get_db_connection()
min_date, max_date = database.get_min_max_dates(conn=conn)
all_dates = database.get_dates_with_briefings(conn=conn)
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Total Briefings", value=f"{len(all_dates)}")
with col2:
    st.metric(label="Min Briefing Date", value=f"{min_date}")
with col3:
    st.metric(label="Max Briefing Date", value=f"{max_date}")
