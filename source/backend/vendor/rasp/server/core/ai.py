import os
import random
import multiprocessing as mp

from core.constants import (
    DAYS, SLOTS_PER_DAY, TOTAL_SLOTS, MAX_GAP,
    PARITY_BOTH, PARITY_ODD, PARITY_EVEN,
    KIND_LECTURE, KIND_PRACTICE, KIND_LAB,
    W_CONFLICT_TEACHER, W_CONFLICT_GROUP, W_CONFLICT_ROOM,
    W_CAPACITY, W_COMPUTER, W_BUILDING_HARD,
    W_DIFF_BUILDING_ADJ_T, W_DIFF_BUILDING_ADJ_G,
    W_GROUP_BUILDING_CHANGES,
    W_PREF_TIME, W_PREF_BUILDING,
    W_GAP, W_GAP_BIG, SYNTH_ENSEMBLE,
)
from core.models import Teacher, Group, Room, Lesson


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
                  is_computer=(i // 5) % 5 == 0,
                  ensemble=SYNTH_ENSEMBLE[i % 5])
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
    # ансамбль -> список аудиторий всех корпусов ансамбля
    by_e = {}
    for r in rooms:
        by_e.setdefault(r.ensemble, []).append(r)
    _CTX["by_ensemble"] = by_e
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

        # --- 5. Сбор данных по ансамблям ---
        # окна и смены ансамбля считаются отдельно для каждой недели;
        # переход между корпусами ОДНОГО ансамбля бесшовный и не штрафуется
        for w in lesson.weeks:
            teacher_day.setdefault(lesson.teacher_id, {}) \
                .setdefault((w, d), []).append((t, room.ensemble, lesson.length))
            for gid in lesson.group_ids:
                group_day.setdefault(gid, {}) \
                    .setdefault((w, d), []).append(
                        (t, room.ensemble, lesson.length))

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
def _candidates(ensemble, lesson, size, by_ensemble):
    """Аудитории ансамбля, подходящие паре по размеру и типу (комп. класс)."""
    rs = by_ensemble.get(ensemble, [])
    fit = [r.id for r in rs
           if r.capacity >= size and r.is_computer == lesson.needs_computer]
    if not fit and not lesson.needs_computer:
        # обычной паре допустим и компьютерный класс, если больше нечего
        fit = [r.id for r in rs if r.capacity >= size]
    return fit


def repair_group_buildings(individual, lessons, groups, rooms, by_ensemble=None):
    """
    Гарантирует (насколько возможно): у группы не более 1 смены АНСАМБЛЯ в день
    (между корпусами одного ансамбля можно ходить свободно).
    Пары дня переводятся в "главный" ансамбль (где их больше всего), при этом
    для каждой пары подбирается аудитория нужного типа (компьютерный класс
    остаётся компьютерным классом) и достаточной вместимости.
    """
    if by_ensemble is None:
        by_ensemble = _CTX["by_ensemble"]
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
            ens_count = {}
            for i in idxs:
                e = rooms[ind[i][1]].ensemble
                ens_count[e] = ens_count.get(e, 0) + 1

            if len(ens_count) <= 1:
                continue

            # ансамбли по убыванию частоты
            order = sorted(ens_count.items(), key=lambda kv: -kv[1])
            main_ens = None
            for e, _ in order:
                # ансамбль годится, если для ВСЕХ пар дня там есть аудитория
                if all(_candidates(e, lessons[i], sizes[i], by_ensemble)
                       for i in idxs):
                    main_ens = e
                    break
            if main_ens is None:
                continue

            for i in idxs:
                slot, room_id = ind[i]
                if rooms[room_id].ensemble != main_ens:
                    cand = _candidates(main_ens, lessons[i], sizes[i],
                                       by_ensemble)
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
    group_buildings = {}   # (group_id, w, day) -> {ансамбли уже стоящих пар}
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
            pref = [r for r in cand if rooms[r].ensemble in gb]
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
                    .add(rooms[rid].ensemble)
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
        # id ансамбля = наименьший индекс его корпуса, поэтому < self.B
        self.room_ens = A([r.ensemble for r in rooms], np.int64)
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
        ens = self.room_ens[room]
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
                    slot_e, bld_e = slot, ens
                else:     # потоковая лекция входит в расписание каждой группы
                    m = self.in_week[w][lidx][None, :]
                    slot_e, bld_e = slot[:, lidx], ens[:, lidx]
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
           device="cpu", progress=None):
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

            if progress is not None:
                progress(gen, generations, best_fit)

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
