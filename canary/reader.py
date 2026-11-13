"""The photo reader: turns a leak image into text, on this Mac, with Apple's built-in text recognition.

Nothing leaves the laptop: the image is read by the Vision framework that ships with macOS, through
PyObjC. There is no key, no account and no network use. Other systems have no photo reader yet, and
there typed leaks still work.

Each photo is read twice, once for English and once for Hindi (which also reads Devanagari digits). The
analysis keeps whichever reading lets it recognise more questions. Lines the recogniser is unsure of are
marked, so a poor photo can be called "unreadable" but never "not our paper".

What is read is untrusted text. It is only ever parsed and compared with the bank.
"""
import sys
import unicodedata
from dataclasses import dataclass

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_SIDE = 12000                  # pixels; anything larger is refused rather than decoded
READER_NAME = "Apple Vision, on this Mac"
LANGUAGE_PASSES = (("English", ("en-US",)), ("Hindi", ("hi-IN", "en-US")))
UNSURE_BELOW = 0.5                # Vision's confidence is coarse (0.3, 0.5, 1.0); under this a line is marked unsure
ROW_TOLERANCE = 0.5               # boxes whose centres are within half a line height are one row


class ReaderError(Exception):
    """A problem reading a photo, worded for the person using the app."""


def image_type(image: bytes) -> str | None:
    """The image's type from its first bytes. Only these three types are ever read."""
    if image[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "image/webp"
    return None


def available() -> tuple[bool, str]:
    """(can photos be read on this computer, a sentence saying so)."""
    if sys.platform != "darwin":
        return False, "Photos can only be read on a Mac. Typed leaks still work."
    try:
        import Vision  # noqa: F401
    except ImportError:
        return False, "The Mac's text recognition is not installed (pyobjc-framework-Vision). Typed leaks still work."
    return True, "Photo reader ready, on this Mac."


def clean(text: str) -> str:
    """Drop control and format characters, which can hide or reorder text on screen.

    The two joiners Devanagari and other Indian scripts need to draw conjuncts are kept.
    """
    return "".join(ch for ch in text if ch in "\n\t\u200c\u200d" or unicodedata.category(ch)[0] != "C")


@dataclass
class Box:
    """One line of text the recogniser found. Positions are fractions of the image, measured from the bottom left."""
    text: str
    confidence: float
    x: float
    y: float                      # vertical centre
    height: float


def assemble(boxes: list[Box]) -> tuple[str, list[tuple[int, int]]]:
    """Put recognised lines back in reading order: rows top to bottom, boxes in a row left to right.

    Returns the text and the character spans of lines the recogniser was unsure of.
    """
    rows: list[list[Box]] = []
    for box in sorted(boxes, key=lambda b: -b.y):
        row = next((r for r in rows if abs(r[0].y - box.y) < max(r[0].height, box.height) * ROW_TOLERANCE), None)
        if row is None:
            rows.append([box])
        else:
            row.append(box)
    lines, unsure, at = [], [], 0
    for row in rows:
        row.sort(key=lambda b: b.x)
        line = "    ".join(clean(b.text).strip() for b in row if clean(b.text).strip())
        if not line:
            continue
        if min(b.confidence for b in row) < UNSURE_BELOW:
            unsure.append((at, at + len(line)))
        lines.append(line)
        at += len(line) + 1
    return "\n".join(lines), unsure


def _recognise(image: bytes, languages: tuple[str, ...]) -> list[Box]:
    import Foundation
    import objc
    import Vision
    with objc.autorelease_pool():
        data = Foundation.NSData.dataWithBytes_length_(image, len(image))
        handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None)
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setRecognitionLanguages_(list(languages))
        request.setUsesLanguageCorrection_(False)          # keep every number exactly as printed
        ok, _error = handler.performRequests_error_([request], None)
        if not ok:
            raise ReaderError("The Mac could not read this image. It may be damaged or in an unusual format.")
        boxes = []
        for observation in request.results() or []:
            candidates = observation.topCandidates_(1)
            if not candidates:
                continue
            frame = observation.boundingBox()
            boxes.append(Box(str(candidates[0].string()), float(candidates[0].confidence()), float(frame.origin.x),
                             float(frame.origin.y + frame.size.height / 2), float(frame.size.height)))
        return boxes


def _size(image: bytes) -> tuple[int, int] | None:
    """The image's width and height in pixels, read without decoding the whole image."""
    import Foundation
    import Quartz
    data = Foundation.NSData.dataWithBytes_length_(image, len(image))
    source = Quartz.CGImageSourceCreateWithData(data, None)
    if source is None or Quartz.CGImageSourceGetCount(source) < 1:
        return None
    props = Quartz.CGImageSourceCopyPropertiesAtIndex(source, 0, None) or {}
    width, height = props.get("PixelWidth"), props.get("PixelHeight")
    return (int(width), int(height)) if width and height else None


def read_image(image: bytes) -> dict:
    """Read a leak image on this Mac.

    Returns {"readings": [{"language", "text", "unsure"}, ...], "model": READER_NAME}. Each reading is the
    whole page as text in reading order; "unsure" lists the character spans of lines the recogniser doubted.
    """
    if len(image) > MAX_IMAGE_BYTES:
        raise ReaderError("This image is larger than 10 MB, so it was not read.")
    if image_type(image) is None:
        raise ReaderError("This file is not a JPEG, PNG or WebP image, so it was not read.")
    ok, why = available()
    if not ok:
        raise ReaderError(why)
    size = _size(image)
    if size is None or not (0 < size[0] <= MAX_SIDE and 0 < size[1] <= MAX_SIDE):
        raise ReaderError("This image could not be opened, or it is far larger than a photo of a page.")
    readings = []
    for language, languages in LANGUAGE_PASSES:
        text, unsure = assemble(_recognise(image, languages))
        readings.append({"language": language, "text": text, "unsure": [list(span) for span in unsure]})
    return {"readings": readings, "model": READER_NAME}


def _blank_png(width: int = 64, height: int = 16) -> bytes:
    """A small white PNG, made here so warming up needs no file."""
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    rows = b"".join(b"\x00" + b"\xff" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def warm_up() -> None:
    """Load the recognition models now, so the first real photo is not the one that waits for them.

    On a Mac that has not used them for a while, loading takes up to about 40 seconds. Run at start-up,
    off the main thread. It never raises: if it fails, the first photo simply takes longer.
    """
    if not available()[0]:
        return
    try:
        read_image(_blank_png())
    except Exception:
        pass
