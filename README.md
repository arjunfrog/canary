<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/Qt-PySide6-41CD52?logo=qt&logoColor=white" alt="PySide6"/>
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey" alt="Platform"/>
  <img src="https://img.shields.io/badge/license-proprietary-red" alt="License"/>
  <img src="https://img.shields.io/badge/tests-244%20passed-brightgreen" alt="Tests"/>
</p>

#  Canary

**Trace a leaked exam paper back to the exact copy it came from — in seconds, on one laptop, with no cloud.**

Canary is a private desktop forensics tool that fingerprints every copy of an exam paper at creation time, then uses those fingerprints to identify the source when a leak surfaces. It monitors Telegram channels for leaks, reads photos with AI vision, and delivers a verdict with mathematically exact confidence — or honestly says it can't.

> Built by **Team RADIOHEAD** · Cybersecurity Track · Colossus 3.0 Final Round

---

##  The Problem

India's exam system is under siege. Over **89 paper leak cases** affecting **6.5 crore+ candidates** have been documented in the last decade. NEET UG 2026 was cancelled nine days after the exam over leak allegations, requiring a CBI probe just to find the source. Current defenses — barcodes, watermarks, printed marks — are trivially defeated by cropping or retyping.

**Canary hides the fingerprint inside the questions themselves.** There's nothing to crop away.

---

##  How It Works

Every copy of the paper is subtly different. A secret key + copy number determines all variations using HMAC-SHA256.

### Stage 1 — Before Printing (~50 translators)

| Fingerprint | Mechanism | Strength |
|---|---|---|
| **Decoy values** | Numeric questions (physics, chemistry, maths) carry decoy numbers. 8 fake sets + 1 real set per question. Translators only see decoys. | 1-in-8 chance rate per question |
| **Trap questions** | Biology gets 6 fake questions per translator from a pool of 24, mixed with the real ones. Removed before printing. | Proves the leak is pre-print |

### Stage 2 — After Printing (5,000 copies)

| Fingerprint | Mechanism | Strength |
|---|---|---|
| **Option order** | Every copy asks identical questions. Only the A/B/C/D order differs. | 1-in-24 chance rate per question |

> [!NOTE]
> Real values are restored and traps are removed before printing. **Students always get identical, correct papers.**

---

##  Verdicts

Canary computes the **exact probability** of a match occurring by chance (Poisson-binomial, never a normal approximation) and returns one of:

| Verdict | Meaning | Threshold |
|---|---|---|
| 🟢 **Traced** | Identified with near-certainty | < 1-in-a-million false match rate |
| 🟡 **Strong lead** | High confidence; a person must investigate | < 1-in-a-thousand false match rate |
| ⚪ **Not enough to name anyone** | Real paper, too few clues | Below both bars |
| 🔴 **Not our paper** | Questions don't match the bank — likely a fake | < 20% bank match |
| ⬛ **Couldn't read this** | Photo too poor to tell | Never calls a blurry paper fake |

**Canary never guesses.** When it can't be sure, it says so.

---

## 📊 Simulation Results

From 4,000 trials across scenarios (full data in [`docs/research/sim_results.txt`](docs/research/sim_results.txt)). `python -m canary sim` reruns it with the tool's own thresholds for the Limits screen. Misread rates are assumed, not measured:

| Scenario | Questions | Traced | Strong Lead |
|---|---|---|---|
| Typed translator leak (2% misread) | 14 | 99.9% | 100% |
| Phone photo of translator copy | 14 | 100% | 100% |
| Phone photo of printed copy (10% misread) | 14 | 99.4% | 100% |
| Two translators merge copies | 14 | 3.1% | 59.7% |
| Two translators merge copies | 30 | 83.4% | 100% |

