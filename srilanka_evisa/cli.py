"""Command line entry point: python -m srilanka_evisa {mock-data,apply}."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import mock_data
from .automation import LIVE_BASE_URL, EtaAutomation, load_profile
from .models import ValidationError, load_application
from .payment import prompt_card_details


def _ask_yes_no(question: str) -> bool:
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes", "o", "oui")


def cmd_mock_data(args: argparse.Namespace) -> int:
    path = mock_data.generate(args.out)
    print(f"Mock passports, photos and applicants file written to {path}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    try:
        app = load_application(args.config)
    except ValidationError as exc:
        print(f"Invalid application file: {exc}", file=sys.stderr)
        return 2
    if args.mode:
        app.mode = args.mode
    problems = app.validate()
    if problems:
        print("Please fix the application file:", *(f"  - {p}" for p in problems), sep="\n", file=sys.stderr)
        return 2

    live = urlparse(args.base_url).hostname in ("eta.gov.lk", "www.eta.gov.lk")
    if live and (args.submit or args.pay) and not args.yes:
        print(f"About to submit {len(app.beneficiaries)} traveller(s) to the REAL Sri Lanka ETA portal.\n"
              "Submitting false or test data to a government system is not allowed.")
        if not _ask_yes_no("Is every detail genuine and do you want to submit?"):
            return 1

    card_provider = None
    if args.pay:
        def card_provider():
            print("\nEnter the card to pay the ETA fee with (kept in memory only, never saved).")
            return prompt_card_details()

    confirm = (lambda _msg: True) if args.yes else _ask_yes_no
    bot = EtaAutomation(
        base_url=args.base_url,
        profile=load_profile(args.profile),
        out_dir=args.out,
        headless=not args.headful,
        submit=args.submit or args.pay,
        slow_mo=args.slow_mo,
        save_pages=args.save_pages,
    )
    results = bot.run(app, card_provider=card_provider, confirm_payment=confirm)

    print("\n=== Summary ===")
    for r in results:
        print(f"- {', '.join(r.beneficiaries)}: {r.status}")
        if r.reference:
            print(f"    reference:   {r.reference}")
        if r.payment_url:
            print(f"    payment link: {r.payment_url}")
        if r.payment_message:
            print(f"    payment:     {r.payment_message}")
        if r.error:
            print(f"    error:       {r.error}")
    print(f"Screenshots and results.json in {Path(args.out).resolve()}")
    return 0 if all(r.status != "error" for r in results) else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="srilanka_evisa", description="Sri Lanka ETA (e-visa) automation")
    sub = ap.add_subparsers(dest="command", required=True)

    m = sub.add_parser("mock-data", help="generate SPECIMEN passports, photos and an applicants file")
    m.add_argument("--out", default="mock_data")
    m.set_defaults(func=cmd_mock_data)

    a = sub.add_parser("apply", help="fill the ETA application for all beneficiaries")
    a.add_argument("config", help="applicants YAML file")
    a.add_argument("--base-url", default=LIVE_BASE_URL,
                   help="portal root; use http://127.0.0.1:8765 for the local mock site")
    a.add_argument("--profile", help="site profile YAML (selectors); defaults to the bundled one")
    a.add_argument("--mode", choices=["group", "individual"], help="override the file's mode")
    a.add_argument("--submit", action="store_true",
                   help="submit the application(s) and return the payment link (default: stop at review)")
    a.add_argument("--pay", action="store_true",
                   help="implies --submit; ask for card details and pay on the gateway")
    a.add_argument("--yes", action="store_true", help="don't ask for confirmations")
    a.add_argument("--headful", action="store_true", help="show the browser (needed to solve CAPTCHAs)")
    a.add_argument("--slow-mo", type=int, default=0, help="ms delay between browser actions")
    a.add_argument("--save-pages", action="store_true",
                   help="also save the HTML of every page reached (to map new portal pages)")
    a.add_argument("--out", default="evisa_output", help="folder for screenshots and results.json")
    a.set_defaults(func=cmd_apply)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
