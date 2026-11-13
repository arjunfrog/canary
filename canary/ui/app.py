import sys

from PySide6.QtWidgets import QApplication

from . import theme
from .main_window import MainWindow


def run_app(argv: list[str] | None = None, replay=None) -> int:
    """Open the window. With `replay` (a saved case), show that case alone: no worker, no listener, no network."""
    app = QApplication(argv if argv is not None else sys.argv[:1])
    app.setApplicationName("Canary")
    theme.apply(app)
    window = MainWindow(replay=replay)
    app.installEventFilter(window)          # any key or mouse activity resets the idle clock
    window.show()
    return app.exec()
