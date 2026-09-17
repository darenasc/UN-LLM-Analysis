from logos import CORRELAID_LOGO
import streamlit as st

from un_llm_analysis import database

st.logo(
    CORRELAID_LOGO,
    link="https://mentoring.correlaid.org",
    size="large",
)

st.title("UN Daily Briefings")


conn = database.get_db_connection()
min_date, max_date = database.get_min_max_dates(conn=conn)
all_dates = database.get_dates_with_briefings(conn=conn)


selected_date = st.sidebar.date_input(
    "Select briefing date", max_date, min_value=min_date, max_value=max_date
)

briefing = database.get_briefing_by_date(conn=conn, date=str(selected_date))
st.header(f"Noon briefing of {selected_date.strftime('%A, %d %B %Y')}")

if briefing.speaker_role:
    st.write(f"By {briefing.speaker_role}, {briefing.speaker_name}")
else:
    st.write("Noon briefing not available.")

for section in briefing.sections:
    with st.expander(f"**{section.title}**"):
        st.markdown(section.text)
