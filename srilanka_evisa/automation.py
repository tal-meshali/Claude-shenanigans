"""Drive the ETA portal: fill one application per group (or per beneficiary),
submit it, and hand back the payment link - or pay on the gateway."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import yaml
from playwright.sync_api import BrowserContext, Dialog, Page, Response, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .forms import FieldNotFound, click, fill_fields, locate
from .models import Application, Beneficiary, Child
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
    site_messages: list[str] = field(default_factory=list)  # alert()/confirm() texts shown by the portal
    artifacts: list[str] = field(default_factory=list)


def load_profile(path: str | Path | None = None) -> dict[str, Any]:
    return yaml.safe_load(Path(path or DEFAULT_PROFILE).read_text(encoding="utf-8"))


def beneficiary_values(b: Beneficiary) -> dict[str, Any]:
    return {
        "title": b.resolved_title,
        "surname": b.surname,
        "given_names": b.given_names,
        "date_of_birth": b.date_of_birth,
        "date_of_birth_confirm": b.date_of_birth,
        "sex": b.sex,
        "nationality": b.nationality,
        "country_of_birth": b.country_of_birth,
        "occupation": b.occupation,
        "relationship": b.relationship,
        "passport_number": b.passport_number,
        "passport_number_confirm": b.passport_number,
        "passport_issue_date": b.passport_issue_date,
        "passport_expiry_date": b.passport_expiry_date,
    }


def child_values(c: Child) -> dict[str, Any]:
    return {
        "enable": True,
        "surname": c.surname,
        "given_names": c.given_names,
        "date_of_birth": c.date_of_birth,
        "date_of_birth_confirm": c.date_of_birth,
        "sex": c.sex,
        "relationship": "Child",
    }


def trip_values(app: Application) -> dict[str, Any]:
    t, c = app.trip, app.contact
    return {
        "departure_country": t.departure_country,
        "visa_days": t.visa_days,
        "arrival_date": t.arrival_date,
        "purpose": t.purpose,
        "port_of_departure": t.port_of_departure,
        "airline": t.airline,
        "flight_number": t.flight_number,
        "address_in_sri_lanka": t.address_in_sri_lanka,
        "address_line1": c.address_line1,
        "address_line2": c.address_line2,
        "city": c.city,
        "state": c.state,
        "postal_code": c.postal_code,
        "country": c.country,
        "email": c.email,
        "email_confirm": c.email,
        "telephone": c.telephone,
        "mobile": c.mobile,
    }


def declaration_values(app: Application) -> dict[str, Any]:
    d = app.declarations
    return {
        "q_residence_visa": d.has_residence_visa,
        "q_currently_in_sri_lanka": d.currently_in_sri_lanka,
        "q_multiple_entry_visa": d.has_multiple_entry_visa,
        "confirm_info": True,
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
        save_pages: bool = False,
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
        self.save_pages = save_pages
        self.log = log
        self.wait_for_human = wait_for_human
        self.steps = self.profile["steps"]
        self._dialogs: list[tuple[str, str]] = []  # since the last click
        self._dialogs_all: list[tuple[str, str]] = []  # whole application

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
                    context = browser.new_context(locale="en-US")
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
                        result.site_messages = [f"{kind}: {text}" for kind, text in self._dialogs_all]
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
        self._dialogs, self._dialogs_all = [], []
        page.on("dialog", self._on_dialog)
        if self.save_pages:
            page.on("response", lambda r: self._save_document(r, tag, result))

        self.log(f"[{tag}] {mode} {app.visa_type} application for {', '.join(result.beneficiaries)}")
        page.goto(self.base_url + self.profile["start_path"])
        self._keep_https(page)
        self._check_fatal(page)

        self._click_and_wait(page, self.steps["terms"]["click"], "I agree", tag, result)
        link_id = self.steps["category"]["link_ids"][app.visa_type][mode]
        self._click_and_wait(page, {"selectors": [f"a[id='{link_id}']"]}, f"{app.visa_type} {mode}", tag, result)

        if mode == "individual":
            step = self.steps["individual_form"]
            values = {**beneficiary_values(members[0]), **trip_values(app), **declaration_values(app)}
            filled = fill_fields(page, step["fields"], values, fmt)
            self.log(f"[{tag}]  application form: {len(filled)} fields")
            self._add_children(page, step, members[0], tag, result)
            self._snapshot(page, f"{tag}-form", result)
            self._click_and_wait(page, step["next"], "next", tag, result)
        else:
            step = self.steps["group_form"]
            filled = fill_fields(page, step["fields"], trip_values(app), fmt)
            self.log(f"[{tag}]  travel & contact: {len(filled)} fields")
            self._click_and_wait(page, step["next"], "next (group details)", tag, result)

            step = self.steps["member_form"]
            for i, member in enumerate(members, 1):
                values = {**beneficiary_values(member), **declaration_values(app)}
                values["country_of_address"] = member.country_of_address or app.contact.country
                self._dialogs.clear()  # a refused passport number shows up as an alert
                filled = fill_fields(page, step["fields"], values, fmt)
                self.log(f"[{tag}]  member {i}/{len(members)} {member.full_name}: {len(filled)} fields")
                self._add_children(page, step, member, tag, result)
                self._click_and_expect(page, step["add"], step["added"].format(n=i), f"add member {i}", tag, result)
            self._click_and_wait(page, step["next"], "next (members)", tag, result)

        self._snapshot(page, f"{tag}-review", result)
        if not self.submit:
            result.status = "ready_for_submission"
            result.confirmation_url = page.url
            self.log(f"[{tag}] stopped at the review page (dry run; pass --submit to submit)")
            return page
        self._click_and_wait(page, self.steps["review"]["submit"], "confirm", tag, result)

        text = page.inner_text("body")
        m = re.search(self.profile["reference_regex"], text)
        result.reference = (m.group(1) if m and m.groups() else m.group(0)) if m else None
        result.confirmation_url = page.url
        self._snapshot(page, f"{tag}-confirmation", result)
        self.log(f"[{tag}] submitted, reference {result.reference or '(not found on page)'}")

        page = self._go_to_payment(page, context, result, tag)
        result.status = "payment_link"
        return page

    def _go_to_payment(self, page: Page, context: BrowserContext, result: SessionResult, tag: str) -> Page:
        step = self.steps.get("payment_options", {})
        fill_fields(page, step.get("fields", {}), {"method": "card"}, self.profile["date_format"])
        pay = locate(page, step["pay"])
        if pay is None:
            raise FieldNotFound(f"no payment button/link on {page.url}")
        href = pay.get_attribute("href")
        before = page.url
        opened: list[Page] = []

        def on_page(new_page: Page) -> None:
            opened.append(new_page)

        context.on("page", on_page)
        pay.click()
        try:
            page.wait_for_url(lambda u: u != before, timeout=15_000)
        except PlaywrightTimeout:
            pass  # new tab, or a link we follow below
        context.remove_listener("page", on_page)
        if opened:  # gateway opened in a new tab
            page = opened[0]
        page.wait_for_load_state()
        if page.url == before and href and not href.startswith(("#", "javascript")):
            page.goto(href)
        if not self._looks_like_gateway(page.url):
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

    def _on_dialog(self, dialog: Dialog) -> None:
        # alert(): validation errors or notices. confirm(): "Are you sure to confirm
        # the details?" and the fraud declaration on the review page - accepted,
        # since the run only submits when the user asked for it.
        self._dialogs.append((dialog.type, dialog.message))
        self._dialogs_all.append((dialog.type, dialog.message))
        dialog.accept()

    def _click_and_wait(self, page: Page, spec: dict[str, Any], what: str, tag: str,
                        result: SessionResult) -> None:
        """Click and wait for the next page; turn a blocked step into a StepError."""
        self._handle_captcha(page, tag)
        self._dialogs.clear()
        # Mark the current document; a real page change replaces it. (The portal's
        # links are href="#", so plain navigation events also fire on hash changes.)
        page.evaluate("() => { window.__etaOldPage = true; }")
        click(page, spec, what)
        try:
            page.wait_for_function("() => !window.__etaOldPage && document.readyState !== 'loading'",
                                   timeout=self.timeout_ms)
        except PlaywrightTimeout:
            alerts = [text for kind, text in self._dialogs if kind == "alert"]
            banner = locate(page, self.profile.get("error_banner", {}))
            reason = alerts[-1] if alerts else (banner.inner_text().strip() if banner else "")
            self._save_debug(page, f"{tag}-{what.replace(' ', '_')}-blocked", result)
            raise StepError(f"'{what}' did not go to the next page" + (f": the site says {reason!r}" if reason else ""))
        page.wait_for_load_state()
        self._keep_https(page)
        self._check_fatal(page)

    def _add_children(self, page: Page, step: dict[str, Any], parent: Beneficiary, tag: str,
                      result: SessionResult) -> None:
        """Add the children travelling on `parent`'s passport, one at a time."""
        spec = step.get("children")
        if parent.children and not spec:
            raise StepError("this form has no section for children on a parent's passport")
        for n, child in enumerate(parent.children, 1):
            fill_fields(page, spec["fields"], child_values(child), self.profile["date_format"])
            self._click_and_expect(page, spec["add"], spec["added"].format(n=n), f"add child {child.full_name}",
                                   tag, result)
            self.log(f"[{tag}]    child on {parent.given_names}'s passport: {child.full_name}")

    def _click_and_expect(self, page: Page, spec: dict[str, Any], selector: str, what: str, tag: str,
                          result: SessionResult) -> None:
        """Click something that updates the current page; wait for `selector` to appear."""
        click(page, spec, what)
        try:
            page.wait_for_selector(selector, state="attached", timeout=self.timeout_ms)
        except PlaywrightTimeout:
            alerts = [text for kind, text in self._dialogs if kind == "alert"]
            self._save_debug(page, f"{tag}-{what.replace(' ', '_')}-blocked", result)
            raise StepError(f"'{what}' was not accepted" + (f": the site says {alerts[-1]!r}" if alerts else ""))

    def _keep_https(self, page: Page) -> None:
        base = urlparse(self.base_url)
        url = urlparse(page.url)
        if self.profile.get("force_https") and base.scheme == "https" and url.scheme == "http" \
                and url.hostname == base.hostname:
            page.goto(url._replace(scheme="https").geturl())

    def _check_fatal(self, page: Page) -> None:
        texts = [text for _, text in self._dialogs]
        for pattern in self.profile.get("fatal_texts", []):
            if any(re.search(pattern, t, re.I) for t in texts):
                raise StepError(f"the portal reported {pattern!r} - start again (sessions time out quickly)")

    def _looks_like_gateway(self, url: str) -> bool:
        host = urlparse(url).hostname or ""
        return host != urlparse(self.base_url).hostname or any(
            p in url.lower() for p in self.profile["payment_url_patterns"])

    def _handle_captcha(self, page: Page, tag: str) -> None:
        captcha = self.profile.get("captcha")
        if not captcha or locate(page, {"selectors": captcha["selectors"]}, all_frames=True) is None:
            return
        if self.headless:
            raise CaptchaRequired("the site shows a CAPTCHA; re-run with --headful to solve it by hand")
        self.wait_for_human(f"[{tag}] Please solve the CAPTCHA in the browser window.")

    def _save_document(self, response: Response, tag: str, result: SessionResult) -> None:
        """Save the raw HTML of a page the portal sent (before the gateway), to map new pages.
        The files hold session ids and personal data: sanitize before committing."""
        req = response.request
        if req.resource_type != "document" or result.status == "payment_link" \
                or urlparse(req.url).hostname != urlparse(self.base_url).hostname:
            return
        try:
            body = response.text()
        except Exception:
            return  # redirects have no body
        path = self.out_dir / f"{tag}-page-{datetime.now():%H%M%S%f}.html"
        path.write_text(f"<!-- {req.method} {req.url} -->\n{body}", encoding="utf-8")
        result.artifacts.append(str(path))

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
