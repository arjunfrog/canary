# Scores

`python -m canary score` runs the tool on `canary/data/score_set.json`: 90 leaks made from known copies, each
with the answer it should get. The score is the share that get the right verdict and the right copy. Naming a
wrong copy fails the whole run.

- 60 leaks may be read to find out why something failed. 30 are set aside: they are scored, never read.
  `score` prints nothing about any one of them, and `score --show` refuses them.
- The set was frozen before the first score was taken. Its SHA-256 is
  `a4ffe1b1f7bb5af6c3d75091600f83f7b9f367def67f0426f135e13d324ea618`, and `tests/test_score.py` fails if it changes.
- It is built by `scripts/make_score_set.py` with a public key used for nothing else. A leak is only in the set if
  the answer declared for its kind and the brief's exact maths (given a perfect read of the clues it really
  carries) agree.

| Kind | Leaks | Right answer |
|---|---|---|
| Typed translator leak, values and options kept | 9 | traced, that translator |
| Typed translator leak, values only | 9 | traced (12 to 15 numeric), strong lead (6 or 7), nobody (3 or 4) |
| Typed printed-copy leak, options kept | 9 | traced (9 or more questions), strong lead (5 or 6) |
| Printed-copy leak, options left out or reshuffled | 6 | not enough to name anyone |
| Translated leak, through the mocked photo reader | 9 | traced, that translator |
| Retold in English and typed, values kept | 6 | traced, that translator |
| Numbers removed | 9 | nobody (6 leaks). Traced where biology kept its option order (3) |
| Fake paper | 12 | not our paper |
| Garbled text, damage 35% to 60% | 9 | couldn't read it. Never "not our paper", never a copy |
| Typed with typing slips in the words | 6 | traced, that copy |
| Photo reader output with two misread questions | 6 | traced, that copy |

No page images are in the set, because the real photo reader is not connected.

## Rounds

A change is kept only if the score on the readable leaks rises and no wrong copy is named anywhere.

| Round | Change | Readable (60) | Set aside (30) | Wrong copy | Kept |
|---|---|---|---|---|---|
| 0 | Starting point: the tool as built by tasks 1 to 13 and the security review | 56 = 93.3% | 28 = 93.3% | none | |
| 1 | A cleanly written question whose four options are plainly not the bank question's options counts as "clearly different", even when its wording resembles a bank stem. Before, one such question in a fake paper ("Litmus solution is obtained from" beside the bank's "Morphine is obtained from") was taken for a damaged real question, and the whole fake was called unreadable | 60 = 100% | 30 = 100% | none | yes |
