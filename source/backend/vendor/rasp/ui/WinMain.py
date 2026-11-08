
"""
Точка входа НЕ здесь — запускайте `python main.py`.
Модуль предоставляет:
load_from_excel(path)
GARunner(QThread)
ScheduleDialog(QDialog)
MainWindow(QMainWindow) — принимает AppManager
"""
from __future__ import annotations
import traceback
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QSpinBox, QDoubleSpinBox, QFormLayout, QGroupBox, QProgressBar,
    QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QTabWidget, QTextEdit,
)

# ---- ядро (пакет core) ----
from core import (
    Teacher, Group, Room, Lesson,
    generate_data, evaluate, run_ga,
    lesson_size, slot_day, slot_time,
    bld_label, room_label,
)
from core.constants import (
    DAY_NAMES, SLOTS_PER_DAY, TOTAL_SLOTS,
    PARITY_LABEL, PARITY_SHORT,
    KIND_LABEL, KIND_SHORT,
)

# ---- экспорт в Excel (может отсутствовать в core.cli) ----
try:
    from core.cli import export_excel
except ImportError:
    def export_excel(path, individual, lessons, teachers, groups, rooms,
                     score, stats, params=None):
        """Fallback-заглушка, если core.cli.export_excel недоступен."""
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Schedule"
        ws.append(["№", "Преподаватель", "Группы", "Вид", "Студентов",
                   "День", "Пара", "Неделя", "Корпус", "Аудитория"])
        for i, (lesson, (slot, rid)) in enumerate(zip(lessons, individual)):
            room = rooms[rid]
            ws.append([
                lesson.id,
                teachers[lesson.teacher_id].name,
                ", ".join(groups[g].name for g in lesson.group_ids),
                KIND_LABEL.get(lesson.kind, lesson.kind),
                lesson_size(lesson, groups),
                DAY_NAMES[slot_day(slot)],
                slot_time(slot) + 1,
                PARITY_LABEL.get(lesson.parity, ""),
                bld_label(room),
                room_label(room),
            ])
        wb.save(path)

# ============================================================
# ЗАГРУЗКА ДАННЫХ ИЗ EXCEL (через data_loader.py)
# ============================================================
def load_from_excel(path: str):
    """
    Читает книгу формата data_loader.py (листы Преподаватели / Группы /
    Аудитории / Нагрузка). При ошибках в данных бросает DataError со
    списком всех проблем — подмены синтетикой НЕТ.
    """
    import types
    import core as _core
    from core import constants as _c
    from data_loader import load_data

    # data_loader ждёт один модуль и с моделями, и с константами
    ns = types.SimpleNamespace(
        **{k: getattr(_c, k) for k in dir(_c) if k.isupper()}
    )
    # ИСПРАВЛЕНО: добавлена кавычка перед Lesson
    for name in ("Teacher", "Group", "Room", "Lesson", "lesson_size"):
        setattr(ns, name, getattr(_core, name))

    return load_data(path, core=ns, verbose=False)

# ============================================================
# ПОТОК ГЕНЕРАЦИИ
# ============================================================
class GARunner(QThread):
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(object, object, object)   # individual, score, stats
    failed = pyqtSignal(str)

    def __init__(self, lessons, teachers, groups, rooms,
                 pop, generations, elite, mutation, workers, device):
        super().__init__()
        self.lessons = lessons
        self.teachers = teachers
        self.groups = groups
        self.rooms = rooms
        self.pop = pop
        self.generations = generations
        self.elite = elite
        self.mutation = mutation
        self.workers = workers
        self.device = device

    def run(self):
        try:
            self.progress.emit("Генерация расписания…")
            best, score = run_ga(
                self.lessons, self.teachers, self.groups, self.rooms,
                pop_size=self.pop, generations=self.generations,
                elite=self.elite, mutation_rate=self.mutation,
                workers=self.workers, device=self.device,
                verbose=False,
            )
            _, stats = evaluate(best, self.lessons, self.teachers,
                                self.groups, self.rooms)
            self.finished_ok.emit(best, score, stats)
        except Exception as exc:
            self.failed.emit(f"{exc}\n\n{traceback.format_exc()}")

