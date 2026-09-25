"""Application data: trip, contact and one or more beneficiaries (travellers)."""

from __future__ import annotations

import re
from dataclasses import MISSING, dataclass, field, fields
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from .mrz import find_td3, parse_td3

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValidationError(ValueError):
    pass


def _to_date(value: Any, name: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationError(f"{name}: expected YYYY-MM-DD, got {value!r}") from exc


@dataclass
class Beneficiary:
    surname: str
    given_names: str
    sex: str  # "M" / "F"
    date_of_birth: date
    nationality: str  # ISO 3166 alpha-3
    country_of_birth: str
    passport_number: str
    passport_issue_date: date
    passport_expiry_date: date
    passport_issuing_country: str = ""
    title: str = ""  # Mr / Mrs / Ms ...
    occupation: str = ""
    home_address: str = ""
    passport_image: Path | None = None  # scan of the passport bio page
    photo: Path | None = None  # passport-style photo

    @property
    def full_name(self) -> str:
        return f"{self.given_names} {self.surname}"

    @property
    def resolved_title(self) -> str:
        return self.title or ("Mr" if self.sex == "M" else "Ms")


@dataclass
class Trip:
    arrival_date: date
    duration_days: int
    purpose: str = "Tourism"
    port_of_departure: str = ""
    mode_of_travel: str = "Air"  # Air / Sea
    flight_number: str = ""
    address_in_sri_lanka: str = ""

    @property
    def departure_date(self) -> date:
        return self.arrival_date + timedelta(days=self.duration_days)


@dataclass
class Contact:
    email: str
    phone: str
    address: str = ""


@dataclass
class Application:
    trip: Trip
    contact: Contact
    beneficiaries: list[Beneficiary]
    mode: str = "group"  # "group": one application for everyone; "individual": one per beneficiary
    visa_type: str = "tourist"
    locale: str = "fr_FR"
    extra: dict[str, Any] = field(default_factory=dict)

    def validate(self, today: date | None = None) -> list[str]:
        """Return a list of problems; raise nothing so the CLI can print them all."""
        today = today or date.today()
        problems: list[str] = []
        if self.mode not in ("group", "individual"):
            problems.append(f"mode must be 'group' or 'individual', not {self.mode!r}")
        if not self.beneficiaries:
            problems.append("at least one beneficiary is required")
        if self.mode == "group" and len(self.beneficiaries) < 2:
            problems.append("group mode needs at least two beneficiaries (use mode: individual)")
        if not EMAIL_RE.match(self.contact.email):
            problems.append(f"contact.email is not a valid address: {self.contact.email!r}")
        if self.trip.arrival_date < today:
            problems.append("trip.arrival_date is in the past")
        if not 1 <= self.trip.duration_days <= 30:
            problems.append("trip.duration_days must be 1-30 for a tourist ETA")

        for i, b in enumerate(self.beneficiaries, 1):
            who = f"beneficiary #{i} ({b.full_name})"
            if b.sex not in ("M", "F"):
                problems.append(f"{who}: sex must be 'M' or 'F'")
            if b.date_of_birth >= today:
                problems.append(f"{who}: date_of_birth must be in the past")
            if b.passport_issue_date > today:
                problems.append(f"{who}: passport_issue_date is in the future")
            # Sri Lanka requires at least 6 months of passport validity on arrival.
            if b.passport_expiry_date < self.trip.arrival_date + timedelta(days=183):
                problems.append(f"{who}: passport must be valid 6 months beyond arrival")
            for attr in ("passport_image", "photo"):
                path = getattr(b, attr)
                if path is not None and not Path(path).is_file():
                    problems.append(f"{who}: {attr} file not found: {path}")
        return problems


def _beneficiary_from_dict(raw: dict[str, Any], base_dir: Path) -> Beneficiary:
    raw = dict(raw)
    mrz_text = raw.pop("mrz", None)
    if raw.pop("read_mrz_from_image", False) and raw.get("passport_image"):
        mrz_text = mrz_text or ocr_mrz(base_dir / raw["passport_image"])
    if mrz_text:
        pair = find_td3(mrz_text)
        if not pair:
            raise ValidationError("could not find a TD3 passport MRZ in the given text")
        m = parse_td3(*pair)
        # Explicit values in the file win over what the MRZ says.
        for key, value in {
            "surname": m.surname.title(),
            "given_names": m.given_names.title(),
            "sex": m.sex,
            "date_of_birth": m.date_of_birth,
            "nationality": m.nationality,
            "passport_number": m.passport_number,
            "passport_expiry_date": m.expiry_date,
            "passport_issuing_country": m.issuing_country,
        }.items():
            raw.setdefault(key, value)

    raw.setdefault("country_of_birth", raw.get("nationality", ""))
    raw.setdefault("passport_issuing_country", raw.get("nationality", ""))
    known = {f.name for f in fields(Beneficiary)}
    unknown = set(raw) - known
    if unknown:
        raise ValidationError(f"unknown beneficiary field(s): {', '.join(sorted(unknown))}")
    missing = [f.name for f in fields(Beneficiary) if f.default is MISSING and f.name not in raw]
    if missing:
        raise ValidationError(f"missing beneficiary field(s): {', '.join(missing)}")

    for key in ("date_of_birth", "passport_issue_date", "passport_expiry_date"):
        raw[key] = _to_date(raw[key], key)
    for key in ("passport_image", "photo"):
        if raw.get(key):
            raw[key] = (base_dir / raw[key]).resolve()
    raw["sex"] = str(raw["sex"]).upper()[:1]
    for key in ("nationality", "country_of_birth", "passport_issuing_country"):
        raw[key] = str(raw[key]).upper()
    return Beneficiary(**raw)


def ocr_mrz(image_path: Path) -> str:
    """OCR the bottom of a passport scan. Needs `pytesseract` + the tesseract binary."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ValidationError("read_mrz_from_image needs `pip install pytesseract` and tesseract") from exc
    img = Image.open(image_path)
    w, h = img.size
    band = img.crop((0, int(h * 0.7), w, h))
    return pytesseract.image_to_string(
        band, config="--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
    )


def load_application(path: str | Path) -> Application:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    base_dir = path.parent
    try:
        trip_raw = dict(raw["trip"])
        trip_raw["arrival_date"] = _to_date(trip_raw["arrival_date"], "trip.arrival_date")
        trip = Trip(**trip_raw)
        contact = Contact(**raw["contact"])
        beneficiaries = [_beneficiary_from_dict(b, base_dir) for b in raw["beneficiaries"]]
    except (KeyError, TypeError) as exc:
        raise ValidationError(f"{path}: invalid application file: {exc}") from exc
    return Application(
        trip=trip,
        contact=contact,
        beneficiaries=beneficiaries,
        mode=raw.get("mode", "group" if len(beneficiaries) > 1 else "individual"),
        visa_type=raw.get("visa_type", "tourist"),
        locale=raw.get("locale", "fr_FR"),
        extra=raw.get("extra", {}),
    )
