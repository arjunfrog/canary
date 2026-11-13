"""The console look: one palette, one typeface, the base stylesheet. Light only, the same on macOS and Windows.

Colours are defined here once. Fonts are always set in code with body() or heading(), never in a stylesheet
rule on a plain widget, because a stylesheet font overrides setFont.
"""
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

# ground and surfaces
BG = QColor("#F6F7F9")            # window ground
SURFACE = QColor("#FFFFFF")       # panels, sidebar, inputs
SUNKEN = QColor("#F2F4F7")        # table headers, hovered rows, quiet fills
BORDER = QColor("#E3E6EB")        # panel and row borders
BORDER_STRONG = QColor("#CDD2DA") # inputs, dividers that must be seen
CELL = QColor("#E4E8EE")          # a ruled-out copy in the funnel

# ink
INK = QColor("#0E1525")           # primary text
INK_2 = QColor("#525B71")         # secondary text (4.5:1 on white and on BG)
INK_3 = QColor("#8A92A6")         # placeholders, disabled, ruled-out items (large or non-text only)

# the one accent
ACCENT = QColor("#2B59E8")        # primary actions, selection, links, live copies
ACCENT_HOVER = QColor("#1F47C9")
ACCENT_SOFT = QColor("#EBF0FE")   # selected rows, exposed questions
ACCENT_INK = QColor("#1D43BE")    # accent text on light grounds
ACCENT_LINE = QColor("#C9D6FB")   # the border of a checked choice row

# brand mark only
CANARY = QColor("#F2C200")

# state tones: (text, fill) pairs, used only where they carry meaning
TONES = {
    "traced": (QColor("#0B6B39"), QColor("#E2F5E9")),
    "strong_lead": (QColor("#8A4A00"), QColor("#FDF0D9")),
    "inconclusive": (QColor("#475069"), QColor("#ECEEF3")),
    "not_our_paper": (QColor("#A3191D"), QColor("#FCE7E7")),
    "unreadable": (QColor("#475069"), QColor("#ECEEF3")),
    "failed": (QColor("#A3191D"), QColor("#FCE7E7")),
    "waiting": (QColor("#475069"), QColor("#ECEEF3")),
}
DANGER = TONES["failed"][0]
SUCCESS = TONES["traced"][0]

FONT_DIR = Path(__file__).parent / "fonts"
FAMILY = "Mukta"

