"""The answer-sheet look: palette, bundled fonts and the base stylesheet."""
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

BOND = QColor("#F5F7F8")          # page
CARBON = QColor("#15171A")        # text
DROPOUT = QColor("#E0457B")       # rules and empty bubbles only
BALLPOINT = QColor("#1A2B8F")     # filled bubbles, actions, links
HIGHLIGHTER = QColor("#FFE100")   # exposed questions and the Traced verdict only
SEAL = QColor("#B3261E")          # errors, "Not our paper"
TIMING = QColor("#000000")
MUTED = QColor("#6C727A")
RULE = QColor("#D6DBE0")

FONT_DIR = Path(__file__).parent / "fonts"

WHITE = QColor("#FFFFFF")

# No font or background rules on plain widgets here: a stylesheet font would override setFont,
# and page colours come from the palette in apply().
STYLESHEET = f"""
QLabel[role="muted"] {{ color: {MUTED.name()}; }}
QLabel[role="error"] {{ color: {SEAL.name()}; }}
QLabel[role="small"] {{ color: {MUTED.name()}; font-size: 14px; }}
QLabel[role="link"] {{ color: {BALLPOINT.name()}; }}
QPushButton {{ border: none; background: transparent; padding: 6px 2px; font-size: 20px; color: {CARBON.name()}; }}
QPushButton[nav="true"]:checked {{ color: {BALLPOINT.name()}; border-bottom: 2px solid {BALLPOINT.name()}; }}
QPushButton[primary="true"] {{ background: {BALLPOINT.name()}; color: white; padding: 9px 24px; font-size: 18px; }}
QPushButton[primary="true"]:disabled {{ background: {RULE.name()}; color: {MUTED.name()}; }}
QPushButton[primary="true"]:focus {{ border-bottom: 2px solid {CARBON.name()}; }}
QPushButton[link="true"] {{ color: {BALLPOINT.name()}; font-size: 16px; padding: 4px 0px; border-bottom: 1px solid transparent; }}
QPushButton[link="true"]:hover {{ border-bottom: 1px solid {BALLPOINT.name()}; }}
QPushButton[link="true"]:disabled {{ color: {MUTED.name()}; }}
QPushButton:focus {{ outline: none; border-bottom: 2px solid {BALLPOINT.name()}; }}
QLineEdit {{ background: white; border: 1px solid {CARBON.name()}; padding: 9px 12px; font-size: 18px; }}
QLineEdit:focus {{ border: 2px solid {BALLPOINT.name()}; }}
QLineEdit:disabled {{ border-color: {RULE.name()}; }}
QPlainTextEdit {{ background: white; border: 1px solid {RULE.name()}; padding: 8px 10px;
                  selection-background-color: {BALLPOINT.name()}; selection-color: white; }}
QPlainTextEdit[editable="true"] {{ border: 1px solid {CARBON.name()}; }}
QPlainTextEdit[editable="true"]:focus {{ border: 2px solid {BALLPOINT.name()}; }}
QScrollArea {{ border: none; background: transparent; }}
QTableView {{ background: transparent; border: none; outline: none; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: transparent; color: {MUTED.name()}; border: none;
                        border-bottom: 1px solid {DROPOUT.name()}; padding: 6px 12px 6px 0px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {RULE.name()}; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {MUTED.name()}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {RULE.name()}; min-width: 32px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QDialog {{ background: {BOND.name()}; }}
QToolTip {{ background: white; color: {CARBON.name()}; border: 1px solid {CARBON.name()}; }}
"""


def load_fonts() -> None:
    for ttf in sorted(FONT_DIR.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(ttf))


def _tabular(font: QFont) -> QFont:
    """Tabular numbers, so digits line up in columns and do not jump while they change."""
    try:
        font.setFeature(QFont.Tag("tnum"), 1)
    except (AttributeError, TypeError):          # older Qt: the font's default figures are used
        pass
    return font


def display(px: int, semibold: bool = True) -> QFont:
    """Khand, for headings and numbers. Sizes are in pixels so macOS and Windows match."""
    font = QFont("Khand")
    font.setPixelSize(px)
    font.setWeight(QFont.Weight.DemiBold if semibold else QFont.Weight.Medium)
    return _tabular(font)


def body(px: int = 16, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont("Mukta")
    font.setPixelSize(px)
    font.setWeight(weight)
    return _tabular(font)


def reduce_motion() -> bool:
    """CANARY_REDUCE_MOTION=1: show the funnel's final state instead of playing it."""
    import os
    return os.environ.get("CANARY_REDUCE_MOTION", "") == "1"


def palette() -> QPalette:
    """One light palette on every system, so macOS or Windows dark mode never changes the sheet."""
    p = QPalette()
    for role, colour in ((QPalette.ColorRole.Window, BOND), (QPalette.ColorRole.WindowText, CARBON),
                         (QPalette.ColorRole.Base, WHITE), (QPalette.ColorRole.Text, CARBON),
                         (QPalette.ColorRole.Button, BOND), (QPalette.ColorRole.ButtonText, CARBON),
                         (QPalette.ColorRole.Highlight, BALLPOINT), (QPalette.ColorRole.HighlightedText, WHITE),
                         (QPalette.ColorRole.PlaceholderText, MUTED)):
        p.setColor(role, colour)
    return p


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")             # the same widget style on macOS and Windows
    app.setPalette(palette())
    load_fonts()
    app.setFont(body())
    app.setStyleSheet(STYLESHEET)
