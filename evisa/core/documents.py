"""Upload preparation and SPECIMEN document generation.

`prepare_upload` makes any image/PDF satisfy a portal's format and size limits.
`generate_mock_documents` renders clearly-marked specimen files (passport bio
page with a valid MRZ, passport photo, e-ticket, hotel voucher) for mock
applicants, so the whole flow can be exercised without real documents.
"""

from __future__ import annotations

import hashlib
import io
import shutil
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import countries
from .models import Applicant, Documents, Trip

FONT_DIRS = (
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/Library/Fonts"),
    Path("C:/Windows/Fonts"),
)


@dataclass(frozen=True)
class DocumentRequirement:
    """What a portal accepts for one upload slot."""

    kind: str  # attribute name on `Documents` (photo, passport_scan, ...)
    label: str
    formats: tuple[str, ...] = ("jpeg", "png")  # target extensions, in preference order
    max_kb: int = 300
    required: bool = True
    # Exact pixel size to resize photos to, if the portal is strict about it.
    pixel_size: tuple[int, int] | None = None
    extension_aliases: dict[str, str] = field(default_factory=lambda: {"jpg": "jpeg"})


class DocumentError(ValueError):
    pass


@lru_cache(maxsize=64)
def _font(size: int, *, bold: bool = False, mono: bool = False) -> ImageFont.ImageFont:
    names = (
        ["DejaVuSansMono-Bold.ttf", "LiberationMono-Bold.ttf", "consolab.ttf"]
        if mono
        else (["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"] if bold else ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "arial.ttf"])
    )
    for directory in FONT_DIRS:
        for name in names:
            candidate = directory / name
            if candidate.exists():
                return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default(size=size)


# --------------------------------------------------------------------- uploads


def _save_jpeg_within(img: Image.Image, dest: Path, max_kb: int) -> None:
    img = img.convert("RGB")
    for scale in (1.0, 0.85, 0.7, 0.55, 0.4):
        candidate = img if scale == 1.0 else img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        for quality in (92, 85, 75, 65, 55, 45):
            buf = io.BytesIO()
            candidate.save(buf, "JPEG", quality=quality, optimize=True)
            if buf.tell() <= max_kb * 1024:
                dest.write_bytes(buf.getvalue())
                return
    raise DocumentError(f"cannot compress image below {max_kb} KB")


def prepare_upload(source: Path, req: DocumentRequirement, workdir: Path) -> Path:
    """Return a file that satisfies `req`, converting/recompressing into `workdir` if needed."""
    source = Path(source)
    if not source.exists():
        raise DocumentError(f"{req.label}: file not found: {source}")
    workdir.mkdir(parents=True, exist_ok=True)
    ext = source.suffix.lower().lstrip(".")
    ext = req.extension_aliases.get(ext, ext)
    size_ok = source.stat().st_size <= req.max_kb * 1024

    if ext == "pdf":
        if "pdf" not in req.formats:
            raise DocumentError(f"{req.label}: PDF not accepted (accepts {', '.join(req.formats)})")
        if not size_ok:
            raise DocumentError(f"{req.label}: PDF is larger than {req.max_kb} KB")
        dest = workdir / f"{req.kind}.pdf"
        shutil.copyfile(source, dest)
        return dest

    image_formats = [f for f in req.formats if f in ("jpeg", "png")]
    if not image_formats:
        # Portal wants a PDF but we were given an image: wrap it.
        dest = workdir / f"{req.kind}.pdf"
        with Image.open(source) as img:
            img.convert("RGB").save(dest, "PDF", resolution=150)
        if dest.stat().st_size > req.max_kb * 1024:
            raise DocumentError(f"{req.label}: converted PDF is larger than {req.max_kb} KB")
        return dest

    with Image.open(source) as img:
        img.load()
        needs_resize = req.pixel_size is not None and img.size != req.pixel_size
        if ext in image_formats and size_ok and not needs_resize:
            # Still copy so the uploaded filename carries the accepted extension
            # (some portals reject ".jpg" but accept ".jpeg").
            dest = workdir / f"{req.kind}.{ext}"
            shutil.copyfile(source, dest)
            return dest
        if needs_resize:
            img = img.convert("RGB").resize(req.pixel_size, Image.LANCZOS)  # type: ignore[arg-type]
        if "jpeg" in image_formats:
            dest = workdir / f"{req.kind}.jpeg"
            _save_jpeg_within(img, dest, req.max_kb)
        else:
            dest = workdir / f"{req.kind}.png"
            img.save(dest, "PNG", optimize=True)
            if dest.stat().st_size > req.max_kb * 1024:
                raise DocumentError(f"{req.label}: PNG is larger than {req.max_kb} KB")
        return dest


