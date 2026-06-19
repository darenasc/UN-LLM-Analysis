from nltk.corpus import stopwords

CUSTOM_STOPWORDS = {
    "also", "today", "secretary", "general", "secretarygeneral", "united", "nations",
    "said", "including", "according", "saying", "says",
    "noted", "added", "stressed", "told", "called", "reported",
    "un", "new", "one", "two", "three", "would", "could", "per", "met", "meet", "meeting", "many", "must", "tell",
    "should", "million", "number",
    "last", "lastly",
    "humanitarian",
    "coordination", "coordinator", "coordinators",
    "office", "affair", "affairs",
    "programme", "food",
    "partner", "continue",
    "people", "nearly",
    "noon", "briefing", "highlight",
    "international", "law", "right", "human",
    "security", "council", "country", "member", "minister","representative",
    "led", "resident", "statement", "issued", "men", "woman", "around", "high", "commissioner", "working"
}
STOPWORDS = set(stopwords.words("english")).union(CUSTOM_STOPWORDS)

PROPER_NOUNS = [
    "worldhealthorganization",
    "demrepcongo",
    "occupiedpalestinianterritory",
    "gazastrip",
    "worldfoodprogramme"
]
