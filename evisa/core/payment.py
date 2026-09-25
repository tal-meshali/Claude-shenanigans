"""Payment: card details, charge confirmation and a generic checkout-form filler.

Card data lives only in memory (pydantic SecretStr), is never logged, written to
the run report, or captured in screenshots, and is only typed into the payment
page after the person explicitly confirms the total.
"""

from __future__ import annotations

import calendar
import getpass
import logging
import re
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Callable, Sequence

from playwright.sync_api import Frame, Page
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError, field_validator, model_validator

from .browser import wait_for_human
from .fields import Field, FieldKind, FormError, click, fill_field, find
from .models import Address, Money

log = logging.getLogger(__name__)


class PaymentMode(str, Enum):
    LINK = "link"  # stop at the payment step and hand back a link
    CARD = "card"  # ask for card details and pay on the external checkout
    NONE = "none"  # stop before payment, no link capture


def luhn_ok(number: str) -> bool:
    digits = [int(d) for d in number][::-1]
    total = sum(d if i % 2 == 0 else (d * 2 - 9 if d * 2 > 9 else d * 2) for i, d in enumerate(digits))
    return total % 10 == 0


def card_brand(number: str) -> str:
    if number.startswith("4"):
        return "Visa"
    if re.match(r"^(5[1-5]|222[1-9]|22[3-9]\d|2[3-6]\d\d|27[01]\d|2720)", number):
        return "Mastercard"
    if re.match(r"^3[47]", number):
        return "American Express"
    return "Card"


