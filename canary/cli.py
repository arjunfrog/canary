"""Command line: python -m canary <command>.

Working now: init, vault set, verify-audit, add-leak, cases, run (opens the app), screenshot.
Every other command is registered and says which task builds it.
"""
import argparse
import asyncio
import getpass
import hashlib
import shutil
import sys
from pathlib import Path

from . import __version__, audit, config, db, worker
from .analyze import analyze_leak
from .vault import SECRET_NAMES, Vault, WrongPassphrase

# command -> (help, task that builds it)
NOT_BUILT = {
    "decode": ("Decode a typed leak from a file", 2),
    "print-copies": ("Write copies as PDF, with sealed slips", 3),
    "seed": ("Create the exam, copies, people and custody chains", 4),
    "verify-chain": ("Check one copy's custody chain", 4),
    "read": ("Read a photo and print the questions found", 5),
    "tg-login": ("Log the Telegram account in, once", 7),
    "watch": ("Watch a public channel or group", 7),
    "unwatch": ("Stop watching a channel or group", 7),
    "verify": ("Verify a signed evidence file", 11),
    "sim": ("Run the limits simulation", 12),
    "check": ("Run the end-to-end health check", 13),
    "reset": ("Delete leaks, cases and evidence files", 13),
    "export-case": ("Save a case as a replay file", 13),
}


def unlock() -> Vault:
    path = config.vault_path()
    if not path.exists():
        sys.exit("No vault yet. Run: python -m canary init")
    try:
        return Vault.open(path, getpass.getpass("Passphrase: "))
    except WrongPassphrase as exc:
        sys.exit(str(exc))


def cmd_init(args) -> int:
    config.ensure_home()
    path = config.vault_path()
    if path.exists():
        sys.exit(f"A vault already exists at {path}. Use: python -m canary vault set NAME")
    first = getpass.getpass("Choose a passphrase: ")
    if len(first) < 12:
        sys.exit("Use at least 12 characters.")
    if first != getpass.getpass("Type it again: "):
        sys.exit("The two did not match.")
    typed = {}
    for name in SECRET_NAMES[2:]:
        value = getpass.getpass(f"{name} (Enter to skip): ").strip()
        if value:
            typed[name] = value
    vault = Vault.create(path, first, typed)
    conn = db.connect()
    audit.record(conn, "vault created", {"secrets": vault.names()})
    print(f"Vault written to {path}. Filled in: {', '.join(vault.names())}")
    return 0


def cmd_vault_set(args) -> int:
    vault = unlock()
    vault.set(args.name, getpass.getpass(f"New value for {args.name}: ").strip())
    audit.record(db.connect(), "secret changed", {"name": args.name})
    print(f"{args.name} updated.")
    return 0


def cmd_verify_audit(args) -> int:
    ok, bad = audit.verify(db.connect())
    print("Audit log verifies." if ok else f"Audit log is broken at row {bad}.")
    return 0 if ok else 1


def cmd_add_leak(args) -> int:
    conn = db.connect()
    text = image_path = sha = None
    if args.text:
        text = Path(args.text).read_text()
    else:
        data = Path(args.image).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        dest = config.home() / "leaks" / f"{sha[:16]}{Path(args.image).suffix.lower()}"
        shutil.copyfile(args.image, dest)
        dest.chmod(0o600)
        image_path = str(dest)
    cur = conn.execute(
        "INSERT INTO leaks (source, raw_text, image_path, image_sha256, posted_at, received_at) VALUES ('manual', ?, ?, ?, ?, ?)",
        (text, image_path, sha, db.now(), db.now()))
    conn.commit()
    audit.record(conn, "leak added by hand", {"leak_id": cur.lastrowid})
    print(f"Leak {cur.lastrowid} queued.")
    return 0


def cmd_cases(args) -> int:
    rows = db.connect().execute(
        """SELECT l.id, l.source, l.status, l.received_at, c.verdict, c.stage, p.copy_no, l.error
           FROM leaks l LEFT JOIN cases c ON c.leak_id = l.id LEFT JOIN copies p ON p.id = c.copy_id
           ORDER BY l.id DESC LIMIT ?""", (args.limit,)).fetchall()
    if not rows:
        print("No leaks yet.")
        return 0
    print(f"{'leak':>5}  {'source':8}  {'status':10}  {'verdict':14}  {'stage':11}  {'copy':>5}  received")
    for r in rows:
        print(f"{r['id']:>5}  {r['source']:8}  {r['status']:10}  {r['verdict'] or '-':14}  {r['stage'] or '-':11}  "
              f"{r['copy_no'] if r['copy_no'] is not None else '-':>5}  {r['received_at']}"
              + (f"  ({r['error']})" if r["error"] else ""))
    return 0


def cmd_run(args) -> int:
    if not args.headless:
        from .ui.app import run_app               # imported here so the other commands work without Qt
        return run_app()
    vault = unlock()
    conn = db.connect()
    audit.record(conn, "unlocked")
    print(f"Canary {__version__} is running with no window. Data: {config.home()}")
    print("Worker: on.  Telegram listener: not built yet (task 7).  Ctrl+C to stop.")
    del vault                                     # task 7 will pass it to the listener

    async def main() -> None:
        await worker.run_worker(conn, analyze_leak, asyncio.Event())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        audit.record(conn, "stopped")
        print("\nStopped.")
    return 0


def cmd_screenshot(args) -> int:
    from .ui.screenshot import render_all
    for path in render_all(Path(args.out)):
        print(path)
    return 0


def cmd_not_built(args) -> int:
    print(f"`{args.command}` is not built yet. It is task {NOT_BUILT[args.command][1]} in docs/PROMPTS.md.")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="canary", description="Traces a leaked exam paper to the copy it came from.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create the encrypted vault").set_defaults(fn=cmd_init)

    vault = sub.add_parser("vault", help="Change one secret in the vault")
    vault_sub = vault.add_subparsers(dest="vault_command", required=True)
    vset = vault_sub.add_parser("set", help="Set one secret")
    vset.add_argument("name", choices=SECRET_NAMES)
    vset.set_defaults(fn=cmd_vault_set)

    sub.add_parser("verify-audit", help="Check the audit log's hash chain").set_defaults(fn=cmd_verify_audit)

    add = sub.add_parser("add-leak", help="Queue a leak by hand")
    source = add.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", metavar="FILE")
    source.add_argument("--image", metavar="FILE")
    add.set_defaults(fn=cmd_add_leak)

    cases = sub.add_parser("cases", help="List the latest leaks and their verdicts")
    cases.add_argument("--limit", type=int, default=20)
    cases.set_defaults(fn=cmd_cases)

    run = sub.add_parser("run", help="Open the Canary app")
    run.add_argument("--headless", action="store_true", help="Run the worker with no window")
    run.set_defaults(fn=cmd_run)

    shot = sub.add_parser("screenshot", help="Save an image of every screen, to check the design")
    shot.add_argument("out", metavar="DIR")
    shot.set_defaults(fn=cmd_screenshot)

    for name, (text, task) in NOT_BUILT.items():
        p = sub.add_parser(name, help=f"{text} (task {task}, not built yet)")
        p.add_argument("rest", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
        p.set_defaults(fn=cmd_not_built)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)
