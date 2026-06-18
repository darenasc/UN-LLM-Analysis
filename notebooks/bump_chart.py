import pandas as pd
from collections import Counter
import re
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
from nltk.corpus import stopwords
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.util import bigrams
import os

lemmatizer = WordNetLemmatizer()
nltk.download("stopwords")
nltk.download("wordnet")

CUSTOM_STOPWORDS = {
    "also", "today", "secretary", "general", "secretarygeneral", "united", "nations",
    "said", "including", "according", "saying", "says",
    "noted", "added", "stressed", "told", "called", "reported",
    "un", "new", "one", "two", "three", "would", "could", "per", "met", "meet", "meeting", "many", "must",
    "should", "million", "number",
    "last", "lastly",
    "humanitarian",
    "coordination", "coordinator", "coordinators",
    "office", "affair", "affairs", "ocha",
    "programme", "food",
    "partner", "continue",
    "people", "nearly",
    "noon", "briefing", "highlight",
}

STOPWORDS = set(stopwords.words("english")).union(CUSTOM_STOPWORDS)

PROPER_NOUNS = [
    "worldhealthorganization",
    "demrepcongo",
    "occupiedpalestinianterritory",
    "gazastrip",
    "securitycouncil",
    "worldfoodprogramme",
]

TOP_N_PER_YEAR = 10      # how many top words to take from each year
MAX_TRACKED_TERMS = 15   # how many unique terms to show on the final chart


def get_word_counts(text):
    """Clean text and return bigram + proper noun counts."""
    text = text.lower()
    text = re.sub(r"[^a-z\s]", "", text)

    text = text.replace("democratic republic of congo", "demrepcongo")
    text = text.replace("democratic republic of the congo", "demrepcongo")
    text = text.replace("world food programme", "worldfoodprogramme")
    text = text.replace("security council", "securitycouncil")
    text = text.replace("occupied palestinian territory", "occupiedpalestinianterritory")
    text = text.replace("occupied palestinian", "occupiedpalestinianterritory")
    text = text.replace("palestinian territory", "occupiedpalestinianterritory")
    text = text.replace("west bank", "occupiedpalestinianterritory")
    text = text.replace("gaza strip", "gazastrip")
    text = text.replace("world health organization", "worldhealthorganization")
    text = text.replace("world health", "worldhealthorganization")
    text = text.replace("health organization", "worldhealthorganization")

    words = [
        lemmatizer.lemmatize(word)
        for word in text.split()
        if word not in STOPWORDS and len(word) > 2
    ]

    bigram_list = list(bigrams(words))
    bigram_strings = [f"{w1} {w2}" for w1, w2 in bigram_list]
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

# Step 2: build union of all top words, then cap at MAX_TRACKED_TERMS
# by picking the words that appear most frequently across all years combined
union_words = set()
for words in yearly_top.values():
    union_words.update(words)

# Score each word by its total count across all years
total_counts = Counter()
for year, counts in yearly_counts.items():
    for word in union_words:
        total_counts[word] += counts.get(word, 0)

tracked_terms = [word for word, _ in total_counts.most_common(MAX_TRACKED_TERMS)]

# Only keep terms that are in the top N in at least one year
tracked_terms = [
    term for term in tracked_terms
    if any(term in yearly_top[year] for year in yearly_top)
]

# Step 3: build rank matrix
# rows = terms, columns = years
# if a word doesn't appear in a year, assign rank = TOP_N_PER_YEAR + 1
rank_matrix = {}
for year in yearly_counts:
    counts = yearly_counts[year]
    # rank all words in this year by frequency
    ranked = [word for word, _ in Counter(counts).most_common()]
    # Replace the fallback rank with TOP_N_PER_YEAR + 1 (just below the cutoff)
    rank_matrix[year] = {
        word: ranked.index(word) + 1 if word in ranked[:TOP_N_PER_YEAR] else TOP_N_PER_YEAR + 1
        for word in tracked_terms
    }

# Step 4: plot bump chart
valid_years = list(yearly_counts.keys())
fig, ax = plt.subplots(figsize=(16, 10))

# Assign a colour to each term
colours = cm.tab20(np.linspace(0, 1, len(tracked_terms)))

for i, term in enumerate(tracked_terms):
    ranks = [rank_matrix[year][term] for year in valid_years]
    ax.plot(valid_years, ranks, marker="o", label=term, color=colours[i], linewidth=2)
    # Label at the end of each line
    ax.text(valid_years[-1] + 0.1, ranks[-1], term, va="center", fontsize=8, color=colours[i])

# Invert y-axis so rank 1 is at the top
ax.invert_yaxis()
ax.set_xlabel("Year")
ax.set_ylabel("Rank")
ax.set_title("Bump Chart: Word Rankings in UN Noon Briefings by Year")
ax.set_xticks(valid_years)
ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
ax.set_ylim(TOP_N_PER_YEAR + 2, 0)  # invert and cap
ax.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
os.makedirs("../reports/figures", exist_ok=True)
plt.savefig("../reports/figures/bump_chart.png", dpi=150)
plt.show()