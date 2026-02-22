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
UZBEKISTAN_AREA_ID = "2759"

# Search queries for vacancy positions
SEARCH_QUERIES = [
    "Flutter",
    "Flutter разработчик",
    "Middle Flutter разработчик",
    "Senior Flutter разработчик",
    "Junior Flutter разработчик",
    "Flutter Developer",
    "Dart Developer",
    "Mobile Flutter Developer",
    "Flutter Lead",
    "Flutter-разработчик",
    "Fullstack Flutter",
    "Mobile Developer (Flutter)",
    "Flutter Engineer",
    "Dart Engineer",
    "Flutter SDK",
    "IOS разработчик Flutter",
    "Android разработчик Flutter",
    "Team Lead Flutter",
    "Tech Lead Flutter",
    "Strong Junior Flutter",
    "Strong Middle Flutter",
    "Lead Flutter Developer",
    "Flutter architect",
    "Junior+ Flutter разработчик",
    "Cross-platform developer Flutter",
    "Mobile App Developer Dart/Flutter",
    "Разработчик Flutter",
    "Программист Flutter",
    "Senior Dart Developer",
    "Middle Dart Developer",
    "Junior Dart Developer",
    "Flutter Intern",
    "Стажер Flutter",
    "Flutter flow",
    "Mobile Dev Flutter",
    "Flutter Mobile Engineer",
    "Dart/Flutter Developer",
    "Dart/Flutter разработчик",
    "Expert Flutter",
    "Principal Flutter Developer",
    "Lead Mobile Developer Flutter",
    "Flutter Specialist",
    "Flutter GDE",
    "Dart GDE",
    "Flutter Framework Developer",
    "Mobile Software Engineer Flutter",
    "React Native to Flutter",
    "Flutter UI/UX",
    "Flutter Animation Developer",
    "Flutter Game Developer",
    "Flame Engine Developer",
    "Flutter Web Developer",
    "Flutter Desktop Developer",
    "Flutter macOS Developer",
    "Flutter Windows Developer",
    "Flutter Linux Developer",
    "Flutter Embedded",
    "Flutter Rust",
    "Flutter FFI",
]

# Experience filters - no experience, up to 1 year, 1-3 years, 3-6 years, 6+ years
EXPERIENCE_FILTERS = [
    "noExperience",
    "between1And3",
    "between3And6",
    "moreThan6",
]
