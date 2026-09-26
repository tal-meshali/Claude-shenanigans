"""Runs a batch of beneficiaries through any `VisaSite`, one isolated browser context each."""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Callable, Sequence

from playwright.sync_api import Page
from pydantic import BaseModel, Field

from .browser import BrowserOptions, BrowserSession, HumanActionRequired
from .captcha import CaptchaHandler, ManualCaptcha
from .documents import generate_mock_documents
from .models import Applicant, ApplicationBatch, ApplicationResult, ApplicationStatus, Money, PaymentStatus
from .payment import CardDetails, PaymentMode, confirm_charge, prompt_card, sum_money
from .site import StepContext, VisaSite

log = logging.getLogger(__name__)


class SafetyError(RuntimeError):
    pass


_PAYMENT_STATUS = {
    PaymentStatus.PAID: ApplicationStatus.PAID,
    PaymentStatus.DECLINED: ApplicationStatus.PAYMENT_DECLINED,
    PaymentStatus.UNCONFIRMED: ApplicationStatus.PAYMENT_UNCONFIRMED,
    PaymentStatus.NOT_AUTHORISED: ApplicationStatus.AWAITING_PAYMENT,
}


class BatchValidationError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("batch is not valid:\n  - " + "\n  - ".join(problems))
        self.problems = problems


@dataclass
class RunOptions:
    payment: PaymentMode = PaymentMode.LINK
    browser: BrowserOptions = field(default_factory=BrowserOptions)
    out_dir: Path = Path("runs")
    allow_production: bool = False
    # When paying by link, also open the external checkout to capture its URL.
    capture_gateway_url: bool = True
    captcha: CaptchaHandler | None = None
    card_provider: Callable[[Sequence[Applicant]], CardDetails] | None = None
    confirm: Callable[[Sequence[str], Money | None], bool] = confirm_charge
    three_ds: Callable[..., None] | None = None
    stop_after: str | None = None
    screenshots: bool = True
    skip_validation: bool = False
    # Called on a failed application while its page is still open (--pause-on-error).
    pause: Callable[[Page], None] | None = None
    # Flushed, so progress and "ACTION NEEDED" show up at once even when stdout is a file.
    notify: Callable[[str], None] = partial(print, flush=True)

    def captcha_handler(self) -> CaptchaHandler:
        return self.captcha or ManualCaptcha(headless=self.browser.headless, timeout_s=self.browser.human_timeout_s, notify=self.notify)


class BatchReport(BaseModel):
    site: str
    site_name: str
    base_url: str
    run_dir: str = ""
    payment_mode: PaymentMode
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime | None = None
    results: list[ApplicationResult] = Field(default_factory=list)

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "report.json"
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        (directory / "summary.md").write_text(self.summary_markdown(), encoding="utf-8")
        return path

    def summary_markdown(self) -> str:
        lines = [
            f"# {self.site_name} e-visa run - {self.started_at:%Y-%m-%d %H:%M}",
            "",
            f"Portal: {self.base_url}  |  payment mode: {self.payment_mode.value}",
            "",
            "| Applicant | Application ID | Status | Fee | Payment |",
            "|---|---|---|---|---|",
        ]
        for r in self.results:
            if r.payment and r.payment.success:
                pay = f"paid ({r.payment.reference})"
            elif r.payment_link:
                pay = r.payment_link.gateway_url or r.payment_link.portal_url
            else:
                pay = r.error or "-"
            lines.append(f"| {r.full_name} | {r.application_id or '-'} | {r.status.value} | {r.fee or '-'} | {pay} |")
        for r in self.results:
            if r.payment_link and r.payment_link.resume:
                lines += ["", f"**{r.full_name}** - to pay later open {r.payment_link.portal_url} and sign in with:"]
                lines += [f"- {k}: `{v}`" for k, v in r.payment_link.resume.items()]
                if r.payment_link.instructions:
                    lines.append(f"- {r.payment_link.instructions}")
        return "\n".join(lines) + "\n"


def check_safety(site: VisaSite, batch: ApplicationBatch, options: RunOptions) -> None:
    if site.is_production and batch.is_mock:
        raise SafetyError(
            f"{site.base_url} is the real {site.name} portal and this batch contains mock applicants; "
            "mock data is only ever sent to the local mock portal (evisa demo / --base-url http://127.0.0.1:...)"
        )
    if site.is_production and not options.allow_production:
        raise SafetyError(f"{site.base_url} files real applications; pass --live to confirm that is what you want")


