<!-- omit in toc -->
# Contributing to UN LLM Analysis

UN LLM Analysis is a CorrelAid mentoring project that explores data analysis and
natural language processing techniques using United Nations noon briefing data.

The project is developed collaboratively through the CorrelAid mentoring programme. It includes tools for scraping, extracting, storing, and analysing UN noon briefing data.

First off, thanks for taking the time to contribute! ❤️

All types of contributions are encouraged and valued. See the [Table of Contents](#table-of-contents) for different ways to help and details about how this project handles them. Please make sure to read the relevant section before making your contribution. It will make it a lot easier for us maintainers and smooth out the experience for all involved. The community looks forward to your contributions. 🎉

> And if you like the project, but just don't have time to contribute, that's fine. There are other easy ways to support the project and show your appreciation, which we would also be very happy about:
> - Star the project
> - Tweet about it
> - Refer this project in your project's readme
> - Mention the project at local meetups and tell your friends/colleagues

<!-- omit in toc -->
## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [I Have a Question](#i-have-a-question)
- [I Want To Contribute](#i-want-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Enhancements](#suggesting-enhancements)
  - [Your First Code Contribution](#your-first-code-contribution)
  - [Testing](#testing)
    - [Installation](#installation)
    - [Generating a Report](#generating-a-report)
    - [Minimum Coverage Threshold](#minimum-coverage-threshold)
  - [Improving The Documentation](#improving-the-documentation)
- [Styleguides](#styleguides)
  - [Commit Messages](#commit-messages)

## Code of Conduct

This project and everyone participating in it is governed by the
[UN LLM Analysis Code of Conduct](https://github.com/darenasc/correlaid-mentoring-project/blob/main/CODE_OF_CONDUCT.md).
By participating, you are expected to uphold this code.

## I Have a Question

> If you want to ask a question, we assume that you have read the available [Documentation]().

Before you ask a question, it is best to search for existing [Issues](https://github.com/darenasc/correlaid-mentoring-project/issues) that might help you. In case you have found a suitable issue and still need clarification, you can write your question in this issue. It is also advisable to search the internet for answers first.

If you then still feel the need to ask a question and need clarification, we recommend the following:

- Open an [Issue](https://github.com/darenasc/correlaid-mentoring-project/issues/new).
- Provide as much context as you can about what you're running into.
- Provide project and platform versions (python version, libraries, etc), depending on what seems relevant.

We will then take care of the issue as soon as possible.

<!--
You might want to create a separate issue tag for questions and include it in this description. People should then tag their issues accordingly.

Depending on how large the project is, you may want to outsource the questioning, e.g. to Stack Overflow or Gitter. You may add additional contact and information possibilities:
- IRC
- Slack
- Gitter
- Stack Overflow tag
- Blog
- FAQ
- Roadmap
- E-Mail List
- Forum
-->

## I Want To Contribute

> ### Legal Notice <!-- omit in toc -->
> When contributing to this project, you must agree that you have authored 100% of the content, that you have the necessary rights to the content and that the content you contribute may be provided under the project licence.

### Reporting Bugs

<!-- omit in toc -->
#### Before Submitting a Bug Report

A good bug report shouldn't leave others needing to chase you up for more information. Therefore, we ask you to investigate carefully, collect information and describe the issue in detail in your report. Please complete the following steps in advance to help us fix any potential bug as fast as possible.

- Make sure that you are using the latest version.
- Determine if your bug is really a bug and not an error on your side e.g. using incompatible environment components/versions (Make sure that you have read the [documentation](). If you are looking for support, you might want to check [this section](#i-have-a-question)).
- To see if other users have experienced (and potentially already solved) the same issue you are having, check if there is not already a bug report existing for your bug or error in the [bug tracker](https://github.com/darenasc/correlaid-mentoring-project/issues?q=label%3Abug).
- Also make sure to search the internet (including Stack Overflow) to see if users outside of the GitHub community have discussed the issue.
- Collect information about the bug:
- Stack trace (Traceback)
- OS, Platform and Version (Windows, Linux, macOS, x86, ARM)
- Version of the interpreter, compiler, SDK, runtime environment, package manager, depending on what seems relevant.
- Possibly your input and the output
- Can you reliably reproduce the issue? And can you also reproduce it with older versions?

<!-- omit in toc -->
#### How Do I Submit a Good Bug Report?

> You must never report security related issues, vulnerabilities or bugs including sensitive information to the issue tracker, or elsewhere in public. Instead sensitive bugs must be sent by email to <>.
<!-- You may add a PGP key to allow the messages to be sent encrypted as well. -->

We use GitHub issues to track bugs and errors. If you run into an issue with the project:

- Open an [Issue](https://github.com/darenasc/correlaid-mentoring-project/issues/new). (Since we can't be sure at this point whether it is a bug or not, we ask you not to talk about a bug yet and not to label the issue.)
- Explain the behavior you would expect and the actual behavior.
- Please provide as much context as possible and describe the *reproduction steps* that someone else can follow to recreate the issue on their own. This usually includes your code. For good bug reports you should isolate the problem and create a reduced test case.
- Provide the information you collected in the previous section.

Once it's filed:

- The project team will label the issue accordingly.
- A team member will try to reproduce the issue with your provided steps. If there are no reproduction steps or no obvious way to reproduce the issue, the team will ask you for those steps and mark the issue as `needs-repro`. Bugs with the `needs-repro` tag will not be addressed until they are reproduced.
- If the team is able to reproduce the issue, it will be marked `needs-fix`, as well as possibly other tags (such as `critical`), and the issue will be left to be [implemented by someone](#your-first-code-contribution).

<!-- You might want to create an issue template for bugs and errors that can be used as a guide and that defines the structure of the information to be included. If you do so, reference it here in the description. -->


### Suggesting Enhancements

This section guides you through submitting an enhancement suggestion for UN LLM Analysis, **including completely new features and minor improvements to existing functionality**. Following these guidelines will help maintainers and the community to understand your suggestion and find related suggestions.

<!-- omit in toc -->
#### Before Submitting an Enhancement

- Make sure that you are using the latest version.
- Read the [documentation]() carefully and find out if the functionality is already covered, maybe by an individual configuration.
- Perform a [search](https://github.com/darenasc/correlaid-mentoring-project/issues) to see if the enhancement has already been suggested. If it has, add a comment to the existing issue instead of opening a new one.
- Find out whether your idea fits with the scope and aims of the project. It's up to you to make a strong case to convince the project's developers of the merits of this feature. Keep in mind that we want features that will be useful to the majority of our users and not just a small subset. If you're just targeting a minority of users, consider writing an add-on/plugin library.

<!-- omit in toc -->
#### How Do I Submit a Good Enhancement Suggestion?

Enhancement suggestions are tracked as [GitHub issues](https://github.com/darenasc/correlaid-mentoring-project/issues).

- Use a **clear and descriptive title** for the issue to identify the suggestion.
- Provide a **step-by-step description of the suggested enhancement** in as many details as possible.
- **Describe the current behavior** and **explain which behavior you expected to see instead** and why. At this point you can also tell which alternatives do not work for you.
- You may want to **include screenshots or screen recordings** which help you demonstrate the steps or point out the part which the suggestion is related to. You can use [LICEcap](https://www.cockos.com/licecap/) to record GIFs on macOS and Windows, and the built-in [screen recorder in GNOME](https://help.gnome.org/users/gnome-help/stable/screen-shot-record.html.en) or [SimpleScreenRecorder](https://github.com/MaartenBaert/ssr) on Linux. <!-- this should only be included if the project has a GUI -->
- **Explain why this enhancement would be useful** to most UN LLM Analysis users. You may also want to point out the other projects that solved it better and which could serve as inspiration.

<!-- You might want to create an issue template for enhancement suggestions that can be used as a guide and that defines the structure of the information to be included. If you do so, reference it here in the description. -->

### Your First Code Contribution

Environment Setup

```bash
git clone git@github.com:darenasc/correlaid-mentoring-project.git
cd correlaid-mentoring-project
pipenv shell # to create or enter into the virtual environment
pipenv install -d Pipfile # installs the libraries in the Pipfile of the repository
```

`pipenv` is used in this project to manage the virtual environment. To install new libraries you can use the command `pipenv install`. More information about the [`pipenv` commands](https://pipenv.pypa.io/en/latest/commands.html).

```bash
pipenv install pandas # to install a library, in this case called pandas
pipenv uninstall pandas # to uninstall a library, in this case called pandas
```

Before start working on the Python code, make sure you create a new branch for your work, that is branched off from the `main` branch. With `git checkout main` you change to the main branch, and then make sure that you have the latest version of the repository with `git pull`.

Then create your own branch to work on the code you want to include to the repository. Branch names are usually short descriptions of the task at hand, for example, an issue number 10 with the task of create a database schema for the project, you can create it as follows `git switch -c 10_database_schema`. With that everyone can know that the task is described in the issue number 10 and to what it refers to.

With your new branch just created feel free to add, delete, modify the files of the project. There is a good practice of writing [atomic commits](https://medium.com/@sandrodz/a-developers-guide-to-atomic-git-commits-c7b873b39223), meaning, small commits that contains meaningful changes. So when you are working on a task from an issue, you can create multiple commits to complete the work.

If it's the first time using `git` in the project, you will need to add your name and email for your commits:

```bash
git config --local user.name "<YOUR NAME>"
git config --local user.email <YOUR@EMAIL>
```

```bash
git checkout main # to change to the main branch
git pull # to pull the updates from the remote repository
git switch -c <name_of_your_new_branch> # to create a feature branch from the updated main branch

# Now you can add, edit, remove files in the project to complete the task(s) in the issue

git status # to check the recent changes
git add . # to add all the files or
git add file_1, file_2, ... file_n # to select the files to include in the commit
git commit -m 'Add your (atomic) commit message here' # to create a new commit to the current feature branch

# You can create multiple commits while working on an issue, just repeat the
# previous steps of status -> add -> commit and then repeat until finish

# Once you finish your work you can push the code to the remote repository
git push # or if the branch exists in the remote repository
git push --set-upstream origin <name_of_your_new_branch> # to create your feature branch in the remote repository

# If the feature branch is ready to be merged into main,
# create a pull request (PR) in GitHub

# And once the PR has been merged you can delete the feature branch
git checkout main # change to the main branch
git pull # pull the changes from the remote repository that will include the changes of the PR
git branch -d <name_of_your_new_branch> # to delete the feature branch locally
```

### Testing

Unit tests are developed using [`pytest`](https://docs.pytest.org/en/stable/).

#### Installation

Install pytest and pytest-cov.

```bash
pipenv install -d pytest pytest-cov
```

Install [pre-commit](https://pre-commit.com) as a dependency, then install the git hook scripts so checks run automatically before each commit.

```bash
pipenv install -d pre-commit
pre-commit install # run before the next command:
```

#### Generating a Report

From the project root:

```bash
pytest --cov=un_llm_analysis
```

Generate a html coverage report:

```bash
pytest --cov=pytest --cov=un_llm_analysis --cov-report=html
open htmlcov/index.html
```

#### Minimum Coverage Threshold

You can set a minimum coverage threshold:

```bash
pytest --cov=pytest --cov=un_llm_analysis --cov-fall-under=80
```

### Improving The Documentation

- Add docstrings in [google format](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) to your code.
- This project will generate documentation with [mkdocs](https://www.mkdocs.org).

## Styleguides

The project follows the recommendations from [PEP8](https://peps.python.org/pep-0008/) enforced by the Python package [`black`](https://black.readthedocs.io/en/stable/).

We recommend to include [type hinting](https://peps.python.org/pep-0484/) to your code and to include docstrings of your classes and functions with the [google format](https://github.com/NilsJPWerner/autoDocstring/blob/HEAD/docs/google.md).

### Commit Messages

Please try to follow the good practice of [atomic commits](https://medium.com/@sandrodz/a-developers-guide-to-atomic-git-commits-c7b873b39223).

<!-- omit in toc -->
## Attribution
This guide is based on the [contributing.md](https://contributing.md/generator)!
