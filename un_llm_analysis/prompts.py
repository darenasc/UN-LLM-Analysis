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
