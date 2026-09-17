from un_llm_analysis.extractor import Extractor
from un_llm_analysis.db.database import Database


def init_db():
    db = Database()
    db.init_db()

# create database from schema

# load extracted briefings from JSON files into database

# query briefings by data, URL or status

# export database contents to JSON/CSV

# show database statistics (count by status, date range etc)

""""
python -m un_llm_analysis.db_cli init
python -m un_llm_analysis.db_cli load 2023-01-01 2023-12-31
python -m un_llm_analysis.db_cli load --since 2023-01-01
python -m un_llm_analysis.db_cli query --date 2023-08-12
python -m un_llm_analysis.db_cli query --status available
python -m un_llm_analysis.db_cli stats

"""