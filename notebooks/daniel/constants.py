from datetime import date

from nltk.corpus import stopwords

CUSTOM_STOPWORDS = {
    "also",
    "today",
    "secretary",
    "general",
    "secretarygeneral",
    "united",
    "nations",
    "said",
    "including",
    "according",
    "saying",
    "says",
    "noted",
    "added",
    "stressed",
    "told",
    "called",
    "reported",
    "un",
    "new",
    "one",
    "two",
    "three",
    "would",
    "could",
    "per",
    "met",
    "meet",
    "meeting",
    "many",
    "must",
    "tell",
    "should",
    "million",
    "number",
    "last",
    "lastly",
    "humanitarian",
    "coordination",
    "coordinator",
    "coordinators",
    "office",
    "affair",
    "affairs",
    "programme",
    "food",
    "partner",
    "continue",
    "people",
    "nearly",
    "noon",
    "briefing",
    "highlight",
    "international",
    "law",
    "right",
    "human",
    "security",
    "council",
    "country",
    "member",
    "minister",
    "representative",
    "envoy",
    "peacekeeping",
    "mission",
    "led",
    "resident",
    "statement",
    "issued",
    "men",
    "around",
    "high",
    "commissioner",
    "working",
    "women",
}
STOPWORDS = set(stopwords.words("english")).union(CUSTOM_STOPWORDS)

# Maps the merged token -> list of phrase variants that should become that token.
# To merge a new phrase, just add it here — no need to touch PROPER_NOUNS or
# remember a separate .replace() call.
MERGED_TERMS = {
    "demrepcongo": [
        "democratic republic of congo",
        "democratic republic of the congo",
        "democratic republic congo",  # in case "of" was already stripped
        "republic of congo",
        "democratic republic",  # shorter fragments last
        "republic congo",
    ],
    "worldfoodprogramme": [
        "world food programme",
    ],
    "occupiedpalestinianterritory": [
        "occupied palestinian territory",
        "occupied palestinian",
        "palestinian territory",
        "west bank",
    ],
    "gazastrip": [
        "gaza strip",
    ],
    "worldhealthorganization": [
        "world health organization",
        "world health",
        "health organization",
    ],
    "womanchild": [
        "woman child",
        "women child",
        "women children",
        "woman children",
        "women and children",
    ],
    "responseplan": [
        "response plan",
    ],
    "centralafricanrepublic": [
        "central african republic",
        "central african",
        "african republic",
    ],
    "sustainabledevelopmentgoals": [  # this term is not appearing frequently anyway
        "sustainable development goal",
        "sustainable development",
        "development goal",
        "sdgs",
        "sdg",
        "unsdg",
    ],
    # To EXCLUDE a phrase entirely (like "local authority"), just don't include
    # its merged token in PROPER_NOUNS below.
    "localauthority": [
        "local authority",
    ],
}

# Only tokens listed here are tracked/counted. Anything merged above but
# NOT listed here is silently dropped — this is how you "exclude" a phrase
# without needing separate stopword logic.
PROPER_NOUNS = [
    "worldhealthorganization",
    "demrepcongo",
    "occupiedpalestinianterritory",
    "gazastrip",
    "worldfoodprogramme",
    "womanchild",
    "centralafricanrepublic",
    # "localauthority"
]

# Build a flat list of (variant_words, merged_token), sorted longest-first
# so longer phrases are always tried before shorter overlapping fragments
ALL_VARIANTS = sorted(
    (
        (variant.split(), merged_token)
        for merged_token, variants in MERGED_TERMS.items()
        for variant in variants
    ),
    key=lambda x: len(x[0]),
    reverse=True,
)

SATURDAY = 5
BACKUP_EVERY_X_ITERATIONS = 50
BASE_URL = "https://www.un.org/sg/en/content/noon-briefing-highlight"
START_DATE = date(2021, 1, 1)
END_DATE = date.today()