# ------------------------------------------------------------------ specimens


def _rng_bytes(seed: str) -> bytes:
    return hashlib.sha256(seed.encode()).digest()


_SKIN = [(241, 194, 167), (224, 172, 105), (198, 134, 66), (141, 85, 36), (255, 219, 172), (171, 115, 76)]
_HAIR = [(40, 30, 25), (90, 60, 30), (160, 120, 60), (20, 20, 20), (120, 80, 50), (200, 170, 110)]
_CLOTHES = [(40, 60, 110), (90, 30, 40), (30, 90, 70), (60, 60, 60), (120, 90, 40)]


def draw_portrait(seed: str, size: tuple[int, int], *, female: bool) -> Image.Image:
    """A synthetic, obviously-drawn face: stands in for a real photo."""
    w, h = size
    r = _rng_bytes(seed)
    img = Image.new("RGB", size, (236, 240, 244))
    d = ImageDraw.Draw(img)
    skin, hair, clothes = _SKIN[r[0] % len(_SKIN)], _HAIR[r[1] % len(_HAIR)], _CLOTHES[r[2] % len(_CLOTHES)]
    cx = w // 2
    # shoulders & neck
    d.ellipse([cx - w * 0.48, h * 0.78, cx + w * 0.48, h * 1.35], fill=clothes)
    d.rectangle([cx - w * 0.08, h * 0.62, cx + w * 0.08, h * 0.82], fill=skin)
    # hair behind head
    hair_len = 0.78 if female else 0.5
    d.ellipse([cx - w * 0.27, h * 0.14, cx + w * 0.27, h * hair_len], fill=hair)
    # head
    d.ellipse([cx - w * 0.22, h * 0.2, cx + w * 0.22, h * 0.7], fill=skin)
    # fringe
    d.chord([cx - w * 0.23, h * 0.16, cx + w * 0.23, h * 0.42], 180, 360, fill=hair)
    # eyes, brows, nose, mouth
    ey = h * 0.43
    for dx in (-0.09, 0.09):
        ex = cx + w * dx
        d.ellipse([ex - w * 0.03, ey - h * 0.012, ex + w * 0.03, ey + h * 0.012], fill=(255, 255, 255))
        d.ellipse([ex - w * 0.014, ey - h * 0.011, ex + w * 0.014, ey + h * 0.011], fill=(60, 40, 30))
        d.line([ex - w * 0.04, ey - h * 0.035, ex + w * 0.04, ey - h * 0.04], fill=hair, width=max(2, w // 80))
    d.line([cx, h * 0.46, cx - w * 0.02, h * 0.54, cx + w * 0.01, h * 0.545], fill=tuple(int(c * 0.8) for c in skin), width=max(2, w // 120))
    d.arc([cx - w * 0.07, h * 0.55, cx + w * 0.07, h * 0.62], 20, 160, fill=(150, 70, 70), width=max(2, w // 90))
    return img


def _watermark(img: Image.Image, text: str) -> Image.Image:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    font = _font(max(24, img.width // 9), bold=True)
    tmp = Image.new("RGBA", (img.width, img.height // 3), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((tmp.width // 2, tmp.height // 2), text, font=font, fill=(200, 0, 0, 90), anchor="mm")
    tmp = tmp.rotate(20, expand=True)
    overlay.paste(tmp, ((img.width - tmp.width) // 2, (img.height - tmp.height) // 2), tmp)
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _fmt(d: date) -> str:
    return d.strftime("%d %b %Y").upper()


def render_passport_bio_page(applicant: Applicant) -> Image.Image:
    p = applicant.passport
    W, H = 1250, 880
    img = Image.new("RGB", (W, H), (226, 238, 234))
    d = ImageDraw.Draw(img)
    # Guilloche-ish background lines
    for i in range(0, W + H, 18):
        d.line([(i, 0), (i - H, H)], fill=(214, 230, 225), width=2)
    d.rectangle([0, 0, W, 95], fill=(30, 70, 90))
    state = countries.country_name(p.issuing_country).upper()
    d.text((40, 22), "PASSPORT  /  PASSEPORT", font=_font(34, bold=True), fill="white")
    d.text((W - 40, 28), state, font=_font(30, bold=True), fill="white", anchor="ra")

    portrait = draw_portrait(p.number, (300, 385), female=p.sex.value == "F")
    img.paste(portrait, (45, 130))
    d.rectangle([45, 130, 345, 515], outline=(30, 70, 90), width=3)

    label_font = _font(17)

    def field(x: int, y: int, label: str, value: str) -> None:
        d.text((x, y), label, font=label_font, fill=(70, 90, 100))
        size = 27
        while size > 14 and d.textlength(value, font=_font(size, bold=True)) > W - 30 - x:
            size -= 1
        d.text((x, y + 20), value, font=_font(size, bold=True), fill=(15, 20, 25))

    col1, col2, col3 = 390, 700, 960
    field(col1, 120, "Type / Type", p.document_type)
    field(col2, 120, "Code / Code", p.issuing_country)
    field(col3, 120, "Passport No. / N° du passeport", p.number)
    field(col1, 190, "Surname / Nom", p.surname.upper())
    field(col1, 260, "Given names / Prénoms", p.given_names.upper())
    field(col1, 330, "Nationality / Nationalité", countries.country_name(p.nationality).upper())
    field(col1, 400, "Date of birth / Date de naissance", _fmt(p.date_of_birth))
    field(col2 + 120, 400, "Sex / Sexe", p.sex.value)
    field(col1, 470, "Place of birth / Lieu de naissance", p.place_of_birth.upper())
    field(col1, 540, "Date of issue / Date de délivrance", _fmt(p.date_of_issue))
    field(col2 + 120, 540, "Authority / Autorité", p.issuing_authority.upper())
    field(col1, 610, "Date of expiry / Date d'expiration", _fmt(p.date_of_expiry))
    if p.personal_number:
        field(col2 + 120, 610, "Personal No. / N° personnel", p.personal_number)

    d.rectangle([0, 700, W, H], fill=(250, 252, 251))
    mrz_font = _font(40, mono=True)
    for i, line in enumerate(p.mrz().lines):
        d.text((W // 2, 745 + i * 58), line, font=mrz_font, fill=(10, 10, 10), anchor="mm")

    img = _watermark(img, "SPECIMEN")
    ImageDraw.Draw(img).text((W // 2, 680), "MOCK DATA - NOT A VALID TRAVEL DOCUMENT", font=_font(20, bold=True), fill=(180, 0, 0), anchor="mm")
    return img


def render_passport_photo(applicant: Applicant, size: tuple[int, int] = (413, 531)) -> Image.Image:
    """35x45 mm @ 300 dpi, plain background, head centred."""
    img = draw_portrait(applicant.passport.number, size, female=applicant.passport.sex.value == "F")
    ImageDraw.Draw(img).text((size[0] - 6, size[1] - 6), "SPECIMEN", font=_font(max(12, size[0] // 22), bold=True), fill=(180, 0, 0), anchor="rd")
    return img


def _document_page(title: str, lines: list[tuple[str, str]], footer: str) -> Image.Image:
    W, H = 1240, 1754  # A4 @ 150 dpi
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 150], fill=(25, 55, 95))
    d.text((70, 75), title, font=_font(52, bold=True), fill="white", anchor="lm")
    y = 220
    for label, value in lines:
        if not label:
            y += 30
            continue
        d.text((80, y), label, font=_font(26), fill=(90, 90, 90))
        d.text((460, y), value, font=_font(28, bold=True), fill=(20, 20, 20))
        y += 58
    d.text((W // 2, H - 90), footer, font=_font(24, bold=True), fill=(180, 0, 0), anchor="mm")
    return _watermark(img, "SPECIMEN")


def _booking_ref(seed: str) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(alphabet[b % len(alphabet)] for b in _rng_bytes(seed)[:6])


def render_return_ticket(applicant: Applicant, trip: Trip) -> Image.Image:
    carrier = trip.carrier or "Specimen Airways"
    inbound = trip.arrival_flight or "SP 101"
    outbound = f"{inbound.split()[0]} {int(''.join(ch for ch in inbound if ch.isdigit()) or 101) + 1}" if inbound else "SP 102"
    lines = [
        ("Passenger", f"{applicant.passport.surname.upper()}/{applicant.passport.given_names.upper()}"),
        ("Booking reference", _booking_ref(applicant.passport.number + "ticket")),
        ("E-ticket number", "999-" + str(int.from_bytes(_rng_bytes(applicant.passport.number)[:5], "big"))[:10]),
        ("Carrier", carrier),
        ("", ""),
        ("Outbound flight", inbound),
        ("From", f"{trip.departure_city or countries.country_name(trip.departure_country)}"),
        ("To", trip.port_of_entry),
        ("Date", _fmt(trip.arrival_date)),
        ("", ""),
        ("Return flight", outbound),
        ("From", trip.port_of_exit or trip.port_of_entry),
        ("To", f"{trip.departure_city or countries.country_name(trip.departure_country)}"),
        ("Date", _fmt(trip.departure_date)),
    ]
    return _document_page("E-TICKET ITINERARY RECEIPT", lines, "MOCK DATA - NOT A VALID TICKET")


def render_accommodation_proof(applicant: Applicant, trip: Trip) -> Image.Image:
    acc = trip.accommodation
    lines = [
        ("Guest", applicant.full_name),
        ("Confirmation no.", _booking_ref(applicant.passport.number + "hotel")),
        ("Property", acc.name),
        ("Address", acc.address),
        ("City", acc.city),
        ("Phone", acc.phone or "-"),
        ("", ""),
        ("Check-in", _fmt(trip.arrival_date)),
        ("Check-out", _fmt(trip.departure_date)),
        ("Nights", str(max(1, trip.duration_days - 1))),
        ("Status", "CONFIRMED"),
    ]
    return _document_page("ACCOMMODATION CONFIRMATION", lines, "MOCK DATA - NOT A VALID BOOKING")


def render_invitation_letter(applicant: Applicant, trip: Trip) -> Image.Image:
    host = trip.host
    lines = [
        ("To", "The Immigration Authority"),
        ("Re", f"Invitation for {applicant.full_name}"),
        ("Passport no.", applicant.passport.number),
        ("Host", host.name if host else "-"),
        ("Host address", host.address if host else "-"),
        ("Host phone", host.phone if host else "-"),
        ("Relationship", host.relationship if host else "-"),
        ("Visit dates", f"{_fmt(trip.arrival_date)} - {_fmt(trip.departure_date)}"),
        ("Purpose", trip.purpose.label),
    ]
    return _document_page("LETTER OF INVITATION", lines, "MOCK DATA - NOT A VALID LETTER")


def generate_mock_documents(applicant: Applicant, trip: Trip, out_dir: Path, *, overwrite: bool = False) -> Documents:
    """Render specimen documents for every slot the applicant has not supplied."""
    if not applicant.mock:
        raise DocumentError(f"refusing to fabricate documents for non-mock applicant {applicant.ref!r}")
    out_dir = Path(out_dir) / applicant.ref
    out_dir.mkdir(parents=True, exist_ok=True)
    docs = applicant.documents.model_copy(deep=True)

    def ensure(attr: str, filename: str, render, fmt: str) -> None:
        if getattr(docs, attr) is not None and not overwrite:
            return
        dest = out_dir / filename
        img = render()
        if fmt == "PDF":
            img.save(dest, "PDF", resolution=150)
        else:
            _save_jpeg_within(img, dest, 280)
        setattr(docs, attr, dest)

    ensure("passport_scan", "passport_bio_page.jpeg", lambda: render_passport_bio_page(applicant), "JPEG")
    ensure("photo", "photo.jpeg", lambda: render_passport_photo(applicant), "JPEG")
    ensure("return_ticket", "return_ticket.pdf", lambda: render_return_ticket(applicant, trip), "PDF")
    ensure("accommodation_proof", "accommodation.pdf", lambda: render_accommodation_proof(applicant, trip), "PDF")
    if trip.host is not None:
        ensure("invitation_letter", "invitation_letter.pdf", lambda: render_invitation_letter(applicant, trip), "PDF")
    return docs
