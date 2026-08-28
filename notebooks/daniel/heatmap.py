from collections import Counter
import os
import re

import matplotlib.pyplot as plt
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.util import bigrams
import pandas as pd

from notebooks.daniel.archive.constants import ALL_VARIANTS, PROPER_NOUNS, STOPWORDS

lemmatizer = WordNetLemmatizer()
nltk.download("stopwords")
nltk.download("wordnet")

TOP_N_PER_YEAR = 15
MAX_TRACKED_TERMS = 20


def get_word_counts(text):
    """Clean text and return bigram + proper noun counts."""
    text = text.lower()
    text = re.sub(r"[^a-z\s]", "", text)
    text = re.sub(r"\s+", " ", text)  # collapse all whitespace types to single spaces

    words = [
        lemmatizer.lemmatize(word)
        for word in text.split()
        if word not in STOPWORDS and len(word) > 2
    ]

    # Apply phrase merges AFTER stopword filtering. Stopword removal can bring
    # two unrelated words next to each other (e.g. "local de facto authority"
    # becomes "local authority" once "de facto" is filtered out), creating a
    # false bigram that a raw-text replace would never catch. Checking
    # adjacency directly on the filtered word list catches both genuine
    # adjacency in the source text and this stopword-collapse case.
    merged_words = []
    i = 0
    while i < len(words):
        matched = False
        for variant_words, merged_token in ALL_VARIANTS:
            if words[i : i + len(variant_words)] == variant_words:
                merged_words.append(merged_token)
                i += len(variant_words)
                matched = True
                break
        if not matched:
            merged_words.append(words[i])
            i += 1

    words = merged_words

    bigram_list = list(bigrams(words))
    bigram_strings = [f"{w1} {w2}" for w1, w2 in bigram_list if w1 != w2]
    counts = Counter(bigram_strings)

    unigram_counts = Counter(words)
    for term in PROPER_NOUNS:
        if term in unigram_counts:
            counts[term] = unigram_counts[term]

    return counts


# Load data
df = pd.read_csv("noon_briefings_clean.csv", parse_dates=["date"])
df["year"] = df["date"].dt.year
years = sorted(df["year"].unique())

# Step 1: get top N words per year and their counts
yearly_counts = {}
yearly_top = {}

for year in years:
    df_year = df[df["year"] == year]
    if len(df_year) < 10:
        continue
    all_text = " ".join(df_year["text"].dropna().tolist())
    counts = get_word_counts(all_text)
    counts = {k: v for k, v in counts.items() if v >= 5}
    yearly_counts[year] = counts
    yearly_top[year] = [word for word, _ in Counter(counts).most_common(TOP_N_PER_YEAR)]

# Step 2: build union of top words scored by total count across all years
union_words = set()
for words in yearly_top.values():
    union_words.update(words)

total_counts = Counter()
for year, counts in yearly_counts.items():
    for word in union_words:
        total_counts[word] += counts.get(word, 0)

tracked_terms = [word for word, _ in total_counts.most_common(MAX_TRACKED_TERMS)]

# Only keep terms appearing in the top N in at least 2 years
tracked_terms = [
    term for term in tracked_terms if sum(term in yearly_top[year] for year in yearly_top) >= 2
]

# Step 3: build frequency matrix
valid_years = list(yearly_counts.keys())
freq_data = []
for term in tracked_terms:
    row = []
    for year in valid_years:
        counts = yearly_counts[year]
        row.append(counts.get(term, 0))
    freq_data.append(row)

freq_df = pd.DataFrame(freq_data, index=tracked_terms, columns=valid_years)

# Normalise by year
freq_df_norm = freq_df.div(freq_df.sum(axis=0), axis=1)

# Now sort by most recent year — freq_df_norm exists at this point
most_recent_year = valid_years[-1]
tracked_terms = sorted(
    tracked_terms, key=lambda term: freq_df_norm.loc[term, most_recent_year], reverse=True
)

# Rebuild matrices in the new order
freq_df = freq_df.loc[tracked_terms]
freq_df_norm = freq_df_norm.loc[tracked_terms]

print(f"Tracking {len(tracked_terms)} terms: {tracked_terms}")

# Step 4: plot heatmap
fig, ax = plt.subplots(figsize=(12, 8))

data = freq_df_norm.values.astype(float)
im = ax.imshow(data, aspect="auto", cmap="YlOrRd")

for i in range(len(tracked_terms)):
    for j in range(len(valid_years)):
        val = freq_df_norm.values[i, j]
        ax.text(j, i, f"{val:.1%}", ha="center", va="center", fontsize=9)

ax.set_xticks(range(len(valid_years)))
ax.set_xticklabels(valid_years)
ax.set_yticks(range(len(tracked_terms)))
ax.set_yticklabels(tracked_terms)
ax.set_title("Word Frequency in UN Noon Briefings by Year")
ax.set_xlabel("Year")
ax.set_ylabel("Term")

plt.colorbar(im, ax=ax, label="Relative frequency (normalised by year)")
plt.tight_layout()
os.makedirs("reports/figures", exist_ok=True)
plt.savefig("reports/figures/heatmap.png", dpi=150)
plt.show()