**Known limits** — Canary reports these honestly:
- Numbers stripped from a pre-print leak → can't trace
- Options reshuffled after printing → can't trace
- Three+ translators merging copies → rarely traced

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Canary Desktop App                │
│                    (PySide6 / Qt)                    │
├──────────┬──────────┬───────────┬───────────────────┤
│  Lock    │  Leaks   │   Case    │      Limits       │
│  Screen  │  List    │   View    │      Chart        │
├──────────┴──────────┴───────────┴───────────────────┤
│              Background Thread (asyncio)             │
│         ┌──────────┐        ┌──────────────┐        │
│         │  Worker  │        │   Telegram   │        │
│         │ Pipeline │        │   Listener   │        │
│         └────┬─────┘        └──────┬───────┘        │
│              │                     │                 │
│    ┌─────────▼─────────────────────▼────────┐       │
│    │          Local SQLite Database          │       │
│    └─────────────────┬──────────────────────┘       │
│                      │                               │
│    ┌─────────────────▼──────────────────────┐       │
│    │      Encrypted Vault (AES-256-GCM)     │       │
│    │   keys · telegram session · signing key │       │
│    └────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────┘
         ▲ read only              ▲ leak images only
    Telegram channels      (photos are read on the Mac itself)
```

- **Zero network surface** — no web server, no open ports, no cloud database
- **Single process** — `python -m canary run` is the whole app
- **All data local** under `~/.canary` (or `CANARY_HOME`)

---

## 📁 Project Structure

```
canary/                    the app — one Python package
  cli.py                     all commands: python -m canary <command>
  config.py                  paths and fixed settings
  db.py                      local SQLite database
  schema.sql                 table definitions
  vault.py                   encrypted secrets (AES-256-GCM, scrypt)
  audit.py                   tamper-evident hash-chained action log
  chain.py                   hash chain primitives
  lock.py                    wrong-passphrase rate limiting
  bank.py                    question bank loader
  fingerprint.py             makes every copy from the key, decodes a leak, exact probability math
  worker.py                  processes queued leaks one by one
  leaks.py                   adding a leak by hand
  queries.py                 the one place the app reads the database
  pdf.py                     exam papers as PDF (ReportLab)
  seed.py                    creates copies, people, custody chains
  reader.py                  photo → text, on the Mac itself (Apple Vision)
  analyze.py                 full leak analysis pipeline
  lurker.py                  Telegram channel listener (Telethon)
  evidence.py                signed evidence files (Ed25519)
  sim.py                     limits simulation
  check.py                   health check, reset, replay
  score.py                   the scored test sets (see SCORES.md)
  samples.py                 sample leaks with known answers
  data/bank.db               question bank (250 questions)
  data/score_set*.json       frozen test leaks with known answers
  ui/                        desktop window (PySide6)
    app.py                     app entry point
    main_window.py             window, navigation, locking
    theme.py                   palette and fonts
    background.py              worker and Telegram listener beside the window
    screenshot.py              renders every screen to PNG
    widgets/                   Panel, Pill, Switch, Funnel, CustodyTimeline, ClueTable, LeakView, LimitsChart…
    pages/                     Lock, Leaks, Case, Limits
    fonts/                     Mukta (bundled)
tests/                     pytest suite (244 tests)
bank/                      question sources & build_bank.py
scripts/                   the scripts that built the frozen test leaks
packaging/                 canary.spec for PyInstaller
docs/                      PITCH.md, PROMPTS.md, BUILD.md, research/, round1/
PROGRESS.md                what is done, decisions made, what is faked
SCORES.md                  every scored round
video/                     explainer animation & render script
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```bash
# Clone the repo
git clone <repo-url> && cd canary

# Create a virtual environment and install
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e ".[dev]"

# On Windows, use .venv\Scripts\python instead of .venv/bin/python
```

### Run

```bash
# Run the test suite (244 tests)
python -m pytest

# Initialize the encrypted vault (first time only). Prints the signing key fingerprint
python -m canary init

# Create the exam, copies, synthetic people and handover logs, then the Limits numbers
python -m canary seed
python -m canary sim

# End-to-end health check: prints PASS
python -m canary check

# Launch the app
python -m canary run

# Preview all screens without opening a window
python -m canary screenshot screenshots/
```

