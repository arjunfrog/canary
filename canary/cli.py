"""Command line: python -m canary <command>. Run `python -m canary --help` for the list."""
import argparse
import asyncio
import getpass
import sys
import time
from pathlib import Path

from . import __version__, analyze, audit, config, db, worker
from .vault import SECRET_NAMES, Vault, WrongPassphrase

# command -> (help, task that builds it). Every task is built, so this is empty.
NOT_BUILT: dict = {}


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
    audit.record(db.connect(), "leak decoded by hand", {"verdict": result.verdict, "status": result.status})
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
    from .bank import load_bank
    try:
        data = reader.read_image(Path(args.photo).read_bytes())
    except (reader.ReaderError, OSError) as exc:
        sys.exit(str(getattr(exc, "strerror", None) or exc))
    questions = analyze.questions_from_readings(data, load_bank())
    audit.record(db.connect(), "photo read by hand", {"questions": len(questions)})
    print(f"{len(questions)} questions read by {data['model']}. Nothing left this laptop.")
    for q in questions:
        print(f"\n{q.number if q.number is not None else '?'}. {q.stem}" + ("" if q.legible else "   [hard to read]"))
        for label, option in zip("ABCDEFGH", q.options):
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


def cmd_sim(args) -> int:
    from . import sim
    started = time.monotonic()
    result = sim.run_sim(trials=args.trials, seed=args.seed)
    audit.record(db.connect(), "simulation run", {"trials": args.trials})
    print(f"Wrote {sim.limits_path()} in {time.monotonic() - started:.1f} s. {args.trials:,} runs per point. "
          f"Misread rates are {result['rates_source']}.")
    for scenario in result["scenarios"]:
        at14 = next(p for p in scenario["points"] if p["k"] == 14)
        print(f"  {scenario['title']:52} 14 questions: traced {at14['traced_right'] * 100:5.1f}%, "
              f"strong lead or better {at14['lead_right'] * 100:5.1f}%")
    return 0


def cmd_check(args) -> int:
    from . import check
    vault = unlock()
    return 0 if check.check(db.connect(), vault) else 1


def cmd_reset(args) -> int:
    from . import check
    unlock()                                       # deleting every leak needs the passphrase
    if not args.yes and input("This deletes every leak, case and evidence file. Type reset to go on: ").strip() != "reset":
        print("Nothing was deleted.")
        return 1
    counts = check.reset(db.connect())
    print("Deleted " + ", ".join(f"{count} {name}" for name, count in counts.items())
          + ". The exam, copies and audit log are kept.")
    return 0


def cmd_prepare_demo(args) -> int:
    from . import demo
    from .ui.widgets.pill import VERDICTS
    vault = unlock()
    if not args.yes and input("This deletes every leak, case and evidence file, then adds the demo leaks. "
                              "Type reset to go on: ").strip() != "reset":
        print("Nothing was changed.")
        return 1
    out = Path(args.out).expanduser() if args.out else config.home() / "demo"
    try:
        made = demo.prepare(db.connect(), fingerprint_key(vault), out, args.paper)
    except ValueError as exc:
        sys.exit(str(exc))
    print("Cleared " + ", ".join(f"{count} {name}" for name, count in made["cleared"].items()) + ".")
    print("Demo leaks, each put through the real analysis:")
    for leak in made["leaks"]:
        words = VERDICTS[leak.verdict][0] if leak.verdict in VERDICTS else "Not analysed"
        named = f", copy {leak.found_copy}" if leak.found_copy is not None else ""
        print(f"  {words + named:34} {leak.name}")
    print(f"\nThe paper to leak is translator copy {made['paper_copy']}. Keep that to yourself until it is traced.")
    for path in made["files"]:
        print(f"  {path}")
    return 0


def cmd_export_case(args) -> int:
    from . import check
    try:
        path = check.export_case(db.connect(), args.case_id)
    except LookupError as exc:
        sys.exit(str(exc))
    print(f"Replay written to {path}")
    print(f"Play it with: python -m canary run --replay {path.stem}")
    return 0


