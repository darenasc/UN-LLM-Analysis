from logos import CORRELAID_LOGO
import streamlit as st

from un_llm_analysis import database
from un_llm_analysis.config import APP_DIR

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

if briefing.sections:
    speaker = ", ".join(x for x in [briefing.speaker_name, briefing.speaker_role] if x)
    st.write(f"By {speaker}" if speaker else "Speaker not specified.")
else:
    st.write("Noon briefing not available.")

for i, section in enumerate(briefing.sections, start=1):
    # Trusting that enumerate can be used to determine the section_id
    with st.expander(f"**{section.title}**"):
        st.markdown(section.text.replace("\n", "\n\n"))

        sdgs = database.get_sdg_by_section_id(
            conn=conn,
            section_id=database.get_briefing_id_from_date(briefing.briefing_date) * 100 + i,
        )
        if sdgs:
            sdg_icons = []
            sdg_names = ""
            for sdg in sdgs:
                sdg_names += f":orange-badge[{sdg}] "

                # SDG icons obtained from https://design-system.fao.org/styles/sdg-icons/
                sdg_icons.append(
                    APP_DIR / "static" / "sdg" / f'sdg{sdg.replace("SDG", "").zfill(2)}-en.svg'
                )
            # st.markdown(sdg_names) # display text badges
            st.image(sdg_icons, width=60)  # display small icons

        countries = database.get_countries_by_section_id(
            conn=conn,
            section_id=database.get_briefing_id_from_date(briefing.briefing_date) * 100 + i,
        )
        if countries:
            with st.container(horizontal=True, gap="xxsmall"):
                for country_code in countries:
                    st.image(
                        APP_DIR / "static" / "flags" / f"{country_code.lower()}.svg", width=60
                    )
