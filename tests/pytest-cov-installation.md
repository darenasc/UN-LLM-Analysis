# Pytest-Cov Documentation

## Installation

`pipenv pip install pytest` # pre-requisite

`pipenv pip install pytest-cov`

From the project root:

`pytest --cov=tests_folder`

Generate a html coverage report:

`pytest --cov=tests_folder --cov-report=html`

You can set a minimum coverage threshold:

`pytest --cov-tests_folder --cov-fall-under=80`