### CLI Commands

| Command | Description |
|---|---|
| `canary init` | Create the encrypted vault |
| `canary run` | Open the desktop app |
| `canary run --headless` | Run the worker and listener with no window |
| `canary run --replay NAME` | Replay one saved case, with no database or network |
| `canary seed` | Create the exam, copies, synthetic people and handover logs |
| `canary print-copies --translator 7,23 --print 12,4821 --out DIR` | Papers as PDF, each with a sealed slip |
| `canary vault set NAME` | Update a secret in the vault |
| `canary add-leak --text FILE` | Queue a typed leak |
| `canary add-leak --image FILE` | Queue a photo leak |
| `canary cases` | List recent leaks and their verdicts |
| `canary decode --text FILE` | Decode a typed leak and print the funnel |
| `canary read PHOTO` | Read one photo on this Mac and print the questions found |
| `canary tg-login`, `canary watch USERNAME`, `canary unwatch USERNAME` | Log the Telegram account in, and choose the chats to watch |
| `canary evidence ID` | Issue the signed evidence file for a case |
| `canary verify FILE [--expect FINGERPRINT]` | Check an evidence file. Needs no passphrase |
| `canary export-case ID` | Save a case as a replay file |
| `canary sim` | Run the limits simulation |
| `canary check` | End-to-end health check |
| `canary score` | Score the tool on the frozen test leaks |
| `canary reset` | Delete all leaks, cases and evidence files |
| `canary verify-audit` | Verify the audit log hash chain |
| `canary verify-chain --stage S --copy N` | Verify one copy's handover log |
| `canary screenshot DIR` | Save a PNG of every screen |

### Connecting the real services

Photos need nothing connecting: they are read on the Mac itself, with Apple's built-in text recognition (the
engine behind Live Text). No key, no account, nothing sent anywhere. It reads English, Hindi and Marathi print.
For other scripts, such as Kannada, physics, chemistry and maths questions are still recognised by their numbers
and options; text-only questions are not. Windows has no photo reader yet. Typed leaks work everywhere.

```bash
python -m canary read PHOTO.jpg               # read one photo on this Mac and print what it found
```

Telegram needs the one login only you can supply:

```bash
python -m canary vault set tg_api_id          # from my.telegram.org, "API development tools"
python -m canary vault set tg_api_hash
python -m canary tg-login                     # phone, code, two-step password. Saved in the vault only
python -m canary watch YOUR_DEMO_CHANNEL      # joins it if needed and starts watching
python -m canary run                          # the listener starts when the window unlocks
```

If a network blocks Telegram's usual port, Canary tries ports 5222 and 80 and remembers the one that works.

---

## 🔒 Security Model

| Layer | Protection |
|---|---|
| **Network** | No web server, no open ports. Nothing on the machine or network can reach the app. |
| **Vault** | All secrets (fingerprint key, signing key, Telegram session) encrypted with AES-256-GCM under scrypt-derived passphrase. Never in SQLite, logs, or on screen. |
| **Access** | Window opens locked. Auto-locks after 10 min idle. 5 wrong passphrases → 60s cooldown. |
| **Audit** | Every action is written to a hash-chained log. Any edit is detectable. |
| **Data** | Directories are `0700`, files are `0600` (macOS). On Windows, protection is the user profile + vault encryption. |
| **External calls** | Telegram only (read-only, public channels only). Photos are read on the Mac itself, so no image or question ever leaves the laptop. |
| **Supply chain** | No GPL dependencies. PySide6 Essentials only (LGPL). Fonts bundled. |
| **Telegram** | The client is wrapped so it can only read. Sending, replying, reacting, marking as read and private chats do not exist in it. |
| **Untrusted text** | Whatever is read from an image or a chat is checked against a schema, stored, and shown as plain text. It is never followed. |
| **Naming nobody** | An inconclusive case names no copy anywhere: not on screen, not in the database, not in the funnel picture. |