class BatchRunner:
    def __init__(self, site: VisaSite, batch: ApplicationBatch, options: RunOptions):
        self.site, self.batch, self.options = site, batch, options
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_dir = Path(options.out_dir) / f"{site.key}-{stamp}"
        self.report = BatchReport(site=site.key, site_name=site.name, base_url=site.base_url, payment_mode=options.payment,
                                  run_dir=str(self.run_dir))

    # ----------------------------------------------------------------- setup

    def _prepare(self) -> None:
        check_safety(self.site, self.batch, self.options)
        if not self.options.skip_validation:
            problems = self.site.validate(self.batch)
            if problems:
                raise BatchValidationError(problems)
        for applicant in self.batch.applicants:
            if applicant.mock:
                applicant.documents = generate_mock_documents(applicant, self.batch.trip_for(applicant), self.run_dir / "mock_documents")

    def _card_for_run(self, units: list[list[Applicant]]) -> CardDetails | None:
        if self.options.payment is not PaymentMode.CARD:
            return None
        fees = [(unit, self.site.fee(unit, self.batch.trip_for(unit[0]))) for unit in units]
        lines = [f"{', '.join(a.full_name for a in unit)}: {fee or 'amount shown by the portal'}" for unit, fee in fees]
        provider = self.options.card_provider or (lambda applicants: prompt_card(default_billing=applicants[0].contact.address))
        card = provider(self.batch.applicants)
        if not self.options.confirm([f"{self.site.name} e-visa - {line}" for line in lines] + [f"card: {card.masked}"], sum_money([f for _, f in fees])):
            raise SafetyError("payment not authorised; nothing was submitted")
        return card

    # ------------------------------------------------------------------- run

    def run(self) -> BatchReport:
        self._prepare()
        units = self.site.application_units(self.batch)
        card = self._card_for_run(units)
        self.options.notify(f"{self.site.name}: {len(self.batch.applicants)} beneficiar{'y' if len(self.batch.applicants) == 1 else 'ies'} "
                            f"in {len(units)} application(s) -> {self.site.base_url}")
        with BrowserSession(self.options.browser, self.run_dir) as session:
            for unit in units:
                for result in self._run_unit(session, unit, card):
                    self.report.results.append(result)
                self.report.save(self.run_dir)  # persist progress after every application
        self.report.finished_at = datetime.now()
        self.report.save(self.run_dir)
        return self.report

    def _run_unit(self, session: BrowserSession, unit: list[Applicant], card: CardDetails | None) -> list[ApplicationResult]:
        primary = unit[0]
        trip = self.batch.trip_for(primary)
        result = ApplicationResult(
            applicant_ref=primary.ref,
            full_name=primary.full_name,
            site=self.site.key,
            status=ApplicationStatus.FAILED,
            fee=self.site.fee(unit, trip),
        )
        context = session.new_context()
        page = context.new_page()
        ctx = StepContext(
            site=self.site, batch=self.batch, applicants=unit, trip=trip, page=page,
            session=session, options=self.options, result=result, folder=primary.ref,
        )
        try:
            for step in self.site.steps():
                ctx.notify(step.name)
                step.run(ctx)
                result.completed_steps.append(step.name)
                ctx.screenshot(step.name)
                if self.options.stop_after and step.name == self.options.stop_after:
                    result.status = ApplicationStatus.STOPPED
                    return self._fan_out(result, unit)

            if self.options.payment is PaymentMode.CARD and card is not None:
                ctx.notify("paying by card")
                outcome = self.site.pay_by_card(ctx, card)
                result.payment = outcome
                result.status = _PAYMENT_STATUS[outcome.status]
                if not outcome.success:
                    ctx.notify(f"payment {outcome.status.value}: {outcome.message}")
                    result.payment_link = self._safe_link(ctx)
            else:
                result.payment_link = self.site.payment_link(ctx, open_checkout=self.options.capture_gateway_url)
                result.status = ApplicationStatus.AWAITING_PAYMENT
            ctx.screenshot("final")
        except HumanActionRequired as exc:
            result.error = str(exc)
        except Exception as exc:  # noqa: BLE001 - one applicant failing must not stop the batch
            log.debug("application failed", exc_info=True)
            result.error = f"{type(exc).__name__}: {exc}"
            (ctx.workdir / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            ctx.screenshot("error")
            ctx.save_html("error")
            if self.options.pause:
                self.options.pause(ctx.page)
        finally:
            result.finished_at = datetime.now()
            context.close()
        if result.error:
            ctx.notify(f"FAILED: {result.error.splitlines()[0]}")
        return self._fan_out(result, unit)

    def _safe_link(self, ctx: StepContext):
        """Best-effort manual-payment link after a failed card payment."""
        try:
            return self.site.payment_link(ctx, open_checkout=False)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _fan_out(result: ApplicationResult, unit: list[Applicant]) -> list[ApplicationResult]:
        """A group application yields one result row per beneficiary."""
        rows = [result]
        for other in unit[1:]:
            rows.append(result.model_copy(update={"applicant_ref": other.ref, "full_name": other.full_name}))
        return rows


def run_batch(site: VisaSite, batch: ApplicationBatch, options: RunOptions) -> BatchReport:
    return BatchRunner(site, batch, options).run()
