"""
ИИ-составитель расписания.
Генетический алгоритм + repair-операторы + параллельные вычисления.

Учитывает:
  - конфликты преподавателей, групп, аудиторий
  - вместимость аудиторий
  - пары, которые возможны ТОЛЬКО в компьютерных классах
  - предпочтения преподавателей по времени и корпусу
  - запрет пар подряд в разных корпусах (для преподавателей и групп)
  - не более 1 смены корпуса в день (для групп)
  - чётные / нечётные недели: пара может идти каждую неделю, только по
    нечётным или только по чётным. Пары разных недель в одном слоте
    не конфликтуют (могут делить преподавателя, группу и аудиторию).
  - потоковые лекции: лекция может идти сразу у нескольких групп (одна
    пара, одна аудитория, вместимость — по сумме студентов); практика и
    лабораторная — только у одной группы. Пара занимает все свои группы.
Экспорт результата в Excel (.xlsx).

Параллельность: используется multiprocessing (процессы), а не потоки,
потому что из-за GIL потоки Python не ускоряют чисто вычислительный код.
Каждое поколение целиком (скрещивание + мутация + repair + оценка)
считается в пуле процессов.

Запуск:
    python main.py                       # большой тест (800 преподавателей)
    python main.py --teachers 100 --groups 60 --rooms 40 \
                   --generations 100 --workers 4 --out schedule.xlsx
"""
import argparse
import multiprocessing as mp
import os
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Optional, Set

# ============================================================
# КОНСТАНТЫ
# ============================================================
DAYS = 5
SLOTS_PER_DAY = 6
TOTAL_SLOTS = DAYS * SLOTS_PER_DAY  # 30

DAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт"]

# Чётность недели пары
PARITY_BOTH, PARITY_ODD, PARITY_EVEN = 0, 1, 2
PARITY_WEEKS = {PARITY_BOTH: (0, 1), PARITY_ODD: (0,), PARITY_EVEN: (1,)}
PARITY_LABEL = {PARITY_BOTH: "Каждая", PARITY_ODD: "Нечётная",
                PARITY_EVEN: "Чётная"}
PARITY_SHORT = {PARITY_BOTH: "", PARITY_ODD: "[нечёт] ", PARITY_EVEN: "[чёт] "}

# Тип занятия: лекция может быть у нескольких групп сразу (поток),
# практика и лабораторная — только у одной группы
KIND_LECTURE, KIND_PRACTICE, KIND_LAB = "lecture", "practice", "lab"
KIND_LABEL = {KIND_LECTURE: "Лекция", KIND_PRACTICE: "Практика",
              KIND_LAB: "Лабораторная"}
KIND_SHORT = {KIND_LECTURE: "лек.", KIND_PRACTICE: "пр.", KIND_LAB: "лаб."}

# Веса штрафов
W_CONFLICT_TEACHER = 1000
W_CONFLICT_GROUP = 1000
W_CONFLICT_ROOM = 1000
W_CAPACITY = 500
W_COMPUTER = 900            # пара требует компьютерный класс, а аудитория обычная
W_BUILDING_HARD = 800
W_DIFF_BUILDING_ADJ_T = 200
W_DIFF_BUILDING_ADJ_G = 200
W_GROUP_BUILDING_CHANGES = 400
W_PREF_TIME = 10
W_PREF_BUILDING = 15
W_GAP = 5                   # за каждый слот "окна" (любое окно)
W_GAP_BIG = 150             # за каждый лишний слот сверх допустимого окна в 1 слот
MAX_GAP = 1                 # допустимое окно между парами в день (в слотах)


# ============================================================
# МОДЕЛИ
# ============================================================
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


