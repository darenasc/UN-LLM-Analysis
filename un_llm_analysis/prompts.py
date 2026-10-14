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
