---
name: Canary
description: A private desktop console that traces a leaked exam paper to the copy it came from, and says exactly how sure it is.
colors:
  ground: "#F6F7F9"
  surface: "#FFFFFF"
  sunken: "#F2F4F7"
  border: "#E3E6EB"
  border-strong: "#CDD2DA"
  cell: "#E4E8EE"
  ink: "#0E1525"
  ink-2: "#525B71"
  ink-3: "#8A92A6"
  accent: "#2B59E8"
  accent-hover: "#1F47C9"
  accent-soft: "#EBF0FE"
  accent-ink: "#1D43BE"
  accent-line: "#C9D6FB"
  canary: "#F2C200"
  traced-ink: "#0B6B39"
  traced-fill: "#E2F5E9"
  lead-ink: "#8A4A00"
  lead-fill: "#FDF0D9"
  slate-ink: "#475069"
  slate-fill: "#ECEEF3"
  alarm-ink: "#A3191D"
  alarm-fill: "#FCE7E7"
typography:
  headline:
    fontFamily: "Mukta"
    fontSize: "20px"
    fontWeight: 600
    fontFeature: "tnum"
  title:
    fontFamily: "Mukta"
    fontSize: "14px"
    fontWeight: 600
    fontFeature: "tnum"
  figure:
    fontFamily: "Mukta"
    fontSize: "22px"
    fontWeight: 600
    fontFeature: "tnum"
  body:
    fontFamily: "Mukta"
    fontSize: "14px"
    fontWeight: 400
    fontFeature: "tnum"
  body-small:
    fontFamily: "Mukta"
    fontSize: "13px"
    fontWeight: 400
    fontFeature: "tnum"
  label:
    fontFamily: "Mukta"
    fontSize: "12px"
    fontWeight: 400
    fontFeature: "tnum"
  button:
    fontFamily: "Mukta"
    fontSize: "14px"
    fontWeight: 500
    fontFeature: "tnum"
  pill:
    fontFamily: "Mukta"
    fontSize: "12px"
    fontWeight: 600
    fontFeature: "tnum"
rounded:
  cell: "3px"
  control: "6px"
  panel: "8px"
  lock-card: "10px"
  pill: "9999px"
spacing:
  hairline: "1px"
  tight: "8px"
  gap: "12px"
  gutter: "16px"
  sidebar: "208px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "4px 12px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
    textColor: "{colors.surface}"
  button-primary-disabled:
    backgroundColor: "{colors.border}"
    textColor: "{colors.ink-3}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "4px 12px"
  button-secondary-hover:
    backgroundColor: "{colors.sunken}"
  button-link:
    textColor: "{colors.accent-ink}"
    typography: "{typography.button}"
    padding: "2px 0px"
  nav-item:
    textColor: "{colors.ink-2}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "5px 10px"
  nav-item-hover:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.ink}"
  nav-item-active:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent-ink}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "6px 10px"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
    padding: "12px"
  sidebar:
    backgroundColor: "{colors.surface}"
    width: "{spacing.sidebar}"
    padding: "14px 10px 12px 10px"
  table-header:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.ink-2}"
    height: "30px"
    padding: "4px 10px"
  table-row:
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    height: "36px"
    padding: "0px 10px"
  table-row-selected:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.ink}"
  pill-traced:
    backgroundColor: "{colors.traced-fill}"
    textColor: "{colors.traced-ink}"
    typography: "{typography.pill}"
    rounded: "{rounded.pill}"
  pill-strong-lead:
    backgroundColor: "{colors.lead-fill}"
    textColor: "{colors.lead-ink}"
    typography: "{typography.pill}"
    rounded: "{rounded.pill}"
  pill-quiet:
    backgroundColor: "{colors.slate-fill}"
    textColor: "{colors.slate-ink}"
    typography: "{typography.pill}"
    rounded: "{rounded.pill}"
  pill-alarm:
    backgroundColor: "{colors.alarm-fill}"
    textColor: "{colors.alarm-ink}"
    typography: "{typography.pill}"
    rounded: "{rounded.pill}"
  funnel-cell-live:
    backgroundColor: "{colors.accent}"
    rounded: "{rounded.cell}"
  funnel-cell-ruled-out:
    backgroundColor: "{colors.cell}"
    rounded: "{rounded.cell}"
