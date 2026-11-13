---
version: 1
slug: "canary-ui"
primary_target: "canary/ui"
related_targets: []
---

# Canary desktop app (all screens)

Scope: the whole PySide6 app: lock, leaks list, case, limits. Visitor mode: Operate.
Audience: an exam controller at a laptop, up close; in the demo, judges standing beside it.
Task: see each leak, open a case, read the verdict and how sure it is, see who held the copy, issue evidence.
Constraints: see PRODUCT.md (plain text for untrusted content, bundled fonts, light only, no copy named on an inconclusive case, reduced motion).
User decisions (14 Nov 2026): the category standard, chosen over two dealt hands. Quality bar: Linear, Vercel, Stripe Dashboard. Density: tighter than the chosen sketch, a case should fit one laptop screen.

## Direction contract

THESIS: A security console executed at the craft of Linear, Vercel and Stripe: side navigation, a header per screen, a row of key figures, then the work in bordered panels. It refuses the old answer-sheet costume and the roomy card-soup dashboard; density comes from tight, aligned panels, not from shrinking type.

OWN-WORLD: Cool near-white ground (#F6F7F9), white panels with 1px #E3E6EB borders and 8px radius, no shadows except a 1px lift on menus. Ink #0E1525, secondary #525B71, tertiary #8A92A6. One accent, Canary blue #2B59E8, for primary buttons, selection, links and live copies in the funnel. State pills only: Traced green, Strong lead amber, Not our paper red, Not enough slate. Mukta throughout, 13 to 14px body, 600 weight headings, tabular figures. Sidebar white, 208px.

STORY: The operator sees at once whether Canary is watching and reading, opens the newest leak, reads one verdict line and the number behind it, and decides what to do from the response panel.

FIRST VIEWPORT: Left sidebar: Canary wordmark, Leaks and Limits, status rows at the foot. Main: header with the case title, the posting chat and time, the synthetic pill and Issue evidence file on the right. A strip of four figures: verdict pill, copy, clues matched, chance by luck. Then two columns: the leak (left) and narrowing it down with the funnel grid (right); below, who held it, clues, response. Everything above the fold at 1440x900.

FORM: The category standard (canon card), chosen by the user after the first hand and a bolder re-roll. Signature move: the funnel, every candidate copy drawn as a cell that greys out clue by clue until the copies that still fit remain in blue. seed:bcb6b5ea3264a163

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
