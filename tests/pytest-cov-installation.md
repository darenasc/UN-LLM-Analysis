# Pytest-Cov Documentation

## Installation

`pipenv pip install pytest` # pre-requisite

`pipenv pip install pytest-cov`

## Generating a Report

From the project root:

`pytest --cov=path_to_tests_folder`

Generate a html coverage report:

`pytest --cov=path_to_tests_folder --cov-report=html`

### Minimum Coverage Threshold

You can set a minimum coverage threshold:

`pytest --cov=path_to_tests_folder --cov-fall-under=80`

