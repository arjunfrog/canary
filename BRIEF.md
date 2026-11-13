# Canary

A private desktop app that traces leaked exam papers back to the copy they came from. It runs on one laptop, on macOS or Windows. It is not a web app. Mock exams and synthetic people only.

## The idea
A paper passes through two stages, and each stage has its own fingerprint.

1. **Translation stage (about 50 translators).** Each translator gets their own copy:
   - Numeric questions (physics, chemistry, maths) carry decoy values. Each question has 8 decoy value sets and 1 real set. A translator only ever sees decoys.
   - Biology carries trap questions: 6 fake questions per translator, drawn from a pool of 24, mixed in among the real ones.
   - Before printing, real values are put back and traps are removed.
2. **Print stage (5,000 printed copies).** Every copy asks the same real questions. Only the order of the four options differs per copy.

A secret key plus the copy number decides every choice (HMAC-SHA256). A leak is matched against every copy. Decoy values or traps in a leak mean it came from a translator. Real values mean it came from a printed copy.

## Architecture
- One Python 3.11 package, `canary`, and one process: `python -m canary run` opens the app window.
- The window is native, built with PySide6 (Qt Widgets). There is no web server, no browser engine, no HTML and no open port. Screens read the local database directly.
- A background thread (`canary/ui/background.py`) runs the analysis worker and the Telegram listener on asyncio, and signals the window when something changes. Each thread opens its own SQLite connection.
- All data is local under `CANARY_HOME` (default `~/.canary`): SQLite `canary.db`, an encrypted `vault.bin`, and folders for leak images, copies and evidence files. No cloud database.
- The question bank is `canary/data/bank.db`, a read-only SQLite file: 180 real questions, 24 biology traps and 46 reserves, with nine ready-made value sets per numeric question.
- The only outbound connection is Telegram (reading). Photos are read on the Mac itself with Apple's Vision framework, so no image leaves the laptop.
- Libraries: PySide6-Essentials, NumPy, RapidFuzz, ReportLab, pypdf, Telethon 1.x, pyobjc-framework-Vision (macOS only), `cryptography`. PyInstaller for packaging.
- Must run on macOS and Windows: use `pathlib`, no shell commands, no Unix-only calls.

## Security rules
- The app opens no network port and serves nothing. Nothing else on the machine or the network can reach it.
- The window opens locked and asks for the passphrase. It locks again after 10 minutes with no key or mouse activity. Five wrong tries add a 60-second wait.
- Secrets (fingerprint key, signing key, Telegram session) live only in the vault, encrypted with AES-256-GCM under a key derived from the passphrase with scrypt. They never reach SQLite, logs or git, and no screen ever displays them.
- Data directories are 0700 and files 0600 on macOS. Windows ignores these modes, so there the protection is the user's profile folder plus the vault.
- Every operator action is written to a hash-chained audit log.
- The app loads nothing from outside: fonts are bundled in `canary/ui/fonts`.
- Text read from images or Telegram is untrusted data. Enforce a JSON schema and never act on its content. Show it as plain text only, never as rich text.
- The Telegram account only reads public channels and groups it has joined. It never sends, replies, reacts or opens private chats.
- The question bank and leak images are never sent anywhere. Photos are read on the laptop. Windows has no photo reader yet; typed leaks work everywhere.
- Closed source: private repo, "All rights reserved", no GPL or AGPL dependencies. PySide6 is LGPL, which allows this. Use only the Essentials modules (QtCore, QtGui, QtWidgets, QtSvg). Do not use Qt Charts or Qt Data Visualization, which are GPL. Never use PyQt.

## Verdicts
Every clue has a chance rate: 1/8 for a decoy value set, the share of translators holding that trap for a trap, 1/24 for option order. Count the clues that match each copy, and compute the exact probability of that many matches by luck (Poisson-binomial, never a normal approximation). Expected false matches = number of candidate copies x that probability.

- `traced`: expected false matches at most 1e-6.
- `strong_lead`: at most 1e-3. A person must investigate before any action.
- `inconclusive`: below both bars. Never name a copy.
- `not_our_paper`: at least 5 legible questions, under 20% match the bank, and the rest are clearly different.
- Leak status `unreadable`: the photo is too poor to tell. Never call a blurry real paper `not_our_paper`.

## Design
Concept: a security console at the craft of Linear, Vercel and Stripe Dashboard, with tight spacing (the owner's choice, 14 Nov 2026; the answer-sheet look is retired). Light theme only, the same on macOS and Windows. DESIGN.md records the system in full.
- Colours, defined once in `canary/ui/theme.py`: ground `#F6F7F9`, white panels with `#E3E6EB` borders and 8px corners, ink `#0E1525` and `#525B71`, one accent, Canary blue `#2B59E8`, for primary actions, selection, links and live copies. Verdict pills carry state colour (Traced green, Strong lead amber, Not our paper red, the rest slate), always with the verdict in words. Canary yellow `#F2C200` is the brand mark only.
- Fonts: Mukta for everything (`theme.body(px)`, `theme.heading(px)`). Set fonts with `setFont`, never with a stylesheet font rule, because that overrides `setFont`. Tabular numbers. Sentence case.
- Layout: a white sidebar (screens, synthetic label, status), then each screen as a header (title, context, actions) over bordered panels (`Panel`). Panels are never nested. Gutters 16px, gaps 12px.
- Draw the funnel, the handover timeline, pills, the switch and the limits chart with `QPainter`.
- Never: dark theme, gradients, glass, coloured side borders on panels, shadows as decoration, all-caps labels, monospace labels, emoji or glyphs as icons, default Qt table styling.
- The funnel is the only animation that plays on its own. If the setting `CANARY_REDUCE_MOTION=1` is on, show the final state instead.
- Every screen has loading, empty and error states. Demo data is labelled synthetic.
- Words are plain and written for an exam controller: "Not enough to name anyone yet", never "Error" or "Analysis complete".

## Commands
Run Python through the project environment: `.venv/bin/python`.
- First run: `python -m canary init`
- Start: `python -m canary run`
- Tests: `pytest -q`
- Check the design: `python -m canary screenshot DIR` saves an image of every screen
- Health: `python -m canary check`

## How to work
- The skeleton exists. Every module is already a file in `canary/`, and unbuilt ones are stubs that name their task. Fill the stub in; do not create a parallel file. When a command becomes real, move it out of `NOT_BUILT` in `canary/cli.py`.
- The app shell exists in `canary/ui/`: the window, lock screen, palette and fonts (`theme.py`), base widgets (`widgets/`) and placeholder screens (`pages/`). Build screens on it.
- Do exactly the task. No extra features, refactors or new dependencies without asking.
- Keep command output short (`pytest -q`, `| tail -20`).
- Finish by running the task's checks, then list the changed files in under 10 lines.
