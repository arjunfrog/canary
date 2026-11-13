"""Render every screen to a PNG without showing a window. Used to check the design by eye.

    python -m canary screenshot OUT_DIR
"""
import os
from pathlib import Path


def render_all(out_dir: Path, width: int = 1440, height: int = 900) -> list[Path]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from . import theme
    from .main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    theme.apply(app)
    out_dir.mkdir(parents=True, exist_ok=True)
    window = MainWindow()
    window.resize(width, height)
    window.show()
    written = []

    def grab(name: str) -> None:
        app.processEvents()
        path = out_dir / f"{name}.png"
        window.grab().save(str(path))
        written.append(path)

    grab("lock")
    window.name.setVisible(True)
    window.nav_bar.setVisible(True)
    window.status.setVisible(True)
    for key, page in window.pages.items():
        window.stack.setCurrentWidget(page)
        if key in window._buttons:
            window._buttons[key].setChecked(True)
        page.refresh()
        grab(key)
    window.close()
    return written
