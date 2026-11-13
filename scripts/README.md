# scripts

One-off helpers that are not part of the tool.

- `make_score_set.py` and `make_score_set_2.py`: built the frozen test leaks in `canary/data/score_set.json` and
  `score_set_2.json`. Both files are frozen, and `tests/test_score.py` fails if either changes. Do not rerun these to
  replace them. See `SCORES.md`.
- `measure_photos.py` (optional extra in `docs/PROMPTS.md`, not built): would measure how well the photo reader
  does on real photos and write `CANARY_HOME/measured.json`, which `python -m canary sim` then uses in place of
  the assumed misread rates.
