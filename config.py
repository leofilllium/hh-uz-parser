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

# HH.uz API Configuration
# Note: api.hh.uz redirects to api.hh.ru, so we use hh.ru with Uzbekistan area filter
HH_API_BASE_URL = "https://api.hh.ru"

# Uzbekistan area ID for filtering vacancies
# 2759 = Tashkent
UZBEKISTAN_AREA_ID = "2759"

# Search queries for vacancy positions
SEARCH_QUERIES = [
    "младший юрист",
    "коммерческий юрист",
    "помощник юриста",
]

# Experience filters - no experience, up to 1 year, 1-3 years
EXPERIENCE_FILTERS = [
    "noExperience",
    "between1And3",
]
