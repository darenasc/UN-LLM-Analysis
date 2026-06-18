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
    "also", "today", "secretary", "general", "secretarygeneral", "united", "nations",
    "said", "including", "according", "said", "saying", "says",
    "noted", "added", "stressed", "told", "called", "reported",
    "un", "new", "one", "two", "three", "would", "could", "per", "met", "meet", "meeting", "many","must","should", "million", "number"
}

STOPWORDS = set(stopwords.words("english")).union(CUSTOM_STOPWORDS)

STUDIED_YEAR = 2025

# Load the cleaned data
df = pd.read_csv("noon_briefings_clean.csv", parse_dates=["date"])

# Add a year column for filtering
df["year"] = df["date"].dt.year


### --- VISUALISATION FOR 2025 ONLY ---
# Filter to last calendar year

df_filtered = df[df["year"] == STUDIED_YEAR]

# Combine all text into one big string
all_text = " ".join(df_filtered["text"].dropna().tolist())

# Clean the text:
# - lowercase everything so "Ukraine" and "ukraine" are counted as one word
# - remove punctuation and numbers, keeping only letters and spaces
all_text = all_text.lower()
all_text = re.sub(r"[^a-z\s]", "", all_text)

# Lemmatize and filter individual words first
words = [
    lemmatizer.lemmatize(word)
    for word in all_text.split()
    if word not in STOPWORDS and len(word) > 2
]

# Generate bigrams from the filtered word list.
# Because stopwords are already removed, bigrams won't contain filler words
# on either side — so you get meaningful pairs like "human rights"
# rather than "the council" or "of people".
bigram_list = list(bigrams(words))

# Convert each bigram tuple to a single string for the word cloud
bigram_strings = [f"{w1} {w2}" for w1, w2 in bigram_list]

# Count bigram frequencies
word_counts = Counter(bigram_strings)

# Apply minimum frequency threshold to remove rare noise
word_counts = {bigram: count for bigram, count in word_counts.items() if count >= 5}

print(f"Top 20 bigrams: {Counter(word_counts).most_common(20)}")
# Generate the word cloud
wordcloud = WordCloud(
    width=1600,
    height=800,
    background_color="white",
    max_words=50,       # cap at 50 words to keep it readable
    colormap="viridis",  # colour scheme — change to e.g. "plasma", "coolwarm"

).generate_from_frequencies(word_counts)

# Plot and save
fig, ax = plt.subplots(figsize=(16, 8))
ax.imshow(wordcloud, interpolation="bilinear")
ax.axis("off")
ax.set_title(f"Most Common Words in UN Noon Briefings ({STUDIED_YEAR})", fontsize=20, pad=20)
plt.tight_layout()
os.makedirs("figures", exist_ok=True)
plt.savefig(f"../reports/figures/wordcloud_{STUDIED_YEAR}.png", dpi=150)
plt.show()