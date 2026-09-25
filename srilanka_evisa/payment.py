"""Card details handling and filling of the external payment gateway page.

Card data is only ever held in memory: it is never logged, written to the
results file, or captured in screenshots/traces."""

from __future__ import annotations

import getpass
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from playwright.sync_api import Page

from .forms import click, fill_fields


class CardError(ValueError):
    pass


def luhn_ok(number: str) -> bool:
    digits = [int(d) for d in number][::-1]
    total = sum(digits[0::2]) + sum(sum(divmod(2 * d, 10)) for d in digits[1::2])
    return total % 10 == 0


@dataclass
class CardDetails:
    number: str = field(repr=False)
    expiry_month: int
    expiry_year: int
    cvv: str = field(repr=False)
    holder: str = ""

    def __post_init__(self) -> None:
        self.number = re.sub(r"[\s-]", "", self.number)
        if not re.fullmatch(r"\d{12,19}", self.number) or not luhn_ok(self.number):
            raise CardError("card number is invalid")
        if self.expiry_year < 100:
            self.expiry_year += 2000
        if not 1 <= self.expiry_month <= 12:
            raise CardError("expiry month must be 1-12")
        today = date.today()
        if (self.expiry_year, self.expiry_month) < (today.year, today.month):
            raise CardError("card has expired")
        if not re.fullmatch(r"\d{3,4}", self.cvv):
            raise CardError("CVV must be 3 or 4 digits")

    @property
    def masked(self) -> str:
        return f"**** **** **** {self.number[-4:]}"

    def __repr__(self) -> str:
        return f"CardDetails({self.masked}, {self.expiry_month:02d}/{self.expiry_year}, holder={self.holder!r})"

    def field_values(self) -> dict[str, Any]:
        return {
            "card_holder": self.holder,
            "card_number": self.number,
            "expiry_month": f"{self.expiry_month:02d}",
            "expiry_year": str(self.expiry_year),
            "expiry": f"{self.expiry_month:02d}/{self.expiry_year % 100:02d}",
            "cvv": self.cvv,
        }


def prompt_card_details(input_fn: Callable[[str], str] = input,
                        secret_fn: Callable[[str], str] = getpass.getpass) -> CardDetails:
    """Ask for card details on the terminal; number and CVV are not echoed."""
    while True:
        try:
            holder = input_fn("Cardholder name: ").strip()
            number = secret_fn("Card number (hidden): ")
            exp = input_fn("Expiry (MM/YY): ").strip()
            m = re.fullmatch(r"(\d{1,2})\s*/\s*(\d{2}|\d{4})", exp)
            if not m:
                raise CardError("expiry must look like MM/YY")
            cvv = secret_fn("CVV (hidden): ").strip()
            return CardDetails(number=number, expiry_month=int(m[1]), expiry_year=int(m[2]), cvv=cvv, holder=holder)
        except CardError as exc:
            print(f"  {exc}, please try again.")


@dataclass
class PaymentOutcome:
    status: str  # "paid" | "declined" | "unknown"
    final_url: str
    message: str = ""


def pay_on_gateway(page: Page, card: CardDetails, profile: dict[str, Any],
                   confirm: Callable[[str], bool], timeout_ms: int = 60_000) -> PaymentOutcome:
    """Fill the hosted payment page the ETA portal redirected to, then pay."""
    gw = profile["payment_gateway"]
    page.wait_for_load_state("domcontentloaded")
    values = card.field_values()
    specs = dict(gw["fields"])
    # Use split month/year inputs when present, otherwise a combined MM/YY box.
    filled = fill_fields(page, specs, values, profile["date_format"], all_frames=True)
    if not ({"expiry_month", "expiry_year"} <= set(filled) or "expiry" in filled):
        raise CardError(f"could not find the card expiry field(s) on {page.url}")

    if not confirm(f"Charge card {card.masked} on {page.url.split('?')[0]}?"):
        return PaymentOutcome("unknown", page.url, "payment not confirmed by user; card fields left filled")

    click(page, gw["submit"], "pay", all_frames=True)
    ok, bad = re.compile(gw["success_regex"], re.I), re.compile(gw["failure_regex"], re.I)
    deadline_step = 500
    for _ in range(timeout_ms // deadline_step):
        page.wait_for_timeout(deadline_step)
        try:
            text = page.inner_text("body")
        except Exception:
            continue  # navigating
        if bad.search(text):
            return PaymentOutcome("declined", page.url, _first_line(text, bad))
        if ok.search(text):
            return PaymentOutcome("paid", page.url, _first_line(text, ok))
    return PaymentOutcome("unknown", page.url, "no success/failure message seen (3-D Secure?)")


def _first_line(text: str, rx: re.Pattern[str]) -> str:
    for line in text.splitlines():
        if rx.search(line):
            return line.strip()
    return ""
