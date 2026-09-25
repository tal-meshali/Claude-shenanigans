"""Country-agnostic applicant, trip and result models.

Every visa site reads the same `ApplicationBatch`: one shared `Trip` plus one or
more `Applicant`s (the beneficiaries). Anything that only one country asks for
lives in `extra[<site key>]` so the shared models stay small.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import countries
from .mrz import TD3, build_td3

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+[1-9]\d{6,14}$")


class _Model(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", use_enum_values=False)


def _country_code(value: str) -> str:
    code = value.strip().upper()
    if not countries.is_valid_code(code):
        raise ValueError(f"{value!r} is not an ISO 3166-1 alpha-3 / ICAO country code")
    return code


class Sex(str, Enum):
    MALE = "M"
    FEMALE = "F"
    UNSPECIFIED = "X"

    @property
    def label(self) -> str:
        return {"M": "Male", "F": "Female", "X": "Other"}[self.value]


class MaritalStatus(str, Enum):
    SINGLE = "single"
    MARRIED = "married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"
    SEPARATED = "separated"

    @property
    def label(self) -> str:
        return self.value.capitalize()


class Purpose(str, Enum):
    TOURISM = "tourism"
    BUSINESS = "business"
    VISITING_FAMILY = "visiting_family"
    CONFERENCE = "conference"
    TRANSIT = "transit"
    MEDICAL = "medical"
    STUDY = "study"
    OTHER = "other"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").capitalize()


class Passport(_Model):
    number: str
    document_type: str = "P"
    issuing_country: str
    nationality: str
    surname: str
    given_names: str
    sex: Sex
    date_of_birth: date
    place_of_birth: str
    country_of_birth: str
    date_of_issue: date
    date_of_expiry: date
    issuing_authority: str
    personal_number: str = ""

    _codes = field_validator("issuing_country", "nationality", "country_of_birth")(_country_code)

    @field_validator("number")
    @classmethod
    def _number(cls, value: str) -> str:
        value = value.replace(" ", "").upper()
        if not re.fullmatch(r"[A-Z0-9]{5,9}", value):
            raise ValueError("passport number must be 5-9 letters/digits")
        return value

    @model_validator(mode="after")
    def _dates(self) -> "Passport":
        if not self.date_of_birth < self.date_of_issue < self.date_of_expiry:
            raise ValueError("expected date_of_birth < date_of_issue < date_of_expiry")
        return self

    @property
    def full_name(self) -> str:
        return f"{self.given_names} {self.surname}"

    @property
    def first_name(self) -> str:
        return self.given_names.split()[0]

    @property
    def middle_names(self) -> str:
        return " ".join(self.given_names.split()[1:])

    def mrz(self) -> TD3:
        return build_td3(
            document_type=self.document_type,
            issuing_country=self.issuing_country,
            surname=self.surname,
            given_names=self.given_names,
            number=self.number,
            nationality=self.nationality,
            date_of_birth=self.date_of_birth,
            sex=self.sex.value,
            date_of_expiry=self.date_of_expiry,
            personal_number=self.personal_number,
        )

    def valid_until_at_least(self, day: date) -> bool:
        return self.date_of_expiry >= day


class Address(_Model):
    line1: str
    line2: str = ""
    city: str
    state: str = ""
    postal_code: str = ""
    country: str

    _code = field_validator("country")(_country_code)

    def one_line(self) -> str:
        parts = [self.line1, self.line2, self.city, self.state, self.postal_code, countries.country_name(self.country)]
        return ", ".join(p for p in parts if p)


class Contact(_Model):
    email: str
    phone: str
    address: Address

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        if not _EMAIL_RE.match(value):
            raise ValueError("invalid email address")
        return value

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        value = re.sub(r"[\s\-()]", "", value)
        if not _PHONE_RE.match(value):
            raise ValueError("phone must be in international format, e.g. +972501234567")
        return value


class Documents(_Model):
    """Paths to the files a portal asks applicants to upload."""

    photo: Path | None = None
    passport_scan: Path | None = None
    return_ticket: Path | None = None
    accommodation_proof: Path | None = None
    invitation_letter: Path | None = None
    other: dict[str, Path] = Field(default_factory=dict)

    def resolved(self, base: Path) -> "Documents":
        def fix(p: Path | None) -> Path | None:
            return None if p is None else (p if p.is_absolute() else (base / p).resolve())

        return Documents(
            photo=fix(self.photo),
            passport_scan=fix(self.passport_scan),
            return_ticket=fix(self.return_ticket),
            accommodation_proof=fix(self.accommodation_proof),
            invitation_letter=fix(self.invitation_letter),
            other={k: fix(v) for k, v in self.other.items()},  # type: ignore[misc]
        )


class Accommodation(_Model):
    name: str
    address: str
    city: str
    phone: str = ""
    email: str = ""


class Host(_Model):
    name: str
    phone: str = ""
    address: str = ""
    relationship: str = ""


class Trip(_Model):
    purpose: Purpose = Purpose.TOURISM
    arrival_date: date
    departure_date: date
    port_of_entry: str
    port_of_exit: str = ""
    arrival_flight: str = ""
    carrier: str = ""
    departure_country: str
    departure_city: str = ""
    accommodation: Accommodation
    host: Host | None = None
    visa_type: str = ""

    _code = field_validator("departure_country")(_country_code)

    @model_validator(mode="after")
    def _dates(self) -> "Trip":
        if self.departure_date < self.arrival_date:
            raise ValueError("departure_date is before arrival_date")
        return self

    @property
    def duration_days(self) -> int:
        return (self.departure_date - self.arrival_date).days + 1


class Applicant(_Model):
    ref: str = ""
    passport: Passport
    contact: Contact
    occupation: str
    marital_status: MaritalStatus = MaritalStatus.SINGLE
    father_name: str = ""
    mother_name: str = ""
    documents: Documents = Field(default_factory=Documents)
    trip: dict[str, Any] = Field(default_factory=dict, description="Per-applicant overrides of the batch trip")
    extra: dict[str, dict[str, Any]] = Field(default_factory=dict, description="Site-specific answers keyed by site")
    mock: bool = False

    @model_validator(mode="after")
    def _ref(self) -> "Applicant":
        if not self.ref:
            slug = re.sub(r"[^a-z0-9]+", "-", self.passport.full_name.lower()).strip("-")
            self.ref = slug or self.passport.number.lower()
        return self

    @property
    def full_name(self) -> str:
        return self.passport.full_name

    def age_on(self, day: date) -> int:
        dob = self.passport.date_of_birth
        return day.year - dob.year - ((day.month, day.day) < (dob.month, dob.day))

    def extra_for(self, site: str) -> dict[str, Any]:
        return self.extra.get(site, {})


class ApplicationBatch(_Model):
    """One trip, many beneficiaries."""

    country: str = Field(description="Registered site key, e.g. 'tanzania'")
    trip: Trip
    applicants: list[Applicant] = Field(min_length=1)
    extra: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _unique_refs(self) -> "ApplicationBatch":
        refs = [a.ref for a in self.applicants]
        dupes = {r for r in refs if refs.count(r) > 1}
        if dupes:
            raise ValueError(f"duplicate applicant refs: {sorted(dupes)}")
        return self

    def trip_for(self, applicant: Applicant) -> Trip:
        if not applicant.trip:
            return self.trip
        merged = self.trip.model_dump() | applicant.trip
        return Trip.model_validate(merged)

    def extra_for(self, site: str) -> dict[str, Any]:
        return self.extra.get(site, {})

    @property
    def is_mock(self) -> bool:
        return any(a.mock for a in self.applicants)


def load_batch(path: str | Path) -> ApplicationBatch:
    """Load a batch JSON file; document paths are resolved relative to it."""
    path = Path(path)
    batch = ApplicationBatch.model_validate(json.loads(path.read_text(encoding="utf-8")))
    base = path.parent.resolve()
    for applicant in batch.applicants:
        applicant.documents = applicant.documents.resolved(base)
    return batch


# --------------------------------------------------------------------------- results


class ApplicationStatus(str, Enum):
    AWAITING_PAYMENT = "awaiting_payment"
    PAID = "paid"
    PAYMENT_FAILED = "payment_failed"
    STOPPED = "stopped"
    FAILED = "failed"
    SKIPPED = "skipped"


class Money(_Model):
    amount: Decimal
    currency: str = "USD"

    def __str__(self) -> str:
        return f"{self.currency} {self.amount:,.2f}"


class PaymentLink(_Model):
    """Everything a person needs to pay for an application later, by hand."""

    portal_url: str = Field(description="Portal page that shows the payment tab (after resuming)")
    gateway_url: str = Field(default="", description="External checkout page, if one was opened (may expire)")
    amount: Money | None = None
    resume: dict[str, str] = Field(default_factory=dict, description="Credentials the portal asks for to resume")
    instructions: str = ""


class PaymentOutcome(_Model):
    success: bool
    reference: str = ""
    message: str = ""
    amount: Money | None = None


class ApplicationResult(_Model):
    applicant_ref: str
    full_name: str
    site: str
    status: ApplicationStatus
    application_id: str = ""
    payment_link: PaymentLink | None = None
    payment: PaymentOutcome | None = None
    fee: Money | None = None
    error: str = ""
    completed_steps: list[str] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime | None = None
