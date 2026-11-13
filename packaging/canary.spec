# PyInstaller spec for Canary. Build on the system you are building for: PyInstaller cannot cross-build.
#
#   macOS:    .venv/bin/pyinstaller --noconfirm packaging/canary.spec          -> dist/Canary.app
#   Windows:  .venv\Scripts\pyinstaller --noconfirm packaging\canary.spec       -> dist\Canary\Canary.exe
#
# Exact steps are in docs/BUILD.md.
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent

# The read-only files the app loads at run time, placed where canary/config.py looks for them.
datas = [
    (str(ROOT / "canary" / "data" / "bank.db"), "canary/data"),
    (str(ROOT / "canary" / "data" / "score_set.json"), "canary/data"),
    (str(ROOT / "canary" / "data" / "score_set_2.json"), "canary/data"),
    (str(ROOT / "canary" / "schema.sql"), "canary"),
    (str(ROOT / "canary" / "ui" / "fonts"), "canary/ui/fonts"),
]

# The app imports QtCore, QtGui and QtWidgets only. Every other Qt module is left out, which also
# keeps the GPL-licensed add-ons (Qt Charts, Qt Data Visualization) out of the bundle for certain.
QT_NOT_USED = [
    "Qt3DAnimation", "Qt3DCore", "Qt3DExtras", "Qt3DInput", "Qt3DLogic", "Qt3DRender", "QtBluetooth", "QtCharts",
    "QtConcurrent", "QtDataVisualization", "QtDBus", "QtDesigner", "QtGraphs", "QtGraphsWidgets", "QtHelp",
    "QtHttpServer", "QtLocation", "QtMultimedia", "QtMultimediaWidgets", "QtNetwork", "QtNetworkAuth", "QtNfc",
    "QtOpenGL", "QtOpenGLWidgets", "QtPdf", "QtPdfWidgets", "QtPositioning", "QtPrintSupport", "QtQml", "QtQuick",
    "QtQuick3D", "QtQuickControls2", "QtQuickTest", "QtQuickWidgets", "QtRemoteObjects", "QtScxml", "QtSensors",
    "QtSerialBus", "QtSerialPort", "QtSpatialAudio", "QtSql", "QtStateMachine", "QtSvg", "QtSvgWidgets", "QtTest",
    "QtTextToSpeech", "QtUiTools", "QtWebChannel", "QtWebEngineCore", "QtWebEngineQuick", "QtWebEngineWidgets",
    "QtWebSockets", "QtWebView", "QtXml", "QtAxContainer",
]
excludes = [f"PySide6.{name}" for name in QT_NOT_USED] + ["PyQt5", "PyQt6", "PySide2", "tkinter", "pytest", "IPython"]

a = Analysis(
    [str(ROOT / "packaging" / "launch.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=["canary.ui.app", "canary.ui.screenshot", "telethon", "objc", "Foundation", "Quartz", "Vision"],
    excludes=excludes,
    noarchive=False,
)
# Qt plugins pull in Qt libraries of their own. Drop the ones Canary has no use for: the TUIO touch plugin
# (the only thing here that links Qt Network), the SVG plugins (Qt Svg) and every image format except
# JPEG, PNG and WebP, the three kinds of leak image the app accepts.
import re

_PLUGIN = re.compile(r"(^|[\\/])(lib)?q(tuiotouchplugin|svgicon|svg|gif|icns|ico|macheif|macjp2|tga|tiff|wbmp)\.(dylib|dll|so)$")
_LIBRARY = re.compile(r"Qt6?(Network|Svg)(\.framework|\.dll|[\\/]|$)")


def _wanted(entry) -> bool:
    name = entry[0]
    return not (_PLUGIN.search(name) or _LIBRARY.search(name))


a.binaries = [b for b in a.binaries if _wanted(b)]
a.datas = [d for d in a.datas if _wanted(d)]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Canary",
    console=False,          # a window, not a terminal. On Windows, run commands with python -m canary instead.
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Canary", upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Canary.app",
        bundle_identifier="team.radiohead.canary",
        info_plist={
            "CFBundleDisplayName": "Canary",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": True,      # light theme only, whatever the system is set to
            "LSMinimumSystemVersion": "12.0",
        },
    )
