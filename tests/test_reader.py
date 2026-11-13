import io
import sys

import pytest

from canary import analyze, cli, reader
from canary import fingerprint as fp
from canary.bank import load_bank
from canary.samples import leak_text

KEY = bytes.fromhex("11" * 32)
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
MAC = pytest.mark.skipif(not reader.available()[0], reason="the Mac's text recognition is not available here")


def page_image(text: str, width: int = 2400) -> bytes:
    """Draw typed text as a page photo, with the app's own font."""
    from PIL import Image, ImageDraw, ImageFont
    from canary.config import PACKAGE_DIR
    font = ImageFont.truetype(str(PACKAGE_DIR / "ui" / "fonts" / "Mukta-Regular.ttf"), 34)
    lines = text.splitlines()
    image = Image.new("RGB", (width, 80 + 52 * len(lines)), "white")
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text((60, 40 + 52 * i), line, font=font, fill="black")
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


# ---- what is refused before anything is read

def test_files_that_are_not_images_are_never_read(monkeypatch):
    monkeypatch.setattr(reader, "_recognise", lambda *a: pytest.fail("must not be read"))
    with pytest.raises(reader.ReaderError, match="not a JPEG, PNG or WebP"):
        reader.read_image(b"%PDF-1.7 ...")
    with pytest.raises(reader.ReaderError, match="larger than 10 MB"):
        reader.read_image(PNG + b"\x00" * reader.MAX_IMAGE_BYTES)


def test_other_systems_say_photos_need_a_mac(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    ok, words = reader.available()
    assert not ok and "only be read on a Mac" in words and "Typed leaks still work" in words
    with pytest.raises(reader.ReaderError, match="only be read on a Mac"):
        reader.read_image(PNG)


@MAC
def test_a_broken_image_is_refused_in_plain_words():
    with pytest.raises(reader.ReaderError, match="could not be opened"):
        reader.read_image(PNG)                                   # a PNG signature and nothing else


# ---- putting the lines back in reading order

def test_lines_are_put_back_in_reading_order_and_doubtful_ones_are_marked():
    boxes = [reader.Box("(B) 300 m", 1.0, 0.5, 0.80, 0.02), reader.Box("1. A car starts from rest", 1.0, 0.05, 0.90, 0.02),
             reader.Box("(A) 30 m", 1.0, 0.1, 0.801, 0.02), reader.Box("(C) 600 m", 1.0, 0.1, 0.70, 0.02),
             reader.Box("(D) 6O m", 0.3, 0.5, 0.70, 0.02)]
    text, unsure = reader.assemble(boxes)
    assert text == "1. A car starts from rest\n(A) 30 m    (B) 300 m\n(C) 600 m    (D) 6O m"
    assert [text[a:b] for a, b in unsure] == ["(C) 600 m    (D) 6O m"]


def test_the_reading_that_recognises_more_questions_is_kept_and_doubtful_questions_are_hard_to_read():
    bank = load_bank()
    copy = fp.render_translator_copy(KEY, 1, 23, bank)[:4]
    good = leak_text(copy)
    data = {"readings": [{"language": "English", "text": "zzq kkx\n(A) &S (B) 988 S", "unsure": []},
                         {"language": "Hindi", "text": good, "unsure": [[0, 5]]}]}
    questions = analyze.questions_from_readings(data, bank)
    assert [q.number for q in questions] == [1, 2, 3, 4]
    assert [q.legible for q in questions] == [False, True, True, True]


# ---- the real reader, on this Mac

@MAC
def test_a_photo_of_a_translator_page_is_read_on_this_mac_and_traced(monkeypatch):
    bank = load_bank()
    image = page_image(leak_text(fp.render_translator_copy(KEY, 1, 23, bank)[:6]))
    data = reader.read_image(image)
    assert data["model"] == reader.READER_NAME and [r["language"] for r in data["readings"]] == ["English", "Hindi"]
    result = analyze.analyse_questions(analyze.questions_from_readings(data, bank), KEY, bank=bank)
    assert (result.verdict, result.stage, result.copy_no) == ("traced", "translation", 23)


@MAC
def test_a_page_with_no_options_lines_found_is_split_by_its_option_groups():
    bank = load_bank()
    copy = fp.render_print_copy(KEY, 1, 4821, bank)[:3]
    options_only = "\n".join(f"(A) {q.options[0]}    (B) {q.options[1]}\n(C) {q.options[2]}    (D) {q.options[3]}" for q in copy)
    questions = analyze.parse_text(options_only)
    assert len(questions) == 3 and all(len(q.options) == 4 for q in questions)
    findings = analyze.collect(questions, bank)
    assert [f.question_id for f in findings] == [q.question_id for q in copy]          # known by their options alone
    assert [f.order for f in findings] == [q.order for q in copy]


def test_read_command_needs_no_passphrase_and_sends_nothing(canary_home, tmp_path, monkeypatch, capsys):
    bank = load_bank()
    text = leak_text(fp.render_translator_copy(KEY, 1, 23, bank)[:2])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": pytest.fail("must not ask for the passphrase"))
    monkeypatch.setattr(reader, "read_image", lambda image: {"readings": [{"language": "English", "text": text, "unsure": []}],
                                                             "model": reader.READER_NAME})
    photo = tmp_path / "leak.png"
    photo.write_bytes(PNG)
    assert cli.main(["read", str(photo)]) == 0
    out = capsys.readouterr().out
    assert "2 questions read by Apple Vision, on this Mac. Nothing left this laptop." in out and "(D)" in out


def test_warming_up_reads_a_blank_image_and_never_raises(monkeypatch):
    seen = []
    monkeypatch.setattr(reader, "available", lambda: (True, "ready"))
    monkeypatch.setattr(reader, "read_image", lambda image: seen.append(image) or {})
    reader.warm_up()
    assert seen and reader.image_type(seen[0]) == "image/png"

    def broken(image):
        raise RuntimeError("anything at all")
    monkeypatch.setattr(reader, "read_image", broken)
    reader.warm_up()                                            # no exception
    monkeypatch.setattr(reader, "available", lambda: (False, "not a Mac"))
    monkeypatch.setattr(reader, "read_image", lambda image: pytest.fail("must not read off a Mac"))
    reader.warm_up()


@MAC
def test_the_blank_warm_up_image_is_a_real_image():
    data = reader.read_image(reader._blank_png())
    assert [r["text"] for r in data["readings"]] == ["", ""]
