
"""
Модуль самодостаточен: единственная публичная сущность — ExcelViewer.
Использование:
from ui.ExcelViewer import ExcelViewer
viewer = ExcelViewer(path="schedule.xlsx", parent=main_window)
viewer.show()
"""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QMessageBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView,
)

class ExcelViewer(QDialog):
    """
    Показывает содержимое любого .xlsx прямо в Qt.
    Один лист = одна вкладка. Читает значения (data_only=True).
    """
    # ИСПРАВЛЕНО: __init__ вместо init
    def __init__(self, path: str | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Просмотр Excel")
        self.resize(1100, 700)
        self.path = None

        self.tabs = QTabWidget(self)

        # верхняя панель
        top = QHBoxLayout()
        self.lbl_path = QLabel("Файл не выбран")
        self.lbl_path.setWordWrap(True)

        btn_open = QPushButton("Открыть…")
        btn_open.clicked.connect(self.on_open)

        btn_reload = QPushButton("Обновить")
        btn_reload.clicked.connect(self.on_reload)

        top.addWidget(btn_open)
        top.addWidget(btn_reload)
        top.addWidget(self.lbl_path, 1)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.tabs)

        if path:
            self.load(path)

    # ---------- открыть файл ----------
    def on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть Excel", "",
            "Excel (*.xlsx *.xlsm);;Все файлы (*)")
        if path:
            self.load(path)

    def on_reload(self):
        if self.path:
            self.load(self.path)

    # ---------- загрузить и построить вкладки ----------
    def load(self, path: str):
        try:
            from openpyxl import load_workbook
            wb = load_workbook(path, data_only=True, read_only=True)
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка открытия", str(exc))
            return

        self.path = path
        self.lbl_path.setText(f"Файл: {path}")

        # очистим вкладки
        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if w is not None:
                w.deleteLater()

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            table = self._make_table(ws)
            self.tabs.addTab(table, sheet_name)
        wb.close()

    # ---------- превратить лист в QTableWidget ----------
    def _make_table(self, ws) -> QTableWidget:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            t = QTableWidget(0, 0)
            t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            return t

        n_cols = max(len(r) for r in rows)
        t = QTableWidget(len(rows), n_cols)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setAlternatingRowColors(True)

        for r, row in enumerate(rows):
            for c in range(n_cols):
                v = row[c] if c < len(row) else None
                text = "" if v is None else str(v)
                item = QTableWidgetItem(text)
                if r == 0:                       # заголовок
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                    item.setBackground(Qt.GlobalColor.lightGray)
                t.setItem(r, c, item)

        headers = [
            str(rows[0][c]) if c < len(rows[0]) and rows[0][c] is not None
            else f"col{c + 1}"
            for c in range(n_cols)
        ]
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        return t
