# Progress

Kept current so the work can be picked up again. Newest state at the top of each list.

## Tasks

| Task | Status |
|---|---|
| 1. Skeleton, storage, vault | Done before this run |
| 2. Fingerprint engine | In progress |
| 3. Papers as PDF | Not started |
| 4. Seed data | Not started |
| 5. Photo reader | Not started |
| 6. Analysing a leak | Not started |
| 7. Telegram listener | Not started |
| 8. App data layer and navigation | Not started |
| 9. Case screen and funnel | Not started |
| 10. Leaks screen, live updates | Not started |
| 11. Evidence file and response | Not started |
| 12. Limits chart | Not started |
| 13. Health check, replay, packaging | Not started |
| Security review | Not started |
| `canary score` and improvement rounds | Not started |

## Decisions

- The exam id is 1 everywhere (`config.EXAM_ID`). The seed creates exam 1.
- Option order applies to both stages, so a translator leak with options visible gives order clues too.
- A translator's 6 traps are the 6 lowest keyed HMAC ranks among the 24. A trap's chance rate is the real share of translators holding it.
- Per-copy tables derived from the key are kept in memory only, never on disk.

## Cannot be done from here

Nothing yet.
