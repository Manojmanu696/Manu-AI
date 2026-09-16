"""Curated non-sensitive seed profile for Manu AI's first-launch personalization.

This is intentionally a small, editable preference seed—not a transcript or a dump of private data.
Sensitive topics are excluded. Users can edit/replace these memories from the Memory page.
"""

SEED_MEMORIES = [
    {"category": "media_taste", "content": "Prefers personalized recommendations that feel like a personal library rather than generic 'best of' lists.", "source": "user", "confidence": 1.0},
    {"category": "media_taste", "content": "Likes Marvel/Avengers and Iron Man; considers Attack on Titan a top favorite and grew up enjoying Doraemon.", "source": "user", "confidence": 1.0},
    {"category": "recommendations", "content": "Prioritize shorter, engaging, non-filler movies, series, and anime; avoid recommendations that are mainly slow emotional drama.", "source": "user", "confidence": 1.0},
    {"category": "recommendations", "content": "For recommendations, include IMDb rating, personal-fit rating, genre/category, intensity, ending type, OTT availability in India, and a short explanation of why it fits.", "source": "user", "confidence": 1.0},
    {"category": "watchlist", "content": "Current watchlist includes The Tree of Life, Shutter Island, Arrival, Eternal Sunshine, Churuli, and The Invisible Guest.", "source": "user", "confidence": 1.0},
    {"category": "watchlist", "content": "Wants existing watchlist items considered instead of being randomly ignored when making recommendations.", "source": "user", "confidence": 1.0},
    {"category": "games", "content": "Prefers story/goal-driven games, especially single-player or cooperative PvE experiences, rather than PvP-focused games.", "source": "user", "confidence": 1.0},
    {"category": "software_engineering", "content": "Manu AI is being developed as a serious software-engineering project and should favor clean architecture, explainability, tests, and maintainability.", "source": "user", "confidence": 1.0},
    {"category": "software_engineering", "content": "Primary technical interests for this project include Python, FastAPI, React/Next.js, local AI with Ollama/Qwen, recommendation systems, and practical software engineering.", "source": "user", "confidence": 1.0},
    {"category": "learning", "content": "Prefers practical, structured, step-by-step learning with mastery checks and useful exercises rather than motivational fluff.", "source": "user", "confidence": 1.0},
    {"category": "ai_product", "content": "Wants Manu AI to open with useful personalized content automatically, not an empty screen that requires asking a question first.", "source": "user", "confidence": 1.0},
    {"category": "ai_product", "content": "Wants live internet research for current discovery while keeping personal memory and local data under local control.", "source": "user", "confidence": 1.0},
]
