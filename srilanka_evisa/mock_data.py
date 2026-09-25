"""Generate SPECIMEN passport scans, ID photos and a ready-to-use applicants file.

Everything produced here is fictitious and watermarked "SPECIMEN"; it exists
only to exercise the automation against the local mock site."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

from .mrz import build_td3

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


def _font(name: str, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(FONT_DIR / name), size)
    except OSError:
        return ImageFont.load_default(size)


@dataclass
class MockPerson:
    surname: str
    given_names: str
    sex: str
    date_of_birth: date
    nationality: str
    place_of_birth: str
    passport_number: str
    issue_date: date
    occupation: str
    title: str

    @property
    def expiry_date(self) -> date:
        return self.issue_date.replace(year=self.issue_date.year + 10) - timedelta(days=1)


MOCK_PEOPLE = [
    MockPerson("Dupont", "Jean Pierre", "M", date(1984, 3, 14), "FRA", "Lyon", "24FR81234",
               date(2024, 2, 1), "Engineer", "Mr"),
    MockPerson("Dupont", "Marie Claire", "F", date(1987, 11, 2), "FRA", "Marseille", "23FR55120",
               date(2023, 6, 20), "Teacher", "Mrs"),
    MockPerson("Dupont", "Lucas", "M", date(2014, 7, 30), "FRA", "Paris", "25FR00731",
               date(2025, 1, 9), "Student", "Master"),
]


def _face_colours(seed: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    h = hashlib.sha256(seed.encode()).digest()
    skin = (200 + h[0] % 40, 160 + h[1] % 50, 120 + h[2] % 50)
    hair = (h[3] % 90, h[4] % 70, h[5] % 50)
    return skin, hair


def draw_photo(person: MockPerson, size: tuple[int, int] = (350, 450)) -> Image.Image:
    """A cartoon head-and-shoulders portrait on a plain background."""
    w, h = size
    img = Image.new("RGB", size, (235, 240, 245))
    d = ImageDraw.Draw(img)
    skin, hair = _face_colours(person.passport_number)
    d.ellipse((w * 0.12, h * 0.72, w * 0.88, h * 1.25), fill=(60, 80, 120))  # shoulders
    d.rectangle((w * 0.42, h * 0.58, w * 0.58, h * 0.78), fill=skin)  # neck
    d.ellipse((w * 0.26, h * 0.14, w * 0.74, h * 0.66), fill=skin)  # face
    d.chord((w * 0.24, h * 0.10, w * 0.76, h * 0.50), 180, 360, fill=hair)  # hair
    for ex in (0.40, 0.60):
        d.ellipse((w * ex - 9, h * 0.38 - 6, w * ex + 9, h * 0.38 + 6), fill=(40, 40, 40))
    d.arc((w * 0.42, h * 0.46, w * 0.58, h * 0.56), 20, 160, fill=(150, 60, 60), width=4)
    return img


def draw_passport(person: MockPerson) -> Image.Image:
    """Passport bio-data page with a valid TD3 MRZ, watermarked SPECIMEN."""
    W, H = 1250, 880
    img = Image.new("RGB", (W, H), (226, 232, 240))
    d = ImageDraw.Draw(img)
    for y in range(0, H, 14):  # guilloche-ish background lines
        d.line((0, y, W, y + 40), fill=(214, 222, 234), width=1)

    title, label, value = _font("DejaVuSans-Bold.ttf", 34), _font("DejaVuSans.ttf", 17), _font("DejaVuSans-Bold.ttf", 25)
    d.text((40, 28), "RÉPUBLIQUE FRANÇAISE — PASSEPORT / PASSPORT", font=title, fill=(20, 40, 90))

    img.paste(draw_photo(person), (50, 110))

    rows = [
        ("Type / Type", "P", "Code / Code", person.nationality, "Passeport n° / Passport No.", person.passport_number),
        ("Nom / Surname", person.surname.upper(), None, None, None, None),
        ("Prénoms / Given names", person.given_names.upper(), None, None, None, None),
        ("Nationalité / Nationality", "FRANÇAISE", "Sexe / Sex", person.sex, None, None),
        ("Date de naissance / Date of birth", person.date_of_birth.strftime("%d %m %Y"),
         "Lieu de naissance / Place of birth", person.place_of_birth.upper(), None, None),
        ("Date de délivrance / Date of issue", person.issue_date.strftime("%d %m %Y"),
         "Date d'expiration / Date of expiry", person.expiry_date.strftime("%d %m %Y"), None, None),
    ]
    y = 110
    for row in rows:
        cells = [(row[i], row[i + 1]) for i in range(0, 6, 2) if row[i] is not None]
        xs = (440, 620, 830) if len(cells) == 3 else (440, 830)
        for x, (lbl, val) in zip(xs, cells):
            d.text((x, y), lbl, font=label, fill=(70, 80, 100))
            d.text((x, y + 22), val, font=value, fill=(10, 10, 10))
        y += 72

    line1, line2 = build_td3(
        issuing_country=person.nationality, surname=person.surname, given_names=person.given_names,
        passport_number=person.passport_number, nationality=person.nationality,
        date_of_birth=person.date_of_birth, sex=person.sex, expiry_date=person.expiry_date,
    )
    d.rectangle((0, H - 170, W, H), fill=(245, 245, 240))
    mrz_font = _font("DejaVuSansMono.ttf", 40)
    d.text((30, H - 150), line1, font=mrz_font, fill=(0, 0, 0))
    d.text((30, H - 85), line2, font=mrz_font, fill=(0, 0, 0))

    stamp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(stamp).text((120, 290), "SPECIMEN", font=_font("DejaVuSans-Bold.ttf", 190), fill=(200, 30, 30, 90))
    img = Image.alpha_composite(img.convert("RGBA"), stamp.rotate(12, center=(W / 2, H / 2)))
    return img.convert("RGB")


def generate(out_dir: str | Path, people: list[MockPerson] | None = None, arrival_in_days: int = 30) -> Path:
    """Write passport scans, photos and applicants.yaml into out_dir; return the YAML path."""
    out = Path(out_dir)
    (out / "passports").mkdir(parents=True, exist_ok=True)
    (out / "photos").mkdir(parents=True, exist_ok=True)
    people = people or MOCK_PEOPLE

    beneficiaries = []
    for p in people:
        slug = f"{p.surname}_{p.given_names.split()[0]}".lower()
        draw_passport(p).save(out / "passports" / f"{slug}.png")
        draw_photo(p).save(out / "photos" / f"{slug}.jpg", quality=92)
        line1, line2 = build_td3(
            issuing_country=p.nationality, surname=p.surname, given_names=p.given_names,
            passport_number=p.passport_number, nationality=p.nationality,
            date_of_birth=p.date_of_birth, sex=p.sex, expiry_date=p.expiry_date,
        )
        beneficiaries.append({
            # Identity fields come from the MRZ; the rest is printed on the page only.
            "mrz": f"{line1}\n{line2}",
            "title": p.title,
            "country_of_birth": p.nationality,
            "passport_issue_date": p.issue_date.isoformat(),
            "occupation": p.occupation,
            "home_address": "12 Rue de la Paix, 75002 Paris, France",
            "passport_image": f"passports/{slug}.png",
            "photo": f"photos/{slug}.jpg",
        })

    arrival = date.today() + timedelta(days=arrival_in_days)
    doc = {
        "mode": "group",
        "visa_type": "tourist",
        "locale": "fr_FR",
        "trip": {
            "arrival_date": arrival.isoformat(),
            "duration_days": 21,
            "purpose": "Tourism",
            "port_of_departure": "Paris CDG",
            "mode_of_travel": "Air",
            "flight_number": "UL564",
            "address_in_sri_lanka": "Galle Face Hotel, 2 Galle Road, Colombo 03",
        },
        "contact": {
            "email": "jean.dupont@example.com",
            "phone": "+33612345678",
            "address": "12 Rue de la Paix, 75002 Paris, France",
        },
        "beneficiaries": beneficiaries,
    }
    path = out / "applicants.yaml"
    path.write_text(
        "# MOCK DATA — fictitious people for testing against the local mock site only.\n"
        + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path
