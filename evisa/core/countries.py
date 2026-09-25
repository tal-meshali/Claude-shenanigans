"""ISO 3166-1 alpha-3 country handling and fuzzy matching against dropdown labels.

Visa portals list countries in their own spelling ("Tanzania", "United Republic of
Tanzania", "TANZANIA, UNITED REPUBLIC OF"...). Applicant data always stores the
ICAO/ISO alpha-3 code; this module turns a code into every name a portal might use.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import pycountry

# Names portals commonly use that pycountry does not carry.
_EXTRA_ALIASES: dict[str, tuple[str, ...]] = {
    "USA": ("USA", "United States", "United States of America", "America", "US"),
    "GBR": ("UK", "United Kingdom", "Great Britain", "Britain", "England"),
    "TZA": ("Tanzania",),
    "RUS": ("Russia",),
    "KOR": ("South Korea", "Korea, South", "Korea (South)", "Republic of Korea"),
    "PRK": ("North Korea", "Korea, North"),
    "IRN": ("Iran",),
    "SYR": ("Syria",),
    "VNM": ("Vietnam", "Viet Nam"),
    "LAO": ("Laos",),
    "BOL": ("Bolivia",),
    "VEN": ("Venezuela",),
    "MDA": ("Moldova",),
    "CZE": ("Czech Republic", "Czechia"),
    "NLD": ("Netherlands", "Holland"),
    "TWN": ("Taiwan",),
    "PSE": ("Palestine",),
    "CIV": ("Ivory Coast", "Cote d'Ivoire"),
    "COD": ("DR Congo", "Congo, Democratic Republic", "Democratic Republic of the Congo"),
    "COG": ("Congo", "Republic of the Congo", "Congo-Brazzaville"),
    "MKD": ("Macedonia", "North Macedonia"),
    "SWZ": ("Swaziland", "Eswatini"),
    "CPV": ("Cape Verde", "Cabo Verde"),
    "TUR": ("Turkey", "Turkiye", "Türkiye"),
    "BRN": ("Brunei",),
    "FSM": ("Micronesia",),
    "VAT": ("Vatican", "Holy See"),
    "LKA": ("Sri Lanka",),
    # ICAO specimen country used on sample passports.
    "UTO": ("Utopia",),
}

# Travel-document codes that are not ISO countries (ICAO Doc 9303 part 3).
_ICAO_ONLY = {"UTO": "Utopia", "XXA": "Stateless", "XXB": "Refugee", "XXX": "Unspecified nationality"}


def normalize(text: str) -> str:
    """Case/accent/punctuation-insensitive form used for all label comparisons."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^0-9a-zA-Z]+", " ", text).strip().casefold()
    return re.sub(r"\s+", " ", text)


def is_valid_code(code: str) -> bool:
    code = code.upper()
    return code in _ICAO_ONLY or pycountry.countries.get(alpha_3=code) is not None


def country_name(code: str) -> str:
    """Short, human name for an alpha-3 code ("TZA" -> "Tanzania")."""
    code = code.upper()
    if code in _ICAO_ONLY:
        return _ICAO_ONLY[code]
    country = pycountry.countries.get(alpha_3=code)
    if country is None:
        raise KeyError(f"Unknown country code {code!r}")
    return getattr(country, "common_name", None) or country.name


@lru_cache(maxsize=None)
def country_aliases(code: str) -> tuple[str, ...]:
    """Every plausible label for a country, most specific first."""
    code = code.upper()
    names: list[str] = []
    country = pycountry.countries.get(alpha_3=code)
    if country is not None:
        for attr in ("name", "common_name", "official_name"):
            value = getattr(country, attr, None)
            if value:
                names.append(value)
        # "Tanzania, United Republic of" -> "United Republic of Tanzania"
        if "," in country.name:
            head, tail = (part.strip() for part in country.name.split(",", 1))
            names.append(f"{tail} {head}")
            names.append(head)
        names.append(country.alpha_2)
    elif code in _ICAO_ONLY:
        names.append(_ICAO_ONLY[code])
    names.extend(_EXTRA_ALIASES.get(code, ()))
    names.append(code)
    seen: set[str] = set()
    ordered = []
    for name in names:
        key = normalize(name)
        if key and key not in seen:
            seen.add(key)
            ordered.append(name)
    return tuple(ordered)


def best_option_match(candidates: list[str] | tuple[str, ...], options: list[str]) -> int | None:
    """Index of the option that best matches any candidate label, or None.

    Ranking: exact normalized match > option starts with candidate > candidate
    contained in option (word boundary) > token-set overlap. Earlier candidates
    win ties, so callers list the most precise wording first.
    """
    norm_options = [normalize(o) for o in options]
    norm_candidates = [normalize(c) for c in candidates if c is not None and str(c).strip()]
    if not norm_candidates:
        return None

    for cand in norm_candidates:
        for idx, opt in enumerate(norm_options):
            if opt == cand:
                return idx
    for cand in norm_candidates:
        for idx, opt in enumerate(norm_options):
            if opt.startswith(cand + " ") or (len(cand) > 3 and opt.startswith(cand)):
                return idx
    for cand in norm_candidates:
        if len(cand) < 3:
            continue
        pattern = re.compile(rf"\b{re.escape(cand)}\b")
        for idx, opt in enumerate(norm_options):
            if pattern.search(opt):
                return idx
    best: tuple[float, int] | None = None
    for cand in norm_candidates:
        cand_tokens = set(cand.split())
        for idx, opt in enumerate(norm_options):
            opt_tokens = set(opt.split())
            if not opt_tokens:
                continue
            overlap = len(cand_tokens & opt_tokens) / len(cand_tokens | opt_tokens)
            if overlap >= 0.5 and (best is None or overlap > best[0]):
                best = (overlap, idx)
    return best[1] if best else None
