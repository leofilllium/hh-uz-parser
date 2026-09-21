#!/usr/bin/env python3
"""
HH.uz Vacancy Notification Telegram Bot

Dual-Gate Architecture:
  1. Gate 1 (Узбекистан):
     - Monitors hh.uz for vacancies located in Uzbekistan.
     - Header: "🆕 <b>Новая вакансия (Узбекистан)!</b>"
  2. Gate 2 (НОВАЯ УДАЛЕНКА):
     - Monitors hh.ru for remote vacancies (schedule=remote) worldwide.
     - Excludes any vacancies from Uzbekistan.
     - Header: "🌐 <b>НОВАЯ УДАЛЕНКА!</b>"

Strict profile filtering:
  Flutter, Dart, Mobile, AI, React, Next.js, Frontend, Fullstack, LLM.

Spam prevention:
  1. Title blocklist for irrelevant professions.
  2. RSS backfill detection (empty search protection).
  3. Keyword matching across vacancy title and description.
"""
import asyncio
import logging
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlencode

import requests
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

from config import (
    TELEGRAM_BOT_TOKEN,
    CHECK_INTERVAL,
    HH_UZ_RSS_BASE_URL,
    HH_GLOBAL_RSS_BASE_URL,
    UZBEKISTAN_AREA_ID,
    UZBEKISTAN_REGIONS,
    EXPERIENCE_FILTERS,
    RELEVANT_KEYWORDS,
    SPAM_TITLE_BLOCKLIST,
    get_search_profile,
)
from database import (
    init_db,
    get_or_create_user,
    deactivate_user,
    get_active_users,
    get_users_count,
    is_vacancy_seen_by_user,
    mark_vacancy_seen_by_user,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


# ==================== RSS Parsing ====================

def _parse_rss_description(desc: str) -> dict:
    """Extract structured fields from RSS description HTML.

    Example description:
      <p>Вакансия компании: PAYNET</p>
      <p>Создана: 10.09.2026</p>
      <p>Регион: Ташкент</p>
      <p>Предполагаемый уровень месячного дохода: от 1 000 до 2 500 $</p>
    """
    result = {}
    desc = desc.replace("<![CDATA[", "").replace("]]>", "").strip()

    # Extract company
    m = re.search(r"Вакансия компании:\s*(.+?)(?:</p>|$)", desc)
    if m:
        result["employer"] = m.group(1).strip()

    # Extract region
    m = re.search(r"Регион:\s*(.+?)(?:</p>|$)", desc)
    if m:
        result["area"] = m.group(1).strip()

    # Extract salary
    m = re.search(r"месячного дохода:\s*(.+?)(?:</p>|$)", desc)
    if m:
        salary_raw = m.group(1).strip()
        if salary_raw != "не указан":
            result["salary"] = salary_raw

    return result


def _vacancy_id_from_url(url: str) -> str:
    """Extract vacancy ID from URL like https://hh.ru/vacancy/137134502."""
    m = re.search(r"/vacancy/(\d+)", url)
    return m.group(1) if m else url


def parse_rss_items(xml_text: str, gate: str = "uz") -> list:
    """Parse RSS XML into a list of vacancy dicts compatible with the bot."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error(f"Failed to parse RSS XML: {e}")
        return []

    items = root.findall(".//item")
    vacancies = []

    for item in items:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        desc_raw = (item.findtext("description") or "").strip()

        parsed = _parse_rss_description(desc_raw)
        vacancy_id = _vacancy_id_from_url(link)

        vacancies.append({
            "id": vacancy_id,
            "name": title,
            "alternate_url": link,
            "published_at": pub_date,
            "employer": {"name": parsed.get("employer", "Компания не указана")},
            "area": {"name": parsed.get("area", "")},
            "salary_text": parsed.get("salary"),
            "gate": gate,
            "_description": desc_raw,
        })

    return vacancies


# ==================== Relevance & Spam Filtering ====================

def _text_blob(vacancy: dict) -> str:
    """Extract a combined lowercase text blob from vacancy fields for matching."""
    parts = [
        vacancy.get("name", ""),
        vacancy.get("_description", ""),
        (vacancy.get("employer") or {}).get("name", ""),
    ]
    return " ".join(parts).lower()


def _is_title_blocked(vacancy: dict, title_blocklist: list = SPAM_TITLE_BLOCKLIST) -> bool:
    """Return True if the vacancy title matches any spam blocklist entry."""
    title = (vacancy.get("name") or "").lower()
    return any(spam in title for spam in title_blocklist)


def _is_relevant(vacancy: dict, relevant_keywords: list = RELEVANT_KEYWORDS) -> bool:
    """Return True if the vacancy matches at least one relevant keyword."""
    blob = _text_blob(vacancy)
    return any(kw.lower() in blob for kw in relevant_keywords)


def _query_matches_title(query: str, title: str) -> bool:
    """Check if the core search terms appear in the vacancy title."""
    clean = re.sub(r'\b(NOT|AND|OR)\b', ' ', query, flags=re.IGNORECASE)
    clean = clean.replace('"', '').replace("'", "")
    words = [w.strip().lower() for w in clean.split() if len(w.strip()) >= 2]
    title_lower = title.lower()
    return any(w in title_lower for w in words)


def _is_uzbekistan_location(vacancy: dict) -> bool:
    """Check if a vacancy is based in Uzbekistan."""
    area = (vacancy.get("area", {}).get("name") or "").lower()
    desc = (vacancy.get("_description") or "").lower()
    for reg in UZBEKISTAN_REGIONS:
        if reg in area or f"регион: {reg}" in desc:
            return True
    return False


def filter_vacancies(
    vacancies: list,
    query: str,
    gate: str = "uz",
    relevant_keywords: list = RELEVANT_KEYWORDS,
    title_blocklist: list = SPAM_TITLE_BLOCKLIST,
) -> list:
    """Apply all spam-prevention filters and gate-specific geographical rules.

    Strategy:
      1. Drop anything whose title is in the blocklist.
      2. Drop Uzbekistan vacancies if we are in the 'remote' gate.
      3. Check if at least one vacancy title matches the query.
         If NONE do, the feed returned backfill junk — drop entire batch.
      4. Ensure EACH vacancy matches our target skills (Flutter, React, AI, Fullstack, etc.).
    """
    if not vacancies:
        return []

    # Step 1 – blocklist
    candidates = [v for v in vacancies if not _is_title_blocked(v, title_blocklist)]
    if not candidates:
        return []

    # Step 2 – geographical gate separation
    if gate == "remote":
        candidates = [v for v in candidates if not _is_uzbekistan_location(v)]
        if not candidates:
            return []

    # Step 3 – detect backfill: did the feed return anything matching the query?
    has_real_match = any(
        _query_matches_title(query, v.get("name", ""))
        for v in candidates
    )

    if not has_real_match:
        logger.info(
            f"[{gate.upper()}] Query '{query}': zero title matches in {len(candidates)} results; "
            f"dropping all items to prevent backfill spam."
        )
        return []

    # Step 4 – skill relevance filter
    filtered = [v for v in candidates if _is_relevant(v, relevant_keywords)]
    dropped = len(candidates) - len(filtered)
    if dropped:
        logger.info(
            f"[{gate.upper()}] Query '{query}': dropped {dropped}/{len(candidates)} "
            f"irrelevant results"
        )
    return filtered


# ==================== Fetch Functions ====================

def fetch_uz_vacancies(query: str, experience: str = None, profile: dict = None) -> list:
    """Gate 1: Fetch vacancies in Uzbekistan via hh.uz RSS."""
    params = {
        "text": query,
        "area": UZBEKISTAN_AREA_ID,
        "search_field": "name",
    }
    if experience:
        params["experience"] = experience

    url = f"{HH_UZ_RSS_BASE_URL}?{urlencode(params)}"
    headers = {
        "Accept": "application/rss+xml, application/xml, text/xml",
        "User-Agent": "hh-uz-parser/1.0 (leofillium@gmail.com)",
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        raw = parse_rss_items(response.text, gate="uz")
        profile = profile or get_search_profile(0)
        return filter_vacancies(
            raw,
            query,
            gate="uz",
            relevant_keywords=profile["relevant_keywords"],
            title_blocklist=profile["title_blocklist"],
        )
    except requests.RequestException as e:
        logger.error(f"[UZ] Failed to fetch RSS for '{query}': {e}")
        return []


def fetch_remote_vacancies(query: str, experience: str = None, profile: dict = None) -> list:
    """Gate 2: Fetch remote vacancies worldwide (excluding Uzbekistan) via hh.ru RSS."""
    params = {
        "text": query,
        "schedule": "remote",
        "search_field": "name",
    }
    if experience:
        params["experience"] = experience

    url = f"{HH_GLOBAL_RSS_BASE_URL}?{urlencode(params)}"
    headers = {
        "Accept": "application/rss+xml, application/xml, text/xml",
        "User-Agent": "hh-uz-parser/1.0 (leofillium@gmail.com)",
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        raw = parse_rss_items(response.text, gate="remote")
        profile = profile or get_search_profile(0)
        return filter_vacancies(
            raw,
            query,
            gate="remote",
            relevant_keywords=profile["relevant_keywords"],
            title_blocklist=profile["title_blocklist"],
        )
    except requests.RequestException as e:
        logger.error(f"[REMOTE] Failed to fetch RSS for '{query}': {e}")
        return []


def format_vacancy_message(vacancy: dict) -> str:
    """Format a vacancy into a Telegram message with appropriate gate header."""
    title = vacancy.get("name", "Без названия")
    employer = vacancy.get("employer", {}).get("name", "Компания не указана")
    salary = vacancy.get("salary_text", "Не указана") or "Не указана"
    area = vacancy.get("area", {}).get("name", "")
    url = vacancy.get("alternate_url", "")
    gate = vacancy.get("gate", "uz")

    published_at = vacancy.get("published_at", "")
    if published_at:
        try:
            dt = datetime.fromisoformat(published_at)
            published = dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            published = published_at
    else:
        published = "Неизвестно"

    if gate == "remote":
        header = "🌐 <b>НОВАЯ УДАЛЕНКА!</b>"
        location_line = f"📍 Регион: {area} (Удаленная работа)" if area else "📍 Удаленная работа"
    else:
        header = "🆕 <b>Новая вакансия (Узбекистан)!</b>"
        location_line = f"📍 {area}" if area else "📍 Узбекистан"

    return (
        f"{header}\n\n"
        f"📋 <b>{title}</b>\n"
        f"🏢 {employer}\n"
        f"{location_line}\n"
        f"💰 {salary}\n"
        f"📅 Опубликовано: {published}\n\n"
        f"🔗 <a href=\"{url}\">Открыть вакансию</a>"
    )


# ==================== Telegram Command Handlers ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - subscribe user to notifications."""
    user = update.effective_user
    if not user:
        return

    get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name
    )

    active, total = get_users_count()
    profile = get_search_profile(user.id)
    query_summary = "\n".join(f"  • {q}" for q in profile["queries"])

    await update.message.reply_html(
        f"👋 Привет, <b>{user.first_name or 'друг'}</b>!\n\n"
        f"🔔 Вы подписаны на уведомления с <b>двух потоков</b>:\n\n"
        f"1️⃣ <b>Узбекистан:</b> вакансии в регионе\n"
        f"2️⃣ <b>НОВАЯ УДАЛЕНКА:</b> удаленная работа со всего мира (кроме Узбекистана)\n\n"
        f"🎯 <b>Направления поиска:</b>\n"
        f"{query_summary}\n\n"
        f"⏱ Проверка каждые {CHECK_INTERVAL // 60} мин.\n"
        f"Чтобы отписаться, отправьте /stop\n\n"
        f"👥 Всего подписчиков: {active}"
    )
    logger.info(f"User subscribed: {user.id} (@{user.username})")

    # Send current vacancies to the new user
    asyncio.create_task(send_existing_vacancies_to_user(context.bot, user.id))


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stop command - unsubscribe user from notifications."""
    user = update.effective_user
    if not user:
        return

    deactivate_user(user.id)

    await update.message.reply_html(
        f"👋 <b>{user.first_name or 'Пользователь'}</b>, вы отписались от уведомлений.\n\n"
        f"Чтобы подписаться снова, отправьте /start"
    )
    logger.info(f"User unsubscribed: {user.id} (@{user.username})")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - show bot status."""
    active, total = get_users_count()

    await update.message.reply_html(
        f"📊 <b>Статус бота</b>\n\n"
        f"👥 Активных подписчиков: {active}\n"
        f"📝 Всего пользователей: {total}\n"
        f"🚪 Активные ворота: Узбекистан + НОВАЯ УДАЛЕНКА (Global)\n"
        f"⏱ Интервал проверки: {CHECK_INTERVAL // 60} мин."
    )