# ============================================================
# ГЕНЕРАЦИЯ ДАННЫХ
# ============================================================
def generate_data(n_teachers=50, n_groups=40, n_rooms=30,
                  computer_lesson_share=0.15, alt_week_share=0.25,
                  lecture_share=0.35, max_stream=4, seed=42):
    random.seed(seed)

    teachers = []
    for i in range(n_teachers):
        prefs = {random.randint(0, TOTAL_SLOTS - 1): random.randint(3, 5)
                 for _ in range(3)}
        pref_building = random.choice([None, 0, 1, 2, 3, 4])
        teachers.append(Teacher(
            id=i, name=f"T{i}",
            preferred_slots=prefs,
            preferred_building=pref_building,
        ))

    groups = [Group(id=i, name=f"G{i}", size=random.randint(10, 120))
              for i in range(n_groups)]

    # Каждая 5-я "пятёрка" аудиторий — компьютерные классы (~20%),
    # при этом в каждом корпусе есть хотя бы один (если аудиторий >= 25).
    rooms = [Room(id=i, building=i % 5,
                  capacity=random.choice([30, 60, 90, 150]),
                  is_computer=(i // 5) % 5 == 0)
             for i in range(n_rooms)]

    lessons = []
    lid = 0
    cap_limit = max(r.capacity for r in rooms)
    for t in teachers:
        for _ in range(random.randint(1, 3)):
            parity = PARITY_BOTH
            if random.random() < alt_week_share:
                parity = random.choice([PARITY_ODD, PARITY_EVEN])
            if random.random() < lecture_share:
                kind = KIND_LECTURE
                k = random.randint(1, min(max_stream, len(groups)))
                picked, total = [], 0
                for g in random.sample(groups, k):
                    # поток должен помещаться в самую большую аудиторию
                    if picked and total + g.size > cap_limit:
                        continue
                    picked.append(g)
                    total += g.size
            else:
                kind = random.choice([KIND_PRACTICE, KIND_LAB])
                picked = [random.choice(groups)]
            lessons.append(Lesson(
                id=lid, teacher_id=t.id, group_id=picked[0].id, length=1,
                needs_computer=random.random() < computer_lesson_share,
                parity=parity, kind=kind,
                extra_group_ids=tuple(g.id for g in picked[1:])))
            lid += 1

    return teachers, groups, rooms, lessons


# ============================================================
# ВСПОМОГАТЕЛЬНОЕ
# ============================================================
def slot_day(s):
    return s // SLOTS_PER_DAY


def slot_time(s):
    return s % SLOTS_PER_DAY


def lesson_size(lesson, groups):
    """Сколько студентов на паре: сумма размеров всех её групп."""
    return sum(groups[g].size for g in lesson.group_ids)


def bld_label(r):
    """Название корпуса для вывода."""
    return r.building_name or str(r.building)


def room_label(r):
    """Название аудитории для вывода."""
    return r.name or f"а.{r.id}"


# ============================================================
# КОНТЕКСТ ВОРКЕРОВ (данные передаются один раз при старте процесса)
# ============================================================
_CTX = {}


def _init_worker(lessons, teachers, groups, rooms, skip_eval=False):
    _CTX["skip_eval"] = skip_eval   # True: фитнес считает GPU в главном процессе
    _CTX["lessons"] = lessons
    _CTX["teachers"] = teachers
    _CTX["groups"] = groups
    _CTX["rooms"] = rooms
    _CTX["comp_rooms"] = [r.id for r in rooms if r.is_computer]
    _CTX["reg_rooms"] = [r.id for r in rooms if not r.is_computer]
    # (building) -> список аудиторий корпуса
    by_b = {}
    for r in rooms:
        by_b.setdefault(r.building, []).append(r)
    _CTX["by_building"] = by_b
    # для каждой пары (по индексу) — список подходящих аудиторий
    _CTX["sizes"] = [lesson_size(l, groups) for l in lessons]
    _CTX["suitable"] = [_suitable_rooms(l, _CTX["sizes"][i], rooms)
                        for i, l in enumerate(lessons)]


def _suitable_rooms(lesson, size, rooms):
    """
    Аудитории, подходящие паре: нужный тип (комп. класс / обычная) и
    достаточная вместимость. Если таких нет — постепенно ослабляем условия.
    """
    need_pc = lesson.needs_computer
    base = [r.id for r in rooms
            if r.capacity >= size and r.is_computer == need_pc]
    if not base and not need_pc:
        base = [r.id for r in rooms if r.capacity >= size]
    if not base:
        base = [r.id for r in rooms if r.is_computer == need_pc]
    if not base:
        base = [r.id for r in rooms]
    return base


# ============================================================
# ФИТНЕС-ФУНКЦИЯ
# ============================================================
def evaluate(individual, lessons, teachers, groups, rooms):
    score = 0
    stats = {
        "conflicts": 0,
        "capacity": 0,
        "computer": 0,
        "pref": 0,
        "teacher_gaps": 0,      # окон больше MAX_GAP у преподавателей
        "group_gaps": 0,        # окон больше MAX_GAP у групп
        "teacher_adj": 0,
        "teacher_extra_changes": 0,
        "group_adj": 0,
        "group_extra_changes": 0,
    }

    teacher_busy = {}
    group_busy = {}
    room_busy = {}

    teacher_day = {}
    group_day = {}

    for lesson, (slot, room_id) in zip(lessons, individual):
        room = rooms[room_id]
        teacher = teachers[lesson.teacher_id]
        size = lesson_size(lesson, groups)
        d = slot_day(slot)
        t = slot_time(slot)

        # --- 1. Конфликты ---
        # конфликт возможен только в одну и ту же неделю
        for w in lesson.weeks:
            for s in range(slot, slot + lesson.length):
                if (lesson.teacher_id, w, s) in teacher_busy:
                    score -= W_CONFLICT_TEACHER
                    stats["conflicts"] += 1
                for gid in lesson.group_ids:
                    if (gid, w, s) in group_busy:
                        score -= W_CONFLICT_GROUP
                        stats["conflicts"] += 1
                if (room_id, w, s) in room_busy:
                    score -= W_CONFLICT_ROOM
                    stats["conflicts"] += 1

                teacher_busy[(lesson.teacher_id, w, s)] = lesson.id
                for gid in lesson.group_ids:
                    group_busy[(gid, w, s)] = lesson.id
                room_busy[(room_id, w, s)] = lesson.id

        # --- 2. Вместимость ---
        if room.capacity < size:
            score -= W_CAPACITY
            stats["capacity"] += 1

        # --- 2.1 Компьютерный класс ---
        if lesson.needs_computer and not room.is_computer:
            score -= W_COMPUTER
            stats["computer"] += 1

        # --- 3. Разрешённый корпус преподавателя ---
        if room.building not in teacher.allowed_buildings:
            score -= W_BUILDING_HARD

        # --- 4. Предпочтения ---
        if slot in teacher.preferred_slots:
            score += W_PREF_TIME * teacher.preferred_slots[slot]
            stats["pref"] += 1
        if teacher.preferred_building is not None \
                and room.building == teacher.preferred_building:
            score += W_PREF_BUILDING
            stats["pref"] += 1

        # --- 5. Сбор данных по корпусам ---
        # окна и смены корпусов считаются отдельно для каждой недели
        for w in lesson.weeks:
            teacher_day.setdefault(lesson.teacher_id, {}) \
                .setdefault((w, d), []).append((t, room.building, lesson.length))
            for gid in lesson.group_ids:
                group_day.setdefault(gid, {}) \
                    .setdefault((w, d), []).append(
                        (t, room.building, lesson.length))

    # --- 6. Преподаватели: подряд в разных корпусах + окна ---
    for tid, days in teacher_day.items():
        for d, entries in days.items():
            entries.sort()
            for i in range(len(entries) - 1):
                t1, b1, l1 = entries[i]
                t2, b2, _ = entries[i + 1]
                if b1 != b2 and (t2 - (t1 + l1)) == 0:
                    score -= W_DIFF_BUILDING_ADJ_T
                    stats["teacher_adj"] += 1
                gap = t2 - (t1 + l1)
                if gap > 0:
                    score -= W_GAP * gap
                    if gap > MAX_GAP:
                        score -= W_GAP_BIG * (gap - MAX_GAP)
                        stats["teacher_gaps"] += 1

    # --- 7. Группы: подряд в разных корпусах + смены корпуса за день ---
    for gid, days in group_day.items():
        for d, entries in days.items():
            entries.sort()

            for i in range(len(entries) - 1):
                t1, b1, l1 = entries[i]
                t2, b2, _ = entries[i + 1]
                if b1 != b2 and (t2 - (t1 + l1)) == 0:
                    score -= W_DIFF_BUILDING_ADJ_G
                    stats["group_adj"] += 1
                gap = t2 - (t1 + l1)
                if gap > 0:
                    score -= W_GAP * gap
                    if gap > MAX_GAP:
                        score -= W_GAP_BIG * (gap - MAX_GAP)
                        stats["group_gaps"] += 1

            seen = []
            for _, b, _ in entries:
                if not seen or seen[-1] != b:
                    seen.append(b)
            changes = max(0, len(seen) - 1)
            if changes > 1:
                score -= W_GROUP_BUILDING_CHANGES * (changes - 1)
                stats["group_extra_changes"] += changes - 1

    return score, stats


# ============================================================
# REPAIR-ОПЕРАТОР ДЛЯ ГРУПП
# ============================================================
def _candidates(building, lesson, size, by_building):
    """Аудитории корпуса, подходящие паре по размеру и типу (комп. класс)."""
    rs = by_building.get(building, [])
    fit = [r.id for r in rs
           if r.capacity >= size and r.is_computer == lesson.needs_computer]
    if not fit and not lesson.needs_computer:
        # обычной паре допустим и компьютерный класс, если больше нечего
        fit = [r.id for r in rs if r.capacity >= size]
    return fit


def repair_group_buildings(individual, lessons, groups, rooms, by_building=None):
    """
    Гарантирует (насколько возможно): у группы не более 1 смены корпуса в день.
    Пары дня переводятся в "главный" корпус (где их больше всего), при этом
    для каждой пары подбирается аудитория нужного типа (компьютерный класс
    остаётся компьютерным классом) и достаточной вместимости.
    """
    if by_building is None:
        by_building = _CTX["by_building"]
    ind = list(individual)
    sizes = _CTX.get("sizes") or [lesson_size(l, groups) for l in lessons]

    # занятость аудиторий — чтобы перенос в другой корпус не создавал конфликтов
    r_busy = set()
    for i, (slot, rid) in enumerate(ind):
        for w in lessons[i].weeks:
            for s in range(slot, slot + lessons[i].length):
                r_busy.add((rid, w, s))

    # ключ — (неделя, день): у группы смены корпуса считаются по неделям
    group_day_idx = {}
    for idx, lesson in enumerate(lessons):
        slot, _ = ind[idx]
        d = slot_day(slot)
        for w in lesson.weeks:
            for gid in lesson.group_ids:
                group_day_idx.setdefault(gid, {}) \
                    .setdefault((w, d), []).append(idx)

    for gid, days in group_day_idx.items():
        for d, idxs in days.items():
            building_count = {}
            for i in idxs:
                b = rooms[ind[i][1]].building
                building_count[b] = building_count.get(b, 0) + 1

            if len(building_count) <= 1:
                continue

            # корпуса по убыванию частоты
            order = sorted(building_count.items(), key=lambda kv: -kv[1])
            main_building = None
            for b, _ in order:
                # корпус годится, если для ВСЕХ пар дня там есть аудитория
                if all(_candidates(b, lessons[i], sizes[i], by_building)
                       for i in idxs):
                    main_building = b
                    break
            if main_building is None:
                continue

            for i in idxs:
                slot, room_id = ind[i]
                if rooms[room_id].building != main_building:
                    cand = _candidates(main_building, lessons[i], sizes[i],
                                       by_building)
                    span = range(slot, slot + lessons[i].length)
                    wk = lessons[i].weeks
                    free = [c for c in cand
                            if all((c, w, s) not in r_busy
                                   for w in wk for s in span)]
                    new_room = random.choice(free or cand)
                    for w in wk:
                        for s in span:
                            r_busy.discard((room_id, w, s))
                            r_busy.add((new_room, w, s))
                    ind[i] = (slot, new_room)

    return ind


def repair_conflicts(individual, lessons, teachers, groups, rooms):
    """
    Жадно устраняет конфликты преподавателей, групп и аудиторий.
    Пары обрабатываются в случайном порядке; если текущее место пары занято,
    она переносится в свободный слот и свободную подходящую аудиторию
    (по типу и вместимости). Среди аудиторий предпочитается корпус, где у
    группы уже есть пары в этот день, затем предпочитаемый корпус преподавателя.
    Если свободного места нет — пара остаётся как есть (штраф посчитает fitness).
    """
    suitable = _CTX["suitable"]
    ind = list(individual)
    t_busy, g_busy, r_busy = set(), set(), set()
    # все ключи включают неделю w (0 — нечётная, 1 — чётная)
    group_buildings = {}   # (group_id, w, day) -> {корпуса уже стоящих пар}
    t_times, g_times = {}, {}   # (id, w, day) -> {номера пар уже стоящих занятий}

    def gap_cost(i, slot):
        """Насколько слот создаёт окна у преподавателя и группы в этот день."""
        L = lessons[i]
        d, t = slot_day(slot), slot_time(slot)
        cost = 0
        for w in L.weeks:
            for times in [t_times.get((L.teacher_id, w, d))] + \
                    [g_times.get((g, w, d)) for g in L.group_ids]:
                if not times:
                    continue
                dist = min(abs(t - x) for x in times)
                if dist > 1:
                    cost += (dist - 1) + 10 * max(0, dist - 1 - MAX_GAP)
        return cost

    def tg_free(i, slot):
        L = lessons[i]
        if slot_time(slot) + L.length > SLOTS_PER_DAY:
            return False
        for w in L.weeks:
            for s in range(slot, slot + L.length):
                if (L.teacher_id, w, s) in t_busy \
                        or any((g, w, s) in g_busy for g in L.group_ids):
                    return False
        return True

    def free_rooms(i, slot):
        L = lessons[i]
        span = range(slot, slot + L.length)
        return [r for r in suitable[i]
                if all((r, w, s) not in r_busy
                       for w in L.weeks for s in span)]

    def choose(i, slot, cand):
        L = lessons[i]
        gb = set()
        for w in L.weeks:
            for g in L.group_ids:
                gb |= group_buildings.get((g, w, slot_day(slot)), set())
        if gb:
            pref = [r for r in cand if rooms[r].building in gb]
            if pref:
                return random.choice(pref)
        pb = teachers[L.teacher_id].preferred_building
        if pb is not None:
            pref = [r for r in cand if rooms[r].building == pb]
            if pref:
                return random.choice(pref)
        return random.choice(cand)

    def place(i, slot, rid):
        L = lessons[i]
        for w in L.weeks:
            for s in range(slot, slot + L.length):
                t_busy.add((L.teacher_id, w, s))
                r_busy.add((rid, w, s))
                t_times.setdefault((L.teacher_id, w, slot_day(s)), set()) \
                    .add(slot_time(s))
                for g in L.group_ids:
                    g_busy.add((g, w, s))
                    g_times.setdefault((g, w, slot_day(s)), set()) \
                        .add(slot_time(s))
            for g in L.group_ids:
                group_buildings.setdefault((g, w, slot_day(slot)), set()) \
                    .add(rooms[rid].building)
        ind[i] = (slot, rid)

    order = list(range(len(ind)))
    random.shuffle(order)
    for i in order:
        slot, rid = ind[i]
        L = lessons[i]
        span = range(slot, slot + L.length)

        # 1. текущее место свободно
        if tg_free(i, slot) and all((rid, w, s) not in r_busy
                                    for w in L.weeks for s in span):
            place(i, slot, rid)
            continue

        # 2. тот же слот, другая аудитория
        if tg_free(i, slot):
            cand = free_rooms(i, slot)
            if cand:
                place(i, slot, choose(i, slot, cand))
                continue

        # 3. другой слот
        slots = list(range(TOTAL_SLOTS))
        random.shuffle(slots)
        slots.sort(key=lambda s_: gap_cost(i, s_))   # сначала слоты без окон
        for s_new in slots:
            if tg_free(i, s_new):
                cand = free_rooms(i, s_new)
                if cand:
                    place(i, s_new, choose(i, s_new, cand))
                    break
        else:
            # 4. места нет — оставляем как есть (конфликт останется)
            place(i, slot, rid)

    # --- второй проход: уплотнение (убираем окна > MAX_GAP) ---
    random.shuffle(order)
    for i in order:
        L = lessons[i]
        if L.length != 1:
            continue
        slot, rid = ind[i]
        d, t = slot_day(slot), slot_time(slot)
        # временно снимаем пару с места (во всех её неделях)
        for w in L.weeks:
            t_times[(L.teacher_id, w, d)].discard(t)
            t_busy.discard((L.teacher_id, w, slot))
            for g in L.group_ids:
                g_times[(g, w, d)].discard(t)
                g_busy.discard((g, w, slot))
            r_busy.discard((rid, w, slot))

        cur = gap_cost(i, slot)
        new_slot, new_rid = slot, rid
        if cur > 0:
            cand_slots = list(range(TOTAL_SLOTS))
            random.shuffle(cand_slots)
            cand_slots.sort(key=lambda s_: gap_cost(i, s_))
            for s_new in cand_slots:
                if s_new == slot or gap_cost(i, s_new) >= cur:
                    continue
                if tg_free(i, s_new):
                    cand = free_rooms(i, s_new)
                    if cand:
                        new_slot, new_rid = s_new, choose(i, s_new, cand)
                        break
        place(i, new_slot, new_rid)

    return ind


# ============================================================
# ГЕНЕТИЧЕСКИЕ ОПЕРАТОРЫ
# ============================================================
def _pick_room(i, rooms=None):
    """Случайная аудитория, подходящая паре с индексом i (тип + вместимость)."""
    return random.choice(_CTX["suitable"][i])


def random_individual(lessons, rooms):
    return [(random.randint(0, TOTAL_SLOTS - 1), _pick_room(i))
            for i in range(len(lessons))]


def tournament_idx(fits, k=5):
    best_idx = random.randint(0, len(fits) - 1)
    for _ in range(k - 1):
        i = random.randint(0, len(fits) - 1)
        if fits[i] > fits[best_idx]:
            best_idx = i
    return best_idx


def crossover(p1, p2):
    n = len(p1)
    if n < 2:
        return p1[:], p2[:]
    point = random.randint(1, n - 1)
    return p1[:point] + p2[point:], p2[:point] + p1[point:]


def mutate(ind, lessons, rooms, rate=0.05):
    ind = list(ind)
    for i in range(len(ind)):
        if random.random() < rate:
            slot, room = ind[i]
            if random.random() < 0.6:
                slot = random.randint(0, TOTAL_SLOTS - 1)
            else:
                room = _pick_room(i)
            ind[i] = (slot, room)
    return ind


# ============================================================
# ПАКЕТНАЯ ОЦЕНКА ФИТНЕСА НА GPU (CuPy) / numpy
# ============================================================
class BatchEvaluator:
    """
    Считает фитнес сразу для всей популяции на массивах.
    Код один и тот же для xp=cupy (CUDA) и xp=numpy (проверка/CPU);
    результат совпадает с evaluate() (проверено тестом).
    Ограничение: все пары длиной 1 слот.
    На GPU уходит только оценка; repair-операторы остаются на CPU
    (они ветвистые и плохо ложатся на GPU).
    """

    def __init__(self, xp, lessons, teachers, groups, rooms):
        import numpy as np
        self.xp = xp
        self.np = np
        self.N, self.G = len(lessons), len(groups)
        self.B = max(5, max(r.building for r in rooms) + 1)
        T = len(teachers)

        def A(x, dtype=None):
            return xp.asarray(np.asarray(x, dtype=dtype))

        self.tid = A([l.teacher_id for l in lessons], np.int64)
        # принадлежность «пара — группа» (у потоковой лекции несколько строк)
        mem = [(i, g) for i, l in enumerate(lessons) for g in l.group_ids]
        self.M = len(mem)
        self.mem_l = A([m[0] for m in mem], np.int64)
        self.mem_g = A([m[1] for m in mem], np.int64)
        self.needs_pc = A([l.needs_computer for l in lessons], bool)
        self.gsize = A([lesson_size(l, groups) for l in lessons], np.int64)
        self.room_cap = A([r.capacity for r in rooms], np.int64)
        self.room_pc = A([r.is_computer for r in rooms], bool)
        self.room_bld = A([r.building for r in rooms], np.int64)
        # in_week[w, i] — идёт ли пара i в неделю w (0 — нечётная, 1 — чётная)
        self.in_week = A([[w in l.weeks for l in lessons] for w in (0, 1)],
                         bool)
        self.ent_big = max(T, len(groups)) + 1   # для «выключенных» пар

        pref_w = np.zeros((T, TOTAL_SLOTS), dtype=np.int64)
        allowed = np.zeros((T, self.B), dtype=bool)
        pref_b = np.full(T, -1, dtype=np.int64)
        for t in teachers:
            for s, w in t.preferred_slots.items():
                pref_w[t.id, s] = w
            for b in t.allowed_buildings:
                if b < self.B:
                    allowed[t.id, b] = True
            if t.preferred_building is not None:
                pref_b[t.id] = t.preferred_building
        self.pref_w, self.allowed = A(pref_w), A(allowed)
        self.pref_b = A(pref_b)

    def _dups(self, key):
        xp = self.xp
        s = xp.sort(key, axis=1)
        return (s[:, 1:] == s[:, :-1]).sum(axis=1)

    def fitness(self, pop):
        xp, np = self.xp, self.np
        arr = np.asarray(pop, dtype=np.int64)          # [P, N, 2]
        slot = xp.asarray(arr[:, :, 0])
        room = xp.asarray(arr[:, :, 1])
        P, B, G = slot.shape[0], self.B, self.G
        tid = self.tid[None, :]
        score = xp.zeros(P, dtype=xp.int64)
        idx = xp.arange(self.N, dtype=xp.int64)[None, :]
        idxm = xp.arange(self.M, dtype=xp.int64)[None, :]
        BIG = 1 << 40

        # 1. конфликты — отдельно для каждой недели; пары, не идущие в эту
        # неделю, получают уникальные «заглушки» и ни с кем не конфликтуют
        for w in (0, 1):
            m = self.in_week[w][None, :]

            def uq(key):
                return xp.where(m, key, BIG + idx)

            score -= W_CONFLICT_TEACHER * self._dups(
                uq(tid * TOTAL_SLOTS + slot))
            mg = self.in_week[w][self.mem_l][None, :]
            score -= W_CONFLICT_GROUP * self._dups(xp.where(
                mg, self.mem_g[None, :] * TOTAL_SLOTS + slot[:, self.mem_l],
                BIG + idxm))
            score -= W_CONFLICT_ROOM * self._dups(
                uq(room * TOTAL_SLOTS + slot))

        # 2. вместимость, компьютерные классы, разрешённые корпуса
        bld = self.room_bld[room]
        score -= W_CAPACITY * (self.room_cap[room] < self.gsize[None, :]).sum(1)
        score -= W_COMPUTER * (self.needs_pc[None, :]
                               & ~self.room_pc[room]).sum(1)
        score -= W_BUILDING_HARD * (~self.allowed[tid, bld]).sum(1)

        # 3. предпочтения
        score += W_PREF_TIME * self.pref_w[tid, slot].sum(1)
        pb = self.pref_b[self.tid][None, :]
        score += W_PREF_BUILDING * ((pb >= 0) & (pb == bld)).sum(1)

        # 4. последовательности пар у преподавателей и групп
        # (по неделям: пары другой недели заменяются уникальными сущностями)
        for w in (0, 1):
            for ent, lidx, is_group in ((self.tid, None, False),
                                        (self.mem_g, self.mem_l, True)):
                if lidx is None:
                    m = self.in_week[w][None, :]
                    slot_e, bld_e = slot, bld
                else:     # потоковая лекция входит в расписание каждой группы
                    m = self.in_week[w][lidx][None, :]
                    slot_e, bld_e = slot[:, lidx], bld[:, lidx]
                idx_e = xp.arange(slot_e.shape[1], dtype=xp.int64)[None, :]
                ent_w = xp.where(m, ent[None, :], self.ent_big + idx_e)
                key = (ent_w * TOTAL_SLOTS + slot_e) * B + bld_e
                k = xp.sort(key, axis=1)
                b = k % B
                es = k // B
                sl = es % TOTAL_SLOTS
                e = es // TOTAL_SLOTS
                day = sl // SLOTS_PER_DAY
                tm = sl % SLOTS_PER_DAY
                same = (e[:, 1:] == e[:, :-1]) & (day[:, 1:] == day[:, :-1])
                gap = tm[:, 1:] - (tm[:, :-1] + 1)
                diff_b = b[:, 1:] != b[:, :-1]

                adj = (same & diff_b & (gap == 0)).sum(1)
                gaps = xp.where(same & (gap > 0), gap, 0).sum(1)
                big = xp.where(same & (gap > MAX_GAP),
                               gap - MAX_GAP, 0).sum(1)
                w_adj = (W_DIFF_BUILDING_ADJ_G if is_group
                         else W_DIFF_BUILDING_ADJ_T)
                score -= w_adj * adj + W_GAP * gaps + W_GAP_BIG * big

                if is_group:
                    change = same & diff_b
                    seg = e[:, 1:] * DAYS + day[:, 1:]
                    base = xp.arange(P, dtype=xp.int64)[:, None] * (G * DAYS)
                    flat = (base + seg)[change]
                    cnt = xp.bincount(flat, minlength=P * G * DAYS) \
                        .reshape(P, G * DAYS)
                    extra = xp.clip(cnt - 1, 0, None).sum(1)
                    score -= W_GROUP_BUILDING_CHANGES * extra

        out = score.get() if hasattr(score, "get") else score
        return [int(x) for x in out]


def make_evaluator(device, lessons, teachers, groups, rooms):
    """
    device: "cpu" -> None (оценка в процессах),
            "cuda" -> CuPy на GPU (если нет GPU/CuPy — предупреждение и CPU),
            "numpy" -> тот же векторизованный код на CPU (для проверки).
    """
    if device == "cpu":
        return None
    if any(l.length != 1 for l in lessons):
        print("  [!] GPU-оценка поддерживает только пары в 1 слот — "
              "использую CPU.")
        return None
    if device == "numpy":
        import numpy as np
        return BatchEvaluator(np, lessons, teachers, groups, rooms)
    try:
        import cupy as cp
        if cp.cuda.runtime.getDeviceCount() < 1:
            raise RuntimeError("CUDA-устройство не найдено")
        ev = BatchEvaluator(cp, lessons, teachers, groups, rooms)
        print(f"  GPU: {cp.cuda.runtime.getDeviceProperties(0)['name'].decode()}")
        return ev
    except Exception as exc:       # нет cupy / драйвера / GPU
        print(f"  [!] CUDA недоступна ({exc}). Продолжаю на CPU.\n"
              "      Установка: pip install cupy-cuda12x (под вашу версию CUDA).")
        return None


# ============================================================
# ЗАДАЧИ ДЛЯ ПУЛА ПРОЦЕССОВ
# ============================================================
def _eval_ctx(ind):
    if _CTX.get("skip_eval"):
        return None
    return evaluate(ind, _CTX["lessons"], _CTX["teachers"],
                    _CTX["groups"], _CTX["rooms"])[0]


def _repair_all(ind):
    """Сначала убираем конфликты, затем выравниваем корпуса у групп."""
    ind = repair_conflicts(ind, _CTX["lessons"], _CTX["teachers"],
                           _CTX["groups"], _CTX["rooms"])
    return repair_group_buildings(ind, _CTX["lessons"], _CTX["groups"],
                                  _CTX["rooms"])


def _task_init(seed):
    """Создать, починить и оценить одну особь стартовой популяции."""
    random.seed(seed)
    ind = random_individual(_CTX["lessons"], _CTX["rooms"])
    ind = _repair_all(ind)
    return ind, _eval_ctx(ind)


def _task_breed(args):
    """Скрещивание пары родителей -> 2 потомка (мутация, repair, оценка)."""
    p1, p2, seed, rate = args
    random.seed(seed)
    out = []
    for child in crossover(p1, p2):
        child = mutate(child, _CTX["lessons"], _CTX["rooms"], rate)
        child = _repair_all(child)
        out.append((child, _eval_ctx(child)))
    return out


# ============================================================
# ГЕНЕТИЧЕСКИЙ АЛГОРИТМ (параллельный)
# ============================================================
def run_ga(lessons, teachers, groups, rooms,
           pop_size=60, generations=300, elite=4,
           mutation_rate=0.05, workers=None, seed=1, verbose=True,
           device="cpu"):
    workers = workers or os.cpu_count() or 1
    rng = random.Random(seed)

    # оценка фитнеса на GPU (или её векторизованная копия на numpy для проверки)
    evaluator = make_evaluator(device, lessons, teachers, groups, rooms)
    skip_eval = evaluator is not None

    if workers > 1:
        pool = mp.Pool(workers, initializer=_init_worker,
                       initargs=(lessons, teachers, groups, rooms, skip_eval))
        pmap = lambda f, xs, cs: pool.map(f, xs, chunksize=cs)
    else:
        _init_worker(lessons, teachers, groups, rooms, skip_eval)
        pool = None
        pmap = lambda f, xs, cs: list(map(f, xs))

    def chunk(n):
        return max(1, n // (workers * 4))

    try:
        init = pmap(_task_init,
                    [rng.randrange(1 << 30) for _ in range(pop_size)],
                    chunk(pop_size))
        pop = [x[0] for x in init]
        fits = evaluator.fitness(pop) if evaluator else [x[1] for x in init]

        best, best_fit = None, float("-inf")

        for gen in range(generations):
            gi = max(range(len(pop)), key=lambda i: fits[i])
            if fits[gi] > best_fit:
                best_fit = fits[gi]
                best = list(pop[gi])

            if verbose and gen % 20 == 0:
                st = evaluate(best, lessons, teachers, groups, rooms)[1]
                print(f"[gen {gen:3d}] best={best_fit:9.1f} | "
                      f"conf={st['conflicts']} cap={st['capacity']} "
                      f"PC={st['computer']} T_gap={st['teacher_gaps']} "
                      f"G_gap={st['group_gaps']} T_adj={st['teacher_adj']} "
                      f"G_adj={st['group_adj']} "
                      f"G_chg={st['group_extra_changes']}", flush=True)

            # элитизм
            order = sorted(range(len(pop)), key=lambda i: -fits[i])
            new_pop = [list(pop[i]) for i in order[:elite]]
            new_fits = [fits[i] for i in order[:elite]]

            # родители выбираются в главном процессе, дети считаются в пуле
            n_pairs = (pop_size - elite + 1) // 2
            tasks = []
            for _ in range(n_pairs):
                p1 = pop[tournament_idx(fits)]
                p2 = pop[tournament_idx(fits)]
                tasks.append((p1, p2, rng.randrange(1 << 30), mutation_rate))

            n_elite = len(new_pop)
            for pair in pmap(_task_breed, tasks, chunk(n_pairs)):
                for child, f in pair:
                    if len(new_pop) < pop_size:
                        new_pop.append(child)
                        new_fits.append(f)
            if evaluator:   # потомков оцениваем одной пачкой на GPU
                new_fits[n_elite:] = evaluator.fitness(new_pop[n_elite:])

            pop, fits = new_pop, new_fits

        # последнее поколение тоже учитываем
        gi = max(range(len(pop)), key=lambda i: fits[i])
        if fits[gi] > best_fit:
            best_fit = fits[gi]
            best = list(pop[gi])
    finally:
        if pool is not None:
            pool.close()
            pool.join()

    return best, best_fit


# ============================================================
# ЭКСПОРТ В EXCEL
# ============================================================
def export_excel(path, individual, lessons, teachers, groups, rooms,
                 score, stats, params=None, elapsed=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    HEAD_FILL = PatternFill("solid", fgColor="305496")
    HEAD_FONT = Font(bold=True, color="FFFFFF")
    RED = PatternFill("solid", fgColor="F8CBAD")
    BLUE = PatternFill("solid", fgColor="DDEBF7")
    YELLOW = PatternFill("solid", fgColor="FFF2CC")
    WRAP = Alignment(wrap_text=True, vertical="top")

    def style_header(ws, row=1):
        for c in ws[row]:
            c.fill, c.font = HEAD_FILL, HEAD_FONT
            c.alignment = Alignment(horizontal="center", vertical="center",
                                    wrap_text=True)

    slot_labels = [f"{DAY_NAMES[s // SLOTS_PER_DAY]} {s % SLOTS_PER_DAY + 1}"
                   for s in range(TOTAL_SLOTS)]

    # ---- занятость для поиска конфликтов ----
    t_busy, g_busy, r_busy = {}, {}, {}
    for lesson, (slot, rid) in zip(lessons, individual):
        for w in lesson.weeks:
            for s in range(slot, min(slot + lesson.length, TOTAL_SLOTS)):
                t_busy.setdefault((lesson.teacher_id, w, s), []).append(lesson.id)
                for gid in lesson.group_ids:
                    g_busy.setdefault((gid, w, s), []).append(lesson.id)
                r_busy.setdefault((rid, w, s), []).append(lesson.id)

    def problems_of(lesson, slot, rid):
        room = rooms[rid]
        size = lesson_size(lesson, groups)
        p = []
        for w in lesson.weeks:
            for s in range(slot, min(slot + lesson.length, TOTAL_SLOTS)):
                if len(t_busy[(lesson.teacher_id, w, s)]) > 1:
                    p.append("Конфликт преподавателя")
                if any(len(g_busy[(g, w, s)]) > 1 for g in lesson.group_ids):
                    p.append("Конфликт группы")
                if len(r_busy[(rid, w, s)]) > 1:
                    p.append("Конфликт аудитории")
        if room.capacity < size:
            p.append("Мала аудитория")
        if lesson.needs_computer and not room.is_computer:
            p.append("Нужен компьютерный класс")
        return sorted(set(p))

    wb = Workbook()

    # ---- Лист 1: сводка ----
    ws = wb.active
    ws.title = "Сводка"
    n = len(lessons)
    rows = [
        ("Параметр", "Значение"),
        ("Пар всего", n),
        ("Из них только в компьютерных классах",
         sum(1 for l in lessons if l.needs_computer)),
        ("Пар каждую неделю",
         sum(1 for l in lessons if l.parity == PARITY_BOTH)),
        ("Пар только по нечётным неделям",
         sum(1 for l in lessons if l.parity == PARITY_ODD)),
        ("Пар только по чётным неделям",
         sum(1 for l in lessons if l.parity == PARITY_EVEN)),
        ("Лекций", sum(1 for l in lessons if l.kind == KIND_LECTURE)),
        ("Из них потоковых (несколько групп)",
         sum(1 for l in lessons if len(l.group_ids) > 1)),
        ("Практик", sum(1 for l in lessons if l.kind == KIND_PRACTICE)),
        ("Лабораторных", sum(1 for l in lessons if l.kind == KIND_LAB)),
        ("Преподавателей", len(teachers)),
        ("Групп", len(groups)),
        ("Аудиторий", len(rooms)),
        ("Из них компьютерных классов", sum(1 for r in rooms if r.is_computer)),
        ("Фитнес", round(score, 1)),
        ("Конфликтов", stats["conflicts"]),
        ("Нарушений вместимости", stats["capacity"]),
        ("Пары не в компьютерном классе", stats["computer"]),
        ("Препод.: окна больше 1 слота", stats["teacher_gaps"]),
        ("Группа: окна больше 1 слота", stats["group_gaps"]),
        ("Препод.: разные корпуса подряд", stats["teacher_adj"]),
        ("Группа: разные корпуса подряд", stats["group_adj"]),
        ("Группа: лишних смен корпуса за день", stats["group_extra_changes"]),
        ("Попаданий в предпочтения", stats["pref"]),
    ]
    if elapsed is not None:
        rows.append(("Время расчёта, сек", round(elapsed, 1)))
    for k, v in (params or {}).items():
        rows.append((k, v))
    for r in rows:
        ws.append(r)
    style_header(ws)
    ws.column_dimensions["A"].width = 48
    ws.column_dimensions["B"].width = 18

    # ---- Лист: сводка по корпусам ----
    ws = wb.create_sheet("По корпусам")
    b_ids = sorted({r.building for r in rooms})
    b_name = {}
    for r in rooms:
        b_name.setdefault(r.building, bld_label(r))
    b_lessons = {b: [] for b in b_ids}      # индексы пар по корпусам
    b_used = {b: set() for b in b_ids}      # аудитории, где есть пары
    occ, occ_day = {}, {}   # занятые аудитории-слоты: (корпус, неделя[, день])
    for i, (lesson, (slot, rid)) in enumerate(zip(lessons, individual)):
        b = rooms[rid].building
        b_lessons[b].append(i)
        b_used[b].add(rid)
        for w in lesson.weeks:
            for s in range(slot, min(slot + lesson.length, TOTAL_SLOTS)):
                occ[(b, w)] = occ.get((b, w), 0) + 1
                k = (b, w, slot_day(s))
                occ_day[k] = occ_day.get(k, 0) + 1
    bad = {i for i, (l, (sl, rid)) in enumerate(zip(lessons, individual))
           if problems_of(l, sl, rid)}

    def b_row(bs, label):
        rs = [r for r in rooms if r.building in bs]
        idx = [i for b in bs for i in b_lessons[b]]
        ls = [lessons[i] for i in idx]
        cap_slots = max(1, len(rs) * TOTAL_SLOTS)
        used = set().union(*(b_used[b] for b in bs))
        return [
            label, len(rs), sum(r.is_computer for r in rs),
            sum(r.capacity for r in rs), len(ls),
            sum(l.parity == PARITY_BOTH for l in ls),
            sum(l.parity == PARITY_ODD for l in ls),
            sum(l.parity == PARITY_EVEN for l in ls),
            sum(l.needs_computer for l in ls),
            len({l.teacher_id for l in ls}), len({g for l in ls for g in l.group_ids}),
            sum(occ.get((b, 0), 0) for b in bs) / cap_slots,
            sum(occ.get((b, 1), 0) for b in bs) / cap_slots,
            len(rs) - len(used),
            sum(1 for i in idx if i in bad),
            sum(1 for l, (sl, rid) in ((lessons[i], individual[i]) for i in idx)
                if teachers[l.teacher_id].preferred_building == rooms[rid].building),
        ]

    ws.append(["Корпус", "Аудиторий", "Из них комп. классов",
               "Суммарная вместимость", "Пар всего", "Каждую неделю",
               "Только нечёт", "Только чёт", "Из них комп. пар",
               "Преподавателей", "Групп", "Загрузка аудиторий, нечётная неделя",
               "Загрузка аудиторий, чётная неделя", "Аудиторий без пар",
               "Пар с нарушениями", "Пар в предпочитаемом корпусе"])
    style_header(ws)
    for b in b_ids:
        ws.append(b_row([b], b_name[b]))
    ws.append(b_row(b_ids, "Всего"))
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=12,
                            max_col=13):
        for c in row:
            c.number_format = "0.0%"

    # занятость по дням: аудитории-слоты отдельно для нечётной и чётной недели
    ws.append([])
    ws.append(["Занято аудиторий-слотов по дням"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append(["Корпус"] + [f"{d} {wn}" for d in DAY_NAMES
                            for wn in ("нечёт", "чёт")])
    style_header(ws, row=ws.max_row)
    for b in b_ids:
        ws.append([b_name[b]] + [occ_day.get((b, w, d), 0)
                                 for d in range(DAYS) for w in (0, 1)])
    ws.freeze_panes = "B2"
    ws.column_dimensions["A"].width = 22
    for i in range(2, 17):
        ws.column_dimensions[get_column_letter(i)].width = 17
    ws.row_dimensions[1].height = 48

    # ---- Лист 2: все пары (плоская таблица) ----
    ws = wb.create_sheet("Все пары")
    ws.append(["№", "Преподаватель", "Группа(ы)", "Вид", "Студентов", "День",
               "Пара", "Неделя", "Корпус", "Аудитория", "Вместимость",
               "Тип аудитории", "Нужен комп. класс", "Проблемы"])
    style_header(ws)
    order = sorted(range(n), key=lambda i: (individual[i][0],
                                            lessons[i].teacher_id))
    for i in order:
        lesson, (slot, rid) = lessons[i], individual[i]
        room = rooms[rid]
        probs = problems_of(lesson, slot, rid)
        ws.append([
            lesson.id, teachers[lesson.teacher_id].name,
            ", ".join(groups[g].name for g in lesson.group_ids),
            KIND_LABEL[lesson.kind], lesson_size(lesson, groups),
            DAY_NAMES[slot_day(slot)], slot_time(slot) + 1,
            PARITY_LABEL[lesson.parity],
            bld_label(room), room_label(room), room.capacity,
            "Компьютерный класс" if room.is_computer else "Обычная",
            "Да" if lesson.needs_computer else "Нет",
            "; ".join(probs),
        ])
        row = ws.max_row
        if probs:
            for c in ws[row]:
                c.fill = RED
        elif lesson.needs_computer:
            for c in ws[row]:
                c.fill = BLUE
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for i, w in enumerate([7, 15, 18, 13, 11, 7, 7, 10, 9, 12, 13, 20, 17, 45], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ---- Листы-сетки: преподаватели и группы ----
    def grid_sheet(title, key_fn, ids, name_fn, cell_fn, header):
        ws = wb.create_sheet(title)
        ws.append([header] + slot_labels)
        style_header(ws)
        cells = {}
        for i, (lesson, (slot, rid)) in enumerate(zip(lessons, individual)):
            for s in range(slot, min(slot + lesson.length, TOTAL_SLOTS)):
                for key in key_fn(lesson):
                    cells.setdefault((key, s), []).append(
                        (cell_fn(lesson, rid), lesson, rid))
        for k in sorted(ids):
            ws.append([name_fn(k)] + [""] * TOTAL_SLOTS)
            r = ws.max_row
            for s in range(TOTAL_SLOTS):
                items = cells.get((k, s))
                if not items:
                    continue
                c = ws.cell(row=r, column=2 + s)
                c.value = "\n".join(x[0] for x in items)
                c.alignment = WRAP
                # конфликт — только если пары пересекаются по неделям
                clash = any(sum(1 for x in items if w in x[1].weeks) > 1
                            for w in (0, 1))
                if clash:
                    c.fill = RED
                elif any(x[1].needs_computer for x in items):
                    c.fill = BLUE
        ws.freeze_panes = "B2"
        ws.column_dimensions["A"].width = 14
        for s in range(TOTAL_SLOTS):
            ws.column_dimensions[get_column_letter(2 + s)].width = 15

    used_t = {l.teacher_id for l in lessons}
    used_g = {g for l in lessons for g in l.group_ids}
    grid_sheet("По преподавателям", lambda l: [l.teacher_id], used_t,
               lambda k: teachers[k].name,
               lambda l, rid: f"{PARITY_SHORT[l.parity]}{KIND_SHORT[l.kind]} {', '.join(groups[g].name for g in l.group_ids)} · корп.{bld_label(rooms[rid])}"
                              f" · {room_label(rooms[rid])}"
                              + (" · ПК" if l.needs_computer else ""),
               "Преподаватель")
    grid_sheet("По группам", lambda l: l.group_ids, used_g,
               lambda k: f"{groups[k].name} ({groups[k].size})",
               lambda l, rid: f"{PARITY_SHORT[l.parity]}{KIND_SHORT[l.kind]} {teachers[l.teacher_id].name} · корп.{bld_label(rooms[rid])}"
                              f" · {room_label(rooms[rid])}"
                              + (" · ПК" if l.needs_computer else ""),
               "Группа")

    # ---- Лист: нарушения ----
    ws = wb.create_sheet("Нарушения")
    ws.append(["№ пары", "Преподаватель", "Группа", "День", "Пара",
               "Неделя", "Корпус", "Аудитория", "Проблема"])
    style_header(ws)
    for lesson, (slot, rid) in zip(lessons, individual):
        probs = problems_of(lesson, slot, rid)
        if probs:
            ws.append([lesson.id, teachers[lesson.teacher_id].name,
                       ", ".join(groups[g].name for g in lesson.group_ids),
                       DAY_NAMES[slot_day(slot)], slot_time(slot) + 1,
                       PARITY_LABEL[lesson.parity],
                       bld_label(rooms[rid]), room_label(rooms[rid]),
                       "; ".join(probs)])
    for i, w in enumerate([9, 15, 10, 7, 7, 10, 9, 12, 50], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"

    wb.save(path)


# ============================================================
# MAIN
# ============================================================
def parse_args():
    p = argparse.ArgumentParser(description="ИИ-составитель расписания")
    p.add_argument("--teachers", type=int, default=800)
    p.add_argument("--groups", type=int, default=400)
    p.add_argument("--rooms", type=int, default=200)
    p.add_argument("--pop", type=int, default=150)
    p.add_argument("--generations", type=int, default=500)
    p.add_argument("--mutation", type=float, default=0.03)
    p.add_argument("--elite", type=int, default=6)
    p.add_argument("--computer-share", type=float, default=0.15,
                   help="доля пар, требующих компьютерный класс")
    p.add_argument("--lecture-share", type=float, default=0.35,
                   help="доля лекций (они могут быть потоковыми, на несколько "
                        "групп) среди тестовых пар")
    p.add_argument("--alt-share", type=float, default=0.25,
                   help="доля пар только по чётным/нечётным неделям "
                        "(для тестовых данных)")
    p.add_argument("--workers", type=int, default=os.cpu_count() or 1,
                   help="число процессов (1 = без параллельности)")
    p.add_argument("--device", choices=["cpu", "cuda", "numpy"], default="cpu",
                   help="где считать фитнес: cpu (по умолчанию), cuda "
                        "(CuPy, нужна NVIDIA GPU), numpy (отладочный режим)")
    p.add_argument("--data", metavar="ФАЙЛ_ИЛИ_ПАПКА", default=None,
                   help="реальные данные: .xlsx или папка с CSV "
                        "(формат: python data_loader.py --make-template t.xlsx)")
    p.add_argument("--out", default="schedule.xlsx")
    return p.parse_args()


def main():
    a = parse_args()

    print("=" * 78)
    src = f"данные из «{a.data}»" if a.data else f"{a.teachers} преподавателей (тестовые данные)"
    print(f"РАСПИСАНИЕ: {src}, процессов: {a.workers}")
    print("=" * 78)

    t0 = time.time()
    if a.data:
        import data_loader
        print("\n[1/4] Загрузка данных...")
        try:
            teachers, groups, rooms, lessons = data_loader.load_data(
                a.data, core=sys.modules[__name__])
        except data_loader.DataError as e:
            print("\nОшибки во входных данных — расписание не запущено:")
            print(e)
            sys.exit(1)
    else:
        print("\n[1/4] Генерация данных...")
        teachers, groups, rooms, lessons = generate_data(
            n_teachers=a.teachers, n_groups=a.groups, n_rooms=a.rooms,
            computer_lesson_share=a.computer_share,
            alt_week_share=a.alt_share,
            lecture_share=a.lecture_share)
    n_pc = sum(1 for l in lessons if l.needs_computer)
    print(f"  Преподавателей: {len(teachers)}")
    print(f"  Групп:          {len(groups)}")
    print(f"  Аудиторий:      {len(rooms)} "
          f"(компьютерных: {sum(r.is_computer for r in rooms)})")
    print(f"  Пар всего:      {len(lessons)} (только в комп. классах: {n_pc})")
    print(f"  По неделям:     каждая {sum(l.parity == PARITY_BOTH for l in lessons)}, "
          f"нечётные {sum(l.parity == PARITY_ODD for l in lessons)}, "
          f"чётные {sum(l.parity == PARITY_EVEN for l in lessons)}")
    print(f"  По видам:       лекций {sum(l.kind == KIND_LECTURE for l in lessons)} "
          f"(потоковых {sum(len(l.group_ids) > 1 for l in lessons)}), "
          f"практик {sum(l.kind == KIND_PRACTICE for l in lessons)}, "
          f"лабораторных {sum(l.kind == KIND_LAB for l in lessons)}")
    print(f"  Время:          {time.time() - t0:.1f} сек")

    print(f"\n[2/4] Запуск GA (pop={a.pop}, gen={a.generations})...")
    t0 = time.time()
    best, best_fit = run_ga(
        lessons, teachers, groups, rooms,
        pop_size=a.pop, generations=a.generations, elite=a.elite,
        mutation_rate=a.mutation, workers=a.workers, verbose=True,
        device=a.device)
    elapsed = time.time() - t0

    print("\n[3/4] Оценка финального решения...")
    score, stats = evaluate(best, lessons, teachers, groups, rooms)
    n_lessons = len(lessons)

    print("\n" + "=" * 78)
    print("РЕЗУЛЬТАТЫ")
    print("=" * 78)
    print(f"Время работы:                  {elapsed:.1f} сек ({elapsed/60:.1f} мин)")
    print(f"Фитнес:                        {score:.1f}")
    print(f"Конфликтов:                    {stats['conflicts']}")
    print(f"Проблем с вместимостью:        {stats['capacity']}")
    print(f"Пар не в комп. классе:         {stats['computer']} из {n_pc}")
    print(f"Попаданий в предпочтения:      {stats['pref']}")
    print(f"Препод: окна больше 1 слота:   {stats['teacher_gaps']}")
    print(f"Группа: окна больше 1 слота:   {stats['group_gaps']}")
    print(f"Препод: разные корпуса подряд: {stats['teacher_adj']}")
    print(f"Группа: разные корпуса подряд: {stats['group_adj']}")
    print(f"Группа: лишних смен корпуса:   {stats['group_extra_changes']}")
    print(f"Конфликты на 100 пар:          {100 * stats['conflicts'] / n_lessons:.2f}")

    print(f"\n[4/4] Экспорт в Excel: {a.out}")
    export_excel(a.out, best, lessons, teachers, groups, rooms, score, stats,
                 params={"Размер популяции": a.pop,
                         "Поколений": a.generations,
                         "Процессов": a.workers},
                 elapsed=elapsed)
    print("  Готово.")


if __name__ == "__main__":
    mp.freeze_support()
    main()