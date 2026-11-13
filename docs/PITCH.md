# Canary: demo, deck and judge questions

Every simulation number here comes from `docs/research/sim_results.txt`. Misread rates in it are assumed. On stage, quote what you measured on real photos, and read live numbers off the screen.

## Demo script (3 minutes)

| Time | Beat | Who |
|---|---|---|
| 0:00 | "In May, 22.79 lakh students sat NEET. Nine days later it was cancelled. Nobody could say quickly whether the leak was real or where it came from. We do both in" [the measured read time]"." | Arjun |
| 0:20 | Two translator copies side by side: same question, different numbers. "Every translator gets different numbers, and a few questions that will never be in the exam. They can't tell which." The barcode: "Crop this, it doesn't matter. Canary never reads it." | Arjun, Adarsh drives |
| 0:35 | **Judge picks a sealed envelope,** photographs page 1 (14 questions), and it is posted in the public demo group. **Akash posts a fake paper at the same moment.** Arjun explains while it is read: "Canary is sitting in this group on an ordinary account, read only. It runs on this laptop. Nothing is hosted." | Akash, Arjun narrates |
| 1:30 | Funnel runs from 50 translators to 1. Wrong-match risk falls. Verdict floods | Adarsh |
| 1:50 | "Leaked before printing. Translator copy" [read it], "held by" [read it]. Open the sealed slip to confirm. "Telegram shows where it surfaced. The fingerprint shows where it came from." | Arjun |
| 2:10 | "The leaker has the wrong numbers. The real values never left the exam cell." Suggested swaps before printing, then the signed evidence file | Adarsh |
| 2:25 | The printed copy Akash posted earlier: "Leaked after printing, copy" [read it] "of 5,000, from option order alone." Then the fake: "Not our paper." | Akash |
| 2:40 | Limits chart: "Here's where we fail. Numbers stripped out, translators merging copies, options reshuffled after printing. Canary says it can't name anyone, instead of guessing." | Arjun |
| 2:50 | Path: college exam, then one state board | Arjun |

The judge's beat is 55 seconds because reading can take 30 or more. Measure the real read time and adjust. If it's over 45 seconds, post the photo during the 0:20 beat.

If the judge's photo gets "Not enough to name anyone" or "Couldn't read this", use it: "It refuses to guess. Here's why, and here's a clearer photo." Then retake, or post Akash's prepared photo. If a real photo ever gets "Not our paper", say so plainly: "That's a wrong answer, and it's why a person still checks these." Then retake.

**90-second cut** for table-side judging: post the photo first and talk over the read, then the funnel, the copy and holder, and limits.

## Fallback ladder

Say on stage which step is in use.

1. Judge's phone photographs a printed copy and posts it in the demo group.
2. No printer: the judge photographs a copy on our laptop screen.
3. Judge has no Telegram: Akash posts the judge's photo, or a prepared one.
4. Telegram is blocked or the account is limited: drop the photo into "Add a leak" in the app.
5. Gemini fails or its quota is gone: paste a typed leak into "Add a leak". This needs no network at all.
6. Wi-Fi fails: hotspot on the second network.
7. Everything fails: a replay of a real case, labelled as a replay, then the backup video.

Gemini's daily quota resets at midnight Pacific, which is 13:30 IST. A key's whole Day 1 afternoon through judging morning is one quota, so stay under 60% of the daily limit before 08:00 on Day 2. Use one key.

## Deck: 8 slides at most

Use the official template if it's required. Every slide shows something, with no paragraphs. Every number has a source or "our script, run live".

1. **Problem:** one number, one sentence, source.
2. **Idea:** one question as two translators see it, and as two printed copies see it.
3. **Live demo:** one line, then switch to the tool.
4. **How it works:** one laptop, no cloud. Telegram in, verdict out, vault in the middle.
5. **Results and limits:** the measured chart, including failures. State the dataset: a mock bank written in the style of previous-year NEET questions, and synthetic people.
6. **Threat model:** attacker, what they try, what happens. Misuse in one line.
7. **What's different and what's real:** comparison below, built in the room versus prepared before, what changed since round 1.
8. **Path:** college, one state board, national. The user is the exam controller.

### Rules for the pitch

- Don't say "100%", "zero false positives", "unbreakable" or "blockchain". We have a hash-chained log.
- Don't put a number on a slide without a source or a script that reproduces it.
- Don't hedge. Say "built", "not built" or "next".
- Label simulated and synthetic data on screen.
- Disclose prior work: the question bank, the research simulation and the design direction were prepared before the event.
- Check every slide for typos and placeholders.

### Fix these round-1 claims

| Round 1 said | Problem | Say this instead |
|---|---|---|
| "Finds the leaker" | The fingerprint identifies a copy, not a person | "Traces the copy, and the custody log shows who held it" |
| "In our test, 98%" | No conditions stated | "From 14 typed questions, 99.9% traced among 50 translators, at a one-in-a-million false-match bar, in simulation", plus our measured photo results |
| "By morning those 14 questions are replaced" | Reprinting overnight isn't credible | "A leak before printing is fixed by swapping in reserve questions. After printing, Canary recommends a corrigendum or the reserve set. A person decides" |
| "Bot watches Telegram channels" | Bots can't join other people's channels | "An ordinary account, read only, in public channels and groups it has joined. No private chats" |
| "WhatsApp tip line" | Not being built | "Not built" |
| "Python and FastAPI" | Sounded like a hosted web app | "A desktop app that runs on one laptop, on macOS or Windows. Nothing is hosted" |
| "The leaker is still unpunished" | Not verified. May 2026 reports describe arrests and a CBI probe | "Cancelled nine days later, with a CBI probe needed to find the source." Check current status |
| "89 exams, 6.5 crore students" | Accurate, but one outlet's count | "At least 6.5 crore candidates across 89 cases, per Newslaundry's 2024 analysis" |
| "Barcodes, like Odisha's board" | Not checked | Verify before reusing |

