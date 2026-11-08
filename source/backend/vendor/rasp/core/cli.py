import argparse
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from core.constants import (
    DAY_NAMES, DAYS, SLOTS_PER_DAY, TOTAL_SLOTS,
    PARITY_BOTH, PARITY_ODD, PARITY_EVEN,
    PARITY_LABEL, PARITY_SHORT,
    KIND_LECTURE, KIND_PRACTICE, KIND_LAB,
    KIND_LABEL, KIND_SHORT,
)
from core.ai import (
    lesson_size, slot_day, slot_time,
    bld_label, room_label,
    generate_data, run_ga, evaluate,
)

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
        ("Препод.: пары подряд в разных ансамблях", stats["teacher_adj"]),
        ("Группа: пары подряд в разных ансамблях", stats["group_adj"]),
        ("Группа: лишних смен ансамбля за день", stats["group_extra_changes"]),
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
    for ws in wb.worksheets:
        ws.sheet_state = "visible"



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