---

# Design System: Canary

This is a native PySide6 (Qt Widgets) app. There is no HTML or CSS anywhere in the product. Every colour above is a `QColor` in `canary/ui/theme.py`, every type role is a call to `theme.body()` or `theme.heading()` at the stated pixel size, and every component is a Qt widget named below. The `theme.STYLESHEET` Qt stylesheet styles controls by object name and dynamic property; fonts are never part of it.

## Overview

**Creative North Star: "The Quiet Console"**

Canary is a security console made to the standard of Linear, Vercel and the Stripe Dashboard. A side navigation, a header per screen, a strip of key figures, then the work in bordered white panels on a cool near-white ground. Everything is visible in one laptop screen at 1440x900. The density comes from tight, aligned panels and hairline rules, not from shrinking the type.

The system holds back colour so that colour means something. Ink and greys do the structural work. One blue marks what the operator can act on and what still fits. State tones appear only as verdict pills, and each pill says its verdict in words. The Canary yellow appears once per screen, as the brand mark. The only thing that moves by itself is the funnel.

The owner retired the old answer-sheet (OMR) look on 14 Nov 2026. Bubbles as decoration, timing marks, pink rules and highlighter yellow are no longer part of the system. The console also must not read as a generic admin dashboard, a dark hacker terminal, a playful colourful app or a lifeless grey one.

**Key Characteristics:**
- Light theme only, identical on macOS and Windows (Fusion style plus one fixed `QPalette`).
- One typeface, Mukta, with tabular figures in every size.
- White 8px panels with 1px borders on a cool ground, never nested, no shadows.
- One blue accent for actions, selection, links and live copies; never for state.
- State colour lives in verdict pills, always beside the verdict in words.
- Sentence case everywhere; plain words for an exam controller.

## Colors

A cool, near-monochrome slate palette with one saturated blue, a small brand yellow, and four muted verdict tones that only appear inside pills.

### Primary
- **Canary Blue** (`accent`): the one accent. Used for primary buttons, input focus borders, text selection, the checked switch track, filled clue marks in tables, and the copies that still fit in the funnel. A screen has one primary button, or two when the second is the only way forward (Read it again, Issue evidence file).
- **Pressed Blue** (`accent-hover`): hover on primary buttons and link buttons; the focus ring on the switch.
- **Blue Wash** (`accent-soft`): the active sidebar item, selected table rows, checked choice rows, and the block tint on real (exposed) questions in the leak text.
- **Blue Ink** (`accent-ink`): accent text on light grounds: links, link buttons, the active nav label, the limits chart's value labels.

### Brand
- **Canary Yellow** (`canary`): the brand mark only. A 16px square with a 4px radius beside the sidebar wordmark, and an 18px square with a 5px radius on the lock card. Nothing else is yellow.

### Neutral
- **Cool Ground** (`ground`): the window ground behind panels, and dialog backgrounds.
- **Paper White** (`surface`): panels, the sidebar, inputs, secondary buttons, the switch knob.
- **Quiet Fill** (`sunken`): table headers, hovered rows and buttons, disabled controls.
- **Hairline** (`border`): panel borders, the sidebar's right edge, row rules, dividers between figures.
- **Firm Line** (`border-strong`): input and secondary-button borders, scrollbar handles, the switch track when off, chart axes.
- **Ruled-out Cell** (`cell`): a copy in the funnel that no longer fits.
- **Ink** (`ink`): primary text, the tooltip ground, the filled dot in the custody timeline.
- **Secondary Ink** (`ink-2`): captions, panel subtitles, table header text, the sidebar status lines, inactive nav labels. Meets 4.5:1 on white and on the ground.
- **Faint Ink** (`ink-3`): placeholders, disabled text, hollow marks. Large text or non-text only.

