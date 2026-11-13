# Progress

Kept current so the work can be picked up again.

## Tasks

| Task | Status | Proof |
|---|---|---|
| 1. Skeleton, storage, vault | Done before this run | `pytest -q` |
| 2. Fingerprint engine | Done | `tests/test_fingerprint.py`, decode of 5,000 copies under 2 s |
| 3. Papers as PDF | Done | `tests/test_pdf.py`: page 1 of a PDF decodes to its copy |
| 4. Seed data | Done | `canary seed` takes 0.1 s: 300 people, 5,050 copies, 20,150 handovers |
| 5. Photo reader | Done, on the Mac (Gemini removed) | `tests/test_reader.py`: a drawn translator page is read on this Mac and traced. The user's real photo reads all 8 questions |
| 6. Analysing a leak | Done | `tests/test_analyze.py`, and `add-leak` while `run --headless` was running |
| 7. Telegram listener | Done against fake messages | `tests/test_lurker.py`. Never run against real Telegram |
| 8. App data layer and navigation | Done | `tests/test_queries.py`, `tests/test_app.py` |
| 9. Case screen and funnel | Done | `tests/test_case_page.py`, screenshots checked by eye |
| 10. Leaks screen, live updates | Done | `tests/test_leaks_page.py`, screenshots checked by eye |
| 11. Evidence file and response | Done | `tests/test_evidence.py` |
| 12. Limits chart | Done | `tests/test_sim.py`, screenshots checked by eye |
| 13. Health check, replay, packaging | Done on macOS | `canary check` passed 3 times from source and 3 times from `dist/Canary.app`, again after the last change |
| Security review | Done | `tests/test_security.py`: 15 guard tests |
| `canary score` and improvement rounds | Done | `SCORES.md`: set 1 from 93.3% to 100%, set 2 from 50.0% (41.7% set aside) to 100%, no wrong copy |
| Fixes after the rounds | Done | `tests/test_robustness.py`: 1,300 random leaks, 0 wrong copies |

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
- The photo reader is Apple's Vision framework on the Mac itself, through PyObjC, chosen by the user over Gemini
  (Gemini needed paid credits and was often overloaded). No key, no network. Each photo is read twice (English,
  and Hindi which also reads Devanagari digits) and the reading that recognises more questions is kept. Lines the
  recogniser doubts are marked hard to read. The models are loaded at unlock, so a cold start (up to ~40 s) never
  lands on the first real photo. An old Gemini key is erased from the vault on the next unlock.
- For photos: a question can be known by its four options alone when they are unique in the bank (385 of 459
  value sets), and a lost ² or ³ ("m/s'") no longer hides a value set. Option groups are split into questions
  even when the question lines were not read, and lenient labels ("D)", "(C]") are accepted, never "[A]".
- Kannada is not read by the Mac. Numeric questions are still traced by numbers and options; text-only ones are not.
- The worker runs each leak on one side thread, so a slow photo read never blocks the Telegram listener.
- Backfill on start (last 50 messages) is not rate limited. Live messages are: 10 new leaks a minute per chat.
- The Telegram client is wrapped in `ReadOnlyTelegram`, which only lets reading calls through.
- Telegram is tried on ports 443, then 5222, then 80, and the first that works is kept for every connection,
  including reconnects and moves to another data centre. Some networks (including the one this was built on)
  cut MTProto off on 443 but let 5222 through. `CANARY_TG_PORT` pins one port.
- A port only counts as working once Telegram answers a request on it (help.getNearestDc, which needs no
  login and changes nothing). With a saved login the connection opens on a blocked port and only fails at
  the first request. The port that worked is kept in `CANARY_HOME/telegram_port` and tried first next time.
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
- The first score set was saturated after one round, so a second, harder set was frozen instead of logging three
  empty rounds. Defects found by probing after both sets were full were fixed as ordinary bugs with their own tests.
- README.md was revamped by a teammate (commit 34aa439) while this work was running. Its layout is theirs; only
  facts that had gone stale were updated.

## Security review: what was found and fixed

Reviewed against each security rule in the brief, as a sceptical judge would.

| Found | Fix |
|---|---|
| Two connections could chain an audit row onto the same previous row, making an honest log fail verification | `audit.record` reads and writes inside one `BEGIN IMMEDIATE` transaction. Tested with 4 threads |
| Two workers (app plus `run --headless`) could claim the same leak | `claim_next` is one `UPDATE ... RETURNING` statement. Tested with 4 threads |
| Rows deleted by `check` and `reset` stayed readable in the database file's freed pages | `PRAGMA secure_delete = ON`, and the write-ahead log is truncated after deletions |
| A spammed chat could write one audit row per dropped message | One audit row per chat per minute; every drop still goes to the Python log |
| "Save a copy" could finish after the window locked, if its folder dialog was open at the time | It checks the lock again after the dialog returns. Same for "Choose an image" |
| Cutting rows off the end of the audit log cannot be detected by the chain alone | `verify-audit` prints the row count and newest hash to keep elsewhere. This limit is stated, not solved |
| An evidence file re-signed with another key would verify against the key beside it | `verify` prints the key fingerprint and `--expect` pins it. `init` prints the fingerprint to publish |
| The reader's cleaning stripped the joiners Indian scripts need | Zero-width joiner and non-joiner are kept; other control and format characters are dropped |
| `decode --text` used the key without an audit row | It records "leak decoded by hand" |
| The packaged app carried Qt Network, Qt Svg and nine image decoders it never uses | The spec drops them. Only JPEG, PNG and WebP can be decoded |
| Funnel data could have named the surviving copies of an inconclusive case | Only counts are stored and drawn (done during task 8) |

Known limits, stated rather than fixed:

- The idle lock is a screen lock. The vault's secrets stay in memory so the worker and listener keep running.
- `canary.db` is not encrypted (SQLCipher is an optional extra). It is protected by file modes and holds no secret.
  `cases`, `add-leak`, `seed` and `export-case` need no passphrase, as in the skeleton.
- `canary/data/bank.db` holds the real values and the reserves in the clear, inside the repo and the packaged app.
  For a real exam the bank would have to live in the vault.
- On Windows, file modes do nothing: the protection there is the user's profile folder plus the vault.

## Faked, and how to make it real

- Photo reader: nothing to connect. It runs on the Mac. Windows has none yet.
- Telegram: tested with fake message objects. Real: `vault set tg_api_id`, `vault set tg_api_hash`,
  `python -m canary tg-login`, `python -m canary watch USERNAME`.
- People, organisations and handover logs are synthetic, from `canary seed`.

## Cannot be done from here

- The Windows build. PyInstaller cannot cross-build. Steps are in docs/BUILD.md.
- Typing the passphrase into the packaged window by hand. The packaged app's vault unlock was proved through
  its `check` command, and its window through `screenshot` and by launching it.
- Posting in a real demo channel (tasks 7 and 10 "done when"). Needs the Telegram login.
