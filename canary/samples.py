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


# ---- more invented questions, used only by the scored test set

MORE_FAKE = [
    ("Which organelle is the site of protein synthesis in a bacterial cell?",
     ("Lysosome", "Ribosome", "Golgi body", "Centriole")),
    ("A train 150 m long crosses a pole in 12 s. Its speed is",
     ("12.5 m/s", "18 m/s", "1800 m/s", "8 m/s")),
    ("Dry ice is the solid form of",
     ("nitrogen", "carbon dioxide", "ammonia", "sulphur dioxide")),
    ("The hardest naturally occurring substance is",
     ("graphite", "quartz", "diamond", "corundum")),
    ("Which part of the human eye controls the amount of light entering it?",
     ("Retina", "Cornea", "Iris", "Optic nerve")),
    ("A lift of mass 800 kg is raised through 15 m. Taking g = 10 m/s², the work done against gravity is",
     ("120 kJ", "12 kJ", "53 kJ", "1200 kJ")),
    ("Litmus solution is obtained from",
     ("a fungus", "a lichen", "a moss", "an alga")),
    ("The planet with the shortest year in the solar system is",
     ("Venus", "Mars", "Mercury", "Earth")),
    ("Which of these animals is a marsupial?",
     ("Platypus", "Kangaroo", "Hedgehog", "Pangolin")),
    ("A pendulum completes 30 swings in 45 s. The time taken for one swing is",
     ("0.67 s", "1.5 s", "15 s", "75 s")),
    ("The gas released when zinc reacts with dilute hydrochloric acid is",
     ("chlorine", "oxygen", "hydrogen", "carbon monoxide")),
    ("Scurvy is caused by a lack of",
     ("vitamin C", "iron", "iodine", "vitamin B1")),
    ("A mirror that always forms an upright and smaller image is",
     ("a plane mirror", "a concave mirror", "a convex mirror", "a parabolic mirror")),
    ("Table salt dissolves in water mainly because water molecules are",
     ("non-polar", "polar", "very heavy", "acidic")),
    ("The largest gland in the human body is the",
     ("pancreas", "liver", "spleen", "pituitary")),
    ("A bulb marked 60 W is lit for 5 hours every day for 30 days. The energy used is",
     ("9 kWh", "90 kWh", "0.9 kWh", "300 kWh")),
    ("An element with 17 protons belongs to which family?",
     ("Alkali metals", "Halogens", "Noble gases", "Alkaline earth metals")),
    ("Which bird lays the largest egg?",
     ("Emu", "Ostrich", "Albatross", "Swan")),
    ("The colour of light bent the most by a glass prism is",
     ("red", "yellow", "green", "violet")),
    ("Milk turns sour because of the formation of",
     ("acetic acid", "lactic acid", "citric acid", "tartaric acid")),
    ("How many chambers does the heart of a frog have?",
     ("two", "three", "four", "one")),
    ("A stone dropped into a well hits the water after 3 s. Taking g = 10 m/s², the depth of the well down to the water is",
     ("45 m", "30 m", "15 m", "90 m")),
]

MORE_TOPICAL = [
    ("Name the pigment that gives red algae their characteristic colour.",
     ("Phycocyanin", "Phycoerythrin", "Carotene", "Chlorophyll a")),
    ("Which element shows the highest electronegativity in the periodic table?",
     ("Oxygen", "Chlorine", "Fluorine", "Neon")),
    ("In which phylum are stinging cells called cnidoblasts found?",
     ("Porifera", "Cnidaria", "Annelida", "Mollusca")),
    ("What type of hybrid orbitals does carbon use in the acetylene molecule?",
     ("sp", "sp2", "sp3", "sp3d")),
]