### State tones (verdict pills only)
Each tone is an ink and fill pair, keyed in `theme.TONES`.
- **Traced Green** (`traced-ink` on `traced-fill`): Traced.
- **Lead Amber** (`lead-ink` on `lead-fill`): Strong lead.
- **Slate** (`slate-ink` on `slate-fill`): Not enough to name anyone yet, We couldn't read this clearly, Waiting to be read, Being read now.
- **Alarm Red** (`alarm-ink` on `alarm-fill`): Not our paper, and a leak that could not be analysed. The alarm ink (`theme.DANGER`) is also the colour of error messages, a broken handover chain, and the wrong-copy line in the limits chart, each always written out in words.

### Named Rules
**The One Accent Rule.** Blue means "act here" or "still fits". It never marks a verdict, a warning or a success.

**The Pill-Only State Rule.** Green, amber and red appear as verdict pills, with the verdict in words on the pill. Colour is never the only carrier of a verdict.

**The One Canary Rule.** Yellow is the brand mark and nothing else: not a highlight, not a warning, not a verdict.

## Typography

**Display Font:** none; Mukta carries every role.
**Body Font:** Mukta (bundled in `canary/ui/fonts`: Regular, Medium, SemiBold)

**Character:** A clean humanist sans with a calm, even texture. Hierarchy comes from weight and a narrow size range, not from a second face.

### Hierarchy
- **Headline** (SemiBold 600, 20px): the page title in `PageHeader`. The lock card's wordmark is 22px and the Add a leak dialog title 18px, in the same weight.
- **Title** (SemiBold 600, 14px): panel titles. The sidebar wordmark is 17px in the same weight.
- **Figure** (SemiBold 600, 22px; 20px on the Leaks strip and the funnel count): key numbers: a copy number, clues matched, the chance by luck.
- **Body** (Regular 400, 14px): running text, table cells, the leak's text, inputs (15px on the lock field). Emphasis inside a panel uses SemiBold 600 at 14px.
- **Body small** (Regular 400, 13px): page subtitles, verdict notes, response lists, chart labels, error messages.
- **Label** (Regular 400, 12px, Secondary Ink): captions over figures, panel subtitles, notes under a value, the sidebar status lines. Table headers use 12px Medium 500.
- **Button** (Medium 500, 14px): every push button and sidebar item.
- **Pill** (SemiBold 600, 12 to 14px): verdict and label pills; 12px in tables and the sidebar, 14px for the case verdict.

### Named Rules
**The setFont Rule.** Fonts are set in code with `theme.body(px, weight)` or `theme.heading(px)` and `setFont`. Never write a font rule in a stylesheet for a plain widget; a stylesheet font overrides `setFont`. Sizes are in pixels so macOS and Windows match.

**The Tabular Rule.** Every font from `theme.body()` turns on `tnum`, so digits line up in columns and do not jump while they change.

**The Sentence Case Rule.** Every label, title, button and pill is in sentence case. No all-caps, no letter-spaced eyebrows, no monospace labels.

## Layout

A fixed shell: a 208px white sidebar on the left with a 1px right border, and one screen beside it on the cool ground. The window opens at 1440x900 and cannot shrink below 1100x700. The lock screen stands alone, with the sidebar hidden.

Every screen uses `Page.frame()`: a 16px gutter (14px at the top) and 12px between stacked regions. A screen reads top to bottom as: `PageHeader` (title and one line of context on the left, actions on the right, 8px apart), a figures strip in one panel, then panels in rows with 12px between them. On the case screen the top row is fixed at 262px so a decided case fits one laptop screen; the panels below take the rest and scroll inside themselves rather than scrolling the page.

