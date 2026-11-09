"""Module to extract Sustainable Development Goals (SDG) mentioned in the UN
Briefings.

The descriptions of the SDG were taken from https://sdgs.un.org/goals
"""

import ast
import sqlite3

from loguru import logger
import ollama

from un_llm_analysis.database import (
    get_briefing_id_from_date,
    get_briefings_between_dates,
    get_db_connection,
    get_sdg_by_section_id,
    insert_into_sdg,
)
from un_llm_analysis.prompts import SDG_MENTION_PROMPT
from un_llm_analysis.utils import _check_ollama_model_exists

SDGS = {
    "SDG1": "End poverty in all its forms everywhere",
    "SDG2": "End hunger, achieve food security and improved nutrition and promote sustainable agriculture",
    "SDG3": "Ensure healthy lives and promote well-being for all at all ages",
    "SDG4": "Ensure inclusive and equitable quality education and promote lifelong learning opportunities for all",
    "SDG5": "Achieve gender equality and empower all women and girls",
    "SDG6": "Ensure availability and sustainable management of water and sanitation for all",
    "SDG7": "Ensure access to affordable, reliable, sustainable and modern energy for all",
    "SDG8": "Promote sustained, inclusive and sustainable economic growth, full and productive employment and decent work for all",
    "SDG9": "Build resilient infrastructure, promote inclusive and sustainable industrialization and foster innovation",
    "SDG10": "Reduce inequality within and among countries",
    "SDG11": "Make cities and human settlements inclusive, safe, resilient and sustainable",
    "SDG12": "Ensure sustainable consumption and production patterns",
    "SDG13": "Take urgent action to combat climate change and its impacts",
    "SDG14": "Conserve and sustainably use the oceans, seas and marine resources for sustainable development",
    "SDG15": "Protect, restore and promote sustainable use of terrestrial ecosystems, sustainably manage forests, combat desertification, and halt and reverse land degradation and halt biodiversity loss",
    "SDG16": "Promote peaceful and inclusive societies for sustainable development, provide access to justice for all and build effective, accountable and inclusive institutions at all levels",
    "SDG17": "Strengthen the means of implementation and revitalize the Global Partnership for Sustainable Development",
}


def get_sdg_text(sdgs: dict = SDGS) -> str:
    """Generate text with the SDG goals to pass to the prompt.

    Returns:
        str: Text with all SDG descriptions.
    """
    sdg_text = ""
    for sdg, description in sdgs.items():
        sdg_text += f"* {sdg} {description}\n"

    return sdg_text.strip()


def _parse_sdg_response(sdgs: str):
    """Parse a string and returns a list object.

    `llama3.2` is efficient and follows the expected pattern.

    Args:
        sdgs (str): Text with the LLM response.

    Returns:
        list | None: List with the SDG mentions to be inserted into the
            database.
    """
    parsed_sdgs = ast.literal_eval(sdgs)
    if parsed_sdgs is None:
        return
    return parsed_sdgs


def extract_sdg_mentions_from_sections(
    start_date: str,
    end_date: str,
    conn: sqlite3.Connection | None = None,
    model: str = "llama3.2",
    prompt: str = SDG_MENTION_PROMPT,
    overwrite: bool = False,
) -> None:
    """Extract the SDG mentions from the sections and insert them into the
    database.

    Args:
        start_date (str): Start date of the analysis.
        end_date (str): End date of the analysis.
        conn (sqlite3.Connection | None, optional): Connection to the database.
            Defaults to None.
        model (str, optional): LLM to be used to extract the information.
            Defaults to "llama3.2".
        prompt (str, optional): Prompt to be used for the information
            extraction. Defaults to SDG_MENTION_PROMPT.
        overwrite (bool, optional): Whether or not to overwrite a value that is
            already in the database. Defaults to False.
    """
    if not _check_ollama_model_exists(model=model):
        logger.warning(f"SDGs cannot be processed using the '{model}' model.")
        return

    conn = conn or get_db_connection()
    briefings = get_briefings_between_dates(conn=conn, start_date=start_date, end_date=end_date)
    if briefings:
        sdg_definitions = get_sdg_text()
        for briefing in briefings:
            if len(briefing.sections) > 0:
                for i, section in enumerate(briefing.sections, start=1):
                    briefing_id = briefing.briefing_id
                    section_id = section.section_id

                    if not overwrite and get_sdg_by_section_id(
                        conn=conn, section_id=section_id, model=model
                    ):
                        logger.info(f"SDG mentions for {section_id} and {model} already exists")
                        continue

                    result = ollama.generate(
                        model=model,
                        prompt=prompt.format(text=section.text, sdg_definitions=sdg_definitions),
                        think=False,
                    )

                    sdgs = _parse_sdg_response(result["response"])
                    if not isinstance(sdgs, list):
                        logger.warning(
                            f"Could not process section {section_id} with {model}. Response: {result["response"]}"
                        )
                        continue

                    insert_into_sdg(
                        conn=conn,
                        briefing_id=briefing_id,
                        section_id=section_id,
                        sdgs=sdgs,
                        model=model,
                        created_at=result["created_at"],
                    )
