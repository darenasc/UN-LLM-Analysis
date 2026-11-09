"""Module to save model prompts and interface to interact with Ollama."""

import ollama

SDG_MENTION_PROMPT = """**Classification Task:**

Classify the following text into one or more of the following 17 Sustainable Development Goals (SDGs):

**Text to be Classified:**

{text}

**SDG Definitions:**

{sdg_definitions}

**Example Response:**

If the text belongs to one or more of the 17 SDGs, provide a list of relevant goal(s) in the format: ['SDG1', 'SDG5'].

**Edge Case:**

If the text does not belong to any of the 17 SDGs, return 'None'. Do not include any text to your answer, just provide the response in a list.
Output ONLY the list, nothing else.
"""

COUNTRY_MENTION_PROMPT = """Analyze the text below and extract all country names and places mentioned.
Provide a list of the extracted locations, with the correspondent ISO3166-1 code, formatted as follows:

[("Germany", "DE"), ("Chile", "CL"), ("Venezuela", "VE")]

Please use the following conventions:

* Capitalize country names
* Do not include cities or regions within countries, e.g. "Europe" instead of "Western Europe"
* Do not include fictional or non-existent locations
* Do not include any country that has not been explicitly mentioned by name
* Do not include any text in parenthesis
* Do not include the given example
* Do not include null or None codes

Please respond ONLY with the list of extracted locations, nothing else.

Here is a list of country and codes for reference:

{country_text}

**Text to be Classified:**

{text}

"""
# sentiment and tone analysis prompt
sentiment_analysis_prompt_version = "V4"
VALID_SENTIMENTS = {"Positive", "Neutral", "Negative"}
VALID_TONES = {
    "Diplomatic",
    "Concerned",
    "Critical",
    "Urgent",
    "Optimistic",
    "Neutral/Informational",
    "Constructive",
}
SENTIMENT_ANALYSIS_PROMPT = """**Classification Task:**

Classify the sentiment and primary tone of  the following text.
SENTIMENT using exactly one label:
- Positive: favorable developments, progress, success, support, or hope.
- Neutral: factual reporting without clearly positive or negative evaluation.
- Negative: adverse developments, harm, criticism, failure, or deterioration.

Classify the PRIMARY TONE using exactly one label:
- Diplomatic
- Concerned
- Critical
- Urgent
- Optimistic
- Neutral/Informational
- Constructive

Rules:
- Sentiment and tone are different. A negative situation can be reported neutrally.
- Do not label text Negative only because it mentions conflict or a crisis.
- Base both labels on the actual wording and overall message.
- Choose the single most prominent tone.
- Do not infer emotions that are not supported by the text.

**Output Format:**

Return only a valid JSON object with exactly these keys:

{{"sentiment": "Neutral", "tone": "Neutral/Informational"}}

**Text to be Classified:**

{text}

"""

ISSUE_MAPPING_PROMPT_VERSION = "v4"
ISSUE_MAPPING_PROMPT = """**Task**

Identify the most relevant issue for the text below.

**Issue Definitions**

{issue_definitions}

**Text**

{section_text}

**Decision Rules**

- Assign one issue by default.
- Return None if none of the issue definitions clearly apply.
- Assign two issues only if the text contains two distinct substantive topics and each independently matches an issue definition.
- Never assign more than two issues.
- Do not assign a second issue only because it is mentioned as background, consequence, or context.

**Output Format**

Return exactly one of the following forms:

None
['ISSUE-<number>']
['ISSUE-<number>', 'ISSUE-<number>']

Do not return ['None'].
Do not include any explanation or additional text.
"""


def run_model_prompt(model: str, prompt: str, think: bool = False, temperature: float = 0):
    """Run a prompt in an Ollama model.

    Args:
        model (str): LLM model that must exists in the Ollama server.
        prompt (str): Prompt to be used.
        text (str): Argument to pass in the prompt.
        think (bool, optional): To limit reasoning models. Defaults to False.

    Returns:
        _type_: Response from the LLM model.
    """
    result = ollama.generate(
        model=model,
        prompt=prompt,
        think=think,
        options={"temperature": temperature},
    )
    return result
