"""Render every screen to a PNG without showing a window. Used to check the design by eye.

    python -m canary screenshot OUT_DIR

The screens are drawn from a throwaway database filled with synthetic leaks, so the pictures always show
real-looking data and never touch CANARY_HOME.
"""
import os
import tempfile
from pathlib import Path

FIXTURE_KEY = bytes.fromhex("5c" * 32)          # only ever used for these pictures


def fixture_home(root: Path) -> list[int]:
    """Fill a temporary CANARY_HOME with a seeded exam and one leak of each kind. Returns the leak ids."""
    from .. import analyze, db, leaks, seed, worker
    from .. import fingerprint as fp
    from ..bank import load_bank
    from ..samples import fake_paper_text, garble, leak_text

    os.environ["CANARY_HOME"] = str(root)
    conn = db.connect()
    seed.seed(conn)
    bank = load_bank()
    translator = fp.render_translator_copy(FIXTURE_KEY, 1, 23, bank)
    printed = fp.render_print_copy(FIXTURE_KEY, 1, 4821, bank)
    texts = [
        leak_text(translator[:14]),
        leak_text(printed[:14]),
        fake_paper_text(),
        leak_text(translator[20:24], options=False),
        garble(leak_text(translator[:14]), 0.4, seed=3),
        leak_text(printed[90:96]),
    ]
    ids = [leaks.add_manual_leak(conn, text=t) for t in texts]
    posts = [("Exam leaks demo", "examleaks_demo", 4107, "Paper Seller", "paper_seller"),
             ("NEET papers 2026", "neet_papers_demo", 911, "R. K.", None)]
    for leak_id, (title, username, message_id, sender, handle) in zip(ids[:2], posts):
        conn.execute("""UPDATE leaks SET source = 'telegram', chat_title = ?, chat_username = ?, chat_id = ?, message_id = ?,
                        message_url = ?, sender_name = ?, sender_username = ?, sender_id = ? WHERE id = ?""",
                     (title, username, -1000000000000 - message_id, message_id, f"https://t.me/{username}/{message_id}",
                      sender, handle, 700000 + message_id, leak_id))
    conn.commit()
    handler = lambda c, leak: analyze.analyze_leak(c, leak, FIXTURE_KEY, None, bank)
    while worker.process_next(conn, handler):
        pass
    failed = leaks.add_manual_leak(conn, text=leak_text(printed[40:50]))
    conn.execute("UPDATE leaks SET status = 'failed', error = ? WHERE id = ?",
                 ("The Mac could not read this image. It may be damaged or in an unusual format.", failed))
    conn.commit()
    queued = leaks.add_manual_leak(conn, text=leak_text(printed[30:40]))
    conn.close()
    return ids + [queued, failed]


def render_all(out_dir: Path, width: int = 1440, height: int = 900) -> list[Path]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from .. import config, queries, sim
    from ..vault import Vault
    from . import theme
    from .main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    theme.apply(app)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    previous_home, previous_motion = os.environ.get("CANARY_HOME"), os.environ.get("CANARY_REDUCE_MOTION")
    with tempfile.TemporaryDirectory(prefix="canary-shots-") as tmp:
        try:
            ids = fixture_home(Path(tmp))
            os.environ["CANARY_REDUCE_MOTION"] = "1"         # pictures show the funnel's final state
            Vault.create(config.vault_path(), "screenshots only")
            window = MainWindow()
            window.resize(width, height)
            window.show()

            def grab(name: str) -> None:
                for _ in range(3):
                    app.processEvents()
                path = out_dir / f"{name}.png"
                window.grab().save(str(path))
                written.append(path)

            grab("lock")
            # Show the screens without the passphrase step and without starting the background thread.
            window._unlocked = True
            window.nav_bar.setVisible(True)
            window.status.show_status(queries.status(window.conn), None, (True, "Photo reader ready, on this Mac."))
            window.show_page("leaks")
            grab("leaks")
            case_ids = [queries.get_leak(window.conn, i).case_id for i in ids]
            window.open_case(case_ids[0], play=False)
            grab("case")
            extras = {"case_print": ("case", 1), "case_fake": ("case", 2), "case_inconclusive": ("case", 3),
                      "case_unreadable": ("leak", 4), "case_lead": ("case", 5), "case_failed": ("leak", 7)}
            for name, (kind, index) in extras.items():
                if kind == "case":
                    window.open_case(case_ids[index], play=False)
                else:
                    window.open_leak(ids[index])
                grab(name)
            window.open_case(case_ids[0], play=False)
            bar = window.pages["case"].scroll.verticalScrollBar()
            for _ in range(3):
                app.processEvents()
            bar.setValue(bar.maximum())
            grab("case_lower")
            window.show_page("limits")
            grab("limits_not_run")
            sim.run_sim()
            window.show_page("limits")
            grab("limits")
            window.pages["limits"].select(4)
            grab("limits_merged")
            window.pages["limits"].select(3)
            grab("limits_fails")
            window.vault = None                              # nothing was unlocked, so nothing to record on close
            window.close()
        finally:
            for name, value in (("CANARY_HOME", previous_home), ("CANARY_REDUCE_MOTION", previous_motion)):
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
    return written
