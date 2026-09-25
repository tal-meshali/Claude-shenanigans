"""Tanzania e-visa reference data (Tanzania Immigration Services Department).

Fees and visa categories follow the portal's published guidelines
(https://visa.immigration.go.tz/guidelines, section 12 "Visa fees"); the
payment tab shows the authoritative amount and the automation asks again
before paying if the two differ.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ...core.models import Applicant, Purpose, Trip


@dataclass(frozen=True)
class VisaType:
    key: str
    labels: tuple[str, ...]  # how the portal may spell it, most specific first
    fee_usd: Decimal


VISA_TYPES: dict[str, VisaType] = {
    "ordinary": VisaType("ordinary", ("Ordinary Visa", "Ordinary", "Single Entry", "Tourist Visa"), Decimal(50)),
    "multiple": VisaType("multiple", ("Multiple Entry Visa", "Multiple Entry", "Multiple"), Decimal(100)),
    "business": VisaType("business", ("Business Visa", "Business"), Decimal(250)),
    "transit": VisaType("transit", ("Transit Visa", "Transit"), Decimal(30)),
}

# Nationalities that the portal only offers the multiple-entry visa to.
MULTIPLE_ENTRY_ONLY = {"USA"}


def visa_type_for(applicant: Applicant, trip: Trip) -> VisaType:
    explicit = applicant.extra_for("tanzania").get("visa_type") or trip.visa_type
    if explicit:
        key = explicit.lower().split()[0]
        if key in VISA_TYPES:
            return VISA_TYPES[key]
        for vt in VISA_TYPES.values():
            if explicit.lower() in (label.lower() for label in vt.labels):
                return vt
        raise ValueError(f"unknown Tanzania visa type {explicit!r}; use one of {sorted(VISA_TYPES)}")
    if applicant.passport.nationality in MULTIPLE_ENTRY_ONLY:
        return VISA_TYPES["multiple"]
    if trip.purpose is Purpose.BUSINESS:
        return VISA_TYPES["business"]
    if trip.purpose is Purpose.TRANSIT:
        return VISA_TYPES["transit"]
    return VISA_TYPES["ordinary"]


PURPOSE_LABELS: dict[Purpose, tuple[str, ...]] = {
    Purpose.TOURISM: ("Tourism", "Holiday", "Leisure", "Tourist"),
    Purpose.BUSINESS: ("Business",),
    Purpose.VISITING_FAMILY: ("Visiting Family", "Visiting Friends and Relatives", "Family Visit", "Visit"),
    Purpose.CONFERENCE: ("Conference", "Meeting", "Seminar"),
    Purpose.TRANSIT: ("Transit",),
    Purpose.MEDICAL: ("Medical Treatment", "Medical"),
    Purpose.STUDY: ("Study", "Education"),
    Purpose.OTHER: ("Other", "Others"),
}

# Official ports of entry; aliases let travellers write "KIA", "Zanzibar", ...
PORTS_OF_ENTRY: dict[str, tuple[str, ...]] = {
    "Julius Nyerere International Airport": ("JNIA", "Dar es Salaam Airport", "DAR", "Dar es Salaam"),
    "Kilimanjaro International Airport": ("KIA", "JRO", "Kilimanjaro", "Arusha"),
    "Abeid Amani Karume International Airport": ("AAKIA", "Zanzibar Airport", "ZNZ", "Zanzibar"),
    "Mwanza Airport": ("MWZ", "Mwanza"),
    "Namanga": ("Namanga Border",),
    "Holili": ("Holili Border", "Taveta"),
    "Horohoro": ("Horohoro Border", "Lunga Lunga"),
    "Sirari": ("Sirari Border", "Isebania"),
    "Rusumo": ("Rusumo Border",),
    "Tunduma": ("Tunduma Border", "Nakonde"),
    "Kasumulu": ("Kasumulu Border", "Songwe"),
    "Mutukula": ("Mutukula Border",),
    "Dar es Salaam Port": ("Dar es Salaam Harbour",),
    "Zanzibar Port": ("Malindi Port", "Zanzibar Harbour"),
}


def port_labels(port: str) -> list[str]:
    """Candidate dropdown labels for a port the traveller typed."""
    wanted = port.strip().lower()
    for official, aliases in PORTS_OF_ENTRY.items():
        if wanted == official.lower() or wanted in (a.lower() for a in aliases):
            return [official, *aliases]
    return [port]


# The portal's questions (observed September 2026, spelling as on the site):
#   "In what city/town/village you were  born?", "what is the name of the hospital you ware born?",
#   "what is the name of the street you grew up?", "What was your childhood nickname?"
DEFAULT_SECURITY_QUESTION = "What was your childhood nickname?"
