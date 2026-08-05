import pandas as pd
import json

df = pd.read_csv("noon_briefings.csv")
records = df.to_dict(orient="records")

with open("noon_briefings.json", "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"Saved {len(records)} records")