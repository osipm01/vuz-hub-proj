import asyncio
import logging

import telebot

from config import config
from exceptions import ApiConflictError, ApiError, ApiNotFoundError
from services import user_service, debt_service

logging.basicConfig(level=logging.INFO)

bot = telebot.TeleBot(config.bot_token)


def run_async(coro):
    """Мост sync-хендлеров telebot в asyncio."""
    return asyncio.get_event_loop().run_until_complete(coro)


@bot.message_handler(commands=["user"])
def cmd_user(message: telebot.types.Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(message, "Использование: /user <user_id>")
        return

    user_id = int(parts[1])
    try:
        user = run_async(user_service.get_user(user_id))
    except ApiNotFoundError:
        bot.reply_to(message, f"Пользователь id={user_id} не найден")
        return
    except ApiError as e:
        bot.reply_to(message, f"Ошибка API: {e}")
        return

    text = f"👤 {user.get('full_name') or user.get('name') or user_id}\nemail: {user.get('email')}"
    bot.reply_to(message, text)


@bot.message_handler(commands=["debts"])
def cmd_debts(message: telebot.types.Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(message, "Использование: /debts <user_id>")
        return

    user_id = int(parts[1])
    try:
        debts = run_async(debt_service.list_debts(user_id=user_id, is_resolved=False))
    except ApiError as e:
        bot.reply_to(message, f"Ошибка API: {e}")
        return

    if not debts:
        bot.reply_to(message, "Долгов нет 🎉")
        return

    lines = [f"#{d['id']} — {d.get('description', 'без описания')}" for d in debts]
    bot.reply_to(message, "📋 Активные долги:\n" + "\n".join(lines))


@bot.message_handler(commands=["link"])
def cmd_link(message: telebot.types.Message) -> None:
    """ /link <user_id> <subject_id> """
    parts = message.text.split()
    if len(parts) != 3 or not (parts[1].isdigit() and parts[2].isdigit()):
        bot.reply_to(message, "Использование: /link <user_id> <subject_id>")
        return

    user_id, subject_id = int(parts[1]), int(parts[2])
    from services import user_subject_service

    try:
        run_async(user_subject_service.create_link(user_id, subject_id))
    except ApiConflictError:
        bot.reply_to(message, "Такая связь уже существует")
        return
    except ApiError as e:
        bot.reply_to(message, f"Ошибка API: {e}")
        return

    bot.reply_to(message, f"✅ Предмет {subject_id} привязан к пользователю {user_id}")