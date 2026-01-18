#!/usr/bin/env python3
"""
HH.uz Vacancy Notification Telegram Bot

Monitors hh.uz for new job vacancies for "младший юрист" and "коммерческий юрист"
positions with no experience required, and sends Telegram notifications to subscribed users.
"""
import asyncio
import logging
import sys
from datetime import datetime

import requests
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

from config import (
    TELEGRAM_BOT_TOKEN,
    CHECK_INTERVAL,
    HH_API_BASE_URL,
    UZBEKISTAN_AREA_ID,
    SEARCH_QUERIES,
    EXPERIENCE_FILTER,
)
from database import (
    init_db,
    get_or_create_user,
    deactivate_user,
    get_active_users,
    get_users_count,
    is_vacancy_seen,
    mark_vacancy_seen,
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
    
    await update.message.reply_html(
        f"👋 Привет, <b>{user.first_name or 'друг'}</b>!\n\n"
        f"🔔 Вы подписаны на уведомления о вакансиях:\n"
        f"• младший юрист\n"
        f"• коммерческий юрист\n\n"
        f"📍 Регион: Узбекистан\n"
        f"🎯 Фильтр: без опыта работы\n"
        f"⏱ Проверка каждые {CHECK_INTERVAL // 60} мин.\n\n"
        f"Чтобы отписаться, отправьте /stop\n\n"
        f"👥 Всего подписчиков: {active}"
    )
    logger.info(f"User subscribed: {user.id} (@{user.username})")


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
        f"⏱ Интервал проверки: {CHECK_INTERVAL // 60} мин."
    )


# ==================== Vacancy Functions ====================

def fetch_vacancies(query: str) -> list:
    """Fetch vacancies from hh.uz API for a given search query."""
    url = f"{HH_API_BASE_URL}/vacancies"
    params = {
        "text": query,
        "area": UZBEKISTAN_AREA_ID,
        "experience": EXPERIENCE_FILTER,
        "per_page": 100,
        "order_by": "publication_time",
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("items", [])
    except requests.RequestException as e:
        logger.error(f"Failed to fetch vacancies for '{query}': {e}")
        return []


def format_vacancy_message(vacancy: dict) -> str:
    """Format a vacancy into a Telegram message."""
    title = vacancy.get("name", "Без названия")
    employer = vacancy.get("employer", {}).get("name", "Компания не указана")
    
    # Format salary
    salary_data = vacancy.get("salary")
    if salary_data:
        salary_from = salary_data.get("from")
        salary_to = salary_data.get("to")
        currency = salary_data.get("currency", "")
        
        if salary_from and salary_to:
            salary = f"{salary_from:,} - {salary_to:,} {currency}".replace(",", " ")
        elif salary_from:
            salary = f"от {salary_from:,} {currency}".replace(",", " ")
        elif salary_to:
            salary = f"до {salary_to:,} {currency}".replace(",", " ")
        else:
            salary = "Не указана"
    else:
        salary = "Не указана"
    
    area = vacancy.get("area", {}).get("name", "")
    url = vacancy.get("alternate_url", vacancy.get("url", ""))
    
    published_at = vacancy.get("published_at", "")
    if published_at:
        try:
            dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            published = dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            published = published_at
    else:
        published = "Неизвестно"
    
    return (
        f"🆕 <b>Новая вакансия!</b>\n\n"
        f"📋 <b>{title}</b>\n"
        f"🏢 {employer}\n"
        f"📍 {area}\n"
        f"💰 {salary}\n"
        f"📅 Опубликовано: {published}\n\n"
        f"🔗 <a href=\"{url}\">Открыть вакансию</a>"
    )


async def send_to_all_users(bot: Bot, message: str) -> int:
    """Send a message to all active users. Returns count of successful sends."""
    users = get_active_users()
    sent_count = 0
    
    for telegram_id, username, first_name in users:
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="HTML",
                disable_web_page_preview=False
            )
            sent_count += 1
            await asyncio.sleep(0.1)  # Rate limiting
        except TelegramError as e:
            logger.warning(f"Failed to send to user {telegram_id}: {e}")
            if "blocked" in str(e).lower() or "deactivated" in str(e).lower():
                deactivate_user(telegram_id)
                logger.info(f"Deactivated user {telegram_id} (bot blocked)")
    
    return sent_count


async def check_new_vacancies(bot: Bot) -> None:
    """Check for new vacancies and send notifications to all users."""
    new_vacancies = []
    
    for query in SEARCH_QUERIES:
        logger.info(f"Checking vacancies for: {query}")
        vacancies = fetch_vacancies(query)
        
        for vacancy in vacancies:
            vacancy_id = str(vacancy.get("id"))
            
            if vacancy_id and not is_vacancy_seen(vacancy_id):
                new_vacancies.append(vacancy)
                mark_vacancy_seen(vacancy_id)
    
    if new_vacancies:
        logger.info(f"Found {len(new_vacancies)} new vacancies, sending to users...")
        
        for vacancy in new_vacancies:
            message = format_vacancy_message(vacancy)
            sent = await send_to_all_users(bot, message)
            logger.info(f"Sent vacancy {vacancy.get('id')} to {sent} users")
            await asyncio.sleep(0.5)
    else:
        logger.info("No new vacancies found")


async def vacancy_checker(app: Application) -> None:
    """Background task to periodically check for new vacancies."""
    bot = app.bot
    
    # Wait a bit for bot to fully start
    await asyncio.sleep(5)
    
    logger.info(f"Starting vacancy checker (interval: {CHECK_INTERVAL}s)")
    
    while True:
        try:
            await check_new_vacancies(bot)
        except Exception as e:
            logger.error(f"Error during vacancy check: {e}")
        
        await asyncio.sleep(CHECK_INTERVAL)


async def post_init(app: Application) -> None:
    """Called after application initialization."""
    # Initialize database
    init_db()
    logger.info("Database initialized")
    
    # Start the vacancy checker as a background task
    asyncio.create_task(vacancy_checker(app))


def main():
    """Main entry point."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        sys.exit(1)
    
    # Build application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status_command))
    
    logger.info("Bot starting...")
    
    # Run the bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