# ============================================================
# ДИАЛОГ ПРОСМОТРА ИЗ ПАМЯТИ
# ============================================================
class ScheduleDialog(QDialog):
    # ИСПРАВЛЕНО: __init__ вместо init
    def __init__(self, individual, lessons, teachers, groups, rooms,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Расписание")
        self.resize(1100, 700)

        self.ind = individual
        self.lessons = lessons
        self.teachers = teachers
        self.groups = groups
        self.rooms = rooms

        tabs = QTabWidget(self)
        tabs.addTab(self._make_flat_table(), "Все пары")
        tabs.addTab(self._make_grid(lambda l: [l.teacher_id],
                                    {l.teacher_id for l in lessons},
                                    lambda k: teachers[k].name,
                                    "Преподаватель"), "По преподавателям")
        tabs.addTab(self._make_grid(lambda l: list(l.group_ids),
                                    {g for l in lessons for g in l.group_ids},
                                    lambda k: groups[k].name,
                                    "Группа"), "По группам")
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)

    def _make_flat_table(self):
        headers = ["№", "Преподаватель", "Группы", "Вид", "Студентов",
                   "День", "Пара", "Неделя", "Корпус", "Аудитория",
                   "Вместимость"]
        t = QTableWidget(len(self.lessons), len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)

        order = sorted(range(len(self.lessons)),
                       key=lambda i: (self.ind[i][0],
                                      self.lessons[i].teacher_id))

        for row, i in enumerate(order):
            lesson, (slot, rid) = self.lessons[i], self.ind[i]
            room = self.rooms[rid]
            vals = [
                str(lesson.id),
                self.teachers[lesson.teacher_id].name,
                ", ".join(self.groups[g].name for g in lesson.group_ids),
                KIND_LABEL.get(lesson.kind, lesson.kind),
                str(lesson_size(lesson, self.groups)),
                DAY_NAMES[slot_day(slot)],
                str(slot_time(slot) + 1),
                PARITY_LABEL.get(lesson.parity, ""),
                bld_label(room),
                room_label(room),
                str(room.capacity),
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if lesson.needs_computer:
                    item.setBackground(Qt.GlobalColor.cyan)
                t.setItem(row, c, item)

        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        return t

    def _make_grid(self, key_fn, ids, name_fn, header):
        n_slots = TOTAL_SLOTS
        t = QTableWidget(len(ids), n_slots + 1)
        t.setHorizontalHeaderLabels(
            [header] + [f"{DAY_NAMES[s // SLOTS_PER_DAY]} {s % SLOTS_PER_DAY + 1}"
                        for s in range(n_slots)])
        t.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)

        cells = {}
        for lesson, (slot, rid) in zip(self.lessons, self.ind):
            for s in range(slot, min(slot + lesson.length, n_slots)):
                for key in key_fn(lesson):
                    cells.setdefault((key, s), []).append((lesson, rid))

        for r, k in enumerate(sorted(ids)):
            t.setItem(r, 0, QTableWidgetItem(name_fn(k)))
            for s in range(n_slots):
                items = cells.get((k, s))
                if not items:
                    continue
                lines = []
                clash = False
                for lesson, rid in items:
                    room = self.rooms[rid]
                    lines.append(
                        f"{PARITY_SHORT.get(lesson.parity, '')}"
                        f"{KIND_SHORT.get(lesson.kind, '')} "
                        f"{self.teachers[lesson.teacher_id].name} "
                        f"· {bld_label(room)} · {room_label(room)}"
                    )
                    # проверка коллизий по неделям (если у Lesson есть weeks)
                    weeks = getattr(lesson, "weeks", (0, 1))
                    if any(sum(1 for x in items if w in getattr(x[0], "weeks", (0, 1))) > 1
                           for w in weeks):
                        clash = True

                item = QTableWidgetItem("\n".join(lines))
                if clash:
                    item.setBackground(Qt.GlobalColor.red)
                t.setItem(r, s + 1, item)

        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        return t

