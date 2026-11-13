#!/usr/bin/env python3
"""Render the Canary explainer animation.

    python3 make_video.py                    writes canary-explainer.mp4 (silent, 1920x1080, 30 fps)
    python3 make_video.py --still 12.5 a.png writes one frame at 12.5 s, for checking a scene

Needs Pillow and ffmpeg. Every scene is a function below: edit the text or timings and rerun.
"""
import math
import random
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
OUT = HERE / "canary-explainer.mp4"
W, H, FPS, S = 1920, 1080, 30, 2          # S = supersampling factor
SPEED = 0.87                              # playback speed: 1.0 is the timings as written, lower is slower

BOND = (245, 247, 248)
CARBON = (21, 23, 26)
DROPOUT = (224, 69, 123)
BALLPOINT = (26, 43, 143)
HIGHLIGHT = (255, 225, 0)
SEAL = (179, 38, 30)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREY = (108, 114, 122)
PALE = (214, 219, 224)

FONTS = {"KS": "Khand-SemiBold.ttf", "KM": "Khand-Medium.ttf",
         "MR": "Mukta-Regular.ttf", "MM": "Mukta-Medium.ttf", "MS": "Mukta-SemiBold.ttf"}


@lru_cache(maxsize=None)
def font(name, size):
    return ImageFont.truetype(str(HERE / "fonts" / FONTS[name]), int(size * S))


