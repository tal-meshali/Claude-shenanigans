"""Pay-by-card and payment-link routines shared by every site profile.

A site only supplies how to open its checkout and how its result pages read
(regexes); the confirmation, card entry, 3-D Secure hand-off, screenshot
suppression and verdict detection live here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from playwright.sync_api import Page

from .browser import host_of
from .fields import FormError
from .models import Money, PaymentOutcome, PaymentStatus
from .payment import CardCheckout, CardDetails, await_checkout
from .site import StepContext


@dataclass(frozen=True)
class ResultPatterns:
    """How the portal / gateway words the outcome of a payment."""

    paid: re.Pattern[str]
    declined: re.Pattern[str]
    receipt: re.Pattern[str] | None = None


def _text(page: Page) -> str:
    try:
        return page.inner_text("body")
    except Exception:  # noqa: BLE001 - closed or navigating
        return ""


def capture_checkout_url(ctx: StepContext, open_checkout: Callable[[], Page]) -> str:
    """Open the external checkout (without paying) and return its URL."""
    portal_host = host_of(ctx.site.base_url)
    try:
        checkout = open_checkout()
    except (FormError, TimeoutError) as exc:
        ctx.notify(f"could not open the checkout page ({exc}); returning the portal link only")
        return ""
    if host_of(checkout.url) != portal_host:
        url = checkout.url
    else:  # checkout embedded as an iframe
        url = next((fr.url for fr in checkout.frames if host_of(fr.url) not in ("", portal_host)), "")
    previous, ctx.page = ctx.page, checkout
    ctx.screenshot("checkout-page")  # empty card form, safe to capture
    ctx.page = previous
    return url


def confirm_amount(ctx: StepContext, portal_amount: Money | None) -> bool:
    """Ask again when the portal's amount is unknown or differs from what was authorised."""
    expected = ctx.result.fee
    if portal_amount is not None and expected is not None and (portal_amount.amount, portal_amount.currency) == (expected.amount, expected.currency):
        return True
    who = ", ".join(a.full_name for a in ctx.applicants)
    if portal_amount is None:
        line = f"{ctx.site.name}: could not read the amount on the portal for {who} (expected {expected or 'unknown'})"
    elif expected is None:
        line = f"{ctx.site.name}: the portal asks {portal_amount} for {who}"
    else:
        line = f"{ctx.site.name}: the portal asks {portal_amount} for {who}, not the expected {expected}"
    return ctx.options.confirm([line], portal_amount or expected)


def pay_by_card(
    ctx: StepContext,
    card: CardDetails,
    *,
    open_checkout: Callable[[], Page],
    patterns: ResultPatterns,
    portal_amount: Money | None,
) -> PaymentOutcome:
    if not confirm_amount(ctx, portal_amount):
        return PaymentOutcome(status=PaymentStatus.NOT_AUTHORISED, message="payment not authorised; nothing was charged",
                              amount=portal_amount)

    portal = ctx.page
    portal_host = host_of(ctx.site.base_url)
    checkout = open_checkout()
    submitted_at: dict[int, str] = {}

    def result_pages() -> list[Page]:
        # Only pages that moved since "Pay" was clicked (or opened after it)
        # carry a verdict; the untouched payment tab may mention "paid" or
        # "unsuccessful" in its instructions.
        found = [p for p in portal.context.pages if not p.is_closed() and submitted_at.get(id(p)) != p.url]
        return found

    def succeeded(_: Page) -> bool:
        return any(patterns.paid.search(_text(p)) for p in result_pages())

    def failed(_: Page) -> str | None:
        for p in result_pages():
            match = patterns.declined.search(_text(p))
            if match:
                return f"payment {match.group(0).lower()}"
        return None

    # Card digits are on screen from here on: no screenshots unless the
    # payment went through and the browser left the card form.
    ctx.sensitive = True
    filler = CardCheckout(overrides=ctx.site.overrides)
    filler.fill(checkout, card)
    for p in portal.context.pages:
        submitted_at[id(p)] = p.url
    filler.submit(checkout)
    result = await_checkout(
        checkout, succeeded=succeeded, failed=failed, challenge=ctx.options.three_ds,
        headless=ctx.options.browser.headless, timeout_s=ctx.options.browser.human_timeout_s, notify=ctx.options.notify,
    )

    final = next((p for p in reversed(result_pages()) if host_of(p.url) == portal_host), None) or next(
        (p for p in result_pages()), portal)
    reference = ""
    if result.status is PaymentStatus.PAID:
        ctx.sensitive = False
        ctx.page = final
        if patterns.receipt:
            match = patterns.receipt.search(_text(final))
            reference = match.group(1) if match else ""
    return PaymentOutcome(status=result.status, reference=reference, message=result.message, amount=portal_amount)
