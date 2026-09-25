# Sri Lanka ETA (e-visa) automation

Python + Playwright automation that fills the Sri Lanka ETA application
(<https://eta.gov.lk/slvisa/visainfo/center.jsp?locale=fr_FR>) for **one or more
travellers**. It then either **returns the payment link**, or **asks for card
details and pays on the external payment gateway**.

```
center.jsp ─► apply (visa type, individual/group, terms) ─► trip & contact
          ─► traveller 1 ─► "add member" ─► traveller 2 … ─► review ─► submit
          ─► confirmation (reference) ─► "Pay now" ─► gateway  ⇒ payment link
                                                          └─► card form ⇒ paid / declined
```

## Quick start

```bash
pip install -r requirements.txt
playwright install chromium          # skip if Chromium is already provided

# 1. SPECIMEN passports + photos + applicants.yaml (3 fictitious travellers)
python -m srilanka_evisa mock-data --out mock_data

# 2. Local copy of the portal and a fake payment gateway
python -m mock_site.server --port 8765 &

# 3a. Group application -> prints the reference and the payment link
python -m srilanka_evisa apply mock_data/applicants.yaml \
    --base-url http://127.0.0.1:8765 --submit

# 3b. One application per traveller, then pay each one with a card you type in
python -m srilanka_evisa apply mock_data/applicants.yaml \
    --base-url http://127.0.0.1:8765 --mode individual --pay
#   mock test cards: 4111 1111 1111 1111 = approved, 4000 0000 0000 0002 = declined
```

Output (screenshots of each review / confirmation / payment page and a
`results.json` with statuses, references and payment links) goes to `evisa_output/`.

## Several travellers

`applicants.yaml` holds one `trip`, one `contact` and a list of `beneficiaries`:

* `mode: group` – a single group application containing everyone (one payment link);
* `mode: individual` – one application per traveller (one payment link each; with
  `--pay` the card is asked **once** and reused for every application).

A traveller can be described field by field, or by the passport's **MRZ** (the two
`P<…` lines at the bottom of the bio page) – name, sex, date of birth, nationality,
passport number and expiry are then taken from it and checksum-verified. With
`read_mrz_from_image: true` the MRZ is OCR'd from `passport_image` (needs
`pytesseract` + tesseract). `passport_image` and `photo` are uploaded when the form
asks for them.

```yaml
beneficiaries:
  - mrz: |
      P<FRADUPONT<<JEAN<PIERRE<<<<<<<<<<<<<<<<<<<<
      24FR812342FRA8403146M3401310<<<<<<<<<<<<<<06
    title: Mr
    passport_issue_date: 2024-02-01
    occupation: Engineer
    passport_image: passports/dupont_jean.png
    photo: photos/dupont_jean.jpg
```

The file is validated before a browser starts (email, arrival date, max 30 days,
passport valid 6 months after arrival, files exist…).

## Payment

* `--submit` – submit and stop on the gateway: the printed **payment link** can be
  opened in any browser to pay (gateway sessions are short-lived, pay soon).
* `--pay` – additionally prompts for cardholder, number, expiry and CVV (number and
  CVV are not echoed), shows the masked card and asks for confirmation, then fills
  the gateway form – including card fields rendered inside iframes. Card data stays
  in memory only: it is never logged, written to `results.json`, or screenshotted.
  If the bank asks for 3-D Secure, run with `--headful` and complete it in the window.

## Using it on the real portal

* **Without `--submit` nothing is sent**: the run stops on the review page and
  leaves a screenshot, so you can check what would be submitted.
* Only submit real, accurate traveller data. The mock passports are SPECIMENs
  for the mock site; submitting them to the government portal is not allowed.
  Submitting to eta.gov.lk asks for an explicit confirmation.
* The portal may show a CAPTCHA; the automation never tries to solve it – run
  with `--headful` and it pauses so you can solve it yourself.
* Every selector lives in [`srilanka_evisa/profiles/eta_gov_lk.yaml`](srilanka_evisa/profiles/eta_gov_lk.yaml).
  Elements are found by CSS selector, then by their **label text in English or
  French**, so small markup changes are absorbed. If a step fails, the run saves
  a screenshot and the page HTML (`*-error.html`); adjust the profile (or pass your
  own with `--profile`) – no code change needed.

> The live portal could not be reached from the environment this was built in,
> so the bundled profile follows the portal's documented flow and field names
> but has **not been verified against the live site**. Expect to tune a few
> selectors on the first `--headful` dry run.

## Layout

| Path | Purpose |
|---|---|
| `srilanka_evisa/models.py` | Application / trip / traveller data, YAML loading, validation |
| `srilanka_evisa/mrz.py` | ICAO 9303 TD3 MRZ builder + parser with check digits |
| `srilanka_evisa/forms.py` | Profile-driven element lookup & form filling (selects, radios, dates, uploads, iframes) |
| `srilanka_evisa/automation.py` | The browser flow, payment link capture, screenshots, results |
| `srilanka_evisa/payment.py` | Card prompt/validation (Luhn, expiry), gateway filling |
| `srilanka_evisa/mock_data.py` | SPECIMEN passport scans, photos and applicants file |
| `mock_site/server.py` | Mock ETA portal + payment gateway for tests / demos |
| `tests/` | Unit tests and end-to-end tests against the mock site |

Run the tests with `python -m pytest`.
