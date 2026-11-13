import pytest
from pypdf import PdfReader

from canary import analyze, audit, cli, config, db, pdf
from canary.bank import load_bank
from canary.vault import Vault

KEY = bytes.fromhex("11" * 32)
PASSPHRASE = "a long test passphrase"


@pytest.fixture(scope="module")
def bank():
    return load_bank()


def pages(path):
    return [page.extract_text() for page in PdfReader(str(path)).pages]


@pytest.mark.parametrize("stage, copy_no", [("translation", 23), ("print", 4821)])
def test_page_one_of_a_pdf_decodes_to_its_copy(conn, bank, stage, copy_no):
    path = pdf.export_copy(conn, KEY, stage, copy_no)
    assert path.parent == config.home() / "copies"
    page_one = pages(path)[0]
    questions = analyze.parse_text(page_one)
    assert [q.number for q in questions] == list(range(1, 15))          # page 1 holds exactly the first 14
    result = analyze.analyse_text(page_one, KEY, bank=bank)
    assert (result.stage, result.verdict, result.copy_no) == (stage, "traced", copy_no)
    assert conn.execute("SELECT action FROM audit_log ORDER BY id DESC").fetchone()["action"] == "copy exported"


def test_the_whole_paper_survives_the_round_trip(conn, bank):
    for stage, copy_no, total in (("translation", 7, 186), ("print", 12, 180)):
        text = "\n".join(pages(pdf.export_copy(conn, KEY, stage, copy_no)))
        questions = analyze.parse_text(text)
        assert [q.number for q in questions] == list(range(1, total + 1))
        result = analyze.analyse_text(text, KEY, bank=bank)
        assert all(f.matched for f in result.findings)
        assert (result.stage, result.copy_no) == (stage, copy_no)
        assert result.decoded.score == result.decoded.clues


def test_nothing_on_the_paper_shows_the_copy_or_stage(conn, bank):
    path = pdf.export_copy(conn, KEY, "translation", 23)
    text = "\n".join(pages(path)).lower()
    assert "mock exam, synthetic data" in text
    assert "translat" not in text and "copy" not in text
    assert b"translation" not in path.read_bytes()
    meta = PdfReader(str(path)).metadata
    assert "23" not in (meta.title or "") and "translation" not in str(dict(meta)).lower()


def test_the_barcode_is_random_and_unrelated_to_the_copy(conn, monkeypatch):
    seen = []
    real = pdf.code128.Code128
    monkeypatch.setattr(pdf.code128, "Code128", lambda value, **kw: seen.append(value) or real(value, **kw))
    pdf.export_copy(conn, KEY, "print", 12)
    pdf.export_copy(conn, KEY, "print", 12)
    first, second = seen[0], seen[-1]
    assert first != second and len(first) == 12 and first.isdigit()


def test_bad_stage_or_copy_number_is_refused(conn):
    with pytest.raises(ValueError):
        pdf.export_copy(conn, KEY, "print", 5001)
    with pytest.raises(ValueError):
        pdf.export_copy(conn, KEY, "translation", 0)
    with pytest.raises(ValueError):
        pdf.export_copy(conn, KEY, "press", 1)


def test_print_copies_command_writes_papers_and_sealed_slips(canary_home, tmp_path, monkeypatch, capsys):
    config.ensure_home()
    vault = Vault.create(config.vault_path(), PASSPHRASE)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": PASSPHRASE)
    out = tmp_path / "envelopes"
    assert cli.main(["print-copies", "--translator", "7,23", "--print", "12", "--out", str(out)]) == 0
    names = sorted(p.name for p in out.iterdir())
    assert names == ["print-0012-slip.pdf", "print-0012.pdf", "translation-0007-slip.pdf", "translation-0007.pdf",
                     "translation-0023-slip.pdf", "translation-0023.pdf"]
    slip = pages(out / "translation-0023-slip.pdf")
    assert len(slip) == 1 and "Translator copy" in slip[0] and "23" in slip[0]
    key = bytes.fromhex(vault.get("fingerprint_key"))
    result = analyze.analyse_text(pages(out / "translation-0023.pdf")[0], key)
    assert (result.stage, result.copy_no) == ("translation", 23)
    assert audit.verify(db.connect()) == (True, None)
    assert "translation-0023.pdf" in capsys.readouterr().out
