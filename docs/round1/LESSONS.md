# What lost points: all six tracks

Source: `Final_Evaluaton_Sheet.xlsx`, 522 teams and 452 written remarks across AgriTech, FinTech, HealthTech, Cybersecurity, Hardware-IoT-Robotics and Open Innovation. Shortlisted teams have blank remarks, so all remarks are about teams that missed the cut.

Scripts and raw output: `eval_*.py` and `eval_results.txt` in this folder.

Treat these as patterns, not proof. Mistakes were found by keyword, one remark can hit several, reviewers differed by track, and round 1 judged slides rather than running software.

## The two biggest findings

**Design was close to a gate** (excluding Open Innovation, whose cutoff was much lower).

| Band | Teams | Shortlisted | Rate | Mean overall |
|---|---|---|---|---|
| Design 19+, Execution 18+ | 24 | 13 | 54.2% | 75.0 |
| Design 19+, Execution under 18 | 52 | 25 | 48.1% | 72.1 |
| Design under 19, Execution 18+ | 48 | 4 | 8.3% | 65.5 |
| Design under 19, Execution under 18 | 209 | 3 | 1.4% | 57.1 |

**Execution has a cliff, even for strong ideas.**

| Impact + Creativity of 36 or more, with | Teams | Shortlisted |
|---|---|---|
| Execution 13 or below | 30 | 4 (13%) |
| Execution 14 to 16 | 36 | 22 (61%) |
| Execution 17 or above | 28 | 20 (71%) |

Bit by Bit in FinTech had exactly our Impact and Creativity (21, 21). With Execution 9 it scored 68: "zero-knowledge proofs are ambitious".

## What each mistake cost

Each row compares teams called out for that mistake with the 452-team average of 57.6 overall.

| Mistake | Teams | Overall vs average | Where it hit | Example | Our guard |
|---|---|---|---|---|---|
| Thin, generic content | 20 | **−12.1** | Design −4.6, Creativity −3.3 | Genblox, "too general"; CRYPTIC CORE, "details are thin" | Real screens, numbers and algorithm on show |
| A demo that can't be built | 11 | **−8.4** | Execution −7.2 (mean 7.2 of 25) | CIRCUIT BREAKERS, flying butterfly; Floating Farm | One software flow, already simulated |
| Workflow or architecture missing | 24 | −5.1 | Design −2.1 | FinWise, NeuroNex | Architecture diagram in the deck |
| Common idea, no differentiator | 82 | −4.2 | Creativity −3.5 | HealthTech NEXORA, "very standard"; Shunya | Direct comparison with existing systems |
| Scope too broad | 19 | −4.1 | Execution −5.8 (mean 8.6) | VANTER, "13 engines"; Pixel Minds, "AR, wearables and SOS" | P0 list and cut order |
| No evidence the problem is real | 94 | −4.0 | Impact −2.6 | 88 of the 94 are in Open Innovation | Sourced figures plus one local quote |
| Dataset not named | 58 | −3.6 | Design −1.5 | NEURAL NEXUS | State it: original mock bank, synthetic custodians |
| Tools or models not named | 60 | −2.7 | Design −1.6 | We Googled It | Named libraries on the stack slide |
| Parts that contradict each other | 7 | −2.3 | Execution −1.5 | Epoch Delta, Bitcoin data for Ethereum tracing; GEM-IN-AI, Windows and Linux mixed; Zenix, conflicting claims | Final deck matches what's built |
| Wrong track | 11 | −0.9 | Execution −2.8 | GitSetGo, "Open Innovation idea, not AgriTech" | Pitch as traitor tracing with a threat model |

## What judges pick at on strong teams

These don't lower the average, because the teams were good. They show what gets challenged at our level.

| Pattern | Teams | Mean overall | Example |
|---|---|---|---|
| Numbers without support | 44 | 61.6 | TEAMDARK, "0% false-positive claim needs evidence"; NeptuneX, "support the 30% figure"; NextGen-Era, "sub-15 ms" |
| Heavy stack (Execution falls to 12.7) | 29 | 64.1 | LakeForge, "AWS stack and five roles"; TEAM PRIME, "blockchain and Flutter"; YUKTI, "eight agents" |
| Roadmap in weeks or months (Execution falls to 11.6) | 8 | 62.8 | Backlog Coders, "12 weeks"; TEAMDARK, "36-hour plan exceeds 24 hours" |

## Being safe also loses