Stated limits:

- The idle lock is a screen lock. The secrets stay in memory so leaks keep being read while it is locked.
- The database is not encrypted. It is protected by file modes (which Windows ignores) and holds no secret.
- The question bank, real values included, sits unencrypted in the repo and the packaged app. A real exam's bank would have to live in the vault.
- Rows cut off the end of the audit log are not detected by the chain alone. `verify-audit` prints the newest hash to keep somewhere else.
- An evidence file is only as trustworthy as the published signing key fingerprint. Check it with `verify --expect FINGERPRINT`.

---

## 🎯 How well it does

`python -m canary score` runs the tool on 126 frozen leaks with known answers. A third are set aside and never read. Every round is in [`SCORES.md`](SCORES.md).

| | Leaks that may be read | Set-aside leaks | Wrong copy named |
|---|---|---|---|
| First set, at the start | 56 of 60 (93.3%) | 28 of 30 (93.3%) | never |
| Second, harder set, at its start | 12 of 24 (50.0%) | 5 of 12 (41.7%) | never |
| Both sets now | 84 of 84 | 42 of 42 | never |

A further 1,300 random leaks (damaged, retold, merged from two or three copies, fakes with random numbers) named a wrong copy 0 times. The score sets are typed text and photo-reader output; real photos were checked separately on this Mac.

---

## 🆚 How Canary Compares

| Approach | Method | Limitation |
|---|---|---|
| CBSE + Microsoft (2018 pilot) | Encrypted download, centre-code watermark | Mark is on the page — croppable |
| Sindh, Pakistan (2026) | Unique watermark per paper | Same: visible mark, croppable |
| Barcodes / printed marks | ID printed on the page | Cropped or retyped away |
| **Canary** | **ID embedded in the questions: decoy values, trap questions, option order** | **Numbers stripped, merged copies, reshuffled options** |

> We didn't find content-based fingerprinting deployed in a real exam. We won't claim nobody has.

---

## 🛤️ Path to Deployment

1. **College internal exam** — Paper setters and moderators each get a decoy-value copy. Real custody log using existing process.
2. **One state board, one exam** — Translators get decoy copies. Printed packets differ in option order per centre.
3. **National scale** — Encrypted delivery before the exam (as CBSE piloted in 2018), enabling question replacement via re-issue rather than reprint.

---

## 📦 Build Status

All 13 tasks in `docs/PROMPTS.md` are built. The optional extras are not. Details are in [`PROGRESS.md`](PROGRESS.md).

| Component | Status |
|---|---|
| Storage, vault, audit log, hash chains | ✅ Built & tested |
| Question bank & loader | ✅ Built & tested |
| Fingerprint engine: copies, decoding, funnel, exact maths | ✅ Built & tested |
| Papers as PDF with sealed slips | ✅ Built & tested: page 1 of a PDF decodes back to its copy |
| Seed data: 300 synthetic people, 5,050 copies, 20,150 handovers | ✅ Built & tested |
| Leak analysis and the poor-read rules | ✅ Built, tested & scored |
| App screens: Lock, Leaks, Case with the funnel, Limits | ✅ Built & tested |
| Evidence files, `verify`, recommended response | ✅ Built & tested |
| Limits simulation, health check, reset, replay | ✅ Built & tested. `check` passes three times in a row |
| Photo reader | ✅ Built & tested on this Mac with Apple's own text recognition, on real and drawn pages. Mac only: Windows has no photo reader yet |
| Telegram listener | ⚠️ Built, tested against fake messages only. Never run against Telegram |
| Packaging | ⚠️ `Canary.app` builds and passes its own `check` on macOS. The Windows build has not been run |

---
