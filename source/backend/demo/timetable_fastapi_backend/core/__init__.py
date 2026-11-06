# ============================================================
# ПАКЕТ CORE — ИИ-СОСТАВИТЕЛЬ РАСПИСАНИЯ
# ============================================================
"""
Пакет с логикой генетического алгоритма составления расписания.

Модули:
    constants — константы (дни, слоты, веса штрафов, типы пар)
    models    — dataclass-модели (Teacher, Group, Room, Lesson)
    ai        — генерация данных, фитнес, операторы ГА, run_ga
    cli       — разбор аргументов, экспорт в Excel, точка входа
"""

__version__ = "1.0.0"

# ---- реэкспорт самого нужного (чтобы было `from core import run_ga`) ----
from core.models import Teacher, Group, Room, Lesson
from core.ai import (
    generate_data,
    evaluate,
    run_ga,
    lesson_size,
    slot_day,
    slot_time,
    bld_label,
    room_label,
)

__all__ = [
    "Teacher", "Group", "Room", "Lesson",
    "generate_data", "evaluate", "run_ga",
    "lesson_size", "slot_day", "slot_time",
    "bld_label", "room_label",
]
