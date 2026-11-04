# Contributing to UN LLM Analysis

Thanks for your interest in contributing! ❤️

UN LLM Analysis is a [CorrelAid](https://www.correlaid.org/) mentoring project exploring data analysis and natural language processing with [United Nations noon briefing](https://www.un.org/sg/en/content/noon-briefing-highlight) data.

All types of contributions are welcome, including code, documentation, tests, and ideas. 🎉


## Code of Conduct

This project and everyone participating in it is governed by the
[UN LLM Analysis Code of Conduct](https://github.com/darenasc/correlaid-mentoring-project/blob/main/CODE_OF_CONDUCT.md).
By participating, you are expected to uphold this code.


## Opening an Issue

If you have a **question**, find a **bug**, or want to **suggest an enhancement**, you can [open an issue](https://github.com/darenasc/correlaid-mentoring-project/issues/new).

Before that, please check the [README](README.md), project [documentation](), and [existing issues](https://github.com/darenasc/correlaid-mentoring-project/issues) to see if the topic has already been addressed.

Please include relevant information in your issue description:
- **Questions:** A clear description of what you need help with.
- **Bugs:** A description of the problem and steps to reproduce it, if possible.
- **Enhancements:** A description of your suggestion and why it would be useful.


## Making a Contribution

> ### Legal Notice
> When contributing to this project, you must agree that you have authored 100% of the content, that you have the necessary rights to the content and that the content you contribute may be provided under the project licence.

### Environment Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and then clone the repository and install the dependencies:

```bash
git clone https://github.com/darenasc/correlaid-mentoring-project.git
cd correlaid-mentoring-project

uv sync # Create the virtual environment and install dependencies
uv run prek install # Install Git hooks
```

`uv` is used in this project to manage the virtual environment and dependencies. You can add or remove dependencies using the following commands:
```bash
uv add pandas # Add a dependency, in this case `pandas`
uv remove pandas # Remove a dependency, in this case `pandas`
```
For more information, run `uv help` or refer to the [uv command reference](https://docs.astral.sh/uv/reference/cli/).

You can use `uv run <command>` to execute commands in the project's virtual environment, or activate it manually:
```bash
# On Unix/macOS:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate

# Deactivate virtual environment
deactivate
```

### Contribution Workflow

Start from the latest `main` branch and create a branch for your changes:

```bash
git switch main
git pull
git switch -c 123-short-description
```

With your new branch, feel free to add, delete, or modify files in the project. It's good practice to make [atomic commits](https://medium.com/@sandrodz/a-developers-guide-to-atomic-git-commits-c7b873b39223), which are small commits focused on meaningful changes. When you are working on an issue, you can create multiple commits to complete the task.

Once your changes are ready, run the relevant tests and checks (see [Testing](#testing)), then push your branch:

```bash
git push -u origin 123-short-description
```

Finally, open a [Pull Request (PR)](https://github.com/darenasc/correlaid-mentoring-project/pulls) targeting `main`. Briefly describe your changes and reference the related issue, if applicable.

If you're new to Git, refer to the [official Git tutorial](https://git-scm.com/docs/gittutorial).

### Testing

Unit tests are developed using [`pytest`](https://docs.pytest.org/en/stable/) and `pytest-cov` for test coverage. [`prek`](https://prek.j178.dev/) is used to manage Git hooks that automatically run checks before each commit.


> **Optional: Manual Installation**
>
> These tools are normally installed with `uv sync`. If you need to add them manually:
>
> ```bash
> uv add --dev pytest pytest-cov
> uv add --dev prek
> uv run prek install
> ```

#### Local checks with `prek`

```bash
prek run --all-files
```

#### Generating a Report

From the project root:

```bash
pytest --cov=un_llm_analysis
```

Generate a html coverage report:

```bash
pytest --cov=un_llm_analysis --cov-report=html
```
Open `htmlcov/index.html` in your browser to view the report.

#### Minimum Coverage Threshold

You can set a minimum coverage threshold, for example 80%:

```bash
pytest --cov=pytest --cov=un_llm_analysis --cov-fail-under=80
```


### Code Style and Documentation

The project follows [PEP 8](https://peps.python.org/pep-0008/) and uses [`black`](https://black.readthedocs.io/en/stable/) for code formatting.

We recommend including [type hints](https://peps.python.org/pep-0484/) and writing docstrings in [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).

This project uses [MkDocs](https://www.mkdocs.org/) to generate documentation.


## Attribution

This guide is originally based on [contributing.md](https://contributing.md/generator).
