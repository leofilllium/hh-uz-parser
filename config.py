"""Configuration module for HH.uz Telegram Bot."""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Polling Configuration
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # 5 minutes default

# Database Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/hh_bot"
)

# HH.uz RSS feed base URL for Uzbekistan vacancies — no OAuth required
HH_UZ_RSS_BASE_URL = "https://hh.uz/search/vacancy/rss"

# HH.ru global RSS feed base URL for remote vacancies anywhere in the world
HH_GLOBAL_RSS_BASE_URL = "https://hh.ru/search/vacancy/rss"

# Uzbekistan area ID for filtering local vacancies
UZBEKISTAN_AREA_ID = "2759"

# Regions of Uzbekistan to exclude from the Remote Gate (since they belong to the Uzbekistan gate)
UZBEKISTAN_REGIONS = [
    "ташкент", "узбекистан", "самарканд", "бухара", "наманган",
    "андижан", "фергана", "нукус", "карши", "навои", "термез",
    "джизак", "ургенч", "хива", "коканд", "чирчик", "алмалык",
]

# ---------------------------------------------------------------------------
# Search queries strictly limited to:
# FLUTTER, DART, MOBILE, AI, REACT, NEXT.JS, FRONTEND, FULLSTACK, LLM
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    # ── Flutter & Dart ────────────────────────────────────────────────
    "Flutter",
    "Flutter разработчик",
    "Dart Developer",

    # ── Mobile ────────────────────────────────────────────────────────
    "Mobile Developer",
    "Мобильный разработчик",

    # ── Fullstack ─────────────────────────────────────────────────────
    "Full-stack разработчик",
    "Fullstack Developer",
    "Fullstack",

    # ── Frontend, React, Next.js ──────────────────────────────────────
    "React разработчик",
    "Frontend разработчик",
    "Frontend Developer",
    "React Developer",
    "Next.js",

    # ── AI & LLM ──────────────────────────────────────────────────────
    "AI разработчик",
    "AI Engineer",
    "LLM",
]

# Experience filters
EXPERIENCE_FILTERS = [
    "noExperience",
    "between1And3",
    "between3And6",
    "moreThan6",
]

# ---------------------------------------------------------------------------
# Relevance filter – ONLY Flutter, Dart, Mobile, AI, React, Next.js,
# Frontend, Fullstack, LLM related keywords.
# ---------------------------------------------------------------------------
RELEVANT_KEYWORDS = [
    # Flutter & Dart
    "flutter", "dart",
    # Mobile
    "mobile", "мобильн", "ios", "android", "кроссплатформ", "cross-platform",
    # Frontend, React, Next.js
    "react", "next.js", "nextjs", "frontend", "фронтенд", "front-end",
    # Fullstack
    "fullstack", "full-stack", "фулстек", "full stack",
    # AI & LLM
    "ai", "llm", "нейросет", "искусственн", "langchain", "rag", "openai", "gemini",
]

# ---------------------------------------------------------------------------
# Spam title blocklist – if a vacancy title contains any of these substrings
# (case-insensitive) it is immediately rejected.
# ---------------------------------------------------------------------------
SPAM_TITLE_BLOCKLIST = [
    "водитель", "курьер", "оператор колл", "оператор call",
    "менеджер по продажам", "продавец", "кассир", "грузчик",
    "охранник", "повар", "уборщ", "сварщик", "слесарь",
    "маляр", "штукатур", "каменщик", "бетонщик", "монтажник",
    "электрик", "сантехник", "плотник", "токар", "фрезеровщик",
    "швея", "закройщик", "портн", "прачеч", "гладильщ",
    "официант", "бармен", "бариста", "посудомой", "хостес",
    "няня", "воспитатель", "гувернант", "домработни",
    "медсестра", "санитар", "фельдшер", "фармацевт",
    "стоматолог", "врач", "ветеринар",
    "агент недвижимости", "риэлтор", "риелтор",
    "страховой агент", "кредитный специалист",
    "учитель", "преподаватель", "репетитор",
    "парикмахер", "маникюр", "косметолог", "визажист",
    "таксист", "экспедитор", "кладовщик",
    "бухгалтер", "аудитор", "маркетолог", "таргетолог",
    "smm", "контент", "копирайтер", "дизайнер",
    "системный администратор", "1с", "1c",
    "devops", "qa", "тестировщик", "manual tester",
]

# Per-user search profiles. Users not listed here use the original default
# configuration above. Keep the original profile explicitly assigned to the
# existing subscriber so later default changes cannot alter their search.
UI_UX_DESIGNER_QUERIES = [
    "UI/UX Designer",
    "UI UX Designer",
    "UX/UI Designer",
    "UI Designer",
    "UX Designer",
    "User Experience Designer",
    "User Interface Designer",
    "Product Designer",
    "Digital Product Designer",
    "UX Product Designer",
    "Product UX/UI Designer",
    "Junior Product Designer",
    "Middle Product Designer",
    "Senior Product Designer",
    "Interaction Designer",
    "Experience Designer",
    "UI/UX дизайнер",
    "UI UX дизайнер",
    "UX/UI дизайнер",
    "UI дизайнер",
    "UX дизайнер",
    "Дизайнер интерфейсов",
    "Дизайнер пользовательских интерфейсов",
    "Дизайнер UX",
    "Дизайнер UI",
    "Продуктовый дизайнер",
    "Продуктовый UX/UI дизайнер",
    "Дизайнер цифровых продуктов",
    "UX дизайнер продукта",
    "Дизайнер цифрового продукта",
    "Дизайнер взаимодействия",
]

USER_SEARCH_PROFILES = {
    308896015: {
        "queries": SEARCH_QUERIES,
        "relevant_keywords": RELEVANT_KEYWORDS,
        "title_blocklist": SPAM_TITLE_BLOCKLIST,
    },
    1823478131: {
        "queries": UI_UX_DESIGNER_QUERIES,
        # The supplied terms are the only matching vocabulary for this user.
        "relevant_keywords": UI_UX_DESIGNER_QUERIES,
        # "дизайнер" is part of the requested titles, so it cannot be blocked.
        "title_blocklist": [term for term in SPAM_TITLE_BLOCKLIST if term != "дизайнер"],
    },
}


def get_search_profile(telegram_id: int) -> dict:
    """Return a user's dedicated profile, or the original default profile."""
    return USER_SEARCH_PROFILES.get(telegram_id, {
        "queries": SEARCH_QUERIES,
        "relevant_keywords": RELEVANT_KEYWORDS,
        "title_blocklist": SPAM_TITLE_BLOCKLIST,
    })
