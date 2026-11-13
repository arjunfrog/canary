# Canary

A private desktop app that traces a leaked exam paper back to the copy it came from. It runs on one laptop, on macOS or Windows, with no website and no cloud.

Team RADIOHEAD, Cybersecurity track, Colossus 3.0 final round. Building starts 11:30 on 13 Nov 2026 and the deadline is 09:00 on 14 Nov.

## Layout

```
canary/          the app, one Python package
  cli.py           every command: python -m canary <command>
  config.py        paths and fixed settings
  db.py            the local SQLite database        schema.sql   its tables
  vault.py         encrypted secrets                audit.py     tamper-evident action log
  chain.py         hash chains                      lock.py      wrong-passphrase rules
  bank.py          reads the question bank          worker.py    takes queued leaks one by one
  fingerprint.py   keyed choices, chance maths, verdict bars
  pdf.py seed.py reader.py analyze.py lurker.py evidence.py sim.py check.py
                   stubs: each names the task that builds it
  data/bank.db     the question bank (250 questions)
  ui/              the desktop window (PySide6)
    app.py           starts the app             main_window.py  the sheet, navigation, locking
    theme.py         palette and fonts          background.py   worker thread beside the window
    screenshot.py    saves an image of every screen
    widgets/         Bubble, OMRNumber, TimingMarks, RuledSection, VerdictBanner, ...
    pages/           lock (built), leaks, case, limits (placeholders)
    fonts/           Khand and Mukta, bundled
tests/           pytest
bank/            question sources and build_bank.py, which writes canary/data/bank.db
scripts/         one-off helpers
docs/            PROMPTS.md (build tasks), PITCH.md (demo and judge questions),
                 research/ (simulation), round1/ (round-1 score analysis)
video/           the explainer animation and the script that renders it
BRIEF.md         the project rules every task relies on (CLAUDE.md points to it)
```

## What is built so far

About a quarter: the foundation works and is tested, and everything else is a labelled stub.

| Part | State |
|---|---|
| Storage, vault, audit log, hash chains | Built, tested |
| Question bank and its loader | Built, tested |
| Fingerprint: keyed choice, chance maths, verdict bars | Built, tested |
| Fingerprint: making copies, decoding, funnel | Stub (task 2) |
| Worker and command line | Built, tested. Unbuilt commands name their task |
| PDFs, seed data, photo reader, analysis, Telegram listener | Stubs (tasks 3 to 7) |
| App window: lock screen, idle lock, navigation, theme, base widgets | Built, tested |
| App screens: Leaks, Case, Limits | Placeholders (tasks 8 to 12) |
| Evidence file, limits simulation, health check, packaging | Stubs (tasks 11 to 13) |

## Set up and run

macOS:

```
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest             # 55 tests
.venv/bin/python -m canary init        # create the vault, once
.venv/bin/python -m canary run         # open the app
```

On Windows the steps are the same with `.venv\Scripts\python` in place of `.venv/bin/python`. The Windows side has not been run yet.

`python -m canary screenshot DIR` saves an image of every screen without opening a window, for checking the design.

## The idea

Everyone who handles the paper gets a slightly different copy, so a leak shows which copy it came from. There are two stages.

1. **Before printing: about 50 translators.**
   - Physics, chemistry and maths questions carry decoy numbers. Each question has 8 decoy sets and 1 real set, and a translator only ever sees decoys.
   - Biology has trap questions: 6 fake questions per translator, from a pool of 24, mixed in with the real ones.
   - Before printing, the real numbers are put back and the traps are removed.
2. **After printing: 5,000 copies.** Every copy asks the same questions. Only the order of the four options differs.

A secret key plus the copy number decides all of this. To trace a leak, Canary recomputes every copy and counts how many clues match each one.

## The parts

| Part | What it does | Built with |
|---|---|---|
| Question bank | 180 questions, 24 traps and 46 reserves, written in the style of previous-year NEET papers | SQLite file, built by `bank/build_bank.py` |
| Fingerprint engine | Makes each copy from the key, and decodes a leak back to a copy | Python, NumPy, HMAC-SHA256 |
| PDF maker | Writes any copy as an exam paper | ReportLab |
| Seed script | Creates the copies, synthetic people and a handover log per copy | Python |
| Telegram listener | Sits in public channels and groups on a normal account, read only, and saves every paper-like post with its sender | Telethon |
| Photo reader | Turns a photo into questions, numbers and option order | Gemini vision |
| Matcher | Finds which bank question each one is, then collects the clues | RapidFuzz |
| Verdict | Decides how sure it is, and never guesses | Exact probability maths |
| Evidence file | A signed file with the result and the handover log | Ed25519 |
| App window | Lock screen, leaks list, case screen with the funnel, limits chart | PySide6 (Qt), a native window on macOS and Windows |
| Storage | One local database file, plus folders for images and files | SQLite |
| Vault | Holds the keys and the Telegram login, encrypted under a passphrase | AES-256-GCM, scrypt |

## How it runs

One command, `python -m canary run`, opens the app. Packaged, it is a normal app you double-click.

1. The window opens locked. You type the passphrase, which unlocks the vault.
2. The listener watches the Telegram chats you chose.
3. A post with a photo or long text is saved as a leak.
4. The worker reads it, matches the questions, decodes the copy and picks a verdict.
5. The app shows the new case and plays the funnel.

A typed leak can also be pasted into the app, which works with no network at all.

## Verdicts

- **Traced:** the chance of a wrong match is under 1 in a million.
- **Strong lead:** under 1 in a thousand, so a person should investigate.
- **Not enough to name anyone:** a real paper, but too few clues.
- **Not our paper:** the questions don't match the bank, so it is likely a fake.
- **Couldn't read this:** the photo is too poor to tell.

## What makes it secure

- Nothing is hosted. The app has no web server and opens no network port, so nothing can connect to it.
- The keys and the Telegram login sit in an encrypted vault, never in the database or on screen.
- The app locks after 10 minutes idle, and five wrong passphrases add a one-minute wait.
- Every action is written to a log where any edit is detectable.
- The only outside connections are Telegram (reading) and Gemini (leak images only).
- The code is private: a private repo, all rights reserved.

## Limits

From `docs/research/sim_results.txt`, with assumed misread rates:

- A translator leak of 14 typed questions is traced 99.9% of the time. It needs at least 9 clean numeric questions to be traced and 6 for a strong lead.
- A phone photo of a printed copy with 14 questions is traced 99% of the time.
- A leak with the numbers removed can't be traced. Traps alone are not enough.
- Two translators merging copies are rarely traced at 14 questions (3%) and usually at 30 (83%).
- A printed copy with the options reshuffled can't be traced.

## Checkpoints on the day

1. **After task 3:** a PDF's text decodes to the right copy. Freeze the algorithm, key and bank, and only then print copies.
2. **After task 7:** a text posted in the demo channel produces the right case.
3. **After task 10:** a real phone photo gives the right verdict in the app, with the funnel.
4. **Midnight:** tasks 1 to 13 done and `python -m canary check` passes three times. Tag the repo. Extras go on a separate branch.
5. **07:00:** code freeze. Rehearse, record a backup video, submit by 08:45.