# ==================== Notification Helpers ====================

async def send_existing_vacancies_to_user(bot: Bot, telegram_id: int) -> None:
    """Send existing vacancies to a newly subscribed user across both gates."""
    await asyncio.sleep(1)

    all_vacancies = []
    seen_ids = set()
    profile = get_search_profile(telegram_id)

    for query in profile["queries"]:
        for experience in EXPERIENCE_FILTERS:
            # Gate 1: Uzbekistan
            uz_vacs = fetch_uz_vacancies(query, experience, profile)
            for v in uz_vacs:
                vid = str(v.get("id"))
                if (
                    vid
                    and vid not in seen_ids
                    and not is_vacancy_seen_by_user(telegram_id, vid)
                ):
                    all_vacancies.append(v)
                    seen_ids.add(vid)

            # Gate 2: Remote Worldwide
            rem_vacs = fetch_remote_vacancies(query, experience, profile)
            for v in rem_vacs:
                vid = str(v.get("id"))
                if (
                    vid
                    and vid not in seen_ids
                    and not is_vacancy_seen_by_user(telegram_id, vid)
                ):
                    all_vacancies.append(v)
                    seen_ids.add(vid)

            await asyncio.sleep(0.25)

    all_vacancies.sort(
        key=lambda x: x.get("published_at", ""),
        reverse=True
    )

    if all_vacancies:
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=f"📋 <b>Текущие вакансии (Узбекистан + Удаленка, {len(all_vacancies)} шт.):</b>",
                parse_mode="HTML"
            )
        except TelegramError as e:
            logger.warning(f"Failed to send header to {telegram_id}: {e}")
            return

        await asyncio.sleep(0.5)

        for vacancy in all_vacancies[:20]:
            try:
                message = format_vacancy_message(vacancy)
                await bot.send_message(
                    chat_id=telegram_id,
                    text=message,
                    parse_mode="HTML",
                    disable_web_page_preview=False
                )
                mark_vacancy_seen_by_user(telegram_id, str(vacancy["id"]))
                await asyncio.sleep(0.3)
            except TelegramError as e:
                logger.warning(f"Failed to send vacancy to {telegram_id}: {e}")
                break

        if len(all_vacancies) > 20:
            try:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=f"... и ещё {len(all_vacancies) - 20} вакансий. Новые будут приходить автоматически!",
                    parse_mode="HTML"
                )
            except TelegramError:
                pass


