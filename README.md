# Sri Lanka ETA (e-visa) automation

Python + Playwright automation that fills the Sri Lanka ETA application on
<https://eta.gov.lk> for **one or more travellers**, then either **returns the
payment link** or **asks for card details and pays on the payment gateway**.

```
termnconuser.jsp ─► terms "I Agree" ─► category (Tourist · Individual / Group)
   individual: one long form (applicant, travel, address, contact, 3 questions)
   group:      travel & contact form ─► member form ("Add Member" × N, same page) ─► Next
─► review "Confirm" (two confirm() dialogs) ─► reference + payment options
─► gateway  ⇒ payment link            └─► card form ⇒ paid / declined
```

## Quick start

```bash
pip install -r requirements.txt
playwright install chromium          # skip if Chromium is already provided

# 1. SPECIMEN passports + photos + applicants.yaml (3 fictitious travellers)
python -m srilanka_evisa mock-data --out mock_data

# 2. Local stand-in for the portal and a fake payment gateway (see below)
python -m mock_site.server --port 8765 &

# 3a. Group application -> prints the reference and the payment link
python -m srilanka_evisa apply mock_data/applicants.yaml \
    --base-url http://127.0.0.1:8765 --submit

# 3b. One application per traveller, then pay each one with a card you type in
python -m srilanka_evisa apply mock_data/applicants.yaml \
    --base-url http://127.0.0.1:8765 --mode individual --pay
#   mock test cards: 4111 1111 1111 1111 = approved, 4000 0000 0000 0002 = declined
```

Output (screenshots of the form / review / confirmation / payment pages and a
`results.json` with statuses, references, payment links and every message the
portal showed) goes to `evisa_output/`.

## Several travellers

`applicants.yaml` holds one `trip`, one `contact` (the home address the portal
asks for), the `declarations` (the three yes/no questions) and a list of
`beneficiaries`:

* `mode: group` – one group application containing everyone (one payment link);
* `mode: individual` – one application per traveller (one payment link each; with
  `--pay` the card is asked **once** and reused for every application).

A traveller can be described field by field, or by the passport's **MRZ** (the two
`P<…` lines at the bottom of the bio page): name, sex, date of birth, nationality,
passport number and expiry are then read from it and checksum-verified. With
`read_mrz_from_image: true` the MRZ is OCR'd from `passport_image` (needs
`pytesseract` + tesseract).

```yaml
beneficiaries:
  - mrz: |-
      P<FRADUPONT<<JEAN<PIERRE<<<<<<<<<<<<<<<<<<<<
      24FR812342FRA8403146M3401310<<<<<<<<<<<<<<06
    title: MR
    passport_issue_date: 2024-02-01
    occupation: Engineer
    country_of_address: FRA   # where they live; defaults to contact.country
    children:                 # children under 16 on this passport (no passport of their own)
      - given_names: Emma
        date_of_birth: 2021-04-18
        sex: F
        # surname: ...        # defaults to the parent's surname
```

A child with their own passport is a traveller (a `beneficiaries` entry) instead;
children on a parent's passport are added in the parent's "Child information"
section, in both group and individual applications.

The file is validated before a browser starts (email, arrival date, 30/90 visa
days, passport valid 6 months after arrival, children under 16, …). Countries are ISO-3 codes.

## Payment

* `--submit` – submit and stop on the gateway: the printed **payment link** can be
  opened in a browser to pay (gateway sessions are short-lived, pay soon).
* `--pay` – additionally prompts for cardholder, number, expiry and CVV (number and
  CVV are not echoed), shows the masked card and asks for confirmation, then fills
  the gateway form, including card fields inside iframes. Card data stays in
  memory only: never logged, written to `results.json`, or screenshotted.
  If the bank asks for 3-D Secure, run with `--headful` and complete it in the window.

## How it deals with the real portal

Mapped from the live site on 2026-09-25 (snapshots in `mock_site/portal_snapshot/`):

* **Anti-paste inputs** – the portal reverts any input that grows by more than one
  character at once, so values are typed key by key, then blurred so the portal's
  `onchange` checks run.