- The 101 teams praised as well-scoped or feasible had good Execution (16.8) but only 55.4 overall, with Creativity at 10.8.
- Nine teams with Execution of 20 or more missed the cut, including NeptuneX (Design 13) and Team Zenith (Impact 15, Creativity 14).
- Ultrons: "the solution is a single subtraction formula". Our Content: "the scope is very basic".
- Design alone doesn't save a team either. Botany Defenders had Design 22 and Execution 9, and missed by one point.

## What judges rewarded

| Remark mentions | Teams | Execution | Overall |
|---|---|---|---|
| Measured results, benchmarks, backtesting | 19 | 17.3 | 65.1 |
| A clear hourly plan | 32 | 16.8 | 65.9 |
| Honesty about limits | 40 | 16.4 | 63.5 |
| Rigorous or thoughtful work | 27 | 13.9 | 65.0 |

Panani's remark singled out "a live attacker demo". Krushi Yantra's praised "honest status labels".

## Missed by one or two points

| Track (cutoff) | Team, score | What the remark raised |
|---|---|---|
| Cyber (75) | PromptPioneers, 74 | Its only complaint: "fix the team-name typo" |
| Cyber (75) | Panani, 74 | Live attacker demo, but "clarify the path from simulation to real deployment" |
| Cyber (75) | TECHNOVA, 74 | "Confirm LoRA fine-tuning fits the time and compute available" |
| Cyber (75) | Pied Piper, 74 | "Define how the planned agent map is authored" |
| AgriTech (72) | Chai And Chaos, 71 | Honest and original, but "add an hour-by-hour build plan" |
| FinTech (73) | Code Alchemists, 71 | Impact 21, Execution 12: "roadmap is in months" |
| Hardware (70) | Wakanda's Vision, 69 | "Scope the four-storey build for two members" |
| HealthTech (73) | AFTER HOURS, 72 | "Name the dataset you will use and simplify the slide layout" |
| Open Innovation (63) | Botany Defenders, 62 | Design 22, Execution 9: "narrow the 24-hour scope" |

## Reviewers differed by track

Share of each track's remarks raising each issue, in percent. We don't know who's on the final panel, so cover all of them.

| Issue | Agri | Cyber | Fin | Hardware | Health | Open |
|---|---|---|---|---|---|---|
| Hourly plan | **50** | 34 | **50** | 21 | 19 | 1 |
| Dataset | 4 | **26** | 3 | 7 | 18 | 10 |
| Named tools or models | 8 | **23** | 6 | 16 | 20 | 7 |
| Evidence of the problem | 0 | 3 | 6 | 2 | 1 | **54** |
| Differentiator | **32** | 16 | 24 | 16 | 18 | 15 |
| Slide mess | 12 | 14 | 9 | 7 | 15 | 0 |
| Consent or safety | 4 | 6 | 0 | 9 | **13** | 2 |
| Number needs support | 8 | 12 | 9 | **16** | 12 | 7 |

## Remarks that apply directly to Canary

| Our risk | Teams told this | What they were told |
|---|---|---|
| OCR accuracy | Pineapple, Tech Forge, Hackaholics | "Test OCR on poor scans", "report OCR accuracy on Indian-language text", "how you'll test OCR accuracy" |
| Simulated data | Panani, DaysGone | "Path from simulation to real deployment", "how synthetic training data is validated" |
| The custody log's trustworthiness | TEAM KALYUGA | "How the verified merchant registry will be populated and kept trustworthy" |
| False accusations | Worriors, NextGen-Era | "Explain how false alarms are handled", "how false positives are handled" |
| Tracing people | NEXOVOLT, Zenix, Byteinit | "Build the consent gate early", "needs authorisation", "address consent" |
| Reliance on data we don't have | Backlog Coders, Anveshan | "Relies on restricted data", "partner data unrealistic" |
| Prior work | BEHEMOTH, 4Win | "Newly built versus reused", "what will be built during the event" |
| Who actually uses it | VectorX, Launchpad, angrybirds | "User value beyond research analysts", "relevance", "practical deployment scenario" |
| Hedged language | ANVESHA | Stack "hedged (if implemented)" |
| Scope versus team size | KiMi, Wakanda's Vision | "Unrealistic for two members" |

## Our own round-1 deck

Our remark is blank, but these are visible in the deck itself:
- All seven slides are paragraphs on a template, with no diagram, screen or chart.
- Grammar: "have limitation", "slightly different version", "the whole country don't have to", "Whatsapp", "Lakhs of NEET, JEE, CUET, state recruitment and board exams aspirants".
- The 98% claim has no stated conditions.