async def check_new_vacancies(bot: Bot) -> None:
    """Check and notify each active user using only that user's profile."""
    for telegram_id, username, first_name in get_active_users():
        profile = get_search_profile(telegram_id)
        new_vacancies = []
        seen_in_this_run = set()

        for query in profile["queries"]:
            for experience in EXPERIENCE_FILTERS:
                for vacancies in (
                    fetch_uz_vacancies(query, experience, profile),
                    fetch_remote_vacancies(query, experience, profile),
                ):
                    for vacancy in vacancies:
                        vacancy_id = str(vacancy.get("id"))
                        if (
                            vacancy_id
                            and vacancy_id not in seen_in_this_run
                            and not is_vacancy_seen_by_user(telegram_id, vacancy_id)
                        ):
                            new_vacancies.append(vacancy)
                            seen_in_this_run.add(vacancy_id)
                await asyncio.sleep(0.25)

        new_vacancies.sort(key=lambda x: x.get("published_at", ""), reverse=True)
        for vacancy in new_vacancies:
            try:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=format_vacancy_message(vacancy),
                    parse_mode="HTML",
                    disable_web_page_preview=False,
                )
                mark_vacancy_seen_by_user(telegram_id, str(vacancy["id"]))
                await asyncio.sleep(0.5)
            except TelegramError as e:
                logger.warning(f"Failed to send vacancy to user {telegram_id}: {e}")
                if "blocked" in str(e).lower() or "deactivated" in str(e).lower():
                    deactivate_user(telegram_id)
                break

        logger.info(
            f"User {telegram_id}: sent {len(new_vacancies)} new vacancies "
            f"using {len(profile['queries'])} queries"
        )


async def vacancy_checker(app: Application) -> None:
    """Background task to periodically check for new vacancies."""
    bot = app.bot

    await asyncio.sleep(5)
    logger.info(f"Starting dual-gate vacancy checker (interval: {CHECK_INTERVAL}s)")

    while True:
        try:
            await check_new_vacancies(bot)
        except Exception as e:
            logger.error(f"Error during vacancy check: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


async def post_init(app: Application) -> None:
    """Called after application initialization."""
    init_db()
    logger.info("Database initialized")
    asyncio.create_task(vacancy_checker(app))


def main():
    """Main entry point."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        sys.exit(1)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status_command))

    logger.info("Bot starting with Dual-Gate (Uzbekistan + НОВАЯ УДАЛЕНКА)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