# A back-translation changes words, not numbers. Each pair is (as written in the bank, as retold).
RETOLD_PHRASES = [
    ("starts from rest", "begins at rest"), ("accelerates uniformly at", "speeds up steadily at"),
    ("The distance it covers is", "How far does it travel?"), ("falls freely", "is dropped"),
    ("it reaches the ground in", "the time it takes to hit the ground is"), ("is thrown vertically upward", "is tossed straight up"),
    ("the maximum height it reaches is", "the greatest height reached is"), ("acts on a body", "is applied to an object"),
    ("initially at rest", "that was not moving"), ("Its speed after", "The velocity it has after"),
    ("moves with a speed of", "travels at"), ("Its kinetic energy is", "Find its kinetic energy."),
    ("is stretched by", "is pulled out by"), ("The potential energy stored in it is", "How much potential energy does it hold?"),
    ("travels with a speed of", "moves at"), ("Its wavelength is", "What is the wavelength?"),
    ("are connected in parallel", "are joined side by side"), ("Their equivalent resistance is", "The combined resistance is"),
    ("An electric heater rated", "A heater with a power of"), ("operates at", "runs on"), ("The current it draws is", "How much current flows?"),
    ("is placed perpendicular to", "is kept at right angles to"), ("The force on it is", "Find the force acting on the wire."),
    ("An object is placed", "A body is kept"), ("in front of a", "before a"), ("The image distance is", "Where is the image formed?"),
    ("falls on a metal", "strikes a metal"), ("The maximum kinetic energy of the photoelectrons is", "The photoelectrons have a maximum kinetic energy of"),
    ("is brought to rest by", "is stopped by"), ("Its stopping distance is", "The distance needed to stop is"),
    ("is charged to", "is charged up to"), ("The energy stored in it is", "It stores an energy of"),
    ("is dissolved in water to make", "is mixed into water to give"), ("The molarity of the solution is", "What is the molarity?"),
    ("is diluted with water to a total volume of", "is topped up with water to"), ("exactly neutralises", "fully neutralises"),
    ("occupies", "takes up"), ("at constant temperature", "with the temperature held fixed"), ("at constant pressure", "with the pressure held fixed"),
    ("The change in its internal energy is", "By how much does its internal energy change?"), ("absorbs", "takes in"),
    ("does", "performs"), ("on its surroundings", "on the surroundings"), ("The heat required to raise", "The heat needed to increase"),
    ("taking its specific heat as", "if the specific heat is"), ("repel each other with a force of", "push each other apart with"),
    ("If the distance between them is doubled", "When they are moved twice as far apart"), ("the force becomes", "the new force is"),
    ("Which of the following", "Which one of these"), ("is called", "is known as"), ("is known as", "is called"),
    ("The number of", "How many"), ("Taking g", "With g"), ("With g", "Taking g"), ("A car", "A vehicle"), ("A stone", "A rock"),
    ("A ball", "A sphere"), ("A body", "An object"), ("A wire", "A conductor"), ("A gas", "Some gas"), ("of mass", "weighing"),
    ("of length", "that is long by"), ("is", "is"),
]


def retell(stem: str, seed: int = 0, strength: float = 0.85) -> str:
    """Reword a question the way a retelling or a translation back into English does. Numbers are untouched."""
    import random
    rng = random.Random(f"retell-{seed}-{stem[:20]}")
    out = stem
    for original, retold in RETOLD_PHRASES:
        if original in out and original != retold and rng.random() < strength:
            out = out.replace(original, retold, 1)
    words = out.split()
    kept = [w for w in words if not (w.lower() in ("the", "a", "an") and rng.random() < 0.25)]
    return " ".join(kept)


def typos(text: str, seed: int = 0, rate: float = 0.12) -> str:
    """Typing slips in ordinary words only: two letters swapped or one dropped. Numbers, units and labels are untouched."""
    import random
    import re
    rng = random.Random(f"typos-{seed}")

    def slip(match):
        word = match.group(0)
        if len(word) < 5 or rng.random() > rate:
            return word
        i = rng.randrange(1, len(word) - 2)
        return word[:i] + word[i + 1] + word[i] + word[i + 2:] if rng.random() < 0.6 else word[:i] + word[i + 1:]
    return re.sub(r"[A-Za-z]+", slip, text)


def strip_numbers(text: str) -> str:
    """Take every number out, as a leaker hiding the values would. Units and words stay."""
    import re
    return re.sub(r"  +", " ", re.sub(r"[-−]?\d+(?:[.,]\d+)*", "", text))
