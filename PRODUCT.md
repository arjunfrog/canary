# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

Canary is a native desktop app (PySide6, Qt Widgets) for macOS and Windows, not a website and not a mobile app.
`web` is recorded only because the schema has no desktop value: none of the iOS or Android guidance applies, and
there is no HTML, CSS or browser anywhere in the product.

## Users

- **Primary: an exam controller**, or a member of an exam cell, who has to decide what to do when a paper
  surfaces on Telegram. They are not a developer. They read the screen at a laptop, up close.
- **In the demo: hackathon judges** standing at the same laptop (Colossus 3.0, Cybersecurity track). They watch
  one leak go from "posted in a channel" to "this copy, held by this person" and judge whether it is real.

## Product Purpose

Trace a leaked exam paper back to the exact copy it came from, and say honestly how sure that is. Every copy of
a paper is made slightly different by a secret key: translators get decoy values and trap questions, printed
copies get a different option order. A leak is matched against every copy and the exact chance of a false match
is computed. Success is a correct copy named when the evidence supports it, and nobody named when it does not.

## Positioning

The identifying mark is in the questions themselves, not on the page, so cropping or retyping a leak does not
remove it. And the tool refuses to guess: below a published bar it names no copy at all.

## Operating Context

- One laptop, offline-capable. No server, no open port, no cloud. The only outbound connection is Telegram,
  read-only. Photos are read on the Mac itself.
- Flow: the window opens locked; a watched Telegram chat posts a paper (or the operator adds one by hand); it is
  read and analysed; the case shows where it surfaced, the leak, the narrowing from all copies to one, the
  verdict, who held the copy, the clues, and a recommended response; a signed evidence file can be issued.
- Screens: Lock, Leaks (list), Case (one leak), Limits (where tracing works and fails).
- Verdict vocabulary is fixed: Traced, Strong lead, Not enough to name anyone yet, Not our paper, Couldn't read this.

## Capabilities and Constraints

- Built with Qt Widgets and QPainter. No Qt Charts, no web engine, no rich text for anything read from a leak or
  Telegram: untrusted text is always shown as plain text.
- Fonts must be bundled with the app (currently Mukta in `canary/ui/fonts`). Nothing is loaded from
  outside, so a new face means adding its font files to the repo.
- Must look the same on macOS and Windows.
- The window locks after 10 minutes idle. Nothing may show behind the lock.
- An inconclusive case must never point at a copy, in words or in pictures.
- All data on screen is a mock exam with synthetic people, and must be labelled as such.
- Words are plain and written for an exam controller: "Not enough to name anyone yet", never "Error" or
  "Analysis complete". Sentence case.
- The funnel (all candidate copies narrowing to the ones that still fit) is the only thing that animates on its
  own, and must respect `CANARY_REDUCE_MOTION=1`.

## Brand Commitments

- Name: Canary. Team RADIOHEAD.
- Voice: plain, direct, honest about limits. No hype words.
- The answer-sheet (OMR) visual concept is retired by the owner's decision on 14 Nov 2026: bubbles as decoration,
  timing marks down the left edge, pink rules and highlighter yellow are not commitments any more.
- Owner's stated preferences for the replacement: professional, easy on the eyes, noticeably less padding, no
  beige. It must not read as a generic admin dashboard, a dark "hacker" terminal, a playful colourful app, or a
  lifeless grey one.
- Standing preference (14 Nov 2026): the category standard for a security console, executed at the craft level
  of Linear, Vercel and Stripe Dashboard, with tight spacing. Chosen over two rounds of bolder directions.

## Evidence on Hand

- Real, working screens with real analysis behind them: `python -m canary screenshot DIR` renders every screen
  from synthetic leaks.
- Scored results in `SCORES.md` (126 frozen leaks, no wrong copy named) and the limits simulation behind the
  Limits screen.
- No customer names, testimonials or deployments exist. None may be implied.

## Product Principles

1. Say how sure, exactly. The number behind a verdict is always visible next to it.
2. Never guess. When the evidence is short, the screen says so plainly and names nobody.
3. A lead, not a verdict on a person. The tool names a copy; people decide what follows.
4. Show the limits as plainly as the successes.
5. Nothing leaves the laptop that does not have to.

## Accessibility & Inclusion

- Readable at laptop distance by someone standing beside the operator.
- Colour is never the only carrier of a verdict: every verdict is also written in words.
- Reduced motion is honoured through `CANARY_REDUCE_MOTION=1`.
