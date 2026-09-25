"""ICAO Doc 9303 TD3 (passport) machine-readable zone: build, parse and verify."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

TD3_LINE_LENGTH = 44
_WEIGHTS = (7, 3, 1)

# Doc 9303 transliterations that are not handled by stripping diacritics.
_TRANSLITERATIONS = {"Ä": "AE", "Ö": "OE", "Ü": "UE", "ß": "SS", "Æ": "AE", "Ø": "OE", "Å": "AA", "Þ": "TH", "Ð": "D"}

# Germany is the one state whose MRZ code differs from ISO alpha-3.
_MRZ_COUNTRY = {"DEU": "D<<"}


def _char_value(ch: str) -> int:
    if ch.isdigit():
        return int(ch)
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A") + 10
    if ch == "<":
        return 0
    raise ValueError(f"Invalid MRZ character {ch!r}")


def check_digit(field: str) -> str:
    return str(sum(_char_value(ch) * _WEIGHTS[i % 3] for i, ch in enumerate(field)) % 10)


def transliterate(text: str) -> str:
    """Upper-case, MRZ-safe version of a name: A-Z and '<' filler only."""
    text = text.upper()
    text = "".join(_TRANSLITERATIONS.get(ch, ch) for ch in text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[\s\-']+", "<", text)
    return re.sub(r"[^A-Z0-9<]", "", text)


def _pad(value: str, length: int) -> str:
    return (value + "<" * length)[:length]


def _mrz_date(value: date) -> str:
    return value.strftime("%y%m%d")


def mrz_country(code: str) -> str:
    code = code.upper()
    return _MRZ_COUNTRY.get(code, code)


@dataclass(frozen=True)
class TD3:
    line1: str
    line2: str

    @property
    def lines(self) -> tuple[str, str]:
        return self.line1, self.line2

    def __str__(self) -> str:
        return f"{self.line1}\n{self.line2}"


def build_td3(
    *,
    document_type: str,
    issuing_country: str,
    surname: str,
    given_names: str,
    number: str,
    nationality: str,
    date_of_birth: date,
    sex: str,
    date_of_expiry: date,
    personal_number: str = "",
) -> TD3:
    doc = _pad(transliterate(document_type), 2)
    name = transliterate(surname) + "<<" + transliterate(given_names)
    line1 = doc + _pad(mrz_country(issuing_country), 3) + _pad(name, 39)

    number_field = _pad(transliterate(number), 9)
    dob = _mrz_date(date_of_birth)
    expiry = _mrz_date(date_of_expiry)
    personal = _pad(transliterate(personal_number), 14)
    personal_cd = check_digit(personal) if personal.strip("<") else "<"
    sex_field = sex.upper() if sex.upper() in ("M", "F") else "<"

    line2 = (
        number_field
        + check_digit(number_field)
        + _pad(mrz_country(nationality), 3)
        + dob
        + check_digit(dob)
        + sex_field
        + expiry
        + check_digit(expiry)
        + personal
        + personal_cd
    )
    composite = line2[0:10] + line2[13:20] + line2[21:43]
    line2 += check_digit(composite)
    assert len(line1) == len(line2) == TD3_LINE_LENGTH
    return TD3(line1, line2)


class MRZError(ValueError):
    pass


def _mrz_to_date(yymmdd: str, *, future: bool) -> date:
    """Expiry dates are always 20xx; birth dates are the most recent past century."""
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    if future:
        return date(2000 + yy, mm, dd)
    century = 1900 if yy > date.today().year % 100 else 2000
    return date(century + yy, mm, dd)


@dataclass(frozen=True)
class ParsedTD3:
    document_type: str
    issuing_country: str
    surname: str
    given_names: str
    number: str
    nationality: str
    birth_yymmdd: str
    sex: str
    expiry_yymmdd: str
    personal_number: str
    checks_ok: bool

    @property
    def date_of_birth(self) -> date:
        return _mrz_to_date(self.birth_yymmdd, future=False)

    @property
    def date_of_expiry(self) -> date:
        return _mrz_to_date(self.expiry_yymmdd, future=True)

    def passport_fields(self) -> dict[str, object]:
        """Values for `models.Passport` (names title-cased)."""
        return {
            "document_type": self.document_type or "P",
            "issuing_country": "DEU" if self.issuing_country == "D" else self.issuing_country,
            "surname": self.surname.title(),
            "given_names": self.given_names.title(),
            "number": self.number,
            "nationality": "DEU" if self.nationality == "D" else self.nationality,
            "date_of_birth": self.date_of_birth,
            "sex": self.sex if self.sex in ("M", "F") else "X",
            "date_of_expiry": self.date_of_expiry,
            "personal_number": self.personal_number,
        }


def parse_td3(line1: str, line2: str, *, strict: bool = False) -> ParsedTD3:
    """Parse a passport MRZ. `strict` raises MRZError when a check digit is wrong."""
    line1, line2 = line1.strip().upper(), line2.strip().upper()
    if len(line1) != TD3_LINE_LENGTH or len(line2) != TD3_LINE_LENGTH:
        raise MRZError("TD3 lines must be 44 characters")
    if not line1.startswith("P"):
        raise MRZError("not a passport MRZ (line 1 must start with 'P')")
    names = line1[5:44].split("<<", 1)
    surname = names[0].replace("<", " ").strip()
    given = names[1].replace("<", " ").strip() if len(names) > 1 else ""
    personal = line2[28:42]
    checks = [
        check_digit(line2[0:9]) == line2[9],
        check_digit(line2[13:19]) == line2[19],
        check_digit(line2[21:27]) == line2[27],
        (line2[42] == "<" and not personal.strip("<")) or check_digit(personal) == line2[42],
        check_digit(line2[0:10] + line2[13:20] + line2[21:43]) == line2[43],
    ]
    if strict and not all(checks):
        raise MRZError("MRZ check digit mismatch")
    return ParsedTD3(
        document_type=line1[0:2].rstrip("<"),
        issuing_country=line1[2:5].rstrip("<"),
        surname=surname,
        given_names=given,
        number=line2[0:9].rstrip("<"),
        nationality=line2[10:13].rstrip("<"),
        birth_yymmdd=line2[13:19],
        sex=line2[20],
        expiry_yymmdd=line2[21:27],
        personal_number=personal.rstrip("<"),
        checks_ok=all(checks),
    )


def find_td3(text: str) -> tuple[str, str] | None:
    """Find a TD3 line pair in free text (pasted MRZ, OCR output)."""
    lines = [re.sub(r"\s", "", ln).upper() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    for first, second in zip(lines, lines[1:]):
        if first.startswith("P") and len(first) == TD3_LINE_LENGTH and len(second) == TD3_LINE_LENGTH:
            return first, second
    return None


def ocr_mrz(image_path: Path) -> str:
    """OCR the MRZ band of a passport scan. Needs `pip install pytesseract` and the tesseract binary."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise MRZError("reading the MRZ from an image needs `pip install pytesseract` and tesseract") from exc
    with Image.open(image_path) as img:
        band = img.crop((0, int(img.height * 0.7), img.width, img.height))
        return pytesseract.image_to_string(band, config="--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")