STYLESHEET = f"""
QToolTip {{ background: {INK.name()}; color: white; border: none; padding: 4px 8px; }}

QLabel[role="muted"] {{ color: {INK_2.name()}; }}
QLabel[role="subtle"] {{ color: {INK_3.name()}; }}
QLabel[role="error"] {{ color: {DANGER.name()}; }}
QLabel[role="link"] {{ color: {ACCENT_INK.name()}; }}

QFrame#sidebar {{ background: {SURFACE.name()}; border: none; border-right: 1px solid {BORDER.name()}; }}
QFrame#panel {{ background: {SURFACE.name()}; border: 1px solid {BORDER.name()}; border-radius: 8px; }}
QFrame#lockcard {{ background: {SURFACE.name()}; border: 1px solid {BORDER.name()}; border-radius: 10px; }}
QFrame#divider {{ background: {BORDER.name()}; border: none; }}

QPushButton {{ background: {SURFACE.name()}; color: {INK.name()}; border: 1px solid {BORDER_STRONG.name()};
               border-radius: 6px; padding: 4px 12px; min-height: 22px; }}
QPushButton:hover {{ background: {SUNKEN.name()}; }}
QPushButton:pressed {{ background: {BORDER.name()}; }}
QPushButton:disabled {{ color: {INK_3.name()}; background: {SUNKEN.name()}; border-color: {BORDER.name()}; }}
QPushButton:focus {{ outline: none; border-color: {ACCENT.name()}; }}
QPushButton[primary="true"] {{ background: {ACCENT.name()}; color: white; border: 1px solid {ACCENT.name()}; }}
QPushButton[primary="true"]:hover {{ background: {ACCENT_HOVER.name()}; border-color: {ACCENT_HOVER.name()}; }}
QPushButton[primary="true"]:disabled {{ background: {BORDER.name()}; color: {INK_3.name()}; border-color: {BORDER.name()}; }}
QPushButton[primary="true"]:focus {{ border-color: {INK.name()}; }}
QPushButton[link="true"] {{ background: transparent; color: {ACCENT_INK.name()}; border: none; padding: 2px 0px; min-height: 0px; }}
QPushButton[link="true"]:hover {{ color: {ACCENT_HOVER.name()}; text-decoration: underline; }}
QPushButton[link="true"]:disabled {{ color: {INK_3.name()}; }}
QPushButton[nav="true"] {{ background: transparent; color: {INK_2.name()}; border: none; border-radius: 6px;
                            text-align: left; padding: 5px 10px; }}
QPushButton[nav="true"]:hover {{ background: {SUNKEN.name()}; color: {INK.name()}; }}
QPushButton[nav="true"]:checked {{ background: {ACCENT_SOFT.name()}; color: {ACCENT_INK.name()}; }}
QPushButton[choice="true"] {{ background: transparent; color: {INK.name()}; border: 1px solid transparent; border-radius: 6px;
                               text-align: left; padding: 6px 10px; }}
QPushButton[choice="true"]:hover {{ background: {SUNKEN.name()}; }}
QPushButton[choice="true"]:checked {{ background: {ACCENT_SOFT.name()}; color: {ACCENT_INK.name()}; border-color: {ACCENT_LINE.name()}; }}

QLineEdit {{ background: {SURFACE.name()}; color: {INK.name()}; border: 1px solid {BORDER_STRONG.name()}; border-radius: 6px;
             padding: 6px 10px; selection-background-color: {ACCENT.name()}; selection-color: white; }}
QLineEdit:focus {{ border: 1px solid {ACCENT.name()}; }}
QLineEdit:disabled {{ background: {SUNKEN.name()}; color: {INK_3.name()}; border-color: {BORDER.name()}; }}
QPlainTextEdit {{ background: {SURFACE.name()}; color: {INK.name()}; border: 1px solid {BORDER.name()}; border-radius: 6px;
                  padding: 6px 8px; selection-background-color: {ACCENT.name()}; selection-color: white; }}
QPlainTextEdit[editable="true"] {{ border: 1px solid {BORDER_STRONG.name()}; }}
QPlainTextEdit[editable="true"]:focus {{ border: 1px solid {ACCENT.name()}; }}
QPlainTextEdit[embedded="true"] {{ border: none; border-radius: 0px; padding: 0px; background: transparent; }}

QScrollArea {{ border: none; background: transparent; }}
QTableView {{ background: transparent; border: none; outline: none; selection-background-color: {ACCENT_SOFT.name()};
              selection-color: {INK.name()}; }}
QHeaderView {{ background: {SUNKEN.name()}; border: none; }}
QHeaderView::section {{ background: {SUNKEN.name()}; color: {INK_2.name()}; border: none; border-bottom: 1px solid {BORDER.name()};
                        padding: 4px 10px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER_STRONG.name()}; min-height: 28px; border-radius: 3px; }}
QScrollBar::handle:vertical:hover {{ background: {INK_3.name()}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER_STRONG.name()}; min-width: 28px; border-radius: 3px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

QDialog {{ background: {BG.name()}; }}
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


def body(px: int = 14, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Mukta, for every piece of text. Sizes are in pixels so macOS and Windows match."""
    font = QFont(FAMILY)
    font.setPixelSize(px)
    font.setWeight(weight)
    return _tabular(font)


def heading(px: int = 15) -> QFont:
    return body(px, QFont.Weight.DemiBold)


def figure(px: int = 22) -> QFont:
    """A key figure: a copy number, a count, a chance. SemiBold: the heaviest Mukta the app bundles."""
    return body(px, QFont.Weight.DemiBold)


def reduce_motion() -> bool:
    """CANARY_REDUCE_MOTION=1: show the funnel's final state instead of playing it."""
    import os
    return os.environ.get("CANARY_REDUCE_MOTION", "") == "1"


def palette() -> QPalette:
    """One light palette on every system, so macOS or Windows dark mode never changes the app."""
    p = QPalette()
    for role, colour in ((QPalette.ColorRole.Window, BG), (QPalette.ColorRole.WindowText, INK),
                         (QPalette.ColorRole.Base, SURFACE), (QPalette.ColorRole.AlternateBase, SUNKEN),
                         (QPalette.ColorRole.Text, INK), (QPalette.ColorRole.Button, SURFACE),
                         (QPalette.ColorRole.ButtonText, INK), (QPalette.ColorRole.Highlight, ACCENT),
                         (QPalette.ColorRole.HighlightedText, QColor("white")), (QPalette.ColorRole.Link, ACCENT_INK),
                         (QPalette.ColorRole.PlaceholderText, INK_3), (QPalette.ColorRole.ToolTipBase, INK),
                         (QPalette.ColorRole.ToolTipText, QColor("white"))):
        p.setColor(role, colour)
    return p


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")             # the same widget style on macOS and Windows
    app.setPalette(palette())
    load_fonts()
    app.setFont(body())
    app.setStyleSheet(STYLESHEET)