* **Read-only date pickers** – dates are `mm-dd-yyyy` and set the way the calendar
  widget sets them.
* **Group member page** – one form reused for every member: "Add Member" checks the
  member in the browser, lists them on the same page and clears the form; the "Next"
  button it then shows posts the whole group. It also asks for each member's
  *Country of Address*.
* **Children on a parent's passport** – same idea one level down: tick *Enable*, fill
  the child, "Add Child" (individual) / "Include" (group member, before "Add Member"),
  once per child.
* **Server-side passport check** – after the passport number is typed the portal
  asks its server whether it is acceptable; the run waits for that before moving on
  and reports the portal's message if it refuses.
* **alert() / confirm()** – validation errors arrive as alerts: they stop the run
  with the portal's own message. The review page's two `confirm()` dialogs ("Are you
  sure…", fraud declaration) are accepted – only when you asked to `--submit`.
* **Sessions** – the portal expires sessions quickly and redirects to `http://`
  mid-flow; the run keeps the session on `https://` and reports "Session Expired".
* **CAPTCHA** – reCAPTCHA is loaded but currently not enforced. If it becomes
  enforced the run stops (headless) or pauses for you to solve it (`--headful`).

### What is verified, and what is not

| Part | Status |
|---|---|
| Terms, category, **individual form**, **group travel & contact form**, **group member form**, **children on a parent's passport**, **review pages** (group and individual) | Driven on the live portal in dry runs (2026-09-25/26), and filled on the saved real pages **with the portal's own JavaScript**; its validation accepts the result (`tests/test_real_markup.py`) |
| Payment options, gateway | **Not verified** – these pages only appear after confirming a real application. Built from text matching; check them on the first `--submit` run |

All selectors live in [`srilanka_evisa/profiles/eta_gov_lk.yaml`](srilanka_evisa/profiles/eta_gov_lk.yaml);
if a step fails, the run saves a screenshot and the page HTML (`*-blocked.html` /
`*-error.html`) – adjust the profile (or pass your own with `--profile`).

## Using it on the real portal

* **Without `--submit` nothing is confirmed**: the run stops on the review page and
  leaves screenshots of what would be submitted. The portal does receive the form
  data on the way there (passport checks, the form pages' "Next"), as an unconfirmed
  draft, so a dry run with the mock data can be used to map the live pages.
* `--save-pages` also keeps the raw HTML of every portal page reached
  (`evisa_output/*-page-*.html`) – the way new pages get mapped. They can hold
  personal data: strip it and any session ids before committing a snapshot.
* `--submit` / `--pay` confirm the application: only with real, accurate traveller
  data. Submitting to eta.gov.lk asks for an explicit confirmation.

## The mock site

`mock_site/server.py` serves the **saved real pages and the portal's own JavaScript**
for the verified steps (its server-side AJAX checks are stubbed to "OK"; passport
`REJECT123` is refused; the review pages always show the saved mock travellers) and
realistic stand-ins for the payment options, plus a fake payment gateway with the card
form inside an iframe.

## Layout

| Path | Purpose |
|---|---|
| `srilanka_evisa/models.py` | Application / trip / contact / traveller data, YAML loading, validation |
| `srilanka_evisa/mrz.py` | ICAO 9303 TD3 MRZ builder + parser with check digits |
| `srilanka_evisa/forms.py` | Profile-driven element lookup & form filling (typing, pickers, split dates, iframes) |
| `srilanka_evisa/automation.py` | The browser flow, dialogs, payment link capture, screenshots, results |
| `srilanka_evisa/payment.py` | Card prompt/validation (Luhn, expiry), gateway filling |
| `srilanka_evisa/mock_data.py` | SPECIMEN passport scans, photos and applicants file |
| `mock_site/` | Mock portal (real page snapshots + stand-ins) and payment gateway |
| `tests/` | Unit tests, real-markup tests, end-to-end tests against the mock site |

Run the tests with `python -m pytest`.
