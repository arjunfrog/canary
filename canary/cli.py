"""Command line: python -m canary <command>.

Working now: init, vault set, verify-audit, add-leak, cases, run (opens the app), screenshot.
Every other command is registered and says which task builds it.
"""
import argparse
import asyncio
import getpass
import sys
import time
from pathlib import Path

from . import __version__, analyze, audit, config, db, worker
from .vault import SECRET_NAMES, Vault, WrongPassphrase

# command -> (help, task that builds it)
NOT_BUILT = {
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
    from . import evidence
    print(f"Signing key fingerprint, to publish so evidence files can be checked: {evidence.signing_fingerprint(vault)}")
    return 0


def cmd_vault_set(args) -> int:
    vault = unlock()
    vault.set(args.name, getpass.getpass(f"New value for {args.name}: ").strip())
    audit.record(db.connect(), "secret changed", {"name": args.name})
    print(f"{args.name} updated.")
    return 0


def fingerprint_key(vault: Vault) -> bytes:
    return bytes.fromhex(vault.get("fingerprint_key"))


def cmd_decode(args) -> int:
    text = Path(args.text).read_text(encoding="utf-8", errors="replace")
    result = analyze.analyse_text(text, fingerprint_key(unlock()))
    if result.status == "unreadable":
        print("We couldn't read this clearly. No verdict.")
        return 0
    stage = {"translation": "translation (leaked before printing)", "print": "print (leaked after printing)"}
    print(f"stage:    {stage.get(result.stage, 'not known')}")
    print(f"verdict:  {result.verdict}")
    if result.decoded is None:
        return 0
    d = result.decoded
    print(f"copy:     {d.copy_no if d.copy_no is not None else 'none named'}")
    print(f"score:    {d.score} of {d.clues} clues matched")
    print(f"expected false matches: {d.expected_false_matches:.3g}  (among {d.candidates} candidate copies)")
    print("funnel:   clue  question  kind    copies left  expected false matches")
    for step in result.steps:
        print(f"          {step['clue']:>4}  {step['question_id']:8}  {step['kind']:6}  {step['remaining']:>11}  "
              f"{step['expected_false_matches']:.3g}")
    return 0


def _numbers(text: str | None) -> list[int]:
    try:
        return [int(n) for n in (text or "").split(",") if n.strip()]
    except ValueError:
        sys.exit(f"Copy numbers must be whole numbers separated by commas, not {text!r}.")


def cmd_print_copies(args) -> int:
    from . import pdf
    translator, printed = _numbers(args.translator), _numbers(args.print)
    if not translator and not printed:
        sys.exit("Name at least one copy: --translator 7,23 or --print 12,4821")
    vault = unlock()
    try:
        written = pdf.print_copies(db.connect(), fingerprint_key(vault), translator, printed, Path(args.out))
    except ValueError as exc:
        sys.exit(str(exc))
    for path in written:
        print(path)
    return 0


def cmd_seed(args) -> int:
    from . import seed
    started = time.monotonic()
    counts = seed.seed(db.connect())
    for name, count in counts.items():
        print(f"{name:18} {count:>6}")
    print(f"Seeded in {time.monotonic() - started:.1f} s. Every person is synthetic.")
    return 0


def cmd_verify_chain(args) -> int:
    from . import seed
    try:
        ok = seed.verify_chain(db.connect(), args.stage, args.copy)
    except LookupError as exc:
        sys.exit(str(exc))
    print(f"The custody chain of {args.stage} copy {args.copy} " + ("verifies." if ok else "is broken."))
    return 0 if ok else 1


def cmd_read(args) -> int:
    from . import reader
    vault = unlock()
    if not vault.get("gemini_api_key"):
        sys.exit("No Gemini key in the vault. Add one with: python -m canary vault set gemini_api_key")
    try:
        data = reader.read_image(Path(args.photo).read_bytes(), vault.get("gemini_api_key"), use_cache=not args.no_cache)
    except reader.ReaderError as exc:
        sys.exit(str(exc))
    audit.record(db.connect(), "photo read by hand", {"questions": len(data["questions"])})
    print(f"{len(data['questions'])} questions read by {data['model']}.")
    for q in data["questions"]:
        print(f"\n{q['number'] if q['number'] is not None else '?'}. {q['stem']}" + ("" if q["legible"] else "   [hard to read]"))
        if q.get("stem_en"):
            print(f"   in English: {q['stem_en']}")
        for label, option in zip("ABCDEFGH", q["options"]):
            print(f"   ({label}) {option}")
    return 0


def cmd_tg_login(args) -> int:
    from . import lurker
    vault = unlock()
    try:
        name = asyncio.run(lurker.login(vault))
    except lurker.TelegramNotReady as exc:
        sys.exit(str(exc))
    audit.record(db.connect(), "telegram login saved")
    print(f"Logged in as {name}. The session is saved in the vault, not in a file.")
    return 0


def cmd_watch(args) -> int:
    from . import lurker
    vault = unlock()
    try:
        title = asyncio.run(lurker.watch(db.connect(), vault, args.username))
    except lurker.TelegramNotReady as exc:
        sys.exit(str(exc))
    print(f"Watching {title}. New posts are read from now on, and the last {lurker.BACKFILL} when the app starts.")
    return 0


def cmd_unwatch(args) -> int:
    from . import lurker
    try:
        removed = lurker.unwatch(db.connect(), args.username)
    except lurker.TelegramNotReady as exc:
        sys.exit(str(exc))
    print("Stopped watching it." if removed else "That chat was not being watched.")
    return 0


def cmd_verify(args) -> int:
    from . import evidence
    checks = evidence.verify_file(Path(args.file), args.expect)
    for name, ok in checks:
        print(f"{'ok  ' if ok else 'FAIL'}  {name}")
    good = all(ok for _, ok in checks)
    print("\nThis evidence file verifies." if good else "\nThis evidence file does NOT verify. Do not rely on it.")
    return 0 if good else 1


def cmd_evidence(args) -> int:
    from . import evidence
    vault = unlock()
    try:
        path = evidence.build_evidence(db.connect(), vault, args.case_id)
    except evidence.NoEvidence as exc:
        sys.exit(str(exc))
    print(f"Evidence file written and signed: {path}")
    print(f"Signing key fingerprint: {evidence.signing_fingerprint(vault)}")
    return 0


def cmd_verify_audit(args) -> int:
    ok, bad = audit.verify(db.connect())
    print("Audit log verifies." if ok else f"Audit log is broken at row {bad}.")
    return 0 if ok else 1


def cmd_add_leak(args) -> int:
    from . import leaks
    conn = db.connect()
    try:
        if args.text:
            leak_id = leaks.add_manual_leak(conn, text=Path(args.text).read_text(encoding="utf-8", errors="replace"))
        else:
            leak_id = leaks.add_manual_leak(conn, image_path=args.image)
    except (leaks.LeakRefused, OSError) as exc:
        sys.exit(str(exc))
    print(f"Leak {leak_id} queued.")
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
    from . import lurker
    vault = unlock()
    conn = db.connect()
    audit.record(conn, "unlocked")
    print(f"Canary {__version__} is running with no window. Data: {config.home()}", flush=True)
    print("Worker: on.  Telegram listener: on if the vault holds a login.  Ctrl+C to stop.", flush=True)

    async def main() -> None:
        stop = asyncio.Event()
        await asyncio.gather(worker.run_worker(analyze.make_handler(vault), stop),
                             lurker.run_listener(conn, vault, stop))

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

    decode = sub.add_parser("decode", help="Decode a typed leak from a file")
    decode.add_argument("--text", metavar="FILE", required=True)
    decode.set_defaults(fn=cmd_decode)

    copies = sub.add_parser("print-copies", help="Write copies as PDF, with a sealed slip for each")
    copies.add_argument("--translator", metavar="N,N", help="translator copy numbers, 1 to 50")
    copies.add_argument("--print", metavar="N,N", help="printed copy numbers, 1 to 5000")
    copies.add_argument("--out", metavar="DIR", required=True)
    copies.set_defaults(fn=cmd_print_copies)

    sub.add_parser("seed", help="Create the exam, copies, synthetic people and custody chains").set_defaults(fn=cmd_seed)

    chain = sub.add_parser("verify-chain", help="Check one copy's custody chain")
    chain.add_argument("--stage", choices=("translation", "print"), required=True)
    chain.add_argument("--copy", type=int, required=True)
    chain.set_defaults(fn=cmd_verify_chain)

    read = sub.add_parser("read", help="Read a photo and print the questions found")
    read.add_argument("photo", metavar="PHOTO")
    read.add_argument("--no-cache", action="store_true", help="ask the reader again even if this photo was read before")
    read.set_defaults(fn=cmd_read)

    sub.add_parser("tg-login", help="Log the Telegram account in, once").set_defaults(fn=cmd_tg_login)
    watch = sub.add_parser("watch", help="Watch a public channel or group")
    watch.add_argument("username", metavar="USERNAME")
    watch.set_defaults(fn=cmd_watch)
    unwatch = sub.add_parser("unwatch", help="Stop watching a channel or group")
    unwatch.add_argument("username", metavar="USERNAME")
    unwatch.set_defaults(fn=cmd_unwatch)

    verify = sub.add_parser("verify", help="Verify a signed evidence file. Needs no passphrase")
    verify.add_argument("file", metavar="FILE", help="the manifest.json inside an evidence folder")
    verify.add_argument("--expect", metavar="FINGERPRINT", help="the signing key fingerprint the exam authority published")
    verify.set_defaults(fn=cmd_verify)
    issue = sub.add_parser("evidence", help="Issue the signed evidence file for a traced or strong-lead case")
    issue.add_argument("case_id", type=int)
    issue.set_defaults(fn=cmd_evidence)

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
