import sys

from PySide6.QtWidgets import QApplication

from . import theme
from .main_window import MainWindow


def run_app(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv[:1])
    app.setApplicationName("Canary")
    theme.apply(app)
    window = MainWindow()
    app.installEventFilter(window)          # any key or mouse activity resets the idle clock
    window.show()
    return app.exec()
