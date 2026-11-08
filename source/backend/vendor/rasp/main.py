from __future__ import annotations

# ============================================================
# MAIN: точка входа всего приложения + AppManager
# ============================================================
"""
Запуск:
    python main.py                 # GUI
    python main.py --cli --pop 100 # консольный режим (ядро ГА из core.cli)
"""

import sys

from PyQt6.QtWidgets import QApplication
from ui.WinMain import MainWindow
from ui.ExcelViewer import ExcelViewer   # ← исправлено: было ExcelVeiwer


class AppManager:
    """
    Собирает приложение: QApplication + MainWindow + модули.
    Точка расширения: добавить модуль = поле + публичный open_*().
    """

    def __init__(self, argv: list[str] | None = None):
        self._ExcelViewer = ExcelViewer

        self.app = QApplication(argv if argv is not None else sys.argv)
        self.app.setApplicationName("ИИ-составитель расписания")

        # модули (создаются лениво)
        self._excel_viewer: ExcelViewer | None = None

        # главное окно
        self.window = MainWindow(self)

    # ---------- публичные API для модулей ----------
    def open_viewer(self, path: str | None = None):
        """Открыть ExcelViewer (переиспользуем одно окно)."""
        if self._excel_viewer is None:
            self._excel_viewer = self._ExcelViewer(path, parent=self.window)
        else:
            if path:
                self._excel_viewer.load(path)
        self._excel_viewer.show()
        self._excel_viewer.raise_()
        self._excel_viewer.activateWindow()

    # ---------- запуск ----------
    def run(self) -> int:
        self.window.show()
        return self.app.exec()


# ============================================================
# MAIN
# ============================================================
def main():
    # консольный режим — целиком уходит в core.cli
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        from core.cli import cli_main
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        cli_main()
        return

    # GUI
    manager = AppManager(sys.argv)
    sys.exit(manager.run())


if __name__ == "__main__":
    import multiprocessing as mp
    mp.freeze_support()      # важно для spawn (Windows/macOS)
    main()
