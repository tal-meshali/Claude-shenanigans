"""The contract every country profile implements."""

from __future__ import annotations

import calendar
import logging
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, ClassVar

from playwright.sync_api import Page

from .browser import BrowserSession, host_of
from .documents import DocumentRequirement, prepare_upload
from .models import Applicant, ApplicationBatch, ApplicationResult, Money, PaymentLink, PaymentOutcome, Trip

if TYPE_CHECKING:
    from .payment import CardDetails
    from .runner import RunOptions

log = logging.getLogger(__name__)


@dataclass
class StepContext:
    """Everything a step needs for one application (one applicant, or one group)."""

    site: "VisaSite"
    batch: ApplicationBatch
    applicants: list[Applicant]
    trip: Trip
    page: Page
    session: BrowserSession
    options: "RunOptions"
    result: ApplicationResult
    folder: str
    state: dict[str, Any] = field(default_factory=dict)
    # Set while card data is on screen: screenshots are suppressed.
    sensitive: bool = False

    @property
    def applicant(self) -> Applicant:
        return self.applicants[0]

    @property
    def workdir(self) -> Path:
        path = self.session.artifacts_dir / self.folder
        path.mkdir(parents=True, exist_ok=True)
        return path

    def screenshot(self, name: str) -> None:
        if self.sensitive or not self.options.screenshots:
            return
        try:
            shot = self.session.screenshot(self.page, self.folder, f"{len(self.result.screenshots) + 1:02d}-{name}")
            self.result.screenshots.append(str(shot))
        except Exception as exc:  # noqa: BLE001 - screenshots are best effort
            log.debug("screenshot failed: %s", exc)

    def save_html(self, name: str) -> None:
        """Page source, for calibrating locators; never while card data is on screen."""
        if self.sensitive:
            return
        try:
            html = self.page.content()
            (self.workdir / f"{name}.html").write_text(f"<!-- {self.page.url} -->\n{html}", encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - best effort, like screenshots
            log.debug("saving page HTML failed: %s", exc)

    def notify(self, message: str) -> None:
        self.options.notify(f"[{self.result.applicant_ref}] {message}")

    def site_extra(self, key: str, default: Any = None) -> Any:
        """Applicant-level site answer, falling back to batch-level, then default."""
        return self.applicant.extra_for(self.site.key).get(key, self.batch.extra_for(self.site.key).get(key, default))


@dataclass(frozen=True)
class Step:
    name: str
    run: Callable[[StepContext], None]


class VisaSite(ABC):
    key: ClassVar[str]
    name: ClassVar[str]
    default_base_url: ClassVar[str]
    # Hosts where real applications are filed. Runs against them need --live
    # and never accept mock applicants.
    production_hosts: ClassVar[frozenset[str]] = frozenset()
    document_requirements: ClassVar[tuple[DocumentRequirement, ...]] = ()
    min_passport_validity_months: ClassVar[int] = 6
    # Whether the portal can put several travellers in one application, and
    # whether to do so when the batch does not say (`batch.mode`).
    supports_group: ClassVar[bool] = False
    prefers_group: ClassVar[bool] = False
    # Languages of the portal's labels, for matching country names etc.
    languages: ClassVar[tuple[str, ...]] = ("en",)

    def __init__(self, base_url: str | None = None, selector_overrides: dict[str, list[str]] | None = None):
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.overrides = selector_overrides or {}

    def url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    @property
    def is_production(self) -> bool:
        return host_of(self.base_url) in self.production_hosts

    # ------------------------------------------------------------- planning

    def application_units(self, batch: ApplicationBatch) -> list[list[Applicant]]:
        """Applicants grouped per application: everyone together, or one each."""
        group = batch.mode == "group" if batch.mode else self.prefers_group
        if group and self.supports_group and len(batch.applicants) > 1:
            return [list(batch.applicants)]
        return [[a] for a in batch.applicants]

    def validate(self, batch: ApplicationBatch) -> list[str]:
        """Problems that would make the portal reject an application."""
        problems: list[str] = []
        if batch.mode == "group" and not self.supports_group:
            problems.append(f"the {self.name} portal has no group applications; use mode: individual (one application each)")
        for applicant in batch.applicants:
            trip = batch.trip_for(applicant)
            needed_until = _add_months(trip.arrival_date, self.min_passport_validity_months)
            if not applicant.passport.valid_until_at_least(needed_until):
                problems.append(
                    f"{applicant.ref}: passport expires {applicant.passport.date_of_expiry}, must be valid until at least {needed_until}"
                )
            if trip.arrival_date <= date.today():
                problems.append(f"{applicant.ref}: arrival date {trip.arrival_date} is not in the future")
            if not applicant.mock:
                for req in self.required_documents(applicant, trip):
                    if getattr(applicant.documents, req.kind) is None:
                        problems.append(f"{applicant.ref}: missing document '{req.kind}' ({req.label})")
                problems += self._document_problems(applicant)
        return problems

    def _document_problems(self, applicant: Applicant) -> list[str]:
        """Convert every given document now: a bad file must fail before anything is filed on the portal."""
        problems: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            for req in self.document_requirements:
                source = getattr(applicant.documents, req.kind, None)
                if source is None:
                    continue
                try:
                    prepare_upload(source, req, Path(tmp))
                except Exception as exc:  # noqa: BLE001 - unreadable image, oversized PDF, missing file, ...
                    problems.append(f"{applicant.ref}: {req.kind}: {exc}")
        return problems

    def required_documents(self, applicant: Applicant, trip: Trip) -> list[DocumentRequirement]:
        return [r for r in self.document_requirements if r.required]

    def fee(self, applicants: list[Applicant], trip: Trip) -> Money | None:
        return None

    def prepared_documents(self, ctx: StepContext) -> dict[str, Path]:
        """Upload-ready copies of the applicant's documents, keyed by kind."""
        out: dict[str, Path] = {}
        for req in self.document_requirements:
            source = getattr(ctx.applicant.documents, req.kind, None)
            if source is None:
                continue
            out[req.kind] = prepare_upload(source, req, ctx.workdir / "uploads")
        return out

    # -------------------------------------------------------------- the flow

    @abstractmethod
    def steps(self) -> list[Step]:
        """Steps from the portal's front page up to (not including) payment."""

    @abstractmethod
    def payment_link(self, ctx: StepContext, *, open_checkout: bool) -> PaymentLink:
        """Information for paying later by hand; `open_checkout` also captures the external checkout URL."""

    @abstractmethod
    def pay_by_card(self, ctx: StepContext, card: "CardDetails") -> PaymentOutcome:
        """Open the external checkout, fill the card, and report the outcome."""


def _add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))