### How we compare

Per-copy marking exists, so don't claim to be first.

| Approach | What it does | Where it stops |
|---|---|---|
| CBSE with Microsoft (2018 pilot, 487 centres) | Encrypted download 30 minutes before the exam, centre code as watermark | The mark is on the page |
| Sindh, Pakistan (announced 2026) | Unique watermark per paper | Reported as a watermark, so the same concern applies |
| Barcodes and printed marks | ID on the page | Cropped or retyped away |
| Patent on perturbed document copies (US 12620252) | Unique copies with content changes, compared against a leak | Only a search summary was read. Read it before claiming differences |
| **Canary** | ID in the questions themselves: decoy values and trap questions before printing, option order after. Tested false-match bar, custody log, fake detection | Numbers stripped from a pre-print leak, merged copies, very small leaks, options reshuffled after printing |

No source was found showing these used in a real exam, which isn't proof nobody has done it. Say "we didn't find it deployed".

### Path to real use

1. **College internal exam.** Paper setters and moderators each get a decoy-value copy. Real custody log using the exam cell's existing process.
2. **One state board, one exam.** Translators get decoy copies. Printed packets differ in option order per centre. Key held by the board.
3. **National.** Encrypted delivery shortly before the exam, as CBSE piloted in 2018, makes question replacement a re-issue rather than a reprint.

### Facts to verify before the deck

Odisha's barcodes, NEET 2026's current status, the CBSE and Sindh details, and the patent's actual claims.

## Judge questions

Learn the first seven.

| Question | Answer |
|---|---|
| **What if the leaker removes the numbers?** | Then we can't name anyone, and we say so. A translator holds 6 trap questions and traps alone need 8 to reach even our lower bar. But a physics question without its numbers is worth far less to a buyer |
| **What if the leaker shuffles the options?** | Before printing it doesn't matter, because the numbers carry the trace. After printing, option order is the only clue, so we say we can't name anyone |
| **What if two translators merge their copies?** | At 14 questions we get a strong lead on one of them about 60% of the time and rarely full tracing (3%). At 30 questions, 83% traced. With three it gets much weaker, and we say we can't name anyone |
| **Could this frame someone innocent?** | Without the key, nobody can produce another person's copy. The one-in-a-million Traced bar is calculated exactly, not estimated. The lower Strong lead bar can be wrong about once in a thousand cases, which is why a person reviews before any action |
| **Does it name a person?** | It names a copy. The custody log shows who held it. The Telegram account that posted it may only be a reseller. It's a lead for investigators, not a verdict |
| **Is your number real?** | It's a simulation, and the script is here to run: 14 typed questions among 50 translators gives 99.9% traced. A phone photo of a printed copy, 14 questions among 5,000 copies, gives 99%. We also measured real photos, and this is the result |
| **Hasn't this been done?** | Per-copy marking has: CBSE with Microsoft, and Sindh, use watermarks. Marks on the page get cropped or retyped away. We didn't find these methods used in a real exam, but we won't claim nobody has |
| Do students get different questions? | No. Decoy values and traps are removed before printing. Every printed copy asks the same questions, and only the option order differs |
| Who puts the real values back? | The tool does, mechanically. Numbers need no translation, so the translated text stays as it is. Translators never see the real values |
| Don't traps waste translators' time? | Six extra questions in a 180-question paper. They also prove a leak came from before printing, since they never appear in the exam |
| Is reading Telegram legal? | We read public channels and groups only, with an ordinary account, and never private chats. A board would run this with legal sign-off |
| Where does the data live? | On one laptop. No cloud database, no website, and the app opens no network port. It locks when idle, and every action goes to a tamper-evident log |
| How's the key protected? | In a vault encrypted under a passphrase. It never reaches the database or the screen. Production would use a hardware key store |
| Do you send question papers to Google? | Only images of leaks, which are already public. Never the bank. Production would run the reader on the board's own servers |
| Why closed source? Isn't that security by obscurity? | The method is public, and we just explained it. The security rests on the key, not on hiding the code. The code is private because it's our product |
| Who fills the custody log, and why trust it? | In production, a scan at each handover. Each entry is hashed with the one before, so edits are detectable. Here it's synthetic. Someone could still enter false data at the start, so it's tamper-evident, not proof of truth |
| Could a board misuse this against staff? | It only traces copies that leaked, and names one only above a published bar. A person reviews every case |
| Is this court-admissible? | We haven't established that. The file gives investigators hashes, a signature and a custody trail. A lawyer would need to advise |

## Sources

Problem facts: [Newslaundry, 89 cases](https://www.newslaundry.com/amp/story/2024/07/31/10-years-89-paper-leak-cases-48-retests-from-centre-to-states-few-plugs-for-a-leaky-record), [ThePrint on NEET 2026](https://theprint.in/india/neet-ug-2026-cancelled-over-paper-leak-allegations-centre-orders-fresh-exam-cbi-probe/2928688/), [The Week on NEET 2026](https://www.theweek.in/news/india/2026/05/12/neet-ug-2026-exam-cancelled-after-paper-leak-row-nta-to-announce-fresh-date-soon.html), [PTI via The Week on NTA and Telegram](https://www.theweek.in/wire-updates/national/2025/05/01/del49-nta-neet.html), [Deccan Chronicle on tip-offs](https://www.deccanchronicle.com/nation/education/neetug-nta-flags-106-telegram-channels-for-1500-leak-tip-offs-1876355).

Build facts: [Telegram: creating an application](https://core.telegram.org/api/obtaining_api_id), [Gemini rate limits](https://aistudio.google.com/docs/rate-limits).