def cmd_score(args) -> int:
    from . import score
    if args.show is not None:
        try:
            print(score.show(args.show))
        except (LookupError, PermissionError) as exc:
            sys.exit(str(exc))
        return 0
    outcomes, digest = score.run()
    return 0 if score.report(outcomes, digest) else 1


def cmd_read_again(args) -> int:
    from . import leaks
    if not leaks.read_again(db.connect(), args.leak_id):
        sys.exit(f"Leak {args.leak_id} is not one that failed, so there is nothing to read again.")
    print(f"Leak {args.leak_id} is queued again. It is read when the app or run --headless is running.")
    return 0


def cmd_verify_audit(args) -> int:
    conn = db.connect()
    ok, bad = audit.verify(conn)
    print("Audit log verifies." if ok else f"Audit log is broken at row {bad}.")
    rows, newest = audit.head(conn)
    print(f"{rows} rows. Newest hash: {newest}")
    print("Keep that hash somewhere else. If rows are ever cut off the end, it will no longer be in the log.")
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
    if args.replay:
        from . import check
        from .ui.app import run_app
        try:
            view = check.load_replay(args.replay)
        except LookupError as exc:
            sys.exit(str(exc))
        return run_app(replay=view)
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
        from . import reader
        asyncio.get_running_loop().run_in_executor(None, reader.warm_up)       # loads the photo models in the background
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

    read = sub.add_parser("read", help="Read a photo on this Mac and print the questions found")
    read.add_argument("photo", metavar="PHOTO")
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

    sim = sub.add_parser("sim", help="Run the limits simulation and save it for the Limits screen")
    sim.add_argument("--trials", type=int, default=20000)
    sim.add_argument("--seed", type=int, default=7)
    sim.set_defaults(fn=cmd_sim)

    sub.add_parser("check", help="Run the end-to-end health check").set_defaults(fn=cmd_check)
    reset = sub.add_parser("reset", help="Delete all leaks, cases and evidence files")
    reset.add_argument("--yes", action="store_true", help="do not ask to confirm")
    reset.set_defaults(fn=cmd_reset)
    demo = sub.add_parser("prepare-demo", help="Clear the leaks, add traced demo leaks, write a Hindi paper to leak")
    demo.add_argument("--out", help="Folder for the papers and the sealed slip. Default: CANARY_HOME/demo")
    demo.add_argument("--paper", type=int, help="Which translator copy the Hindi paper is. Default: one at random")
    demo.add_argument("--yes", action="store_true", help="Do not ask before clearing")
    demo.set_defaults(fn=cmd_prepare_demo)
    export = sub.add_parser("export-case", help="Save a case as a replay file")
    export.add_argument("case_id", type=int, metavar="ID")
    export.set_defaults(fn=cmd_export_case)

    score = sub.add_parser("score", help="Score the tool on the fixed set of leaks with known answers")
    score.add_argument("--show", type=int, metavar="ID", help="print one leak's text. Set-aside leaks are refused")
    score.set_defaults(fn=cmd_score)

    again = sub.add_parser("read-again", help="Queue a leak that could not be analysed, to read it again")
    again.add_argument("leak_id", type=int, metavar="ID")
    again.set_defaults(fn=cmd_read_again)

    add = sub.add_parser("add-leak", help="Queue a leak by hand")
    source = add.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", metavar="FILE")
    source.add_argument("--image", metavar="FILE")
    add.set_defaults(fn=cmd_add_leak)

    cases = sub.add_parser("cases", help="List the latest leaks and their verdicts")
    cases.add_argument("--limit", type=int, default=20)
    cases.set_defaults(fn=cmd_cases)

    run = sub.add_parser("run", help="Open the Canary app")
    run.add_argument("--headless", action="store_true", help="Run the worker and listener with no window")
    run.add_argument("--replay", metavar="NAME", help="Show one saved case from CANARY_HOME/replay, with no database or network")
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
