# e-visa automation: Tanzania and Sri Lanka

Python + Playwright automation that fills an e-visa application for **one or more
beneficiaries**. At the payment step it either **returns a payment link**, or **asks
for card details and pays on the portal's external checkout**. The generic logic
(data model, form filling, CAPTCHA and 3-D Secure hand-off, card checkout, runner,
reports, specimen documents, mock portals) lives in one shared core. Each country
is a small profile on top of it.

| Country | Portal | Applications | Profile |
|---|---|---|---|
| Tanzania | https://visa.immigration.go.tz | one per passport holder (the portal's rule, minors included) | `evisa/sites/tanzania/` |
| Sri Lanka | https://eta.gov.lk | one **group** application, or one each | `evisa/sites/srilanka/` |

## Quick start

```bash
pip install -e .[dev]               # or: pip install -r requirements.txt
playwright install chromium         # skip if Chromium is already provided

# Full flow against a local mock portal; nothing leaves your machine:
python -m evisa demo --country tanzania                      # 4 mock beneficiaries -> payment links
python -m evisa demo --country srilanka                      # 1 group application -> payment link
python -m evisa demo --country srilanka --mode individual --payment card --test-card 3ds
python -m evisa demo --country tanzania --payment card       # prompts for a card; use a test card below
```

Mock test cards (any future expiry, any CVV): `4111 1111 1111 1111` approved,
`4000 0000 0000 3220` 3-D Secure (code `123456`), `4000 0000 0000 0002` declined.

Each run writes `runs/<country>-<timestamp>/` containing:
- `report.json`: statuses, Application IDs, payment links and resume details.
- `summary.md`
- one screenshot per step.

## Batch file: one trip, many beneficiaries

JSON or YAML; see [`examples/tanzania_family.json`](examples/tanzania_family.json)
and [`examples/srilanka_family.yaml`](examples/srilanka_family.yaml).

```yaml
country: tanzania            # or srilanka
mode: individual             # or group (Sri Lanka only); default: the portal's preference
trip: {arrival_date: 2027-02-10, departure_date: 2027-02-24, port_of_entry: Kilimanjaro International Airport,
       departure_country: ISR, accommodation: {name: ..., address: ..., city: Arusha}}
contact: {email: ..., phone: "+972...", address: {...}}   # shared; applicants may override
applicants:
  - mock: true               # SPECIMEN person: documents are generated, never sent to a real portal
    passport:
      mrz: |                 # or give surname / given_names / number / dates ... field by field
        P<FRADUPONT<<JEAN<PIERRE<<<<<<<<<<<<<<<<<<<<
        24FR812342FRA8403146M3401310<<<<<<<<<<<<<<06
      date_of_issue: 2024-02-01
    occupation: Engineer
    documents: {photo: photos/jean.jpeg, passport_scan: scans/jean.jpeg}   # real applicants
```

- **Passport data:** give it field by field, or as the two MRZ lines (check digits are
  verified). With `read_mrz_from_image: true` the MRZ is OCR'd from
  `documents.passport_scan`; this needs `pip install .[ocr]` and tesseract.
- **Uploads:** converted and recompressed to what the portal accepts. For example,
  `.jpg` is renamed to `.jpeg`, and photos are kept under 500 KB for Tanzania.
- **Site-specific answers** go under `extra.<country>`:
  - Tanzania: `security_question`, `security_answer`, `visa_type`.
  - Sri Lanka: `questions: {QN1: no, ...}`.

`python -m evisa mock-docs examples/tanzania_family.json` renders the SPECIMEN
passport bio page (with a valid MRZ), photo, e-ticket and hotel voucher on its own.

## Payment

- `--payment link` (default): stops on the payment page. For every application it
  returns:
  - the **checkout link** (a live gateway session, short-lived);
  - the **portal link**, plus what is needed to sign back in. For Tanzania that is the
    Application ID, email and security question and answer, entered at
    `/continueapplication?ReturnUrl=/payment`.