# ============================================================
# ГЛАВНОЕ ОКНО
# ============================================================
class MainWindow(QMainWindow):
    # ИСПРАВЛЕНО: __init__ вместо init
    def __init__(self, app_manager):
        super().__init__()
        self.app = app_manager
        self.setWindowTitle("ИИ-составитель расписания")
        self.resize(720, 600)

        self.teachers = self.groups = self.rooms = self.lessons = None
        self.individual = None
        self.score = None
        self.stats = None
        self.runner = None
        self._last_saved_path = None

        self._build_menu()
        self._build_ui()

    # ---------- меню ----------
    def _build_menu(self):
        m_file = self.menuBar().addMenu("Файл")
        a_load = QAction("Загрузить данные…", self)
        a_load.setShortcut(QKeySequence.StandardKey.Open)
        a_load.triggered.connect(self.on_load)
        m_file.addAction(a_load)

        a_open_xlsx = QAction("Открыть Excel…", self)
        a_open_xlsx.triggered.connect(lambda: self.app.open_viewer(None))
        m_file.addAction(a_open_xlsx)

        m_file.addSeparator()
        a_quit = QAction("Выход", self)
        a_quit.setShortcut(QKeySequence.StandardKey.Quit)
        a_quit.triggered.connect(self.close)
        m_file.addAction(a_quit)

        m_view = self.menuBar().addMenu("Просмотр")
        a_viewer = QAction("Excel Viewer", self)
        a_viewer.triggered.connect(lambda: self.app.open_viewer(None))
        m_view.addAction(a_viewer)

    # ---------- интерфейс ----------
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)

        self.lbl_status = QLabel(
            "Данные не загружены. Можно сгенерировать тестовые.")
        self.lbl_status.setWordWrap(True)
        root.addWidget(self.lbl_status)

        # --- исходные данные ---
        box_data = QGroupBox("Исходные данные")
        ld = QHBoxLayout(box_data)
        self.btn_load = QPushButton("Загрузить из Excel…")
        self.btn_load.clicked.connect(self.on_load)
        self.btn_gen_data = QPushButton("Сгенерировать тестовые")
        self.btn_gen_data.clicked.connect(self.on_generate_test_data)
        ld.addWidget(self.btn_load)
        ld.addWidget(self.btn_gen_data)
        root.addWidget(box_data)

        # --- параметры ГА ---
        box_ga = QGroupBox("Параметры генетического алгоритма")
        form = QFormLayout(box_ga)

        self.sp_pop = QSpinBox(); self.sp_pop.setRange(10, 5000); self.sp_pop.setValue(150)
        self.sp_gen = QSpinBox(); self.sp_gen.setRange(10, 5000); self.sp_gen.setValue(300)
        self.sp_elite = QSpinBox(); self.sp_elite.setRange(0, 100); self.sp_elite.setValue(6)
        self.ds_mut = QDoubleSpinBox(); self.ds_mut.setRange(0, 1); self.ds_mut.setSingleStep(0.01); self.ds_mut.setValue(0.03)
        self.sp_workers = QSpinBox(); self.sp_workers.setRange(1, 256); self.sp_workers.setValue(4)
        self.cb_device = QComboBox(); self.cb_device.addItems(["cpu", "numpy", "cuda"])

        form.addRow("Популяция:", self.sp_pop)
        form.addRow("Поколений:", self.sp_gen)
        form.addRow("Элита:", self.sp_elite)
        form.addRow("Мутация:", self.ds_mut)
        form.addRow("Процессов:", self.sp_workers)
        form.addRow("Устройство:", self.cb_device)
        root.addWidget(box_ga)

        # --- прогресс и лог ---
        self.pb = QProgressBar()
        self.pb.setRange(0, 0)
        self.pb.setVisible(False)
        root.addWidget(self.pb)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFixedHeight(110)
        self.txt_log.setFont(QFont("monospace"))
        root.addWidget(self.txt_log)

        # --- кнопки ---
        box_act = QHBoxLayout()
        self.btn_run = QPushButton("Сгенерировать расписание")
        self.btn_run.clicked.connect(self.on_run)

        self.btn_save = QPushButton("Скачать расписание…")
        self.btn_save.clicked.connect(self.on_save)
        self.btn_save.setEnabled(False)

        self.btn_view = QPushButton("Посмотреть…")
        self.btn_view.clicked.connect(self.on_view)
        self.btn_view.setEnabled(False)

        self.btn_open_saved = QPushButton("Открыть в Excel Viewer")
        self.btn_open_saved.clicked.connect(self.on_open_viewer)
        self.btn_open_saved.setEnabled(False)

        box_act.addWidget(self.btn_run)
        box_act.addWidget(self.btn_view)
        box_act.addWidget(self.btn_save)
        box_act.addWidget(self.btn_open_saved)
        root.addLayout(box_act)

        self.setCentralWidget(central)

    # ---------- лог ----------
    def log(self, msg: str):
        self.txt_log.append(msg)

    # ---------- данные ----------
    def on_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите Excel с исходными данными", "",
            "Excel (*.xlsx *.xlsm);;Все файлы (*)")
        if not path:
            return
        try:
            self.teachers, self.groups, self.rooms, self.lessons = \
                load_from_excel(path)
            self._update_status(path)
        except Exception as exc:
            errs = getattr(exc, "errors", None)
            if errs:     # DataError: показываем первые 30 проблем
                msg = (f"Найдено проблем: {len(errs)}\n\n" +
                       "\n".join(f"• {e}" for e in errs[:30]) +
                       (f"\n… и ещё {len(errs) - 30}" if len(errs) > 30 else ""))
            else:
                msg = str(exc)
            QMessageBox.critical(self, "Ошибка загрузки", msg)

    def on_generate_test_data(self):
        self.teachers, self.groups, self.rooms, self.lessons = \
            generate_data(n_teachers=80, n_groups=40, n_rooms=30)
        self._update_status("синтетические данные")

    def _update_status(self, source: str):
        self.lbl_status.setText(
            f"Источник: {source}\n"
            f"Преподавателей: {len(self.teachers)} | "
            f"Групп: {len(self.groups)} | "
            f"Аудиторий: {len(self.rooms)} | "
            f"Пар: {len(self.lessons)}"
        )
        self.log(f"[данные] {source}")

    # ---------- ГА ----------
    def on_run(self):
        if not self.lessons:
            QMessageBox.warning(self, "Нет данных",
                                "Сначала загрузите или сгенерируйте данные.")
            return
        self.btn_run.setEnabled(False)
        self.btn_view.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.btn_open_saved.setEnabled(False)
        self.pb.setVisible(True)
        self.txt_log.clear()
        self.log("[ГА] старт…")

        self.runner = GARunner(
            self.lessons, self.teachers, self.groups, self.rooms,
            pop=self.sp_pop.value(),
            generations=self.sp_gen.value(),
            elite=self.sp_elite.value(),
            mutation=self.ds_mut.value(),
            workers=self.sp_workers.value(),
            device=self.cb_device.currentText(),
        )
        self.runner.progress.connect(self.log)
        self.runner.finished_ok.connect(self._on_finished)
        self.runner.failed.connect(self._on_failed)
        self.runner.start()

    def _on_finished(self, individual, score, stats):
        self.pb.setVisible(False)
        self.btn_run.setEnabled(True)
        self.btn_view.setEnabled(True)
        self.btn_save.setEnabled(True)
        self.individual = individual
        self.score = score
        self.stats = stats
        self.log(f"[ГА] готово. фитнес={score:.1f}")
        for k, v in stats.items():
            self.log(f"  {k}: {v}")

    def _on_failed(self, msg):
        self.pb.setVisible(False)
        self.btn_run.setEnabled(True)
        QMessageBox.critical(self, "Ошибка ГА", msg)
        self.log("[ГА] ошибка:\n" + msg)

    # ---------- просмотр из памяти ----------
    def on_view(self):
        if self.individual is None:
            return
        ScheduleDialog(self.individual, self.lessons,
                       self.teachers, self.groups, self.rooms,
                       parent=self).exec()

    # ---------- сохранение ----------
    def on_save(self):
        if self.individual is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить расписание", "schedule.xlsx",
            "Excel (*.xlsx)")
        if not path:
            return
        try:
            export_excel(
                path,
                self.individual,
                self.lessons,
                self.teachers,
                self.groups,
                self.rooms,
                self.score,
                self.stats,
                params={
                    "Популяция": self.sp_pop.value(),
                    "Поколений": self.sp_gen.value(),
                    "Элита": self.sp_elite.value(),
                    "Мутация": self.ds_mut.value(),
                    "Процессов": self.sp_workers.value(),
                    "Устройство": self.cb_device.currentText(),
                },
            )
            self._last_saved_path = path
            self.btn_open_saved.setEnabled(True)
            QMessageBox.information(self, "Готово", f"Сохранено: {path}")
            self.log(f"[сохранение] {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка сохранения", str(exc))

    # ---------- открыть ExcelViewer ----------
    def on_open_viewer(self):
        if self._last_saved_path:
            self.app.open_viewer(self._last_saved_path)
        else:
            self.app.open_viewer(None)
