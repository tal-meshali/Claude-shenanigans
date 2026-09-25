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
    title: str = ""  # MR / MRS / MS / MISS / MASTER / DR
    occupation: str = ""
    relationship: str = ""  # for group members, e.g. "Spouse", "Child"
    country_of_address: str = ""  # ISO3 country the traveller lives in (default: the contact's country)
    passport_image: Path | None = None  # scan of the passport bio page (source of the MRZ)
    photo: Path | None = None  # passport-style photo, for portals that ask for one

    @property
    def full_name(self) -> str:
        return f"{self.given_names} {self.surname}"

    @property
    def resolved_title(self) -> str:
        if self.title:
            return self.title.upper().rstrip(".")
        return "MR" if self.sex == "M" else "MS"


@dataclass
class Trip:
    arrival_date: date
    departure_country: str  # ISO3: where the travellers are in the 14 days before travel
    visa_days: int = 30
    purpose: str = "Tourism"
    port_of_departure: str = ""
    airline: str = ""
    flight_number: str = ""
    address_in_sri_lanka: str = ""


@dataclass
class Contact:
    email: str
    telephone: str
    address_line1: str
    city: str
    state: str
    country: str  # ISO3
    address_line2: str = ""
    postal_code: str = ""
    mobile: str = ""


@dataclass
class Declarations:
    """The yes/no questions at the end of the ETA form."""
    has_residence_visa: bool = False
    currently_in_sri_lanka: bool = False
    has_multiple_entry_visa: bool = False


@dataclass
class Application:
    trip: Trip
    contact: Contact
    beneficiaries: list[Beneficiary]
    mode: str = "group"  # "group": one application for everyone; "individual": one per beneficiary
    visa_type: str = "tourist"  # tourist / business / transit
    declarations: Declarations = field(default_factory=Declarations)

    def validate(self, today: date | None = None) -> list[str]:
        """Return a list of problems; raise nothing so the CLI can print them all."""
        today = today or date.today()
        problems: list[str] = []
        if self.mode not in ("group", "individual"):
            problems.append(f"mode must be 'group' or 'individual', not {self.mode!r}")
        if self.visa_type not in ("tourist", "business", "transit"):
            problems.append(f"visa_type must be tourist, business or transit, not {self.visa_type!r}")
        if not self.beneficiaries:
            problems.append("at least one beneficiary is required")
        if self.mode == "group" and len(self.beneficiaries) < 2:
            problems.append("group mode needs at least two beneficiaries (use mode: individual)")
        if not EMAIL_RE.match(self.contact.email):
            problems.append(f"contact.email is not a valid address: {self.contact.email!r}")
        if self.trip.arrival_date < today:
            problems.append("trip.arrival_date is in the past")
        if self.trip.visa_days not in (30, 90):
            problems.append("trip.visa_days must be 30 or 90")
        if self.trip.address_in_sri_lanka and len(self.trip.address_in_sri_lanka) > 250:
            problems.append("trip.address_in_sri_lanka is longer than 250 characters")

        for i, b in enumerate(self.beneficiaries, 1):
            who = f"beneficiary #{i} ({b.full_name})"
            if b.sex not in ("M", "F"):
                problems.append(f"{who}: sex must be 'M' or 'F'")
            if b.date_of_birth >= today:
                problems.append(f"{who}: date_of_birth must be in the past")
            if b.passport_issue_date > today:
                problems.append(f"{who}: passport_issue_date is in the future")
            if not re.fullmatch(r"[A-Z0-9]{5,12}", b.passport_number):
                problems.append(f"{who}: passport_number must be 5-12 letters/digits")
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
            "surname": m.surname,
            "given_names": m.given_names,
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
    # The portal only accepts upper-case names and passport numbers.
    for key in ("surname", "given_names", "passport_number"):
        raw[key] = str(raw[key]).upper().strip()
    for key in ("nationality", "country_of_birth", "passport_issuing_country", "country_of_address"):
        raw[key] = str(raw.get(key, "")).upper()
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
        trip_raw["departure_country"] = str(trip_raw["departure_country"]).upper()
        trip = Trip(**trip_raw)
        contact_raw = dict(raw["contact"])
        contact_raw["country"] = str(contact_raw["country"]).upper()
        contact = Contact(**{k: str(v) for k, v in contact_raw.items()})
        declarations = Declarations(**raw.get("declarations", {}))
        beneficiaries = [_beneficiary_from_dict(b, base_dir) for b in raw["beneficiaries"]]
    except (KeyError, TypeError) as exc:
        raise ValidationError(f"{path}: invalid application file: {exc}") from exc
    return Application(
        trip=trip,
        contact=contact,
        beneficiaries=beneficiaries,
        mode=raw.get("mode", "group" if len(beneficiaries) > 1 else "individual"),
        visa_type=raw.get("visa_type", "tourist"),
        declarations=declarations,
    )