- `--payment card`:
  - Asks for the card **once** for the whole batch; number and CVV are not echoed.
  - Shows every charge and asks you to type `pay`.
  - Asks again if the portal's amount differs from the expected fee, or if the fee
    was unknown up front.
  - Fills the checkout, including card fields inside iframes. A 3-D Secure challenge
    is left to you in the browser (`--headed`).
  - Card data stays in memory only. It is never logged, never written to reports,
    and never screenshotted.
  - Each application ends up `paid`, `payment_declined`, or `payment_unconfirmed`.
    Unconfirmed means no verdict was seen; check with your bank before paying again.

## Using the real portals

```bash
python -m evisa apply my_family.yaml --live --headed                   # payment links
python -m evisa apply my_family.yaml --live --headed --payment card    # pay now
python -m evisa apply my_family.yaml --live --headed --stop-after review   # Sri Lanka dry run
```

- **Safety rules:**
  - Runs against a real portal need `--live`.
  - Batches containing `mock: true` applicants are **always refused** there.
  - Only submit genuine, accurate traveller data.
- **CAPTCHA:** both portals use Google reCAPTCHA. The automation never tries to solve
  it. It waits, with the browser in `--headed` mode, until you tick it, then continues.
- **Calibrating locators:**
  - Each field lists several candidate locators, and `-v` logs which one matched.
  - If a portal changes, `python -m evisa inspect <url> --headed` lists a page's
    fields (read-only).
  - `--selectors overrides.json` (`{"surname": ["#LastName"]}`) fixes a field
    without code changes.

### What has been checked against the live portals (September 2026)

| | Tanzania | Sri Lanka |
|---|---|---|
| Entry form | `/start` and `/continueapplication`: field names, labels, security questions, country spellings, reCAPTCHA, all resolved by the profile against the real HTML | terms page, visa-type/mode selection, the full **individual** form and **group** travel/contact page: all fields resolved against the real HTML (mm-dd-yyyy dates, re-entry fields, yes/no questions, alert() validation, hidden 90-day option) |
| Later pages | Personal / Travel / Attachments / Declaration / Payment tabs follow the official guidelines and applicant walkthroughs; **not observed** (needs a real application) | group member pages, review, payment options, gateway: **not observed** |
| Fees | from the portal's guidelines (Ordinary $50, Multiple Entry $100 (US citizens), Business $250, Transit $30) | read from the portal at payment time |

Expect to tune a few locators for the unobserved pages on your first real `--headed`
run.

## Layout

| Path | Purpose |
|---|---|
| `evisa/core/models.py` | Batch / trip / applicant / passport (with MRZ input), results; JSON + YAML loading |
| `evisa/core/fields.py` | Declarative form filling: candidate locators, fuzzy dropdown and radio matching, alert capture |
| `evisa/core/checkout.py`, `payment.py` | Card details, confirmation, generic checkout filler (iframes, 3-D Secure), payment links |
| `evisa/core/runner.py`, `site.py` | Batch runner (isolated browser context per application, safety gates, reports), `VisaSite` contract |
| `evisa/core/documents.py`, `mrz.py` | SPECIMEN documents, upload preparation, ICAO 9303 MRZ |
| `evisa/sites/<country>/` | Country profiles: steps, field maps, fees, reference data |
| `evisa/mock/` | Local mock portals for both countries + a shared mock card gateway |
| `tests/` | Unit tests and end-to-end runs against the mock portals (`python -m pytest`) |

**Adding a country:**
1. Subclass `VisaSite` in `evisa/sites/<country>/`: its steps, its field maps
   (`Field(key, kind, locators, value)`), `payment_link` and `pay_by_card`. The last
   two usually just call `evisa.core.checkout`.
2. Register it in `evisa/sites/__init__.py`.
3. Optionally add a mock portal to `evisa/mock/`.
