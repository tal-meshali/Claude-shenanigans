"""ICAO 9303 TD3 (passport) machine readable zone: build and parse."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_WEIGHTS = (7, 3, 1)
TD3_LINE_LENGTH = 44


def _char_value(ch: str) -> int:
    if ch.isdigit():
        return int(ch)
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A") + 10
    if ch == "<":
        return 0
    raise ValueError(f"Invalid MRZ character: {ch!r}")


def check_digit(data: str) -> str:
    return str(sum(_char_value(c) * _WEIGHTS[i % 3] for i, c in enumerate(data)) % 10)


def _clean(text: str) -> str:
    """Upper-case and transliterate to the MRZ alphabet (A-Z, 0-9, <)."""
    table = str.maketrans("ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖØÙÚÛÜÝ", "AAAAAACEEEEIIIINOOOOOOUUUUY")
    text = text.upper().translate(table)
    text = re.sub(r"[\s\-']", "<", text)
    return re.sub(r"[^A-Z0-9<]", "", text)


def _pad(text: str, length: int) -> str:
    return text[:length].ljust(length, "<")


def _yymmdd(d: date) -> str:
    return d.strftime("%y%m%d")


@dataclass(frozen=True)
class MRZData:
    document_type: str
    issuing_country: str
    surname: str
    given_names: str
    passport_number: str
    nationality: str
    date_of_birth: date
    sex: str
    expiry_date: date
    personal_number: str = ""


def build_td3(
    *,
    issuing_country: str,
    surname: str,
    given_names: str,
    passport_number: str,
    nationality: str,
    date_of_birth: date,
    sex: str,
    expiry_date: date,
    personal_number: str = "",
) -> tuple[str, str]:
    name_field = _clean(surname) + "<<" + _clean(given_names)
    line1 = _pad("P<" + _clean(issuing_country) + name_field, TD3_LINE_LENGTH)

    number = _pad(_clean(passport_number), 9)
    dob = _yymmdd(date_of_birth)
    exp = _yymmdd(expiry_date)
    personal = _pad(_clean(personal_number), 14)
    sex_char = {"M": "M", "F": "F"}.get(sex.upper(), "<")

    part_number = number + check_digit(number)
    part_dob = dob + check_digit(dob)
    part_exp = exp + check_digit(exp)
    part_personal = personal + check_digit(personal)
    composite = check_digit(part_number + part_dob + part_exp + part_personal)

    line2 = (
        part_number + _pad(_clean(nationality), 3) + part_dob + sex_char + part_exp + part_personal + composite
    )
    return line1, line2


def _parse_date(yymmdd: str, *, future: bool) -> date:
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:])
    this_year = date.today().year % 100
    if future:
        century = 2000
    else:
        century = 1900 if yy > this_year else 2000
    return date(century + yy, mm, dd)


class MRZError(ValueError):
    pass


def parse_td3(line1: str, line2: str) -> MRZData:
    line1, line2 = line1.strip().upper(), line2.strip().upper()
    if len(line1) != TD3_LINE_LENGTH or len(line2) != TD3_LINE_LENGTH:
        raise MRZError("TD3 lines must be 44 characters long")
    if line1[0] != "P":
        raise MRZError("Not a passport MRZ (line 1 must start with 'P')")

    checks = {
        "passport number": (line2[0:9], line2[9]),
        "date of birth": (line2[13:19], line2[19]),
        "expiry date": (line2[21:27], line2[27]),
        "composite": (line2[0:10] + line2[13:20] + line2[21:43], line2[43]),
    }
    for name, (data, digit) in checks.items():
        if check_digit(data) != digit:
            raise MRZError(f"Check digit mismatch for {name}")

    names = line1[5:].rstrip("<")
    surname, _, given = names.partition("<<")
    return MRZData(
        document_type=line1[0:2].rstrip("<"),
        issuing_country=line1[2:5].rstrip("<"),
        surname=surname.replace("<", " ").strip(),
        given_names=given.replace("<", " ").strip(),
        passport_number=line2[0:9].rstrip("<"),
        nationality=line2[10:13].rstrip("<"),
        date_of_birth=_parse_date(line2[13:19], future=False),
        sex=line2[20] if line2[20] in "MF" else "X",
        expiry_date=_parse_date(line2[21:27], future=True),
        personal_number=line2[28:42].rstrip("<"),
    )


def find_td3(text: str) -> tuple[str, str] | None:
    """Find a TD3 MRZ pair in free text (e.g. OCR output)."""
    lines = [re.sub(r"\s", "", ln).upper() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    for first, second in zip(lines, lines[1:]):
        if first.startswith("P") and len(first) == TD3_LINE_LENGTH and len(second) == TD3_LINE_LENGTH:
            return first, second
    return None
