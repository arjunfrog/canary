"""Sample leaks with known answers: used by the health check, the scored test set and the tests.

Nothing here is secret. The fake paper is a set of invented questions that are not in the bank.
"""
from .fingerprint import Rendered

LABELS = "ABCD"

# (stem, four options). Written for this file; none of them is in the bank, or close to a bank question.
FAKE_PAPER = [
    ("Which gland in the human neck region secretes the hormone calcitonin?",
     ("Adrenal cortex", "Thyroid gland", "Pineal body", "Thymus")),
    ("A submarine emits a sonar pulse that returns from a rock after 1.2 s. If sound travels at 1500 m/s in sea water, how far away is the rock?",
     ("900 m", "1800 m", "450 m", "1250 m")),
    ("Which vitamin deficiency leads to night blindness in children?",
     ("Vitamin K", "Vitamin D", "Vitamin A", "Vitamin B12")),
    ("An astronaut weighs 720 N on Earth. On a planet whose surface gravity is one sixth as strong, the astronaut would weigh",
     ("120 N", "4320 N", "360 N", "72 N")),
    ("Brass is an alloy made mainly from",
     ("iron and carbon", "tin and lead", "copper and zinc", "copper and tin")),
    ("A cyclist rides 18 km north and then 24 km east. Her displacement from the starting point is",
     ("42 km", "30 km", "6 km", "21 km")),
    ("Which noble gas is used to fill advertising signs that glow orange-red?",
     ("Argon", "Neon", "Krypton", "Radon")),
    ("The longest bone found in the human skeleton is the",
     ("humerus", "tibia", "fibula", "femur")),
    ("Light year is a unit used by astronomers to measure",
     ("time", "brightness", "distance", "angular speed")),
    ("The chemical commonly known as baking soda is",
     ("sodium carbonate", "sodium hydrogen carbonate", "calcium oxide", "sodium chloride")),
    ("A kettle rated 2000 W is switched on for 3 minutes. The electrical energy it uses is",
     ("6000 J", "360 kJ", "666 J", "36 kJ")),
    ("Which blood group is known as the universal donor?",
     ("AB positive", "A negative", "O negative", "B positive")),
    ("The powerhouse organelle found in aerobic eukaryotic cells is surrounded by how many membranes?",
     ("one", "two", "three", "none")),
    ("Rusting of an iron nail left in damp air is an example of",
     ("a physical change", "sublimation", "a slow oxidation reaction", "neutralisation")),
]

# Invented questions on facts the bank also asks about, worded differently and with other options.
# A real fake paper covers the same syllabus, so some of its questions always look like these.
FAKE_TOPICAL = [
    ("The oxidation number of manganese in potassium permanganate is",
     ("+7", "+2", "+4", "+6")),
    ("Who proposed the fluid mosaic model of the plasma membrane?",
     ("Watson and Crick", "Singer and Nicolson", "Schleiden and Schwann", "Robert Hooke")),
    ("How many moles of water are present in 54 g of water (molar mass 18 g/mol)?",
     ("3 mol", "2 mol", "36 mol", "0.33 mol")),
    ("Insulin is secreted by which cells of the islets of Langerhans?",
     ("Alpha cells", "Beta cells", "Delta cells", "Acinar cells")),
]


def leak_text(questions, options: bool = True, start: int = 1, renumber: bool = False) -> str:
    """Type questions out the way a leak would be pasted: a numbered stem, then options two per line.

    `questions` holds Rendered questions from a copy, or (stem, options) pairs.
    """
    blocks = []
    for i, q in enumerate(questions):
        if isinstance(q, Rendered):
            number, stem, opts = (start + i if renumber else q.number), q.stem, q.options
        else:
            number, (stem, opts) = start + i, q
        lines = [f"{number}. {stem}"]
        if options:
            lines.append(f"(A) {opts[0]}    (B) {opts[1]}")
            lines.append(f"(C) {opts[2]}    (D) {opts[3]}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def fake_paper_text(count: int = 14) -> str:
    return leak_text(FAKE_PAPER[:count])


# ---- ways a leak gets damaged or changed on its way to a channel

def garble(text: str, rate: float, seed: int = 0) -> str:
    """Damage text the way a bad scan does: wrong, missing and doubled characters. Digits are hit too."""
    import random
    rng = random.Random(f"garble-{seed}-{rate}")
    out = []
    for ch in text:
        if ch == "\n" or (ch in "().ABCD" and rng.random() > rate * 0.3):
            out.append(ch)
            continue
        roll = rng.random()
        if roll < rate * 0.5:
            out.append(rng.choice("abcdefghijklmnopqrstuvwxyz#@~ "))
        elif roll < rate * 0.8:
            continue
        elif roll < rate:
            out.append(ch + rng.choice("il1|.,'"))
        else:
            out.append(ch)
    return "".join(out)


def reader_answer(questions, stems=None, stems_en=None, legible: bool = True) -> dict:
    """What the photo reader would return for these Rendered questions. Used to mock the reader.

    `stems` replaces the stems as shown (for a paper in another language), and `stems_en` gives the
    reader's English translations of them.
    """
    out = []
    for i, q in enumerate(questions):
        out.append({"number": q.number, "legible": legible, "stem": stems[i] if stems else q.stem,
                    "options": list(q.options), "stem_en": stems_en[i] if stems_en else None,
                    "options_en": list(q.options) if stems_en else None})
    return {"questions": out}
