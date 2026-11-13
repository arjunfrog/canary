# Progress

Kept current so the work can be picked up again.

## Tasks

| Task | Status | Proof |
|---|---|---|
| 1. Skeleton, storage, vault | Done before this run | `pytest -q` |
| 2. Fingerprint engine | Done | `tests/test_fingerprint.py`, decode of 5,000 copies under 2 s |
| 3. Papers as PDF | Done | `tests/test_pdf.py`: page 1 of a PDF decodes to its copy |
| 4. Seed data | Done | `canary seed` takes 0.1 s: 300 people, 5,050 copies, 20,150 handovers |
| 5. Photo reader | Done against a mocked Gemini | `tests/test_reader.py`. Never run against the real service |
| 6. Analysing a leak | Done | `tests/test_analyze.py`, and `add-leak` while `run --headless` was running |
| 7. Telegram listener | Done against fake messages | `tests/test_lurker.py`. Never run against real Telegram |
| 8. App data layer and navigation | Done | `tests/test_queries.py`, `tests/test_app.py` |
| 9. Case screen and funnel | Done | `tests/test_case_page.py`, screenshots checked by eye |
| 10. Leaks screen, live updates | Done | `tests/test_leaks_page.py`, screenshots checked by eye |
| 11. Evidence file and response | Done | `tests/test_evidence.py` |
| 12. Limits chart | Done | `tests/test_sim.py`, screenshots checked by eye |
| 13. Health check, replay, packaging | Done on macOS | `canary check` passed 3 times from source and 3 times from `dist/Canary.app` |
| Security review | Not started | |
| `canary score` and improvement rounds | Not started | |

## Decisions

- The exam id is 1 everywhere (`config.EXAM_ID`). The seed creates exam 1.
- Copy numbers run from 1: translators 1 to 50, printed copies 1 to 5,000.
- Option order applies to both stages, so a translator leak with options visible gives order clues too.
- A translator's 6 traps are the 6 lowest keyed HMAC ranks among the 24. A trap's chance rate is the real share
  of translators holding it.
- Per-copy tables derived from the key are kept in memory only, never on disk.
- The stored funnel keeps counts only. Which copies were still in the running is never written down, and the
  funnel picture shuffles which bubble is which, so an inconclusive case names nobody anywhere.
- A leak with no matched question that is not clearly a fake is "unreadable", not "inconclusive".
- The "damaged questions make it unreadable" rule only applies when under half the questions matched, so a
  mostly clean leak with a few damaged questions is still decoded.
- Matching score = (RapidFuzz ratio - 50) x 2 on normalised stems. Match at 70, clearly different under 40.
- The worker runs each leak on one side thread, so a slow photo read never blocks the Telegram listener.
- Backfill on start (last 50 messages) is not rate limited. Live messages are: 10 new leaks a minute per chat.
- The Telegram client is wrapped in `ReadOnlyTelegram`, which only lets reading calls through.
- Seed timestamps hang off the exam's creation time. Translator copies come back 3 days before it and printed
  copies reach the superintendent about 12 hours before it, so a leak posted after seeding finds the copy
  with the exam cell (translator copies) or the superintendent (printed copies). The Case screen shows who it
  was issued to as well as who held it when the leak was posted.
- Evidence verification prints the signing key's fingerprint, and `verify --expect FINGERPRINT` pins it.
  Without a published fingerprint a forger could re-sign with their own key.
- A replay still asks for the passphrase and records "replay opened", but starts no worker, no listener and
  makes no network connection. The case itself comes from the replay file alone.
- `reset` also deletes the leak images and the photo reader's cache, and needs the passphrase.
- The packaged app drops the Qt plugins it has no use for, so only QtCore, QtGui, QtWidgets and QtDBus
  (which QtGui itself needs on macOS) are inside it.
- Added commands the tasks did not name: `evidence ID` (issue from the command line) and `verify --expect`.

## Faked, and how to make it real

- Photo reader: tested with a mocked Gemini client. Real: `python -m canary vault set gemini_api_key`.
- Telegram: tested with fake message objects. Real: `vault set tg_api_id`, `vault set tg_api_hash`,
  `python -m canary tg-login`, `python -m canary watch USERNAME`.
- People, organisations and handover logs are synthetic, from `canary seed`.

## Cannot be done from here

- The Windows build. PyInstaller cannot cross-build. Steps are in docs/BUILD.md.
- Typing the passphrase into the packaged window by hand. The packaged app's vault unlock was proved through
  its `check` command, and its window through `screenshot` and by launching it.
- Posting in a real demo channel (tasks 7 and 10 "done when"). Needs the Telegram login.
