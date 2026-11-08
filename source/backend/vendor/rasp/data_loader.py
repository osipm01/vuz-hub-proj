"""
Загрузка реальных данных для составителя расписания.

Источник данных — Excel-книга (.xlsx) с четырьмя листами ИЛИ папка с
четырьмя CSV-файлами с теми же именами (Преподаватели.csv и т.д.).

Листы / файлы и колонки (порядок колонок не важен, регистр не важен):

  Преподаватели:  Преподаватель*, Предпочитаемый корпус, Разрешённые корпуса,
                  Предпочитаемое время
  Группы:         Группа*, Размер*
  Аудитории:      Аудитория*, Корпус*, Вместимость*, Компьютерный класс,
                  Ансамбль
  Нагрузка:       Преподаватель*, Группа*, Тип, Пар в неделю,
                  Компьютерный класс, Длительность (слотов), Неделя

  (* — обязательная колонка)

Формат поля «Предпочитаемое время»: "Пн 1, Ср 3-4, Пт 2:5"
  день + номер пары (или диапазон), необязательный вес после двоеточия
  (1..5, по умолчанию 4 — чем больше, тем сильнее пожелание).
«Ансамбль» (только для аудиторий, необязательно): название ансамбля корпуса.
  Корпуса с одинаковым названием ансамбля связаны «бесшовными» переходами:
  пары подряд в них допустимы. Между корпусами РАЗНЫХ ансамблей (и корпусами
  без ансамбля) между парами нужно окно не менее 1 слота (иначе штраф).
  Достаточно указать ансамбль в любой строке корпуса; если у одного корпуса
  указаны разные ансамбли — это ошибка.
Формат «Разрешённые корпуса»: названия корпусов через запятую (пусто = любые).
«Компьютерный класс»: да/нет (для аудитории — это компьютерный класс,
для нагрузки — пара возможна ТОЛЬКО в компьютерном классе).
«Тип» (только для нагрузки): лекция / практика / лабораторная.
  Лекция может идти сразу у нескольких групп (поток): в колонке «Группа»
  перечислите их через запятую, например "ИС-101, ИС-102". Аудитория
  подбирается по суммарному числу студентов потока. У практики и
  лабораторной группа только одна. Если «Тип» пуст: несколько групп —
  это лекция, одна группа — практика.
«Неделя» (только для нагрузки): когда идёт пара —
  каждая (или пусто) — каждую неделю;
  нечёт — только по нечётным неделям;
  чёт — только по чётным неделям.
«Пар в неделю» считается в неделях этого типа: строка с «Неделя = нечёт»
и «Пар в неделю = 2» даёт 2 пары на каждой нечётной неделе.
Пары разных недель в одном слоте не конфликтуют (даже с одной группой,
преподавателем и аудиторией). Одно и то же занятие «раз в две недели» у
двух групп в одном слоте — это две строки: одна «нечёт», другая «чёт».

Использование:
    python data_loader.py --make-template шаблон.xlsx   # создать пример
    python data_loader.py --check данные.xlsx            # проверить файл
    python main.py --data данные.xlsx                    # составить расписание
"""
import argparse
import csv
import os
import re
import sys

SHEETS = ("Преподаватели", "Группы", "Аудитории", "Нагрузка")

# допустимые названия колонок (после приведения к нижнему регистру)
ALIASES = {
    "teacher": ("преподаватель", "препод", "фио", "teacher"),
    "pref_building": ("предпочитаемый корпус", "желаемый корпус",
                      "предпочтительный корпус"),
    "allowed_buildings": ("разрешённые корпуса", "разрешенные корпуса",
                          "допустимые корпуса"),
    "pref_slots": ("предпочитаемое время", "желаемое время",
                   "предпочтения по времени"),
    "group": ("группа", "group"),
    "size": ("размер", "численность", "студентов", "кол-во студентов",
             "количество студентов"),
    "room": ("аудитория", "room", "номер аудитории"),
    "building": ("корпус", "building"),
    "ensemble": ("ансамбль", "ансамбль корпусов", "комплекс", "ensemble"),
    "capacity": ("вместимость", "мест", "capacity"),
    "computer": ("компьютерный класс", "компьютерный", "пк", "комп. класс",
                 "комп класс"),
    "count": ("пар в неделю", "количество пар", "кол-во пар", "пар"),
    "length": ("длительность (слотов)", "длительность", "слотов"),
    "week": ("неделя", "четность", "четность недели", "week"),
    "kind": ("тип", "тип занятия", "вид занятия", "вид", "kind"),
}

