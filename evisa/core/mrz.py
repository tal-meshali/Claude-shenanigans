"""ICAO Doc 9303 TD3 (passport) machine-readable zone: build, parse and verify."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

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


def parse_td3(line1: str, line2: str) -> ParsedTD3:
    if len(line1) != TD3_LINE_LENGTH or len(line2) != TD3_LINE_LENGTH:
        raise ValueError("TD3 lines must be 44 characters")
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
