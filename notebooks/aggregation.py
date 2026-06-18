import pandas as pd
from collections import Counter
import re
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from nltk.corpus import stopwords
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.util import bigrams
import os
lemmatizer = WordNetLemmatizer()
# Download stopwords if you don't have them already
nltk.download("stopwords")
nltk.download("wordnet")
CUSTOM_STOPWORDS = {
    # generic filler words
    "also", "today", "secretary", "general", "secretarygeneral", "united", "nations",
    "said", "including", "according", "saying", "says",
    "noted", "added", "stressed", "told", "called", "reported",
    "un", "new", "one", "two", "three", "would", "could", "per", "met", "meet", "meeting", "many", "must",
    "should", "million", "number", "took", "led"
    # time references — adding "last" removes all "last x" bigrams at once
    "last", "lastly", "lasting",
    # humanitarian cluster
    "humanitarian",
    # coordination cluster
    "coordination", "coordinator", "coordinators",
    # office/affairs cluster
    "office", "affair", "affairs", "ocha",
    # world food programme fragments
    "programme", "food",
    # other noise bigrams
    "partner", "continue",
    # people-related noise
    "people", "nearly",
    # noon briefing noise
    "noon", "briefing", "highlight",

}

STOPWORDS = set(stopwords.words("english")).union(CUSTOM_STOPWORDS)


# Load the cleaned data
df = pd.read_csv("noon_briefings_clean.csv", parse_dates=["date"])

# Add a year column for filtering
df["year"] = df["date"].dt.year


### --- VISUALISATION FOR 2025 ONLY ---
# Filter to last calendar year

proper_nouns = [
    "worldhealthorganization",
    "demrepcongo",
    "occupiedpalestinianterritory",
    "gazastrip",
    "securitycouncil",
    "worldfoodprogramme",
]

for STUDIED_YEAR in sorted(df["year"].unique()):
    df_filtered = df[df["year"] == STUDIED_YEAR]

    # Skip years with very little data
    if len(df_filtered) < 10:
        print(f"Skipping {STUDIED_YEAR} — not enough data")
        continue

    print(f"Processing {STUDIED_YEAR}...")

    # Combine all text into one big string
    all_text = " ".join(df_filtered["text"].dropna().tolist())

    # Lowercase and clean first
    all_text = all_text.lower()
    all_text = re.sub(r"[^a-z\s]", "", all_text)

    # Replacements
    all_text = all_text.replace("democratic republic of congo", "demrepcongo")
    all_text = all_text.replace("democratic republic of the congo", "demrepcongo")
    all_text = all_text.replace("world food programme", "worldfoodprogramme")
    all_text = all_text.replace("security council", "securitycouncil")
    all_text = all_text.replace("occupied palestinian territory", "occupiedpalestinianterritory")
    all_text = all_text.replace("occupied palestinian", "occupiedpalestinianterritory")
    all_text = all_text.replace("palestinian territory", "occupiedpalestinianterritory")
    all_text = all_text.replace("west bank", "occupiedpalestinianterritory")
    all_text = all_text.replace("gaza strip", "gazastrip")
    all_text = all_text.replace("world health organization", "worldhealthorganization")
    all_text = all_text.replace("world health", "worldhealthorganization")
    all_text = all_text.replace("health organization", "worldhealthorganization")

    # Lemmatize and filter
    words = [
        lemmatizer.lemmatize(word)
        for word in all_text.split()
        if word not in STOPWORDS and len(word) > 2
    ]

    # Bigrams
    bigram_list = list(bigrams(words))
    bigram_strings = [f"{w1} {w2}" for w1, w2 in bigram_list]
    word_counts = Counter(bigram_strings)

    # Add proper nouns as unigrams
    unigram_counts = Counter(words)
    for term in proper_nouns:
        if term in unigram_counts:
            word_counts[term] = unigram_counts[term]

    # Frequency threshold
    word_counts = {k: v for k, v in word_counts.items() if v >= 5}

    print(f"  Top 20: {Counter(word_counts).most_common(20)}")

    # Word cloud
    wordcloud = WordCloud(
        width=1600,
        height=800,
        background_color="white",
        max_words=50,
        colormap="viridis",
    ).generate_from_frequencies(word_counts)

    fig, ax = plt.subplots(figsize=(16, 8))
    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(f"Most Common Words in UN Noon Briefings ({STUDIED_YEAR})", fontsize=20, pad=20)
    plt.tight_layout()
    os.makedirs("../reports/figures", exist_ok=True)
    plt.savefig(f"../reports/figures/wordcloud_{STUDIED_YEAR}.png", dpi=150)
    plt.close()  # close instead of show to avoid blocking the loop
    print(f"  Saved wordcloud_{STUDIED_YEAR}.png")