# значения колонки «Тип» (после _norm: регистр и «ё» не важны)
KIND_VALUES = {
    "лекция": "lecture", "лекции": "lecture", "лек": "lecture",
    "lecture": "lecture",
    "практика": "practice", "практическая": "practice",
    "практическое": "practice", "практ": "practice", "прак": "practice",
    "пр": "practice", "семинар": "practice", "practice": "practice",
    "лабораторная": "lab", "лабораторное": "lab", "лабораторные": "lab",
    "лаб": "lab", "лр": "lab", "lab": "lab",
}

# значения колонки «Неделя» (после _norm: регистр и «ё» не важны)
WEEK_VALUES = {
    "": "both", "каждая": "both", "каждую": "both", "все": "both",
    "обе": "both", "кажд": "both", "0": "both", "both": "both",
    "нечет": "odd", "нечетная": "odd", "нечетные": "odd", "нечетн": "odd",
    "н": "odd", "1": "odd", "odd": "odd",
    "чет": "even", "четная": "even", "четные": "even", "четн": "even",
    "ч": "even", "2": "even", "even": "even",
}
WEEK_NAMES = {0: "нечётной", 1: "чётной"}

YES = {"да", "д", "yes", "y", "true", "1", "+", "x", "х"}
NO = {"нет", "н", "no", "n", "false", "0", "-", ""}


