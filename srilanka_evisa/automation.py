"""Drive the ETA portal: fill one application per group (or per beneficiary),
submit it, and hand back the payment link - or pay on the gateway."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml
from playwright.sync_api import BrowserContext, Page, sync_playwright

from .forms import FieldNotFound, click, fill_fields, locate
from .models import Application, Beneficiary
from .payment import CardDetails, PaymentOutcome, pay_on_gateway

DEFAULT_PROFILE = Path(__file__).parent / "profiles" / "eta_gov_lk.yaml"
LIVE_BASE_URL = "https://eta.gov.lk"


class StepError(RuntimeError):
    pass


class CaptchaRequired(StepError):
    pass


@dataclass
class SessionResult:
    beneficiaries: list[str]
    status: str = "started"  # ready_for_submission | payment_link | paid | declined | payment_unconfirmed | error
    reference: str | None = None
    payment_url: str | None = None
    confirmation_url: str | None = None
    payment_message: str | None = None
    error: str | None = None
    artifacts: list[str] = field(default_factory=list)


def load_profile(path: str | Path | None = None) -> dict[str, Any]:
    return yaml.safe_load(Path(path or DEFAULT_PROFILE).read_text(encoding="utf-8"))


def beneficiary_values(b: Beneficiary) -> dict[str, Any]:
    return {
        "title": b.resolved_title,
        "surname": b.surname,
        "given_names": b.given_names,
        "date_of_birth": b.date_of_birth,
        "sex": b.sex,
        "nationality": b.nationality,
        "country_of_birth": b.country_of_birth,
        "occupation": b.occupation,
        "passport_number": b.passport_number,
        "passport_issuing_country": b.passport_issuing_country,
        "passport_issue_date": b.passport_issue_date,
        "passport_expiry_date": b.passport_expiry_date,
        "home_address": b.home_address,
        "passport_image": b.passport_image,
        "photo": b.photo,
    }


def trip_values(app: Application) -> dict[str, Any]:
    t, c = app.trip, app.contact
    return {
        "purpose": t.purpose,
        "arrival_date": t.arrival_date,
        "duration_days": t.duration_days,
        "mode_of_travel": t.mode_of_travel,
        "port_of_departure": t.port_of_departure,
        "flight_number": t.flight_number,
        "address_in_sri_lanka": t.address_in_sri_lanka,
        "email": c.email,
        "email_confirm": c.email,
        "phone": c.phone,
        "contact_address": c.address,
    }


class EtaAutomation:
    def __init__(
        self,
        base_url: str = LIVE_BASE_URL,
        profile: dict[str, Any] | None = None,
        out_dir: str | Path = "evisa_output",
        headless: bool = True,
        submit: bool = False,
        slow_mo: int = 0,
        timeout_ms: int = 30_000,
        log: Callable[[str], None] = print,
        wait_for_human: Callable[[str], None] = lambda msg: input(f"{msg} Press Enter to continue... "),
    ):
        self.base_url = base_url.rstrip("/")
        self.profile = profile or load_profile()
        self.out_dir = Path(out_dir)
        self.headless = headless
        self.submit = submit
        self.slow_mo = slow_mo
        self.timeout_ms = timeout_ms
        self.log = log
        self.wait_for_human = wait_for_human
        self.steps = self.profile["steps"]

    # ------------------------------------------------------------------ public

    def run(
        self,
        app: Application,
        card_provider: Callable[[], CardDetails] | None = None,
        confirm_payment: Callable[[str], bool] = lambda _msg: True,
    ) -> list[SessionResult]:
        """Apply for every beneficiary. With `card_provider`, also pay each application."""
        groups = [app.beneficiaries] if app.mode == "group" else [[b] for b in app.beneficiaries]
        self.out_dir.mkdir(parents=True, exist_ok=True)
        results: list[SessionResult] = []
        card: CardDetails | None = None

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
            try:
                for n, members in enumerate(groups, 1):
                    result = SessionResult(beneficiaries=[b.full_name for b in members])
                    results.append(result)
                    context = browser.new_context(locale=app.locale.replace("_", "-"))
                    context.set_default_timeout(self.timeout_ms)
                    page = context.new_page()
                    tag = f"app{n}"
                    try:
                        page = self._apply(page, context, app, members, result, tag)
                        if result.status == "payment_link" and card_provider:
                            card = card or card_provider()  # ask once, reuse for every application
                            self._pay(page, card, result, confirm_payment, tag)
                    except Exception as exc:  # keep going with the next application
                        on_gateway = result.status == "payment_link"
                        result.status = "error"
                        result.error = f"{type(exc).__name__}: {exc}"
                        if not on_gateway:  # never capture a card form that may hold card data
                            self._save_debug(page, f"{tag}-error", result)
                        self.log(f"[{tag}] ERROR {result.error}")
                    finally:
                        context.close()
            finally:
                browser.close()

        (self.out_dir / "results.json").write_text(
            json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return results

    # ----------------------------------------------------------------- flow

    def _apply(self, page: Page, context: BrowserContext, app: Application, members: list[Beneficiary],
               result: SessionResult, tag: str) -> Page:
        mode = "group" if len(members) > 1 else "individual"
        fmt = self.profile["date_format"]
        start = self.base_url + self.profile["start_path"].format(locale=app.locale)
        self.log(f"[{tag}] {mode} application for {', '.join(result.beneficiaries)}")
        page.goto(start)
        click(page, self.steps["start"]["click"], "apply")
        page.wait_for_load_state()

        step = self.steps["eligibility"]
        fill_fields(page, step["fields"], {"visa_type": app.visa_type, "application_type": mode,
                                           "accept_terms": True}, fmt)
        self._next(page, step, "eligibility", tag, result)

        step = self.steps["trip"]
        fill_fields(page, step["fields"], trip_values(app), fmt)
        if step.get("next"):
            self._next(page, step, "trip", tag, result)

        step = self.steps["beneficiary"]
        for i, member in enumerate(members, 1):
            filled = fill_fields(page, step["fields"], beneficiary_values(member), fmt)
            self.log(f"[{tag}]  beneficiary {i}/{len(members)} {member.full_name}: {len(filled)} fields")
            last = i == len(members)
            self._next(page, step if last else {"next": step["add_another"]},
                       "beneficiary" if last else "add member", f"{tag}-member{i}", result)

        step = self.steps["review"]
        fill_fields(page, step.get("fields", {}), {"declaration": True}, fmt)
        self._snapshot(page, f"{tag}-review", result)
        if not self.submit:
            result.status = "ready_for_submission"
            result.confirmation_url = page.url
            self.log(f"[{tag}] stopped at the review page (dry run; pass --submit to submit)")
            return page
        self._next(page, {"next": step["submit"]}, "submit", tag, result)

        text = page.inner_text("body")
        m = re.search(self.profile["reference_regex"], text)
        result.reference = m.group(0) if m else None
        result.confirmation_url = page.url
        self._snapshot(page, f"{tag}-confirmation", result)
        self.log(f"[{tag}] submitted, reference {result.reference or '(not found on page)'}")

        page = self._go_to_payment(page, context, result, tag)
        result.status = "payment_link"
        return page

    def _go_to_payment(self, page: Page, context: BrowserContext, result: SessionResult, tag: str) -> Page:
        pay = locate(page, self.steps["confirmation"]["pay"])
        if pay is None:
            raise FieldNotFound(f"no payment button/link on the confirmation page {page.url}")
        href = pay.get_attribute("href")
        before = page.url
        opened: list[Page] = []

        def on_page(new_page: Page) -> None:
            opened.append(new_page)

        context.on("page", on_page)
        pay.click()
        try:
            page.wait_for_url(lambda u: u != before, timeout=10_000)
        except Exception:
            pass  # new tab, or a link we follow below
        page.wait_for_load_state()
        context.remove_listener("page", on_page)
        if opened:  # gateway opened in a new tab
            page = opened[0]
            page.wait_for_load_state()
        if page.url == before and href:
            page.goto(href)
        patterns = self.profile["payment_url_patterns"]
        if not any(p in page.url.lower() for p in patterns):
            self.log(f"[{tag}] warning: {page.url} does not look like a payment gateway URL")
        result.payment_url = page.url
        self._snapshot(page, f"{tag}-payment-page", result)  # empty card form, safe to capture
        self.log(f"[{tag}] payment link: {page.url}")
        return page

    def _pay(self, page: Page, card: CardDetails, result: SessionResult,
             confirm: Callable[[str], bool], tag: str) -> None:
        self.log(f"[{tag}] filling payment gateway with card {card.masked}")
        outcome: PaymentOutcome = pay_on_gateway(page, card, self.profile, confirm)
        result.payment_message = outcome.message
        result.status = {"paid": "paid", "declined": "declined"}.get(outcome.status, "payment_unconfirmed")
        # Only capture the gateway after it left the card form (never a filled form).
        if outcome.status != "unknown":
            self._snapshot(page, f"{tag}-payment-result", result)
        self.log(f"[{tag}] payment {outcome.status}: {outcome.message}")

    # -------------------------------------------------------------- helpers

    def _next(self, page: Page, step: dict[str, Any], what: str, tag: str, result: SessionResult) -> None:
        self._handle_captcha(page, tag)
        url_before = page.url
        click(page, step["next"], what)
        page.wait_for_load_state()
        banner = locate(page, self.profile.get("error_banner", {}))
        if banner is not None:
            message = banner.inner_text().strip()
            if message:
                self._save_debug(page, f"{tag}-{what}-rejected", result)
                raise StepError(f"site rejected the '{what}' step: {message}")
        if page.url == url_before and self.profile.get("strict_navigation"):
            raise StepError(f"clicking '{what}' did not navigate")

    def _handle_captcha(self, page: Page, tag: str) -> None:
        captcha = self.profile.get("captcha")
        if not captcha or locate(page, {"selectors": captcha["selectors"]}) is None:
            return
        if self.headless:
            raise CaptchaRequired("the site shows a CAPTCHA; re-run with --headful to solve it by hand")
        self.wait_for_human(f"[{tag}] Please solve the CAPTCHA in the browser window.")

    def _snapshot(self, page: Page, name: str, result: SessionResult) -> None:
        path = self.out_dir / f"{datetime.now():%H%M%S}-{name}.png"
        page.screenshot(path=str(path), full_page=True)
        result.artifacts.append(str(path))

    def _save_debug(self, page: Page, name: str, result: SessionResult) -> None:
        try:
            self._snapshot(page, name, result)
            html = self.out_dir / f"{name}.html"
            html.write_text(page.content(), encoding="utf-8")
            result.artifacts.append(str(html))
        except Exception:
            pass