def clamp(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease(x):
    x = clamp(x)
    return 4 * x * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def seg(t, start, dur):
    """Eased 0 to 1 progress of an animation that starts at `start` and lasts `dur`."""
    return ease((t - start) / dur)


def lerp(a, b, k):
    return a + (b - a) * k


def mix(c1, c2, k):
    return tuple(round(lerp(c1[i], c2[i], k)) for i in range(3))


def rot(x, y, cx, cy, deg):
    r = math.radians(deg)
    dx, dy = x - cx, y - cy
    return cx + dx * math.cos(r) - dy * math.sin(r), cy + dx * math.sin(r) + dy * math.cos(r)


class Canvas:
    """Drawing helpers in 1920x1080 units. `a` fades everything towards the page colour."""

    def __init__(self, img, a=1.0):
        self.d = ImageDraw.Draw(img)
        self.a = a

    def col(self, c, a=1.0, bg=BOND):
        return mix(bg, c, clamp(self.a * a))

    def text(self, x, y, s, f="MR", size=36, color=CARBON, a=1.0, anchor="la", bg=BOND):
        if a <= 0.003:
            return
        self.d.text((x * S, y * S), s, font=font(f, size), fill=self.col(color, a, bg), anchor=anchor)

    def width(self, s, f="MR", size=36):
        return self.d.textlength(s, font=font(f, size)) / S

    def runs(self, x, y, parts, a=1.0, bg=BOND):
        """Draw [(text, font, size, colour), ...] on one baseline. Returns the end x."""
        for s, f, size, color in parts:
            self.text(x, y, s, f, size, color, a, anchor="ls", bg=bg)
            x += self.width(s, f, size)
        return x

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, w=2, a=1.0, r=0, bg=BOND):
        if a <= 0.003 or x1 <= x0 or y1 <= y0:
            return
        box = [x0 * S, y0 * S, x1 * S, y1 * S]
        kw = dict(fill=self.col(fill, a, bg) if fill else None,
                  outline=self.col(outline, a, bg) if outline else None, width=int(w * S))
        if r:
            self.d.rounded_rectangle(box, radius=r * S, **kw)
        else:
            self.d.rectangle(box, **kw)

    def circle(self, x, y, r, fill=None, outline=None, w=2, a=1.0, bg=BOND):
        if a <= 0.003:
            return
        self.d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S],
                       fill=self.col(fill, a, bg) if fill else None,
                       outline=self.col(outline, a, bg) if outline else None, width=int(w * S))

    def line(self, pts, color=CARBON, w=2, a=1.0, bg=BOND):
        if a <= 0.003:
            return
        self.d.line([(x * S, y * S) for x, y in pts], fill=self.col(color, a, bg), width=int(w * S))

    def poly(self, pts, fill=None, outline=None, w=2, a=1.0, bg=BOND):
        if a <= 0.003:
            return
        self.d.polygon([(x * S, y * S) for x, y in pts], fill=self.col(fill, a, bg) if fill else None,
                       outline=self.col(outline, a, bg) if outline else None, width=int(w * S))

    def arrow(self, x0, y0, x1, y1, color=CARBON, w=3, a=1.0, head=14):
        ang = math.atan2(y1 - y0, x1 - x0)
        bx, by = x1 - head * math.cos(ang), y1 - head * math.sin(ang)
        self.line([(x0, y0), (bx, by)], color, w, a)
        px, py = -math.sin(ang) * head * 0.55, math.cos(ang) * head * 0.55
        self.poly([(x1, y1), (bx + px, by + py), (bx - px, by - py)], fill=color, a=a)

    def dashed_rect(self, x0, y0, x1, y1, color=CARBON, w=2, a=1.0, dash=14, gap=10):
        def run(xa, ya, xb, yb):
            n = int(math.hypot(xb - xa, yb - ya) // (dash + gap)) + 1
            ux, uy = (xb - xa) / math.hypot(xb - xa, yb - ya), (yb - ya) / math.hypot(xb - xa, yb - ya)
            for i in range(n):
                s0 = i * (dash + gap)
                s1 = min(s0 + dash, math.hypot(xb - xa, yb - ya))
                self.line([(xa + ux * s0, ya + uy * s0), (xa + ux * s1, ya + uy * s1)], color, w, a)
        run(x0, y0, x1, y0); run(x1, y0, x1, y1); run(x1, y1, x0, y1); run(x0, y1, x0, y0)

    def tick(self, x, y, size=12, color=BALLPOINT, w=4, a=1.0):
        self.line([(x - size, y), (x - size * 0.3, y + size * 0.7), (x + size, y - size * 0.8)], color, w, a)

    def paper(self, cx, cy, w, h, ang=0, a=1.0, outline=CARBON, lines=5, ow=2):
        corners = [rot(cx + sx * w / 2, cy + sy * h / 2, cx, cy, ang) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        self.poly(corners, fill=WHITE, outline=outline, w=ow, a=a)
        for k in range(lines):
            y = cy - h / 2 + h * 0.2 + k * h * 0.15
            x1 = cx + w * 0.32 * (0.35 if k == lines - 1 else 1)
            self.line([rot(cx - w * 0.32, y, cx, cy, ang), rot(x1, y, cx, cy, ang)], mix(WHITE, DROPOUT, 0.55), 2, a, bg=WHITE)

    def bubble_row(self, y, n, filled, progress, a=1.0, x0=140, gap=72, r=22):
        for i in range(n):
            k = seg(progress, i / (n + 6), 6 / (n + 6))
            self.circle(x0 + r + i * gap, y, r, outline=DROPOUT, w=2, a=a * k)
            if i == filled:
                self.circle(x0 + r + i * gap, y, r, fill=BALLPOINT, a=a * seg(progress, 0.85, 0.15))


# ------------------------------------------------------------------ scenes

def title(c, t):
    c.text(140, 250, "Canary", "KS", 230, a=seg(t, 0.1, 0.6))
    c.text(146, 540, "Every copy of the question paper is different.", "MR", 46, a=seg(t, 0.8, 0.6))
    c.text(146, 606, "So a leak tells us which copy it came from.", "MR", 46, a=seg(t, 1.3, 0.6))
    c.bubble_row(800, 23, 16, clamp((t - 1.6) / 1.8))
    c.text(146, 950, "Team RADIOHEAD", "KM", 34, GREY, a=seg(t, 2.2, 0.5))


def problem(c, t):
    xs = [255 + i * 160 for i in range(10)]
    leak = 6
    for i, x in enumerate(xs):
        k = seg(t, 0.3 + i * 0.08, 0.45)
        y = 430 + (1 - k) * 24
        if i == leak:
            m = seg(t, 2.6, 0.9)
            c.paper(x, y + 310 * m, 110, 150, ang=-9 * m, a=k, outline=mix(CARBON, SEAL, m), ow=2 + 2 * m)
            c.text(x + 86, y + 310 * m - 6, "leaked", "KS", 48, SEAL, a=seg(t, 3.3, 0.4), anchor="lm")
        else:
            c.paper(x, y, 110, 150, a=k)
            q = seg(t, 4.3 + i * 0.07, 0.4)
            c.text(x, 296, "?", "KS", 72, DROPOUT, a=q, anchor="mm")
    c.line([(200, 550), (1750, 550)], PALE, 2, a=seg(t, 1.2, 0.5))
    c.text(975, 572, "paper setters  ·  translators  ·  press  ·  transport  ·  exam centres", "MR", 30, GREY,
           a=seg(t, 1.3, 0.5), anchor="ma")


QUESTION = ("A car starts from rest and", "accelerates at ", " m/s² for ", " s.", "The distance it covers is")


def roll(value, t, start, slot):
    """Digits tumble for 0.8 s after `start`, then settle on the value."""
    if t < start + 0.8:
        return str(random.Random(int(t * 15) * 31 + slot).choice([2, 3, 4, 5, 6, 8, 10, 12]))
    return str(value)


def question_card(c, x, y, w, label, a_val, t_val, a, t=99, start=0, slot=0, redact=False, bg=WHITE):
    c.rect(x, y, x + w, y + 320, fill=WHITE, outline=CARBON, w=2, a=a)
    c.text(x + 32, y + 22, label, "KM", 42, a=a, bg=bg)
    c.line([(x + 32, y + 88), (x + w - 32, y + 88)], DROPOUT, 2, a=a, bg=bg)
    c.text(x + 32, y + 150, QUESTION[0], "MR", 33, a=a, anchor="ls", bg=bg)
    num = lambda v, s: (roll(v, t, start, s), "MS", 40, BALLPOINT)
    end = c.runs(x + 32, y + 204, [(QUESTION[1], "MR", 33, CARBON), num(a_val, slot), (QUESTION[2], "MR", 33, CARBON),
                                   num(t_val, slot + 7), (QUESTION[3], "MR", 33, CARBON)], a=a, bg=bg)
    c.text(x + 32, y + 258, QUESTION[4], "MR", 33, a=a, anchor="ls", bg=bg)
    return end


def decoys(c, t):
    cards = [(150, "Translator 07", 3, 6), (710, "Translator 23", 4, 8), (1270, "Translator 41", 6, 10)]
    for i, (x, label, av, tv) in enumerate(cards):
        start = 0.3 + i * 0.6
        k = seg(t, start, 0.5)
        question_card(c, x, 210 + (1 - k) * 20, 500, label, av, tv, k, t, start + 0.2, slot=i * 3)
    k = seg(t, 5.0, 0.6)
    x, y = 480, 610
    c.rect(x, y, x + 960, y + 210, fill=WHITE, a=k)
    c.dashed_rect(x, y, x + 960, y + 210, CARBON, 2, a=k)
    c.text(x + 32, y + 20, "The real paper", "KM", 42, a=k, bg=WHITE)
    yb = y + 150
    end = c.runs(x + 32, yb, [("accelerates at ", "MR", 33, CARBON)], a=k, bg=WHITE)
    c.rect(end, yb - 30, end + 44, yb + 4, fill=BLACK, a=k, bg=WHITE)
    end = c.runs(end + 44, yb, [(" m/s² for ", "MR", 33, CARBON)], a=k, bg=WHITE)
    c.rect(end, yb - 30, end + 44, yb + 4, fill=BLACK, a=k, bg=WHITE)
    c.runs(end + 44, yb, [(" s.", "MR", 33, CARBON)], a=k, bg=WHITE)
    c.text(x + 928, yb, "real numbers kept by the exam cell", "MR", 30, GREY, a=k, anchor="rs", bg=WHITE)


TRAPS = [(330, "Translator 07", (5, 8, 10)), (810, "Translator 23", (4, 7, 11)), (1290, "Translator 41", (6, 9, 10))]


def traps(c, t):
    fade = seg(t, 5.2, 0.5)        # traps fade out
    close = seg(t, 5.6, 0.8)       # rows below slide up
    real = seg(t, 5.4, 0.8)        # decoy dots turn into real ones
    rng = random.Random(4)
    widths = [rng.uniform(0.55, 0.95) for _ in range(12)]
    for p, (x, label, trap_rows) in enumerate(TRAPS):
        k = seg(t, 0.2 + p * 0.2, 0.5)
        h = 660 - 138 * close
        c.rect(x, 190, x + 300, 190 + h, fill=WHITE, outline=CARBON, w=2, a=k)
        c.text(x + 24, 204, label, "KM", 36, a=k, bg=WHITE)
        c.line([(x + 24, 262), (x + 276, 262)], DROPOUT, 2, a=k, bg=WHITE)
        y = 286.0
        base = 0
        for r in range(12):
            is_trap = r in trap_rows
            if is_trap:
                on = seg(t, 1.3 + trap_rows.index(r) * 0.5 + p * 0.15, 0.4)
                a = k * (1 - fade)
                c.rect(x + 20, y, x + 280, y + 34, fill=mix(WHITE, DROPOUT, 0.16 * on), outline=mix(PALE, DROPOUT, on), w=2, a=a, bg=WHITE)
                c.rect(x + 34, y + 13, x + 34 + 130 * widths[r], y + 21, fill=mix(PALE, DROPOUT, 0.6 * on), a=a, bg=WHITE)
                c.text(x + 268, y + 17, "fake", "KS", 26, DROPOUT, a=a * on, anchor="rm", bg=WHITE)
                y += 46 * (1 - close)
            else:
                if base < 4:
                    c.circle(x + 40, y + 17, 7, fill=mix(BALLPOINT, CARBON, real), a=k, bg=WHITE)
                    c.rect(x + 58, y + 13, x + 58 + 190 * widths[base], y + 21, fill=PALE, a=k, bg=WHITE)
                else:
                    c.rect(x + 34, y + 13, x + 34 + 214 * widths[base], y + 21, fill=PALE, a=k, bg=WHITE)
                base += 1
                y += 46
    # legend
    k = seg(t, 1.0, 0.5)
    c.circle(1668, 300, 8, fill=mix(BALLPOINT, CARBON, real), a=k)
    c.text(1690, 300, "decoy numbers" if real < 0.5 else "real numbers", "MR", 28, GREY, a=k, anchor="lm")
    c.rect(1658, 346, 1680, 364, outline=DROPOUT, w=2, a=k * (1 - fade))
    c.text(1690, 355, "fake question", "MR", 28, GREY, a=k * (1 - fade), anchor="lm")
    for x in (706, 1186):
        c.text(x + 14, 450, "=", "KS", 90, CARBON, a=seg(t, 6.6, 0.5), anchor="mm")
    c.text(960, 770, "all three are now the same real paper, ready to print", "MR", 32, GREY, a=seg(t, 7.0, 0.5), anchor="ma")


OPTION_TEXT = ["25 m", "50 m", "10 m", "5 m"]


def option_card(c, x, label, slots_from, slots_to, k_move, a):
    y, w = 250, 760
    c.rect(x, y, x + w, y + 450, fill=WHITE, outline=CARBON, w=2, a=a)
    c.text(x + 36, y + 24, label, "KM", 44, a=a, bg=WHITE)
    c.text(x + w - 36, y + 38, "of 5,000", "MR", 30, GREY, a=a, anchor="ra", bg=WHITE)
    c.line([(x + 36, y + 96), (x + w - 36, y + 96)], DROPOUT, 2, a=a, bg=WHITE)
    c.text(x + 36, y + 162, "A car starts from rest and accelerates at 2 m/s²", "MR", 32, a=a, anchor="ls", bg=WHITE)
    c.text(x + 36, y + 210, "for 5 s. The distance it covers is", "MR", 32, a=a, anchor="ls", bg=WHITE)
    slot_xy = [(x + 60, y + 300), (x + 420, y + 300), (x + 60, y + 384), (x + 420, y + 384)]
    for i, (sx, sy) in enumerate(slot_xy):
        c.text(sx, sy, "ABCD"[i], "KS", 38, a=a, anchor="lm", bg=WHITE)
        c.circle(sx + 56, sy, 17, outline=DROPOUT, w=2, a=a, bg=WHITE)
    for v, txt in enumerate(OPTION_TEXT):
        (ax, ay), (bx, by) = slot_xy[slots_from[v]], slot_xy[slots_to[v]]
        lift = math.sin(math.pi * k_move) * 16
        c.text(lerp(ax, bx, k_move) + 96, lerp(ay, by, k_move) - lift, txt, "MS", 36,
               mix(CARBON, BALLPOINT, math.sin(math.pi * k_move)), a=a, anchor="lm", bg=WHITE)


def options(c, t):
    base = [0, 1, 2, 3]
    first, second = [3, 2, 0, 1], [1, 0, 3, 2]
    option_card(c, 170, "Printed copy 0012", base, base, 0, seg(t, 0.3, 0.5))
    a = seg(t, 0.6, 0.5)
    if t < 5.4:
        option_card(c, 990, "Printed copy 4821", base, first, seg(t, 2.8, 1.1), a)
    else:
        option_card(c, 990, "Printed copy 2907", first, second, seg(t, 5.6, 1.1), a)
    c.text(960, 762, "same questions, same real numbers", "MR", 32, GREY, a=seg(t, 1.2, 0.5), anchor="ma")


def leak(c, t):
    k = seg(t, 0.2, 0.5)
    c.rect(170, 200, 800, 880, fill=WHITE, outline=CARBON, w=2, a=k)
    c.text(206, 218, "Public channel", "KM", 42, a=k, bg=WHITE)
    c.line([(206, 284), (764, 284)], DROPOUT, 2, a=k, bg=WHITE)
    for i, wd in enumerate((330, 250, 380)):
        c.rect(206, 314 + i * 78, 206 + wd, 366 + i * 78, fill=mix(WHITE, PALE, 0.6), a=k, r=10, bg=WHITE)
    m = seg(t, 1.2, 0.6)
    my = 560 + (1 - m) * 40
    c.rect(206, my, 640, my + 290, fill=mix(WHITE, PALE, 0.6), a=k * m, r=12, bg=WHITE)
    c.paper(316, my + 146, 150, 200, ang=5, a=k * m)
    c.rect(430, my + 70, 600, my + 84, fill=PALE, a=k * m, bg=WHITE)
    c.rect(430, my + 106, 560, my + 120, fill=PALE, a=k * m, bg=WHITE)
    c.text(616, my + 262, "21:40", "MR", 24, GREY, a=k * m, anchor="rs", bg=WHITE)
    # the laptop running Canary
    c.rect(1180, 300, 1720, 650, fill=WHITE, outline=CARBON, w=3, a=k)
    c.poly([(1120, 650), (1780, 650), (1750, 690), (1150, 690)], fill=WHITE, outline=CARBON, w=3, a=k)
    c.text(1220, 330, "Canary", "KS", 84, a=k, bg=WHITE)
    pulse = 0.55 + 0.45 * math.sin(t * 4.2)
    arrived = seg(t, 4.6, 0.3)
    status = "listening  ·  read only" if t < 4.6 else "reading the photo" if t < 6.2 else "14 questions found"
    c.circle(1234, 540, 10, fill=BALLPOINT, a=k * (pulse if t < 6.2 else 1), bg=WHITE)
    c.text(1260, 540, status, "MR", 32, CARBON, a=k, anchor="lm", bg=WHITE)
    del arrived
    # dotted path and the photo travelling along it
    p0, p1 = (820, 705), (1160, 500)
    n = 16
    shown = seg(t, 2.4, 1.0)
    for i in range(n):
        if i / n <= shown:
            c.circle(lerp(p0[0], p1[0], i / (n - 1)), lerp(p0[1], p1[1], i / (n - 1)), 4, fill=GREY, a=k)
    go = seg(t, 3.2, 1.4)
    if 0 < go < 1:
        c.paper(lerp(p0[0], p1[0], go), lerp(p0[1], p1[1], go), 54, 72, ang=5, a=k, lines=3)
    c.text(1450, 760, "saves the post, the time and who sent it", "MR", 30, GREY, a=seg(t, 5.0, 0.5), anchor="ma")


CLUES = ["3 m/s²  ·  6 s", "80 m", "40 m/s", "20 N  ·  4 kg  ·  3 s", "6 kg  ·  5 m/s",
         "400 N/m  ·  10 cm", "200 Hz  ·  340 m/s", "60 cm  ·  15 cm", "1100 W  ·  220 V"]
RISK = ["", "", "", "1 in 10", "1 in 82", "1 in 655", "1 in 5,243", "1 in 41,943", "1 in 335,544", "1 in 2,684,355"]
FIT = [50, 7, 2, 1, 1, 1, 1, 1, 1, 1]
LEAKER = 22


def _eliminations():
    rng = random.Random(7)
    others = [i for i in range(50) if i != LEAKER]
    rng.shuffle(others)
    out = {}
    for n, i in enumerate(others):
        out[i] = (1 if n < 43 else 2 if n < 48 else 3, rng.random() * 0.35)
    return out


ELIM = _eliminations()


def which_copy(c, t):
    clue_time = lambda k: 1.0 + (k - 1) * 0.95          # k = 1..9
    done = sum(1 for k in range(1, 10) if t >= clue_time(k))
    a0 = seg(t, 0.2, 0.5)
    c.text(150, 196, "Read from the photo", "KM", 40, a=a0)
    for k in range(1, 10):
        a = seg(t, clue_time(k) - 0.15, 0.35)
        y = 300 + (k - 1) * 58
        c.rect(150, y - 6, 186, y + 6, fill=mix(PALE, BLACK, a), a=a0)
        c.text(214, y, f"Q{k}", "KS", 34, a=a, anchor="lm")
        c.text(300, y, CLUES[k - 1], "MS", 32, BALLPOINT, a=a, anchor="lm")
        c.tick(690, y, a=a)
    c.text(860, 196, "50 translator copies", "KM", 40, a=a0)
    for i in range(50):
        x, y = 890 + (i % 10) * 88, 300 + (i // 10) * 78
        if i == LEAKER:
            c.circle(x, y, 26, fill=BALLPOINT, a=a0)
            c.text(x, y - 1, "23", "KS", 28, WHITE, a=a0 * seg(t, clue_time(3), 0.4), anchor="mm", bg=BALLPOINT)
            continue
        k, delay = ELIM[i]
        gone = seg(t, clue_time(k) + delay, 0.35)
        c.circle(x, y, 26, fill=mix(BALLPOINT, BOND, gone), a=a0)
        c.circle(x, y, 26, outline=mix(BALLPOINT, DROPOUT, gone), w=2, a=a0)
    c.line([(860, 668), (1700, 668)], DROPOUT, 2, a=a0)
    c.text(860, 690, "Copies that still fit", "MR", 30, GREY, a=a0)
    c.text(860, 722, str(FIT[done]), "KS", 84, a=a0)
    c.text(1180, 690, "Chance of a wrong match", "MR", 30, GREY, a=a0)
    c.text(1180, 722, RISK[done] or "too many copies fit", "KS", 84 if RISK[done] else 52,
           CARBON if RISK[done] else GREY, a=a0)
    y0, y1 = 838, 908
    if done < 6:
        c.rect(860, y0, 1700, y1, outline=PALE, w=2, a=a0)
        c.text(884, (y0 + y1) / 2, "Not enough to name anyone yet", "KM", 40, GREY, a=a0, anchor="lm")
    elif done < 9:
        c.rect(860, y0, 1700, y1, outline=BALLPOINT, w=3, a=a0)
        c.text(884, (y0 + y1) / 2, "Strong lead: a person should investigate", "KM", 40, BALLPOINT, a=a0, anchor="lm")
    else:
        swipe = seg(t, clue_time(9) + 0.1, 0.6)
        c.rect(860, y0, 1700, y1, outline=PALE, w=2, a=a0)
        c.rect(860, y0, 860 + 840 * swipe, y1, fill=HIGHLIGHT, a=a0)
        c.text(884, (y0 + y1) / 2, "Traced: translator copy 23", "KS", 44, BLACK, a=a0 * seg(t, clue_time(9) + 0.3, 0.4),
               anchor="lm", bg=HIGHLIGHT)


def custody(c, t):
    k = seg(t, 0.2, 0.5)
    y = 430
    hot = seg(t, 2.9, 0.5)
    c.rect(560, y - 30, 1300, y + 30, fill=HIGHLIGHT, a=k * hot)
    c.line([(260, y), (1660, y)], CARBON, 4, a=k)
    for x, date in ((560, "2 Nov"), (1300, "9 Nov")):
        c.line([(x, y - 26), (x, y + 26)], CARBON, 4, a=k)
        c.text(x, y + 44, date, "MR", 30, GREY, a=k, anchor="ma")
    for x, name in ((410, "Exam cell"), (930, "Translator 23"), (1480, "Exam cell")):
        c.text(x, y - 96, name, "KM", 44, a=k, anchor="ma")
    c.text(930, y - 150, "copy 23 was with", "MR", 30, GREY, a=k * hot, anchor="ma")
    drop = seg(t, 2.0, 0.8)
    lx = 1080
    c.line([(lx, y - 30 - 0), (lx, y + 110)], SEAL, 4, a=k * drop)
    c.circle(lx, y, 11, fill=SEAL, a=k * drop)
    c.text(lx, y + 122, "leak posted 6 Nov, 21:40", "KM", 36, SEAL, a=k * drop, anchor="ma")
    # evidence file
    e = seg(t, 4.4, 0.6)
    c.paper(330, 760, 130, 170, a=e, lines=4)
    c.circle(376, 826, 26, fill=BALLPOINT, a=e)
    c.tick(376, 826, 11, WHITE, 4, a=e)
    c.text(450, 716, "Signed evidence file", "KM", 46, a=e)
    c.text(450, 780, "hashes  ·  signature  ·  handover log", "MR", 30, GREY, a=e)
    c.text(1180, 716, "A person reviews every case", "KM", 46, a=seg(t, 5.0, 0.6))
    c.text(1180, 780, "before any action is taken.", "MR", 30, GREY, a=seg(t, 5.0, 0.6))


VERDICTS = [("Traced", "a wrong match is under 1 in 1,000,000", True, CARBON),
            ("Strong lead", "under 1 in 1,000, so a person investigates", True, CARBON),
            ("Not enough to name anyone", "too few clues, so no name is given", False, CARBON),
            ("Not our paper", "the questions are not ours: a fake leak", False, SEAL)]


def verdicts(c, t):
    for i, (name, note, filled, color) in enumerate(VERDICTS):
        a = seg(t, 0.4 + i * 0.9, 0.5)
        y = 290 + i * 150
        if i == 0:
            wd = c.width(name, "KS", 60)
            c.rect(286, y - 40, 286 + (wd + 36) * seg(t, 0.8, 0.5), y + 40, fill=HIGHLIGHT, a=a)
        c.circle(220, y, 27, fill=BALLPOINT if filled else None, outline=BALLPOINT if filled else DROPOUT, w=2, a=a)
        c.text(304, y - 2, name, "KS", 60, BLACK if i == 0 else color, a=a, anchor="lm", bg=HIGHLIGHT if i == 0 else BOND)
        c.text(1010, y, note, "MR", 32, GREY, a=a, anchor="lm")
        c.line([(180, y + 75), (1840, y + 75)], PALE, 2, a=a * (i < 3))


def machine(c, t):
    k = seg(t, 0.2, 0.5)
    c.text(640, 196, "One laptop", "KM", 42, a=k)
    c.rect(640, 256, 1280, 716, fill=WHITE, outline=CARBON, w=3, a=k)
    boxes = [(300, 400, "Listener", "reads public channels"), (424, 548, "Engine and vault", "keys never leave it"),
             (572, 672, "Dashboard", "opens only on this machine")]
    for i, (y0, y1, name, note) in enumerate(boxes):
        a = seg(t, 0.6 + i * 0.35, 0.45)
        c.rect(684, y0, 1236, y1, outline=DROPOUT, w=2, a=a, bg=WHITE)
        c.text(712, (y0 + y1) / 2 - 20, name, "KM", 38, a=a, anchor="lm", bg=WHITE)
        c.text(712, (y0 + y1) / 2 + 22, note, "MR", 26, GREY, a=a, anchor="lm", bg=WHITE)
    a = seg(t, 1.9, 0.5)
    c.rect(170, 300, 470, 400, outline=CARBON, w=2, a=a)
    c.text(320, 350, "Public channels", "KM", 36, a=a, anchor="mm")
    c.arrow(486, 350, 668, 350, a=a)
    c.text(577, 316, "read only", "MR", 26, GREY, a=a, anchor="mm")
    a = seg(t, 2.5, 0.5)
    c.rect(1500, 436, 1790, 536, outline=CARBON, w=2, a=a)
    c.text(1645, 486, "Photo reader", "KM", 36, a=a, anchor="mm")
    c.arrow(1252, 486, 1484, 486, a=a)
    c.text(1390, 452, "leak photos only", "MR", 26, GREY, a=a, anchor="mm")
    for i, s in enumerate(("Nothing is hosted", "Keys are encrypted", "Every action is logged")):
        a = seg(t, 3.3 + i * 0.4, 0.5)
        x = 300 + i * 500
        c.rect(x, 804, x + 36, 816, fill=BLACK, a=a)
        c.text(x + 56, 810, s, "KM", 40, a=a, anchor="lm")


def end(c, t):
    c.text(140, 250, "Canary", "KS", 230, a=seg(t, 0.1, 0.5))
    c.text(146, 540, "Traces a leaked paper to the copy it came from.", "MR", 46, a=seg(t, 0.5, 0.5))
    c.text(146, 606, "And says so when it cannot.", "MR", 46, a=seg(t, 0.9, 0.5))
    c.bubble_row(800, 23, 16, 1.0, a=seg(t, 0.3, 0.6))


# (function, seconds, header, [(caption start, caption), ...])
SCENES = [
    (title, 5.0, None, []),
    (problem, 7.5, "The problem", [
        (0.2, "One question paper passes through many hands before the exam."),
        (3.6, "When it leaks, every copy looks the same. Nobody can say whose it was.")]),
    (decoys, 11.5, "Before printing: different numbers", [
        (0.3, "Each translator gets the same questions with different numbers."),
        (5.2, "The real numbers stay with the exam cell. No translator ever sees them.")]),
    (traps, 10.0, "Before printing: fake questions", [
        (0.3, "Each translator also gets a few fake questions, different for each person."),
        (5.2, "Before printing, the fakes are removed and the real numbers go back.")]),
    (options, 8.5, "After printing: option order", [
        (0.3, "All 5,000 printed copies ask the same questions."),
        (2.6, "Only the order of the options differs from copy to copy.")]),
    (leak, 8.5, "A leak appears", [
        (0.3, "A photo of the paper turns up in a public channel."),
        (3.2, "Canary is already there on an ordinary account, reading only.")]),
    (which_copy, 13.5, "Which copy is it?", [
        (0.3, "Canary reads the numbers in the photo and checks them against every copy."),
        (4.0, "One copy left is not enough. It keeps going until a wrong match is under one in a million.")]),
    (custody, 8.5, "Who held that copy?", [
        (0.3, "The handover log shows who held the copy when the leak was posted."),
        (4.4, "The result is a lead for investigators, not a verdict.")]),
    (verdicts, 7.5, "It never guesses", [
        (0.3, "Four possible answers. Below the bar, Canary names no one.")]),
    (machine, 8.0, "One machine, no cloud", [
        (0.3, "Everything runs on one laptop. There is no website and no cloud database.")]),
    (end, 5.0, None, []),
]
STARTS = [sum(s[1] for s in SCENES[:i]) for i in range(len(SCENES))]
TOTAL = sum(s[1] for s in SCENES)
FADE_IN, FADE_OUT = 0.45, 0.35


def frame(t):
    img = Image.new("RGB", (W * S, H * S), BOND)
    idx = max(i for i, s in enumerate(STARTS) if t >= s)
    idx = min(idx, len(SCENES) - 1)
    fn, dur, header, captions = SCENES[idx]
    lt = t - STARTS[idx]
    a = min(clamp(lt / FADE_IN), clamp((dur - lt) / FADE_OUT))
    a = ease(a)

    page = Canvas(img)                                     # the sheet itself never fades
    page.line([(112, 0), (112, H)], mix(BOND, DROPOUT, 0.45), 2)
    chapters = len(SCENES) - 2
    for i in range(chapters):
        y = 196 + i * 84
        reached = idx - 1 >= i or idx == len(SCENES) - 1
        current = idx - 1 == i
        wide = 40 + 24 * (ease(clamp(lt / 0.5)) if current else 0)
        page.rect(24, y, 24 + wide, y + 12, fill=BLACK if reached else PALE)

    c = Canvas(img, a)
    if header:
        c.text(140, 62, f"{idx:02d}", "KS", 60, DROPOUT)
        c.text(236, 62, header, "KS", 60)
        page.line([(140, 152), (1840, 152)], DROPOUT, 2)
        page.line([(140, 944), (1840, 944)], mix(BOND, DROPOUT, 0.45), 2)
        for i, (start, text) in enumerate(captions):
            stop = captions[i + 1][0] if i + 1 < len(captions) else dur + 1
            ca = min(seg(lt, start, 0.4), 1 - seg(lt, stop - 0.3, 0.3))
            c.text(140, 966, text, "MR", 38, CARBON, a=ca)
    fn(c, lt)
    return img.reduce(S)


def frame_bytes(i):
    return frame(i / FPS * SPEED).tobytes()


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "--still":
        frame(float(sys.argv[2]) * SPEED).save(sys.argv[3])
        return
    n = int(TOTAL / SPEED * FPS)
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(OUT)], stdin=subprocess.PIPE)
    with Pool() as pool:
        for i, data in enumerate(pool.imap(frame_bytes, range(n), chunksize=8)):
            ff.stdin.write(data)
            if i % 300 == 0:
                print(f"{i}/{n} frames", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"Wrote {OUT} ({TOTAL / SPEED:.1f} s)")


if __name__ == "__main__":
    main()
