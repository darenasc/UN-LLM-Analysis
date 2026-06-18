import json
import re
import pandas as pd

# Load the JSON file
with open("noon_briefings.json", "r", encoding="utf-8") as f:
    records = json.load(f)

# We will collect all rows here
all_sections = []

# Loop over every briefing record
for record in records:
    date = record["date"]
    url = record["url"]
    text = record["text"]

    # Split the full text into individual lines and strip whitespace
    lines = [line.strip() for line in text.splitlines()]

    # Track which topic we are currently under, and collect its lines
    current_topic = None
    current_lines = []

    for line in lines:
        # Skip blank lines
        if not line:
            continue

        # Check if this line is a topic heading.
        # Headings are ALL CAPS, at least 3 characters, and only contain
        # letters, spaces, hyphens and slashes.
        is_heading = (
            len(line) >= 3
            and line == line.upper()
            and re.match(r'^[A-Z][A-Z\s\-\/]+$', line)
        )

        if is_heading:
            # We have hit a new heading. First, save whatever we have
            # collected under the previous heading (if anything).
            if current_topic and current_lines:
                all_sections.append({
                    "date": date,
                    "url": url,
                    "topic": current_topic,
                    "text": " ".join(current_lines).strip()
                })
            # Start a new section
            current_topic = line
            current_lines = []
        else:
            # This is a content line. Only collect it if we are already
            # inside a topic section — this discards the header boilerplate
            # at the top of each briefing.
            if current_topic:
                current_lines.append(line)

    # After the loop ends, save the last section which has no heading after it
    if current_topic and current_lines:
        all_sections.append({
            "date": date,
            "url": url,
            "topic": current_topic,
            "text": " ".join(current_lines).strip()
        })

# Convert the list of dicts to a dataframe
df = pd.DataFrame(all_sections)

# Convert date to datetime for time-based analysis
df["date"] = pd.to_datetime(df["date"])

# Sort chronologically
df = df.sort_values("date").reset_index(drop=True)

print(df.head(10))
print(f"\nShape: {df.shape}")
print(f"Unique topics: {df['topic'].nunique()}")

df.to_csv("noon_briefings_clean.csv", index=False)