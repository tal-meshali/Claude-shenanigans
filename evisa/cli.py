"""Command line: python -m evisa {apply,demo,mock-server,mock-docs,inspect,countries}."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .core.browser import BrowserOptions
from .core.captcha import LoopbackCheckboxCaptcha
from .core.documents import generate_mock_documents
from .core.models import ApplicationStatus, load_batch
from .core.payment import CardDetails, PaymentMode, confirm_charge
from .core.runner import BatchReport, BatchValidationError, RunOptions, SafetyError, run_batch
from .sites import SITES, get_site

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
DEMO_BATCHES = {"tanzania": EXAMPLES / "tanzania_family.json", "srilanka": EXAMPLES / "srilanka_family.yaml"}
TEST_CARDS = {"approved": "4111111111111111", "3ds": "4000000000003220", "declined": "4000000000000002"}


def _print_summary(report: BatchReport, run_dir: Path) -> None:
    print(f"\n=== {report.site_name}: {len(report.results)} beneficiar{'y' if len(report.results) == 1 else 'ies'} ===")
    for r in report.results:
        print(f"- {r.full_name}: {r.status.value}" + (f"  [{r.application_id}]" if r.application_id else ""))
        if r.payment and r.payment.success:
            print(f"    paid {r.payment.amount or ''}  receipt {r.payment.reference or '-'}")
        elif r.payment:
            print(f"    payment {r.payment.status.value}: {r.payment.message}")
        if r.payment_link:
            link = r.payment_link
            if link.gateway_url:
                print(f"    checkout link: {link.gateway_url}")
            print(f"    portal link:   {link.portal_url}")
            for k, v in link.resume.items():
                print(f"      {k}: {v}")
        if r.error:
            print(f"    error: {r.error.splitlines()[0]}")
    print(f"\nReport, screenshots and summary.md: {run_dir.resolve()}")


def _options(args: argparse.Namespace, **overrides) -> RunOptions:
    opts = RunOptions(
        payment=PaymentMode(args.payment),
        browser=BrowserOptions(headless=not args.headed, slow_mo_ms=args.slow_mo),
        out_dir=Path(args.out),
        allow_production=getattr(args, "live", False),
        stop_after=args.stop_after,
        capture_gateway_url=not args.no_checkout_link,
    )
    for key, value in overrides.items():
        setattr(opts, key, value)
    return opts


def _run(site, batch, opts: RunOptions) -> int:
    try:
        report = run_batch(site, batch, opts)
    except (BatchValidationError, SafetyError) as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 2
    _print_summary(report, Path(report.run_dir))
    return 1 if any(r.status is ApplicationStatus.FAILED for r in report.results) else 0


def _auto_confirm(lines, total) -> bool:
    """Demo with a mock test card: show what would be charged and go ahead."""
    confirm_charge(lines, total, input_fn=lambda _prompt: "pay")
    return True


def cmd_apply(args: argparse.Namespace) -> int:
    batch = load_batch(args.batch)
    if args.mode:
        batch.mode = args.mode
    overrides = json.loads(Path(args.selectors).read_text()) if args.selectors else None
    site = get_site(args.country or batch.country, base_url=args.base_url, selector_overrides=overrides)
    if site.is_production:
        print(f"Target: the REAL {site.name} portal ({site.base_url}). Only genuine traveller data may be submitted.")
    return _run(site, batch, _options(args))


def cmd_demo(args: argparse.Namespace) -> int:
    from .mock import start_mock
    from .mock.gateway import complete_mock_3ds

    batch = load_batch(args.batch or DEMO_BATCHES[args.country])
    if args.mode:
        batch.mode = args.mode
    overrides = {"captcha": LoopbackCheckboxCaptcha()}
    if args.payment == "card" and args.test_card:
        test_number = TEST_CARDS[args.test_card]
        overrides["card_provider"] = lambda applicants: CardDetails(
            holder_name=applicants[0].full_name, number=test_number, exp_month=12, exp_year=2030, cvv="123",
            billing_address=applicants[0].contact.address)
        overrides["confirm"] = _auto_confirm
        overrides["three_ds"] = complete_mock_3ds
    with start_mock(batch.country, port=args.port) as env:
        print(f"Mock {batch.country} portal on {env.base_url} (gateway {env.gateway.base_url})")
        site = get_site(batch.country, base_url=env.base_url)
        return _run(site, batch, _options(args, **overrides))


def cmd_mock_server(args: argparse.Namespace) -> int:
    from .mock import start_mock

    env = start_mock(args.country, port=args.port, gateway_port=args.gateway_port)
    print(f"Mock {args.country} portal: {env.base_url}\nMock card gateway: {env.gateway.base_url}\nCtrl+C to stop.")
    try:
        import threading

        threading.Event().wait()
    except KeyboardInterrupt:
        env.close()
    return 0


def cmd_mock_docs(args: argparse.Namespace) -> int:
    batch = load_batch(args.batch)
    for applicant in batch.applicants:
        if not applicant.mock:
            print(f"skipping {applicant.ref}: not marked mock: true")
            continue
        docs = generate_mock_documents(applicant, batch.trip_for(applicant), Path(args.out), overwrite=True)
        print(f"{applicant.ref}: " + ", ".join(f"{k}={v}" for k, v in docs.model_dump().items() if v and k != "other"))
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """Read-only: list the form controls of a page, to calibrate selectors."""
    from playwright.sync_api import sync_playwright

    js = """() => Array.from(document.querySelectorAll('input,select,textarea,button')).filter(e => e.type !== 'hidden').map(e => {
        const cell = e.closest('td'); const prev = cell && cell.previousElementSibling;
        const label = (e.labels && e.labels[0] && e.labels[0].innerText) || (prev && prev.innerText) || e.getAttribute('aria-label') || e.placeholder || '';
        const o = {tag: e.tagName.toLowerCase(), type: e.type, name: e.name, id: e.id, label: label.trim().slice(0, 80)};
        if (e.tagName === 'SELECT') o.options = Array.from(e.options).slice(0, 15).map(x => x.text.trim());
        if (e.type === 'submit' || e.type === 'button' || e.tagName === 'BUTTON') o.text = (e.innerText || e.value || '').trim();
        return o; })"""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        page = browser.new_page()
        page.goto(args.url)
        if args.headed:
            input("Navigate to the page you want to inspect in the browser window, then press Enter here... ")
        for row in page.evaluate(js):
            print(json.dumps(row, ensure_ascii=False))
        browser.close()
    return 0


def cmd_countries(args: argparse.Namespace) -> int:
    for key, cls in SITES.items():
        print(f"{key:10} {cls.name:12} {cls.default_base_url}  group applications: {'yes' if cls.supports_group else 'no'}")
    return 0


def _run_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--payment", choices=[m.value for m in PaymentMode], default="link",
                   help="link: stop at payment and return the payment link (default); card: ask for a card and pay")
    p.add_argument("--mode", choices=["group", "individual"], help="override the batch file's group/individual mode")
    p.add_argument("--stop-after", metavar="STEP", help="dry run: stop after this step (e.g. 'declaration' or 'review')")
    p.add_argument("--no-checkout-link", action="store_true", help="in link mode, do not open the checkout to capture its URL")
    p.add_argument("--headed", action="store_true", help="show the browser (needed to solve CAPTCHAs / 3-D Secure yourself)")
    p.add_argument("--slow-mo", type=int, default=0, metavar="MS", help="delay between browser actions")
    p.add_argument("--out", default="runs", help="folder for reports and screenshots (default: runs/)")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="evisa", description="e-visa application automation (Tanzania, Sri Lanka)")
    ap.add_argument("-v", "--verbose", action="store_true", help="log which locator matched each field")
    sub = ap.add_subparsers(dest="command", required=True)

    a = sub.add_parser("apply", help="apply for every beneficiary in a batch file")
    a.add_argument("batch", help="batch file (.json or .yaml)")
    a.add_argument("--country", choices=sorted(SITES), help="override the batch's country")
    a.add_argument("--base-url", help="portal root (default: the real portal; use the mock's URL for testing)")
    a.add_argument("--live", action="store_true", help="confirm you intend to file real applications on the real portal")
    a.add_argument("--selectors", help="JSON {field key: [locator, ...]} tried before the built-in locators")
    _run_flags(a)
    a.set_defaults(func=cmd_apply)

    d = sub.add_parser("demo", help="run a batch against the bundled mock portal (nothing leaves this machine)")
    d.add_argument("--country", choices=sorted(DEMO_BATCHES), default="tanzania")
    d.add_argument("--batch", help="batch file (default: the country's example family)")
    d.add_argument("--port", type=int, default=0)
    d.add_argument("--test-card", choices=sorted(TEST_CARDS), help="with --payment card: use a mock test card instead of prompting")
    _run_flags(d)
    d.set_defaults(func=cmd_demo)

    m = sub.add_parser("mock-server", help="serve a mock portal + card gateway until Ctrl+C")
    m.add_argument("--country", choices=sorted(DEMO_BATCHES), default="tanzania")
    m.add_argument("--port", type=int, default=8765)
    m.add_argument("--gateway-port", type=int, default=8766)
    m.set_defaults(func=cmd_mock_server)

    g = sub.add_parser("mock-docs", help="render SPECIMEN passport / photo / ticket / hotel files for mock applicants")
    g.add_argument("batch")
    g.add_argument("--out", default="examples/mock_documents")
    g.set_defaults(func=cmd_mock_docs)

    i = sub.add_parser("inspect", help="read-only: list a page's form fields to calibrate selectors")
    i.add_argument("url")
    i.add_argument("--headed", action="store_true", help="open a window so you can navigate to the page first")
    i.set_defaults(func=cmd_inspect)

    c = sub.add_parser("countries", help="list supported countries")
    c.set_defaults(func=cmd_countries)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if args.verbose:
        logging.getLogger("evisa").setLevel(logging.DEBUG)
    return args.func(args)
