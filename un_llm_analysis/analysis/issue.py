"""Module to extract relevant ISSUEs for the sections of the briefings and insert them into the database."""

SELECTED_ISSUES = {
    "ISSUE-1": "Israel-Palestine conflict, Gaza and the Occupied Palestinian Territory",
    "ISSUE-2": "War in Ukraine and its direct security and humanitarian consequences",
    "ISSUE-3": "Sudan conflict, political process and humanitarian crisis",
    "ISSUE-4": "Democratic Republic of the Congo conflict and humanitarian crisis",
    "ISSUE-5": "Yemen conflict and humanitarian crisis",
    "ISSUE-6": "South Sudan conflict, peace process and humanitarian crisis",
    "ISSUE-7": "Syria conflict and humanitarian crisis",
    "ISSUE-8": "Haiti political, security and humanitarian crisis",
    "ISSUE-9": "Afghanistan political and humanitarian crisis",
    "ISSUE-10": "Myanmar conflict and Rohingya crisis",
    "ISSUE-11": "Central African Republic conflict and political transition",
    "ISSUE-12": "Lebanon political and humanitarian crisis and Israel-Lebanon hostilities",
    "ISSUE-13": "Ethiopia conflict and humanitarian crisis",
    "ISSUE-14": "Libya political transition and insecurity",
    "ISSUE-15": "Sahel and Lake Chad Basin conflict and insecurity",
    "ISSUE-16": "Somalia conflict and humanitarian crisis",
    "ISSUE-17": "Climate change and long-term environmental issues",
    "ISSUE-18": "Natural disasters and acute emergency response",
    "ISSUE-19": "Global health, disease outbreaks and vaccination",
    "ISSUE-20": "Food security, hunger and malnutrition as a primary or cross-country issue",
    "ISSUE-21": "Refugees, displacement and migration as a primary or cross-border issue",
    "ISSUE-22": "Human rights, gender equality and child protection as a primary or cross-country issue",
    "ISSUE-23": "Sustainable development and development financing",
    "ISSUE-24": "Disarmament, arms control and non-proliferation",
}


def get_issue_text(issues: dict = SELECTED_ISSUES) -> str:
    """Generate text with the selected issues to pass to the prompt.

    Returns:
        str: Text with all selected issue descriptions.
    """
    issue_text = ""
    for issue, description in issues.items():
        issue_text += f"* {issue} {description}\n"

    return issue_text.strip()