Inside a panel: a title row with 8px vertical and 12px horizontal padding, a 1px divider, then a body with 12px padding (10px at the top) and 8px between items. Tables run flush to the panel edge. Figure cells use 14px horizontal padding and are separated by vertical 1px dividers, never by gaps.

The sidebar has 10px side padding, 2px between nav items, the brand row then 14px of space, the screens, a stretch, and the status lines at the foot.

### Named Rules
**The One Screen Rule.** A decided case fits at 1440x900 without the page scrolling. Long content scrolls inside its panel.

## Elevation & Depth

Flat. Depth comes from the ground and surface contrast and from 1px borders, never from shadows. The only dark surface is the tooltip (Ink ground, white text, 4px 8px padding). Panels sit side by side on the ground; nothing floats over the work except dialogs and tooltips.

### Named Rules
**The Flat Panel Rule.** No drop shadows, no gradients. A panel is white with a 1px Hairline border.

**The No Nesting Rule.** Panels are never nested inside each other. Inside a panel, separate regions with `divider()` (a 1px Hairline line), not with another bordered box.

## Shapes

Gently rounded and consistent. Controls (buttons, inputs, nav items, choice rows) take a 6px radius; panels take 8px; the lock card 10px. Pills are fully round (radius equal to half their height). Funnel cells are small squares with a gap and at most a 3px radius; clue marks in tables are 9px squares with a 2px radius. Scrollbars are 10px wide with 3px-radius handles. Lines are 1px everywhere; timeline and chart strokes are 1.2px.

## Components

### Buttons
Quiet and compact, made with `button()`, `primary_button()` and `link_button()` in `widgets/text.py`.
- **Shape:** gently rounded (6px), 22px minimum height, 4px 12px padding.
- **Primary:** Canary Blue with white text and a matching border. Hover moves to Pressed Blue; focus draws an Ink border; disabled turns Hairline with Faint Ink text.
- **Secondary:** white with a Firm Line border and Ink text. Hover fills Quiet Fill, pressed fills Hairline, focus draws a Canary Blue border.
- **Link:** no ground or border, Blue Ink text, 2px 0 padding; hover goes to Pressed Blue and underlines. Used for small in-panel actions such as Play again.
- Button labels are plain verbs in sentence case, with no arrows or icons.

### Pills (`Pill`, `VerdictBadge`)
- **Style:** fully round, tinted with a tone's fill, text in the tone's ink, SemiBold, horizontal padding about 0.7 times the text size. Painted with `QPainter`.
- **VerdictBadge:** the pill with one plain sentence under it in 13px Secondary Ink, 4px apart. It is the headline wherever a verdict is shown.
- In tables, `PillRole` draws the same pill at 12px, 20px tall.

### Switch
A 30x18 track drawn with `QPainter`: Firm Line when off, Canary Blue when on, a white knob, the label 8px to the right in 14px Ink. Focus draws a Pressed Blue ring on the track.

### Panels (`Panel`)
- **Corner Style:** 8px.
- **Background:** Paper White on the Cool Ground.
- **Shadow Strategy:** none (see Elevation & Depth).
- **Border:** 1px Hairline.
- **Internal Padding:** 12px, with an optional title row (14px SemiBold title, 12px muted subtitle, actions on the right) above a 1px divider. `flush=True` drops the body padding for tables and strips; `scroll=True` scrolls the body inside the panel.

### Inputs / Fields
- **Style:** white, 1px Firm Line border, 6px radius, 6px 10px padding, selection in Canary Blue with white text.
- **Focus:** the border turns Canary Blue. No glow.
- **Disabled:** Quiet Fill ground, Faint Ink text, Hairline border.
- Read-only text boxes (`QPlainTextEdit`) take a Hairline border; editable ones a Firm Line border; embedded ones lose border and padding.

