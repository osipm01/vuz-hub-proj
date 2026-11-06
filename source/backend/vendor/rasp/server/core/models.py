from dataclasses import dataclass, field
from typing import Optional, Set

from core.constants import KIND_PRACTICE, PARITY_BOTH, PARITY_WEEKS


@dataclass
class Teacher:
    id: int
    name: str
    preferred_slots: dict = field(default_factory=dict)
    preferred_building: Optional[int] = None
    allowed_buildings: Set[int] = field(default_factory=lambda: {0, 1, 2, 3, 4})


@dataclass
class Group:
    id: int
    name: str
    size: int


@dataclass
class Room:
    id: int
    building: int
    capacity: int
    is_computer: bool = False      # компьютерный класс
    name: str = ""                 # название/номер аудитории (из реальных данных)
    building_name: str = ""        # название корпуса (из реальных данных)
    # Ансамбль — группа корпусов с «бесшовными» переходами: пары подряд
    # в корпусах одного ансамбля допустимы без окна. Идентификатор —
    # наименьший индекс корпуса ансамбля; по умолчанию корпус = свой ансамбль.
    ensemble: int = -1

    def __post_init__(self):
        if self.ensemble < 0:
            self.ensemble = self.building


@dataclass
class Lesson:
    id: int
    teacher_id: int
    group_id: int                  # основная (первая) группа пары
    length: int = 1
    needs_computer: bool = False   # пара возможна только в компьютерном классе
    parity: int = PARITY_BOTH      # 0 — каждую неделю, 1 — нечётные, 2 — чётные
    kind: str = KIND_PRACTICE      # лекция / практика / лабораторная
    extra_group_ids: tuple = ()    # остальные группы потоковой лекции

    @property
    def group_ids(self):
        """Все группы пары (у практики и лабораторной — одна)."""
        return (self.group_id,) + tuple(self.extra_group_ids)

    @property
    def weeks(self):
        """Индексы недель (0 — нечётная, 1 — чётная), когда идёт пара."""
        return PARITY_WEEKS[self.parity]
