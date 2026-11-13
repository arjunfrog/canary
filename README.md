<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/Qt-PySide6-41CD52?logo=qt&logoColor=white" alt="PySide6"/>
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey" alt="Platform"/>
  <img src="https://img.shields.io/badge/license-proprietary-red" alt="License"/>
  <img src="https://img.shields.io/badge/tests-54%20passed-brightgreen" alt="Tests"/>
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

From 4,000 trials across scenarios (full data in [`docs/research/sim_results.txt`](file:///c:/Users/Adarsh/OneDrive/Desktop/Canary/canary/docs/research/sim_results.txt)):

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
│    │   keys · telegram session · gemini key  │       │
│    └────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────┘
         ▲ read only              ▲ leak images only
    Telegram channels          Gemini Vision API
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
  fingerprint.py             keyed choices, probability math, verdict bars
  worker.py                  processes queued leaks one by one
  pdf.py                     exam papers as PDF (ReportLab)
  seed.py                    creates copies, people, custody chains
  reader.py                  photo → questions (Gemini Vision)
  analyze.py                 full leak analysis pipeline
  lurker.py                  Telegram channel listener (Telethon)
  evidence.py                signed evidence files (Ed25519)
  sim.py                     limits simulation
  check.py                   end-to-end health check
  data/bank.db               question bank (250 questions)
  ui/                        desktop window (PySide6)
    app.py                     app entry point
    main_window.py             window, navigation, locking
    theme.py                   palette and fonts
    background.py              worker thread
    screenshot.py              renders every screen to PNG
    widgets/                   Bubble, OMRNumber, TimingMarks, VerdictBanner…
    pages/                     Lock, Leaks, Case, Limits
    fonts/                     Khand & Mukta (bundled)
tests/                     pytest suite (55 tests)
bank/                      question sources & build_bank.py
docs/                      PITCH.md, PROMPTS.md, research/, round1/
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
# Run the test suite (55 tests)
python -m pytest

# Initialize the encrypted vault (first time only)
python -m canary init

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
| `canary run --headless` | Run the worker with no window |
| `canary vault set NAME` | Update a secret in the vault |
| `canary add-leak --text FILE` | Queue a typed leak |
| `canary add-leak --image FILE` | Queue a photo leak |
| `canary cases` | List recent leaks and their verdicts |
| `canary verify-audit` | Verify the audit log hash chain |
| `canary screenshot DIR` | Save a PNG of every screen |

---

## 🔒 Security Model

| Layer | Protection |
|---|---|
| **Network** | No web server, no open ports. Nothing on the machine or network can reach the app. |
| **Vault** | All secrets (fingerprint key, signing key, Telegram session, Gemini key) encrypted with AES-256-GCM under scrypt-derived passphrase. Never in SQLite, logs, or on screen. |
| **Access** | Window opens locked. Auto-locks after 10 min idle. 5 wrong passphrases → 60s cooldown. |
| **Audit** | Every action is written to a hash-chained log. Any edit is detectable. |
| **Data** | Directories are `0700`, files are `0600` (macOS). On Windows, protection is the user profile + vault encryption. |
| **External calls** | Telegram (read-only, public channels only) and Gemini (leak images only, never the question bank). |
| **Supply chain** | No GPL dependencies. PySide6 Essentials only (LGPL). Fonts bundled. |

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

| Component | Status |
|---|---|
| Storage, vault, audit log, hash chains | ✅ Built & tested |
| Question bank & loader | ✅ Built & tested |
| Fingerprint engine (keyed choice, probability math, verdicts) | ✅ Built & tested |
| Worker pipeline & CLI | ✅ Built & tested |
| App window (lock, idle lock, navigation, theme, widgets) | ✅ Built & tested |
| Copy generation & decoding | 🔧 In progress |
| PDF maker, seed data, photo reader | 🔧 In progress |
| Telegram listener, analysis pipeline | 🔧 In progress |
| App screens (Leaks, Case, Limits) | 🔧 In progress |
| Evidence files, simulation, health check | 🔧 In progress |

---