class DataError(Exception):
    """Ошибки во входных данных (со списком всех найденных проблем)."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("\n".join(f"  • {e}" for e in self.errors))


# ============================================================
# ЧТЕНИЕ ТАБЛИЦ
# ============================================================
def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower().replace("ё", "е"))


def _read_xlsx(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    names = {_norm(n): n for n in wb.sheetnames}
    tables = {}
    for sheet in SHEETS:
        key = _norm(sheet)
        if key not in names:
            tables[sheet] = None
            continue
        rows = list(wb[names[key]].iter_rows(values_only=True))
        tables[sheet] = rows
    return tables


def _read_csv_file(path):
    for enc in ("utf-8-sig", "cp1251"):
        try:
            with open(path, newline="", encoding=enc) as f:
                text = f.read()
            break
        except UnicodeDecodeError:
            continue
    else:
        raise DataError([f"Не удалось прочитать кодировку файла {path}"])
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
    return [tuple(r) for r in csv.reader(text.splitlines(), dialect)]


def _read_csv_dir(path):
    files = {_norm(os.path.splitext(f)[0]): os.path.join(path, f)
             for f in os.listdir(path) if f.lower().endswith(".csv")}
    return {s: (_read_csv_file(files[_norm(s)]) if _norm(s) in files else None)
            for s in SHEETS}


def _rows_to_dicts(sheet, rows, required, errors):
    """Список (номер_строки, {поле: значение}) по заголовку таблицы."""
    if rows is None:
        errors.append(f"Нет листа/файла «{sheet}»")
        return []
    rows = [r for r in rows]
    # пропускаем пустые строки в начале
    while rows and all(c in (None, "") for c in rows[0]):
        rows.pop(0)
    if not rows:
        errors.append(f"«{sheet}»: таблица пуста")
        return []
    header = [_norm(c) for c in rows[0]]
    col = {}
    for field, names in ALIASES.items():
        for i, h in enumerate(header):
            if h in names:
                col[field] = i
                break
    missing = [f for f in required if f not in col]
    if missing:
        nice = [ALIASES[f][0] for f in missing]
        errors.append(f"«{sheet}»: нет обязательных колонок: {', '.join(nice)}")
        return []
    out = []
    for n, r in enumerate(rows[1:], start=2):
        if all(c in (None, "") for c in r):
            continue
        d = {f: (r[i] if i < len(r) else None) for f, i in col.items()}
        out.append((n, d))
    return out


# ============================================================
# РАЗБОР ЗНАЧЕНИЙ
# ============================================================
def _s(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _int(v, where, errors, minimum=1, default=None):
    if v in (None, ""):
        if default is not None:
            return default
        errors.append(f"{where}: не заполнено числовое поле")
        return None
    try:
        x = int(float(str(v).replace(",", ".").strip()))
    except ValueError:
        errors.append(f"{where}: «{v}» — не число")
        return None
    if x < minimum:
        errors.append(f"{where}: значение {x} меньше {minimum}")
        return None
    return x


def _bool(v, where, errors):
    t = _norm(v)
    if t in YES:
        return True
    if t in NO:
        return False
    errors.append(f"{where}: «{v}» — ожидалось да/нет")
    return False


def _parse_slots(text, core, where, errors):
    """'Пн 1, Ср 3-4, Пт 2:5' -> {слот: вес}"""
    result = {}
    days = {_norm(n): i for i, n in enumerate(core.DAY_NAMES)}
    for part in re.split(r"[;,]", _s(text)):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"([^\d\s]+)\s*(\d+)(?:\s*-\s*(\d+))?(?:\s*:\s*(\d))?",
                         _norm(part))
        if not m or m.group(1) not in days:
            errors.append(f"{where}: не удалось разобрать «{part}» "
                          f"(пример: Пн 1, Ср 3-4, Пт 2:5)")
            continue
        d = days[m.group(1)]
        a = int(m.group(2))
        b = int(m.group(3) or a)
        w = int(m.group(4) or 4)
        if not (1 <= a <= b <= core.SLOTS_PER_DAY) or not (1 <= w <= 5):
            errors.append(f"{where}: «{part}» — пары 1..{core.SLOTS_PER_DAY}, "
                          f"вес 1..5")
            continue
        for p in range(a, b + 1):
            result[d * core.SLOTS_PER_DAY + p - 1] = w
    return result


def _parity(v, where, errors, core):
    """'нечёт' / 'чёт' / 'каждая' / пусто -> код чётности из main.py."""
    code = WEEK_VALUES.get(_norm(_s(v)))
    if code is None:
        errors.append(f"{where}: неделя «{v}» — ожидалось каждая / нечёт / чёт")
        return core.PARITY_BOTH
    return {"both": core.PARITY_BOTH, "odd": core.PARITY_ODD,
            "even": core.PARITY_EVEN}[code]


def _kind(v, n_groups, where, errors, core):
    """Тип занятия; без явного значения: несколько групп -> лекция."""
    text = _norm(_s(v))
    if not text:
        return core.KIND_LECTURE if n_groups > 1 else core.KIND_PRACTICE
    code = KIND_VALUES.get(text)
    if code is None:
        errors.append(f"{where}: тип «{v}» — ожидалось лекция / практика / "
                      f"лабораторная")
        return core.KIND_LECTURE if n_groups > 1 else core.KIND_PRACTICE
    kind = {"lecture": core.KIND_LECTURE, "practice": core.KIND_PRACTICE,
            "lab": core.KIND_LAB}[code]
    if n_groups > 1 and kind != core.KIND_LECTURE:
        errors.append(f"{where}: у практики и лабораторной должна быть одна "
                      f"группа, указано {n_groups} (несколько групп — только "
                      f"у лекции)")
    return kind


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================
def _default_core():
    """Единый объект с моделями и константами из пакета core."""
    import types
    import core as pkg
    from core import constants as c
    ns = types.SimpleNamespace(
        **{k: getattr(c, k) for k in dir(c) if k.isupper()})
    for name in ("Teacher", "Group", "Room", "Lesson", "lesson_size"):
        setattr(ns, name, getattr(pkg, name))
    return ns


def load_data(path, core=None, verbose=True):
    """
    Читает и проверяет данные. Возвращает (teachers, groups, rooms, lessons)
    в тех же структурах, что и generate_data() из main.py.
    `core` — модуль с моделями (Teacher, Group, Room, Lesson, DAY_NAMES, ...);
    по умолчанию импортируется main.
    При ошибках в данных бросает DataError со списком ВСЕХ проблем.
    """
    if core is None:
        core = _default_core()

    if os.path.isdir(path):
        tables = _read_csv_dir(path)
    elif path.lower().endswith((".xlsx", ".xlsm")):
        tables = _read_xlsx(path)
    else:
        raise DataError([f"Неизвестный формат «{path}»: нужен .xlsx или папка "
                         f"с CSV-файлами"])

    errors, warnings = [], []

    t_rows = _rows_to_dicts("Преподаватели", tables["Преподаватели"],
                            ["teacher"], errors)
    g_rows = _rows_to_dicts("Группы", tables["Группы"],
                            ["group", "size"], errors)
    r_rows = _rows_to_dicts("Аудитории", tables["Аудитории"],
                            ["room", "building", "capacity"], errors)
    l_rows = _rows_to_dicts("Нагрузка", tables["Нагрузка"],
                            ["teacher", "group"], errors)
    if errors:                     # без структуры дальше идти нельзя
        raise DataError(errors)

    # ---- корпуса: название -> индекс ----
    building_names = []
    for _, d in r_rows:
        b = _s(d["building"])
        if b and b not in building_names:
            building_names.append(b)
    b_index = {b: i for i, b in enumerate(building_names)}

    # ---- ансамбли: корпус -> id ансамбля (наименьший индекс корпуса в нём) ----
    b_ens_name = {}
    for n, d in r_rows:
        b, e = _s(d["building"]), _s(d.get("ensemble"))
        if not (b and e):
            continue
        if b in b_ens_name and _norm(b_ens_name[b]) != _norm(e):
            errors.append(f"Аудитории, строка {n}: у корпуса «{b}» указаны "
                          f"разные ансамбли («{b_ens_name[b]}» и «{e}»)")
        else:
            b_ens_name.setdefault(b, e)
    ens_members = {}
    for b in building_names:
        key = ("e", _norm(b_ens_name[b])) if b in b_ens_name else ("b", b)
        ens_members.setdefault(key, []).append(b_index[b])
    ens_id = {}
    for members in ens_members.values():
        for i in members:
            ens_id[i] = min(members)

    # ---- аудитории ----
    rooms, seen = [], set()
    for n, d in r_rows:
        where = f"Аудитории, строка {n}"
        name, b = _s(d["room"]), _s(d["building"])
        if not name:
            errors.append(f"{where}: пустое название аудитории")
            continue
        if not b:
            errors.append(f"{where}: не указан корпус")
            continue
        if (b, name) in seen:
            errors.append(f"{where}: аудитория «{name}» в корпусе «{b}» "
                          f"встречается повторно")
            continue
        seen.add((b, name))
        cap = _int(d["capacity"], f"{where}, вместимость", errors)
        pc = _bool(d.get("computer"), f"{where}, компьютерный класс", errors)
        if cap is None:
            continue
        r = core.Room(id=len(rooms), building=b_index[b], capacity=cap,
                      is_computer=pc, ensemble=ens_id[b_index[b]])
        r.name, r.building_name = name, b
        rooms.append(r)

    # ---- группы ----
    groups, g_by_name = [], {}
    for n, d in g_rows:
        where = f"Группы, строка {n}"
        name = _s(d["group"])
        if not name:
            errors.append(f"{where}: пустое название группы")
            continue
        if name in g_by_name:
            errors.append(f"{where}: группа «{name}» указана повторно")
            continue
        size = _int(d["size"], f"{where}, размер", errors)
        if size is None:
            continue
        g = core.Group(id=len(groups), name=name, size=size)
        g_by_name[name] = g
        groups.append(g)

    # ---- преподаватели ----
    teachers, t_by_name = [], {}
    for n, d in t_rows:
        where = f"Преподаватели, строка {n}"
        name = _s(d["teacher"])
        if not name:
            errors.append(f"{where}: пустое имя преподавателя")
            continue
        if name in t_by_name:
            errors.append(f"{where}: преподаватель «{name}» указан повторно")
            continue
        pref_b = None
        pb = _s(d.get("pref_building"))
        if pb:
            if pb in b_index:
                pref_b = b_index[pb]
            else:
                errors.append(f"{where}: неизвестный корпус «{pb}» "
                              f"(есть: {', '.join(building_names)})")
        allowed = set(range(len(building_names)))
        ab = _s(d.get("allowed_buildings"))
        if ab:
            allowed = set()
            for b in re.split(r"[;,]", ab):
                b = b.strip()
                if not b:
                    continue
                if b in b_index:
                    allowed.add(b_index[b])
                else:
                    errors.append(f"{where}: неизвестный корпус «{b}» "
                                  f"в разрешённых")
            if not allowed:
                errors.append(f"{where}: список разрешённых корпусов пуст")
        slots = _parse_slots(d.get("pref_slots"), core, where, errors)
        t = core.Teacher(id=len(teachers), name=name, preferred_slots=slots,
                         preferred_building=pref_b, allowed_buildings=allowed)
        t_by_name[name] = t
        teachers.append(t)

    # ---- нагрузка -> пары ----
    lessons = []
    for n, d in l_rows:
        where = f"Нагрузка, строка {n}"
        tn = _s(d["teacher"])
        gnames = [x.strip() for x in re.split(r"[;,]", _s(d["group"]))
                  if x.strip()]
        if tn not in t_by_name:
            errors.append(f"{where}: преподавателя «{tn}» нет на листе "
                          f"«Преподаватели»")
        if not gnames:
            errors.append(f"{where}: не указана группа")
        for gn in gnames:
            if gn not in g_by_name:
                errors.append(f"{where}: группы «{gn}» нет на листе «Группы»")
        dup = len(set(gnames)) != len(gnames)
        if dup:
            errors.append(f"{where}: одна и та же группа указана в списке "
                          f"дважды")
        kind = _kind(d.get("kind"), len(gnames), where, errors, core)
        count = _int(d.get("count"), f"{where}, пар в неделю", errors,
                     default=1)
        length = _int(d.get("length"), f"{where}, длительность", errors,
                      default=1)
        pc = _bool(d.get("computer"), f"{where}, компьютерный класс", errors)
        parity = _parity(d.get("week"), f"{where}, неделя", errors, core)
        if (tn not in t_by_name or not gnames or dup
                or any(g not in g_by_name for g in gnames)
                or not count or not length):
            continue
        if length > core.SLOTS_PER_DAY:
            errors.append(f"{where}: длительность {length} больше числа пар "
                          f"в дне ({core.SLOTS_PER_DAY})")
            continue
        for _ in range(count):
            lessons.append(core.Lesson(
                id=len(lessons), teacher_id=t_by_name[tn].id,
                group_id=g_by_name[gnames[0]].id, length=length,
                needs_computer=pc, parity=parity, kind=kind,
                extra_group_ids=tuple(g_by_name[g].id for g in gnames[1:])))

    if not teachers:
        errors.append("Нет ни одного преподавателя")
    if not groups:
        errors.append("Нет ни одной группы")
    if not rooms:
        errors.append("Нет ни одной аудитории")
    if not lessons:
        errors.append("Нагрузка пуста — нет ни одной пары")
    if errors:
        raise DataError(errors)

    # ---- смысловые проверки ----
    total_slots = core.TOTAL_SLOTS
    # нагрузка считается отдельно для нечётной (0) и чётной (1) недели
    t_load, g_load = {}, {}
    for l in lessons:
        for w in l.weeks:
            t_load[(l.teacher_id, w)] = t_load.get((l.teacher_id, w), 0) + l.length
            for gid in l.group_ids:
                g_load[(gid, w)] = g_load.get((gid, w), 0) + l.length
    for (tid, w), v in t_load.items():
        if v > total_slots:
            errors.append(f"Преподаватель «{teachers[tid].name}»: {v} слотов "
                          f"нагрузки на {WEEK_NAMES[w]} неделе, а в неделе "
                          f"только {total_slots}")
    for (gid, w), v in g_load.items():
        if v > total_slots:
            errors.append(f"Группа «{groups[gid].name}»: {v} слотов нагрузки "
                          f"на {WEEK_NAMES[w]} неделе, а в неделе только "
                          f"{total_slots}")

    pc_rooms = [r for r in rooms if r.is_computer]
    if any(l.needs_computer for l in lessons) and not pc_rooms:
        errors.append("Есть пары только для компьютерных классов, но ни одна "
                      "аудитория не помечена как компьютерный класс")
    for l in lessons:
        size = core.lesson_size(l, groups)
        gname = ", ".join(groups[x].name for x in l.group_ids)
        pool = pc_rooms if l.needs_computer else rooms
        if pool and max(r.capacity for r in pool) < size:
            warnings.append(
                f"Пара «{gname}» ({size} чел.) не помещается ни в одну "
                f"{'компьютерную ' if l.needs_computer else ''}аудиторию "
                f"(максимум {max(r.capacity for r in pool)}) — будет нарушение "
                f"вместимости")
            break
    # загрузка аудиторий — по самой загруженной неделе
    pc_need = max(sum(l.length for l in lessons
                      if l.needs_computer and w in l.weeks) for w in (0, 1))
    if pc_rooms and pc_need > 0.8 * len(pc_rooms) * total_slots:
        warnings.append(
            f"Компьютерные классы загружены на "
            f"{100 * pc_need / (len(pc_rooms) * total_slots):.0f}% — "
            f"найти расписание без конфликтов будет трудно")
    all_need = max(sum(l.length for l in lessons if w in l.weeks)
                   for w in (0, 1))
    if all_need > 0.8 * len(rooms) * total_slots:
        warnings.append(
            f"Аудитории загружены на "
            f"{100 * all_need / (len(rooms) * total_slots):.0f}% — "
            f"найти расписание без конфликтов будет трудно")

    if errors:
        raise DataError(errors)

    if verbose:
        print(f"  Загружено: преподавателей {len(teachers)}, групп "
              f"{len(groups)}, аудиторий {len(rooms)} "
              f"(корпусов {len(building_names)} в {len(ens_members)} "
              f"ансамблях, комп. классов "
              f"{len(pc_rooms)}), пар {len(lessons)} "
              f"(только в комп. классах: "
              f"{sum(l.needs_computer for l in lessons)}; "
              f"только нечёт: {sum(l.parity == core.PARITY_ODD for l in lessons)}, "
              f"только чёт: {sum(l.parity == core.PARITY_EVEN for l in lessons)}; "
              f"лекций {sum(l.kind == core.KIND_LECTURE for l in lessons)}, "
              f"из них потоковых {sum(len(l.group_ids) > 1 for l in lessons)})")
        for w in warnings:
            print(f"  [!] {w}")
    return teachers, groups, rooms, lessons


# ============================================================
# ШАБЛОН
# ============================================================
def make_template(path):
    """Создаёт пример книги Excel с правильной структурой."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    data = {
        "Преподаватели": (
            ["Преподаватель", "Предпочитаемый корпус", "Разрешённые корпуса",
             "Предпочитаемое время"],
            [["Иванов И.И.", "Главный", "", "Пн 1-2, Ср 3:5"],
             ["Петрова А.С.", "Лабораторный", "Лабораторный, Главный",
              "Вт 2, Чт 2"],
             ["Сидоров В.П.", "", "", ""]]),
        "Группы": (
            ["Группа", "Размер"],
            [["ИС-101", 25], ["ИС-102", 28], ["МАТ-201", 90]]),
        "Аудитории": (
            ["Аудитория", "Корпус", "Вместимость", "Компьютерный класс",
             "Ансамбль"],
            [["101", "Главный", 30, "нет", "Центр"],
             ["102", "Главный", 100, "нет", ""],
             ["201", "Лабораторный", 30, "да", "Центр"],
             ["202", "Лабораторный", 60, "да", ""]]),
        "Нагрузка": (
            ["Преподаватель", "Группа", "Тип", "Пар в неделю",
             "Компьютерный класс", "Длительность (слотов)", "Неделя"],
            [["Иванов И.И.", "ИС-101, ИС-102", "лекция", 1, "нет", 1, "каждая"],
             ["Иванов И.И.", "ИС-101", "лабораторная", 2, "да", 1, "каждая"],
             ["Иванов И.И.", "МАТ-201", "лекция", 1, "нет", 1, "нечёт"],
             ["Иванов И.И.", "ИС-102", "практика", 1, "нет", 1, "чёт"],
             ["Петрова А.С.", "ИС-102", "лабораторная", 2, "да", 1, ""],
             ["Сидоров В.П.", "МАТ-201", "практика", 3, "нет", 1, "каждая"]]),
    }
    first = True
    for title, (head, rows) in data.items():
        ws = wb.active if first else wb.create_sheet()
        first = False
        ws.title = title
        ws.append(head)
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="305496")
            c.alignment = Alignment(wrap_text=True, vertical="center")
        for r in rows:
            ws.append(r)
        for i in range(1, len(head) + 1):
            ws.column_dimensions[get_column_letter(i)].width = 26
        ws.freeze_panes = "A2"

    ws = wb.create_sheet("Инструкция")
    for line in (__doc__ or "").strip().splitlines():
        ws.append([line])
    ws.column_dimensions["A"].width = 110
    wb.save(path)


# ============================================================
# CLI
# ============================================================
def _cli():
    p = argparse.ArgumentParser(description="Загрузка данных для расписания")
    p.add_argument("--make-template", metavar="FILE.xlsx",
                   help="создать пример файла с данными")
    p.add_argument("--check", metavar="FILE", help="проверить файл/папку")
    a = p.parse_args()
    if a.make_template:
        make_template(a.make_template)
        print(f"Шаблон создан: {a.make_template}")
    elif a.check:
        try:
            load_data(a.check)
            print("Данные корректны.")
        except DataError as e:
            print("Найдены ошибки в данных:")
            print(e)
            sys.exit(1)
    else:
        p.print_help()


if __name__ == "__main__":
    _cli()