class CardDetails(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    holder_name: str
    number: SecretStr
    exp_month: int
    exp_year: int
    cvv: SecretStr
    billing_address: Address | None = None
    email: str = ""
    phone: str = ""

    @field_validator("number", mode="before")
    @classmethod
    def _number(cls, value):
        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        digits = re.sub(r"[\s-]", "", raw)
        if not re.fullmatch(r"\d{12,19}", digits) or not luhn_ok(digits):
            raise ValueError("card number is not valid")
        return SecretStr(digits)

    @field_validator("cvv", mode="before")
    @classmethod
    def _cvv(cls, value):
        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        if not re.fullmatch(r"\d{3,4}", raw.strip()):
            raise ValueError("CVV must be 3 or 4 digits")
        return SecretStr(raw.strip())

    @field_validator("exp_year")
    @classmethod
    def _year(cls, value: int) -> int:
        return value + 2000 if value < 100 else value

    @model_validator(mode="after")
    def _not_expired(self) -> "CardDetails":
        if not 1 <= self.exp_month <= 12:
            raise ValueError("expiry month must be 1-12")
        today = date.today()
        if (self.exp_year, self.exp_month) < (today.year, today.month):
            raise ValueError("card has expired")
        return self

    @property
    def brand(self) -> str:
        return card_brand(self.number.get_secret_value())

    @property
    def masked(self) -> str:
        return f"{self.brand} **** {self.number.get_secret_value()[-4:]}"

    @property
    def first_name(self) -> str:
        return self.holder_name.split()[0]

    @property
    def last_name(self) -> str:
        parts = self.holder_name.split()
        return parts[-1] if len(parts) > 1 else parts[0]

    def __repr__(self) -> str:  # never leak digits through logs/tracebacks
        return f"CardDetails({self.masked}, exp {self.exp_month:02d}/{self.exp_year})"

    __str__ = __repr__


def prompt_card(
    *,
    default_billing: Address | None = None,
    input_fn: Callable[[str], str] = input,
    secret_fn: Callable[[str], str] = getpass.getpass,
    out: Callable[[str], None] = print,
    attempts: int = 3,
) -> CardDetails:
    """Interactively collect card details; number and CVV are not echoed."""
    out("\nCard details (used once for this run, never saved):")
    for attempt in range(1, attempts + 1):
        try:
            holder = input_fn("  Name on card: ").strip()
            number = secret_fn("  Card number (hidden): ")
            expiry = input_fn("  Expiry (MM/YY): ").strip()
            month_str, _, year_str = expiry.replace(" ", "").partition("/")
            cvv = secret_fn("  CVV (hidden): ")
            billing = default_billing
            if default_billing is not None:
                answer = input_fn(f"  Billing address [{default_billing.one_line()}] - press Enter to use it or type 'n' to enter another: ").strip().lower()
                if answer.startswith("n"):
                    billing = None
            if billing is None:
                billing = Address(
                    line1=input_fn("  Billing street address: "),
                    city=input_fn("  Billing city: "),
                    postal_code=input_fn("  Billing postal code: "),
                    country=input_fn("  Billing country (3-letter code, e.g. ISR, USA): "),
                )
            return CardDetails(
                holder_name=holder,
                number=number,
                exp_month=int(month_str),
                exp_year=int(year_str),
                cvv=cvv,
                billing_address=billing,
            )
        except (ValidationError, ValueError) as exc:
            msgs = [e["msg"] for e in exc.errors()] if isinstance(exc, ValidationError) else [str(exc)]
            out(f"  Invalid card details ({'; '.join(msgs)}). Attempt {attempt}/{attempts}.")
    raise ValueError("no valid card details entered")


def confirm_charge(lines: Sequence[str], total: Money | None, *, input_fn: Callable[[str], str] = input, out: Callable[[str], None] = print) -> bool:
    out("\nAbout to pay:")
    for line in lines:
        out(f"  - {line}")
    if total is not None:
        out(f"  Total: {total}")
    return input_fn("Type 'pay' to authorise these charges: ").strip().lower() == "pay"


def sum_money(amounts: Sequence[Money | None]) -> Money | None:
    known = [m for m in amounts if m is not None]
    if not known or len({m.currency for m in known}) != 1:
        return None
    return Money(amount=sum((m.amount for m in known), Decimal(0)), currency=known[0].currency)


# ----------------------------------------------------------- checkout filling


CARD_LOCATORS: dict[str, tuple[str, ...]] = {
    "card_type": ("input[type='radio'][name*='card_type' i]", "input[type='radio'][name*='cardtype' i]"),
    "card_type_select": ("select[name*='card_type' i]", "select[name*='cardtype' i]"),
    "number": (
        "[autocomplete='cc-number']", "input[name*='card_number' i]", "input[name*='cardnumber' i]", "input[id*='cardnumber' i]",
        "input[id*='card_number' i]", "input[name='pan' i]", "input[name*='accountnumber' i]", "label~=Card number", "placeholder=Card number",
    ),
    "holder": (
        "[autocomplete='cc-name']", "input[name*='holder' i]", "input[name*='name_on_card' i]", "input[name*='nameoncard' i]",
        "input[name*='cardname' i]", "label~=Name on card", "label~=Cardholder",
    ),
    "expiry": (
        "[autocomplete='cc-exp']", "input[name*='expiry' i]:not([name*='month' i]):not([name*='year' i])",
        "input[name*='exp_date' i]", "input[name*='expdate' i]", "placeholder=MM/YY", "placeholder=MM / YY",
    ),
    "exp_month": ("[autocomplete='cc-exp-month']", "select[name*='month' i]", "select[id*='month' i]", "input[name*='month' i]"),
    "exp_year": ("[autocomplete='cc-exp-year']", "select[name*='year' i]", "select[id*='year' i]", "input[name*='year' i]"),
    "cvv": (
        "[autocomplete='cc-csc']", "input[name*='cvv' i]", "input[name*='cvc' i]", "input[name*='cvn' i]", "input[name*='csc' i]",
        "input[name*='securitycode' i]", "label~=CVV", "label~=Security code",
    ),
    "first_name": ("input[name*='forename' i]", "input[name*='first_name' i]", "input[name*='firstname' i]", "[autocomplete='given-name']"),
    "last_name": ("input[name*='surname' i]", "input[name*='last_name' i]", "input[name*='lastname' i]", "[autocomplete='family-name']"),
    "address": ("input[name*='address_line1' i]", "input[name*='address1' i]", "input[name*='street' i]", "[autocomplete='address-line1']"),
    "city": ("input[name*='city' i]", "[autocomplete='address-level2']"),
    "postal_code": ("input[name*='postal' i]", "input[name*='zip' i]", "[autocomplete='postal-code']"),
    "country": ("select[name*='country' i]", "[autocomplete='country']"),
    "email": ("input[type='email']", "input[name*='email' i]"),
    "phone": ("input[type='tel']", "input[name*='phone' i]"),
}

PAY_BUTTONS: tuple[str, ...] = (
    "role=button:Pay", "button[type='submit']", "input[type='submit']", "text=Pay now", "text=Submit payment", "role=button:Confirm",
)

_THREE_DS_URL = re.compile(r"(3ds|acs|challenge|authenticat|securecode|verifiedbyvisa)", re.I)


def _month_candidates(month: int) -> list[str]:
    return [f"{month:02d}", str(month), calendar.month_name[month], calendar.month_abbr[month]]


def _card_fields(card: CardDetails) -> list[Field]:
    number = card.number.get_secret_value()
    billing = card.billing_address
    yy = f"{card.exp_year % 100:02d}"
    optional = dict(required=False)
    fields = [
        Field("card_type", FieldKind.RADIO, CARD_LOCATORS["card_type"], card.brand, **optional),
        Field("card_type_select", FieldKind.SELECT, CARD_LOCATORS["card_type_select"], card.brand, **optional),
        Field("number", FieldKind.TEXT, CARD_LOCATORS["number"], number),
        Field("holder", FieldKind.TEXT, CARD_LOCATORS["holder"], card.holder_name, **optional),
        # Separate month/year controls first; a combined MM/YY box only if those are absent.
        Field("exp_month", FieldKind.SELECT, CARD_LOCATORS["exp_month"], _month_candidates(card.exp_month), **optional),
        Field("exp_year", FieldKind.SELECT, CARD_LOCATORS["exp_year"], [str(card.exp_year), yy], **optional),
        Field("expiry", FieldKind.TEXT, CARD_LOCATORS["expiry"], f"{card.exp_month:02d}/{yy}", **optional),
        Field("cvv", FieldKind.TEXT, CARD_LOCATORS["cvv"], card.cvv.get_secret_value()),
        Field("first_name", FieldKind.TEXT, CARD_LOCATORS["first_name"], card.first_name, **optional),
        Field("last_name", FieldKind.TEXT, CARD_LOCATORS["last_name"], card.last_name, **optional),
    ]
    if billing is not None:
        from .countries import country_aliases

        fields += [
            Field("address", FieldKind.TEXT, CARD_LOCATORS["address"], billing.line1, **optional),
            Field("city", FieldKind.TEXT, CARD_LOCATORS["city"], billing.city, **optional),
            Field("postal_code", FieldKind.TEXT, CARD_LOCATORS["postal_code"], billing.postal_code, **optional),
            Field("country", FieldKind.SELECT, CARD_LOCATORS["country"], list(country_aliases(billing.country)), **optional),
        ]
    if card.email:
        fields.append(Field("email", FieldKind.TEXT, CARD_LOCATORS["email"], card.email, **optional))
    if card.phone:
        fields.append(Field("phone", FieldKind.TEXT, CARD_LOCATORS["phone"], card.phone, **optional))
    return fields


def _frames(page: Page) -> list[Frame]:
    return [page.main_frame, *[f for f in page.frames if f is not page.main_frame]]


@dataclass
class CheckoutResult:
    success: bool
    message: str
    reference: str = ""


class CardCheckout:
    """Fills card + billing fields on an unknown checkout page (including iframes)."""

    def __init__(self, overrides: dict[str, list[str]] | None = None, pay_buttons: Sequence[str] = PAY_BUTTONS):
        self.overrides = overrides or {}
        self.pay_buttons = tuple(pay_buttons)

    def fill(self, page: Page, card: CardDetails, *, timeout_ms: int = 15_000) -> list[str]:
        """Returns the keys that were filled (never the values)."""
        # Wait until *some* frame shows a card-number input.
        number_specs = [*self.overrides.get("number", []), *CARD_LOCATORS["number"]]
        deadline = time.monotonic() + timeout_ms / 1000
        while not any(find(fr, number_specs) for fr in _frames(page)):
            if time.monotonic() > deadline:
                raise FormError(f"no card-number field found on checkout page {page.url}")
            page.wait_for_timeout(300)

        filled: list[str] = []
        for f in _card_fields(card):
            if f.key == "expiry" and {"exp_month", "exp_year"} & set(filled):
                continue
            for frame in _frames(page):
                try:
                    record = fill_field(frame, f, None, extra_locators=self.overrides.get(f.key, ()), timeout_ms=0)
                except FormError:
                    record = None
                if record:
                    filled.append(f.key)
                    break
            else:
                if f.required:
                    raise FormError(f"checkout field {f.key!r} not found")
        log.info("checkout fields filled: %s", ", ".join(filled))
        return filled

    def submit(self, page: Page) -> None:
        for frame in reversed(_frames(page)):  # the pay button usually lives next to the card inputs
            if find(frame, self.pay_buttons):
                click(frame, self.pay_buttons, what="pay button", timeout_ms=0)
                return
        raise FormError("pay button not found on checkout page")


def three_ds_challenge_visible(page: Page) -> bool:
    return any(_THREE_DS_URL.search(fr.url or "") for fr in page.frames)


def await_checkout(
    page: Page,
    *,
    succeeded: Callable[[Page], bool],
    failed: Callable[[Page], str | None],
    challenge: Callable[[Page], None] | None,
    headless: bool,
    timeout_s: int,
    notify: Callable[[str], None] = print,
) -> CheckoutResult:
    """Wait for the checkout to finish; hand 3-D Secure challenges to `challenge` or a person."""
    deadline = time.monotonic() + timeout_s
    challenged = False
    while time.monotonic() < deadline:
        try:
            if succeeded(page):
                return CheckoutResult(True, "payment accepted")
            reason = failed(page)
            if reason:
                return CheckoutResult(False, reason)
            if not challenged and three_ds_challenge_visible(page):
                challenged = True
                if challenge is not None:
                    challenge(page)
                else:
                    wait_for_human(
                        page,
                        "approve the payment with your bank (3-D Secure / one-time code)",
                        lambda: not three_ds_challenge_visible(page) or succeeded(page) or bool(failed(page)),
                        headless=headless,
                        timeout_s=max(1, int(deadline - time.monotonic())),
                        notify=notify,
                    )
        except Exception as exc:  # noqa: BLE001 - navigation in flight
            if "Target page, context or browser has been closed" in str(exc):
                raise
        page.wait_for_timeout(500)
    return CheckoutResult(False, "timed out waiting for the payment result")


def open_external_checkout(page: Page, click_pay: Callable[[], None], *, timeout_ms: int = 30_000) -> Page:
    """Click the portal's pay button and return the page that shows the checkout.

    Handles the three shapes portals use: a popup/new tab, a same-tab redirect
    to another host, or a checkout embedded as an iframe from another host.
    """
    from .browser import host_of

    portal_host = host_of(page.url)
    before = set(page.context.pages)
    click_pay()
    waited = 0
    while waited < timeout_ms:
        new_pages = [p for p in page.context.pages if p not in before]
        if new_pages:
            checkout = new_pages[-1]
            checkout.wait_for_load_state()
            return checkout
        if host_of(page.url) not in ("", portal_host):
            page.wait_for_load_state()
            return page
        if any(host_of(fr.url) not in ("", portal_host, "about:blank") for fr in page.frames if fr is not page.main_frame):
            return page
        page.wait_for_timeout(250)
        waited += 250
    raise TimeoutError("the payment page did not open")
