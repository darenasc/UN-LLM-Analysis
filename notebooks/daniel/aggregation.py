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
from notebooks.daniel.constants import CUSTOM_STOPWORDS, PROPER_NOUNS, ALL_VARIANTS

lemmatizer = WordNetLemmatizer()
nltk.download("stopwords")
nltk.download("wordnet")

STOPWORDS = set(stopwords.words("english")).union(CUSTOM_STOPWORDS)

# Load the cleaned data
df = pd.read_csv("noon_briefings_clean.csv", parse_dates=["date"])
df["year"] = df["date"].dt.year

### --- VISUALISATION FOR EACH YEAR ---

for STUDIED_YEAR in sorted(df["year"].unique()):
    df_filtered = df[df["year"] == STUDIED_YEAR]

    if len(df_filtered) < 10:
        print(f"Skipping {STUDIED_YEAR} — not enough data")
        continue

    print(f"Processing {STUDIED_YEAR}...")

    all_text = " ".join(df_filtered["text"].dropna().tolist())

    all_text = all_text.lower()
    all_text = re.sub(r"[^a-z\s]", "", all_text)
    all_text = re.sub(r"\s+", " ", all_text)

    words = [
        lemmatizer.lemmatize(word)
        for word in all_text.split()
        if word not in STOPWORDS and len(word) > 2
    ]

    # Apply phrase merges AFTER stopword filtering, on the filtered word list,
    # so longer/more specific phrases are matched before shorter fragments
    # and stopword removal can't accidentally create false adjacency.
    merged_words = []
    i = 0
    while i < len(words):
        matched = False
        for variant_words, merged_token in ALL_VARIANTS:
            if words[i:i + len(variant_words)] == variant_words:
                merged_words.append(merged_token)
                i += len(variant_words)
                matched = True
                break
        if not matched:
            merged_words.append(words[i])
            i += 1

    words = merged_words

    # Bigrams
    bigram_list = list(bigrams(words))
    bigram_strings = [f"{w1} {w2}" for w1, w2 in bigram_list if w1 != w2]
    word_counts = Counter(bigram_strings)

    # Add proper nouns as unigrams (only tokens listed in PROPER_NOUNS are tracked)
    unigram_counts = Counter(words)
    for term in PROPER_NOUNS:
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
    os.makedirs("reports/figures", exist_ok=True)
    plt.savefig(f"../reports/figures/wordcloud_{STUDIED_YEAR}.png", dpi=150)
    plt.close()
    print(f"  Saved wordcloud_{STUDIED_YEAR}.png")