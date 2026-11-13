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

## Stage 2: a second, harder set

After round 1 the first set had nothing left to fail, so three more rounds on it could only have been empty.
Instead a second set was frozen: `canary/data/score_set_2.json`, 36 leaks, 12 of them set aside, SHA-256
`ce089a056ce6ff3fd99594f02dcb38d61ef900635f4c00690bfcd3e446b3e073`, built by `scripts/make_score_set_2.py` under the
same rules. The first set is unchanged and is still scored in every round. `score` now reports both.

| Kind | Leaks | Right answer |
|---|---|---|
| Fake with no options, 3 or 4 stems sharing a sentence frame with a bank stem | 6 | not our paper |
| Translated leak, loosely retold, numbers sometimes in another order | 6 | traced, that translator |
| Typed in Hindi with nothing to translate it: only numbers, units and options are readable | 6 | traced, that translator |
| A real leak inside a longer post, with chatter and questions from elsewhere | 6 | traced, that copy |
| Garbled text, damage 70% to 90% | 6 | couldn't read it. Never "not our paper" |
| No question numbers, paragraphs only | 6 | traced, that copy |

Scores below are for both sets together: 84 readable leaks and 42 set aside.

| Round | Change | Readable (84) | Set aside (42) | Wrong copy | Kept |
|---|---|---|---|---|---|
| 1 (restated) | Starting point for stage 2: the tool as round 1 left it. Set 2 alone: 12 of 24 readable, 5 of 12 set aside | 72 = 85.7% | 35 = 83.3% | none | |
| 2 | A question is recognised by its numbers when its words do not match: the numbers in the stem (in any order) and all four options must equal exactly one value set of exactly one bank question. Before, a translator's paper typed in Hindi was called "not our paper", and a loosely retold one was unreadable | 78 = 92.9% | 38 = 90.5% | none | yes |
| 3 | Typed questions that are not "cleanly written" (most words found in the bank's vocabulary) count as hard to read, so ruined text can be unreadable but never "not our paper". It fixed the ruined leaks but broke 8 fakes: ordinary words such as "bird" or "egg" are not in the bank, so clean fakes were taken for damage | 72 = 85.7% | 36 = 85.7% | none | no, reverted |
