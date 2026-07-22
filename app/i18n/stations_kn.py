"""Hand-written Kannada->English transliterations for proper nouns.

LLM transliteration of proper nouns is unreliable; this list is small and authoritative.
Applied to the query BEFORE routing so station names resolve exactly.
"""
STATIONS_KN = {
    "ಕೆಂಗೇರಿ": "Kengeri",
    "ರಾಜರಾಜೇಶ್ವರಿ ನಗರ": "Rajarajeshwari Nagar",
    "ಜ್ಞಾನಭಾರತಿ": "Jnanabharathi",
    "ಬನಶಂಕರಿ": "Banashankari",
    "ಜೆಪಿ ನಗರ": "JP Nagar",
    "ವೈಟ್‌ಫೀಲ್ಡ್": "Whitefield",
    "ಮಾರತಹಳ್ಳಿ": "Marathahalli",
    "ಇಂದಿರಾನಗರ": "Indiranagar",
    "ಯಲಹಂಕ": "Yelahanka",
    "ಹೆಬ್ಬಾಳ": "Hebbal",
    "ಪೀಣ್ಯ": "Peenya",
    "ರಾಜಾಜಿನಗರ": "Rajajinagar",
    "ವಿಜಯನಗರ": "Vijayanagar",
    "ದೇವನಹಳ್ಳಿ": "Devanahalli",
    "ಹೊಸಕೋಟೆ": "Hoskote",
    "ಮೈಸೂರು": "Mysuru",
    "ನಂಜನಗೂಡು": "Nanjangud",
    "ಬೆಂಗಳೂರು": "Bengaluru",
    "ಬೆಂಗಳೂರು ದಕ್ಷಿಣ": "Bengaluru South",
}

# Divisions / districts that also appear in Kannada queries.
AREAS_KN = {
    "ದಕ್ಷಿಣ": "South",
    "ಉತ್ತರ": "North",
    "ಪೂರ್ವ": "East",
    "ಪಶ್ಚಿಮ": "West",
}


def apply_station_map(text: str) -> str:
    """Replace known Kannada proper nouns with their English forms, longest first."""
    for kn, en in sorted({**STATIONS_KN, **AREAS_KN}.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(kn, en)
    return text
