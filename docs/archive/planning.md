# Project Planning

## Scoping

- [Slides from the first meeting on 08.06.2026 "Volunteer Project Correlaid"](https://docs.google.com/presentation/d/1eMzWXqI4xPCCzbhxbL_EYkOfEE-uKAT6_fdOmvRROlI/edit?usp=sharing)
- [Scoping Document](https://docs.google.com/document/d/1BXssHaiz7N6zIianLfSOAW3zsMlipRtTeRzJ5Ryj-jA/edit?usp=sharing) based on [Data Science Project Scoping Guide](https://datasciencepublicpolicy.org/our-work/tools-guides/data-science-project-scoping-guide/)

## Timeline

A generic data science project will look like the following. In theory, the
implementation part is planned to last between 4 to 10 weeks. The Gantt chart
shows dependencies that, in practice, can progress in parallel with
communication among the assigned people.

```mermaid
gantt
    title A Generic timeline for a Data Science project
    dateFormat YYYY-MM-DD
    tickInterval 1month
    section Preparation
      First call: done, milestone, 2026-06-01, 0d
      Kickoff: done, milestone, kickoff, 2026-06-08, 0d
      Scoping: scoping, after kickoff, 14d
      Scoping document: milestone, after scoping, 0d
      Software stack: after scoping, 14d
      Planning: planning, after scoping, 2w
      Project Plan: milestone, plan, after planning, 0d
    section Implementation
      Data Exploration: exploration, after plan, 2w
      Database Design: database, after exploration, 2w
      Data Collection: collection, after exploration, 3w
      LLM pipelines: llms, after database, 3w
      LLM evaluation: evaluation, after llms, 2w
      Data visualizations: dataviz, after collection, 2w
    section Deployment
      Deployment: deploy, after collection llms dataviz evaluation, 2w
      Documentation: after deploy, 1w
    Finish: milestone, after kickoff 4month
    Correlcon: 2026-11-13, 3d
```