### Navigation
The sidebar (`QFrame#sidebar`): the Canary mark and a 17px SemiBold wordmark, then Leaks and Limits as checkable nav buttons (14px Medium, left-aligned, 5px 10px padding, 6px radius). Inactive items are Secondary Ink; hover fills Quiet Fill with Ink text; the active item fills Blue Wash with Blue Ink text. A case belongs to Leaks, so Leaks stays active on the case screen. The `StatusLine` (12px Secondary Ink, one fact per line) sit at the foot.

### Tables (`RuledTable`)
A console table, never default Qt table styling. No grid and no frame; a 30px header in Quiet Fill with 12px Medium Secondary Ink text and a Hairline rule beneath; rows 36px tall (30px in the clue table) with one Hairline rule under each and 10px cell padding. Hover fills Quiet Fill; selection fills Blue Wash and keeps Ink text. Cells are painted as plain text and elided, never as rich text. A cell may carry a 9px mark (filled Canary Blue for a clue that fits, hollow Faint Ink otherwise), a muted or error tone, or a pill.

### Figures strip
One flush panel holding a row of figure cells separated by vertical dividers. Each cell is a 12px caption over a Bold figure, with an optional 12px muted note under it. On the case screen the verdict badge is the first cell, followed by copy, clues that match, and chance by luck.

### Funnel (signature component)
Every candidate copy is a small square cell in a grid, drawn with `QPainter` into cached pixmaps. Cells that no longer fit are Ruled-out Cell grey; the copies that still fit stay Canary Blue. Cells are at most 30px. The animation crossfades clue by clue over 2.6 to 9 seconds (420ms per clue). It is the only self-playing animation, and with `CANARY_REDUCE_MOTION=1` it shows the final state instead. The mapping from cell to copy is shuffled by a fixed seed, and only counts are shown beside it, so on an inconclusive case the picture never says which copies were still in the running. When a single named cell is too small to find, a 2px Canary Blue ring marks it.

### Custody timeline and limits chart
Both are painted with `QPainter` in theme colours only: a 1.2px Firm Line spine, hollow and filled dots, 12px dates and 13px names; chart lines in Canary Blue for right copies and Alarm Red for a wrong copy named, with labels on white knockouts so they stay readable.

## Do's and Don'ts

### Do:
- **Do** take every colour from `canary/ui/theme.py`; never write a new hex in a screen.
- **Do** set fonts with `theme.body(px, weight)` or `theme.heading(px)` and `setFont`, in pixels, with tabular figures.
- **Do** show anything read from a leak or from Telegram through `plain()` or `Qt.TextFormat.PlainText`, never as rich text or a live link.
- **Do** put state colour only in a `Pill` or `VerdictBadge`, with the verdict in words on it.
- **Do** keep the number behind a verdict next to the verdict, in the figures strip.
- **Do** separate regions inside a panel with `divider()`, and lay screens out with `Page.frame()` (16px gutter, 12px gap).
- **Do** give every screen a loading, empty and error state, and label demo data synthetic in the exam title, papers and evidence files. The owner removed the on-screen label from the lock screen and sidebar (14 Nov 2026).
- **Do** draw pills, the switch, funnel cells, table marks, timelines and charts with `QPainter`.
- **Do** honour `CANARY_REDUCE_MOTION=1` by showing the funnel's final state.

### Don't:
- **Don't** use a dark theme, or let macOS or Windows dark mode change the palette.
- **Don't** use Canary Blue for a state, a warning or a success.
- **Don't** use Canary Yellow anywhere but the brand mark.
- **Don't** nest a panel inside a panel, or add drop shadows or gradients.
- **Don't** write a font rule in a stylesheet for a plain widget.
- **Don't** use all-caps labels, letter-spaced eyebrows or monospace labels.
- **Don't** put arrows or icons in buttons.
- **Don't** use default Qt table styling, native grey group boxes, Qt Charts or a web view.
- **Don't** point at a copy on an inconclusive case, in words or in pictures.
- **Don't** animate anything except the funnel.
- **Don't** bring back the retired answer-sheet look: decorative bubbles, timing marks, pink rules, highlighter yellow.
