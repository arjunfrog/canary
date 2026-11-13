# Building the Canary app

PyInstaller cannot cross-build. Build `Canary.app` on a Mac and `Canary.exe` on a Windows PC.
The spec is `packaging/canary.spec`. It bundles the question bank (`canary/data/bank.db`), the database
schema (`canary/schema.sql`) and the fonts (`canary/ui/fonts`), and leaves out every Qt module the app
does not import, so no GPL Qt add-on can end up in the bundle.

The packaged app keeps its data in the same place as the source version: `CANARY_HOME`, by default
`~/.canary` on macOS and `C:\Users\NAME\.canary` on Windows. Nothing is stored inside the app itself.

## macOS

```
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/pyinstaller --noconfirm packaging/canary.spec
```

Result: `dist/Canary.app`. Check it before copying it anywhere:

```
dist/Canary.app/Contents/MacOS/Canary --version
dist/Canary.app/Contents/MacOS/Canary screenshot /tmp/canary-shots     # draws every screen with no window
dist/Canary.app/Contents/MacOS/Canary check                            # asks for the passphrase, prints PASS
open dist/Canary.app                                                   # the lock screen appears
```

The app is not signed or notarised. On another Mac, right-click it and choose Open the first time.

## Windows

In PowerShell, from the repo folder:

```
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
.venv\Scripts\python -m pytest -q
.venv\Scripts\pyinstaller --noconfirm packaging\canary.spec
```

Result: `dist\Canary\Canary.exe`, with its libraries in the same folder. Copy the whole `dist\Canary`
folder, not the `.exe` alone. Double-click `Canary.exe` to open the lock screen.

`Canary.exe` is built as a window app, so it prints nothing to a terminal. On Windows, run commands such
as `init`, `seed`, `check` and `tg-login` from the source tree with `.venv\Scripts\python -m canary ...`.
They use the same `CANARY_HOME` as the packaged app.

The Windows build has not been run yet. The Mac build has: see PROGRESS.md.

## First run of a packaged app

The vault has to exist before the window can unlock:

```
python -m canary init        # creates the vault and prints the signing key fingerprint
python -m canary seed        # the exam, copies, synthetic people and handover logs
python -m canary sim         # the numbers behind the Limits screen
```

## What is and is not in the bundle

- In: Python 3.11, PySide6 Essentials (QtCore, QtGui, QtWidgets only), NumPy, RapidFuzz, ReportLab, pypdf,
  Telethon, google-genai, cryptography, the bank, the schema and the fonts.
- Not in: any secret. The vault, the database and every leak stay in `CANARY_HOME`.
- Not in: Qt Charts, Qt Data Visualization, Qt WebEngine, Qt Network or any other Qt add-on.
