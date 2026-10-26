import asyncio
import logging
from datetime import datetime

import telebot

from config import config
from exceptions import ApiConflictError, ApiError, ApiNotFoundError
from services import (
    user_service,
    debt_service,
    group_service,
    subject_service,
    schedule_service,
    dop_service,
    user_subject_service,
)

logging.basicConfig(level=logging.INFO)

bot = telebot.TeleBot(config.bot_token)


def run_async(coro):
    """Мост sync-хендлеров telebot в asyncio."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _args(message: telebot.types.Message) -> list[str]:
    return message.text.split()[1:]


def _reply_api_error(message: telebot.types.Message, e: ApiError) -> None:
    bot.reply_to(message, f"⚠️ Ошибка API: {e}")


WEEKDAYS = {
    1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 7: "Вс",
}


# ─────────────────────────── РЕГИСТРАЦИЯ (единственное изменение) ───────────────────────────

@bot.message_handler(commands=["register"])
def cmd_register(message: telebot.types.Message) -> None:
    """
    /register <email> <full_name> [group_id]
    Создаёт пользователя в системе.
    """
    parts = _args(message)
    if len(parts) < 2:
        bot.reply_to(
            message,
            "Использование: /register <email> <full_name> [group_id]\n"
            "Пример: /register ivan@mail.ru Иван_Иванов 3",
        )
        return

    email, full_name = parts[0], parts[1].replace("_", " ")
    payload = {"email": email, "full_name": full_name}
    if len(parts) >= 3 and parts[2].isdigit():
        payload["group_id"] = int(parts[2])

    try:
        user = run_async(user_service.create_user(payload))
    except ApiConflictError:
        bot.reply_to(message, f"Пользователь с email {email} уже существует")
        return
    except ApiError as e:
        _reply_api_error(message, e)
        return

    bot.reply_to(
        message,
        f"✅ Зарегистрирован: #{user['id']} {user.get('full_name', full_name)} ({email})",
    )


# ─────────────────────────── ПОЛЬЗОВАТЕЛИ ───────────────────────────

@bot.message_handler(commands=["user"])
def cmd_user(message: telebot.types.Message) -> None:
    parts = _args(message)
    if len(parts) != 1 or not parts[0].isdigit():
        bot.reply_to(message, "Использование: /user <user_id>")
        return

    user_id = int(parts[0])
    try:
        user = run_async(user_service.get_user(user_id))
    except ApiNotFoundError:
        bot.reply_to(message, f"Пользователь id={user_id} не найден")
        return
    except ApiError as e:
        _reply_api_error(message, e)
        return

    text = (
        f"👤 {user.get('full_name') or user.get('name') or user_id}\n"
        f"email: {user.get('email')}\n"
        f"группа: {user.get('group_id', '—')}"
    )
    bot.reply_to(message, text)


@bot.message_handler(commands=["user_email"])
def cmd_user_by_email(message: telebot.types.Message) -> None:
    parts = _args(message)
    if len(parts) != 1:
        bot.reply_to(message, "Использование: /user_email <email>")
        return

    try:
        user = run_async(user_service.get_user_by_email(parts[0]))
    except ApiNotFoundError:
        bot.reply_to(message, f"Пользователь с email {parts[0]} не найден")
        return
    except ApiError as e:
        _reply_api_error(message, e)
        return

    bot.reply_to(
        message,
        f"👤 #{user['id']} {user.get('full_name', '—')}\nemail: {user.get('email')}",
    )


@bot.message_handler(commands=["users"])
def cmd_users(message: telebot.types.Message) -> None:
    """ /users [group_id] """
    parts = _args(message)
    group_id = int(parts[0]) if parts and parts[0].isdigit() else None

    try:
        users = run_async(user_service.list_users(group_id=group_id))
    except ApiError as e:
        _reply_api_error(message, e)
        return

    if not users:
        bot.reply_to(message, "Пользователей не найдено")
        return

    lines = [
        f"#{u['id']} — {u.get('full_name', '—')} ({u.get('email', '—')})"
        for u in users
    ]
    bot.reply_to(message, "👥 Пользователи:\n" + "\n".join(lines))


# ─────────────────────────── ГРУППЫ ───────────────────────────

@bot.message_handler(commands=["groups"])
def cmd_groups(message: telebot.types.Message) -> None:
    try:
        groups = run_async(group_service.list_groups())
    except ApiError as e:
        _reply_api_error(message, e)
        return

    if not groups:
        bot.reply_to(message, "Групп нет")
        return

    lines = [f"#{g['id']} — {g.get('name', '—')}" for g in groups]
    bot.reply_to(message, "🏫 Группы:\n" + "\n".join(lines))


@bot.message_handler(commands=["group"])
def cmd_group(message: telebot.types.Message) -> None:
    """ /group <id|name> """
    parts = _args(message)
    if len(parts) != 1:
        bot.reply_to(message, "Использование: /group <id или название>")
        return

    try:
        if parts[0].isdigit():
            group = run_async(group_service.get_group(int(parts[0])))
        else:
            group = run_async(group_service.get_group_by_name(parts[0]))
    except ApiNotFoundError:
        bot.reply_to(message, "Группа не найдена")
        return
    except ApiError as e:
        _reply_api_error(message, e)
        return

    bot.reply_to(message, f"🏫 #{group['id']} — {group.get('name', '—')}")


# ─────────────────────────── ПРЕДМЕТЫ ───────────────────────────

@bot.message_handler(commands=["subjects"])
def cmd_subjects(message: telebot.types.Message) -> None:
    try:
        subjects = run_async(subject_service.list_subjects())
    except ApiError as e:
        _reply_api_error(message, e)
        return

    if not subjects:
        bot.reply_to(message, "Предметов нет")
        return

    lines = [f"#{s['id']} — {s.get('name', '—')}" for s in subjects]
    bot.reply_to(message, "📚 Предметы:\n" + "\n".join(lines))


@bot.message_handler(commands=["subject"])
def cmd_subject(message: telebot.types.Message) -> None:
    """ /subject <id|name> """
    parts = _args(message)
    if len(parts) != 1:
        bot.reply_to(message, "Использование: /subject <id или название>")
        return

    try:
        if parts[0].isdigit():
            subject = run_async(subject_service.get_subject(int(parts[0])))
        else:
            subject = run_async(subject_service.get_subject_by_name(parts[0]))
    except ApiNotFoundError:
        bot.reply_to(message, "Предмет не найден")
        return
    except ApiError as e:
        _reply_api_error(message, e)
        return

    bot.reply_to(message, f"📚 #{subject['id']} — {subject.get('name', '—')}")


@bot.message_handler(commands=["my_subjects"])
def cmd_my_subjects(message: telebot.types.Message) -> None:
    """ /my_subjects <user_id> — предметы, привязанные к пользователю """
    parts = _args(message)
    if len(parts) != 1 or not parts[0].isdigit():
        bot.reply_to(message, "Использование: /my_subjects <user_id>")
        return

    user_id = int(parts[0])
    try:
        links = run_async(user_subject_service.list_links(user_id=user_id))
    except ApiError as e:
        _reply_api_error(message, e)
        return

    if not links:
        bot.reply_to(message, "Предметы не привязаны")
        return

    lines = []
    for link in links:
        subject = link.get("subject") or {}
        name = subject.get("name") or f"subject_id={link.get('subject_id')}"
        lines.append(f"#{link.get('subject_id')} — {name}")

    bot.reply_to(message, f"📚 Предметы пользователя {user_id}:\n" + "\n".join(lines))


# ─────────────────────────── ДОЛГИ ───────────────────────────

@bot.message_handler(commands=["debts"])
def cmd_debts(message: telebot.types.Message) -> None:
    """ /debts <user_id> [all] — по умолчанию только нерешённые """
    parts = _args(message)
    if not parts or not parts[0].isdigit():
        bot.reply_to(message, "Использование: /debts <user_id> [all]")
        return

    user_id = int(parts[0])
    show_all = len(parts) > 1 and parts[1] == "all"
    is_resolved = None if show_all else False

    try:
        debts = run_async(debt_service.list_debts(user_id=user_id, is_resolved=is_resolved))
    except ApiError as e:
        _reply_api_error(message, e)
        return

    if not debts:
        bot.reply_to(message, "Долгов нет 🎉")
        return

    lines = []
    for d in debts:
        status = "✅" if d.get("is_resolved") else "❗"
        lines.append(f"{status} #{d['id']} — {d.get('description', 'без описания')}")

    title = "📋 Все долги:" if show_all else "📋 Активные долги:"
    bot.reply_to(message, title + "\n" + "\n".join(lines))


@bot.message_handler(commands=["debt"])
def cmd_debt(message: telebot.types.Message) -> None:
    """ /debt <debt_id> """
    parts = _args(message)
    if len(parts) != 1 or not parts[0].isdigit():
        bot.reply_to(message, "Использование: /debt <debt_id>")
        return

    try:
        debt = run_async(debt_service.get_debt(int(parts[0])))
    except ApiNotFoundError:
        bot.reply_to(message, "Долг не найден")
        return
    except ApiError as e:
        _reply_api_error(message, e)
        return

    status = "✅ решён" if debt.get("is_resolved") else "❗ активен"
    bot.reply_to(
        message,
        f"💰 Долг #{debt['id']} ({status})\n"
        f"Описание: {debt.get('description', '—')}\n"
        f"Пользователь: {debt.get('user_id', '—')}\n"
        f"Предмет: {debt.get('subject_id', '—')}",
    )


# ─────────────────────────── ДОПы ───────────────────────────

@bot.message_handler(commands=["dops"])
def cmd_dops(message: telebot.types.Message) -> None:
    """ /dops [user_id] """
    parts = _args(message)
    user_id = int(parts[0]) if parts and parts[0].isdigit() else None

    try:
        dops = run_async(dop_service.list_dops(user_id=user_id))
    except ApiError as e:
        _reply_api_error(message, e)
        return

    if not dops:
        bot.reply_to(message, "Допов нет")
        return

    lines = [f"#{d['id']} — {d.get('description', 'без описания')}" for d in dops]
    bot.reply_to(message, "📌 Допы:\n" + "\n".join(lines))


@bot.message_handler(commands=["dop"])
def cmd_dop(message: telebot.types.Message) -> None:
    """ /dop <dop_id> """
    parts = _args(message)
    if len(parts) != 1 or not parts[0].isdigit():
        bot.reply_to(message, "Использование: /dop <dop_id>")
        return

    try:
        dop = run_async(dop_service.get_dop(int(parts[0])))
    except ApiNotFoundError:
        bot.reply_to(message, "Доп не найден")
        return
    except ApiError as e:
        _reply_api_error(message, e)
        return

    bot.reply_to(
        message,
        f"📌 Доп #{dop['id']}\n"
        f"Описание: {dop.get('description', '—')}\n"
        f"Пользователь: {dop.get('user_id', '—')}",
    )


# ─────────────────────────── РАСПИСАНИЕ ───────────────────────────

@bot.message_handler(commands=["schedule"])
def cmd_schedule(message: telebot.types.Message) -> None:
    """
    /schedule [group_id] [weekday] [subject_id]
    Все аргументы опциональны. Без аргументов — первые 100 записей.
    """
    parts = _args(message)
    filters: dict = {}
    if len(parts) > 0 and parts[0].isdigit():
        filters["group_id"] = int(parts[0])
    if len(parts) > 1 and parts[1].isdigit():
        filters["weekday"] = int(parts[1])
    if len(parts) > 2 and parts[2].isdigit():
        filters["subject_id"] = int(parts[2])

    try:
        schedule = run_async(schedule_service.list_schedules(**filters))
    except ApiError as e:
        _reply_api_error(message, e)
        return

    if not schedule:
        bot.reply_to(message, "Расписание пустое")
        return

    lines = []
    for item in schedule:
        wd = WEEKDAYS.get(item.get("weekday"), item.get("weekday", "—"))
        subj = item.get("subject") or {}
        subj_name = subj.get("name") or item.get("subject_id", "—")
        group = item.get("group") or {}
        group_name = group.get("name") or item.get("group_id", "—")
        lines.append(
            f"{wd} #{item['id']} — {subj_name} "
            f"(группа {group_name}, {item.get('start_time', '??:??')}–{item.get('end_time', '??:??')})"
        )

    bot.reply_to(message, "🗓 Расписание:\n" + "\n".join(lines))


@bot.message_handler(commands=["schedule_id"])
def cmd_schedule_item(message: telebot.types.Message) -> None:
    """ /schedule_id <id> — конкретная запись расписания """
    parts = _args(message)
    if len(parts) != 1 or not parts[0].isdigit():
        bot.reply_to(message, "Использование: /schedule_id <id>")
        return

    try:
        item = run_async(schedule_service.get_schedule(int(parts[0])))
    except ApiNotFoundError:
        bot.reply_to(message, "Запись расписания не найдена")
        return
    except ApiError as e:
        _reply_api_error(message, e)
        return

    wd = WEEKDAYS.get(item.get("weekday"), item.get("weekday", "—"))
    bot.reply_to(
        message,
        f"🗓 Запись #{item['id']}\n"
        f"День: {wd}\n"
        f"Время: {item.get('start_time', '—')}–{item.get('end_time', '—')}\n"
        f"Группа: {item.get('group_id', '—')}\n"
        f"Предмет: {item.get('subject_id', '—')}",
    )

if __name__ == "__main__":
    logging.info("Bot started")
    bot.infinity_polling(skip_pending=True)
