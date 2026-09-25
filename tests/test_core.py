from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from PIL import Image
from pydantic import ValidationError

from evisa.core import countries
from evisa.core.documents import DocumentRequirement, generate_mock_documents, prepare_upload
from evisa.core.fields import Choice, choose_option
from evisa.core.models import Passport, load_batch
from evisa.core.mrz import MRZError, build_td3, check_digit, find_td3, parse_td3
from evisa.core.payment import CardDetails, find_amount, luhn_ok, prompt_card
from evisa.core.runner import RunOptions, SafetyError, check_safety
from evisa.sites import get_site

from .conftest import EXAMPLES, card

# ------------------------------------------------------------------- MRZ


def test_icao_check_digits():
    assert check_digit("L898902C3") == "6"
    assert check_digit("740812") == "2"


def test_icao_specimen_td3():
    td3 = build_td3(document_type="P", issuing_country="UTO", surname="Eriksson", given_names="Anna Maria", number="L898902C3",
                    nationality="UTO", date_of_birth=date(1974, 8, 12), sex="F", date_of_expiry=date(2012, 4, 15),
                    personal_number="ZE184226B")
    assert td3.line1 == "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    assert td3.line2 == "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
    parsed = parse_td3(*td3.lines, strict=True)
    assert (parsed.surname, parsed.given_names, parsed.date_of_birth) == ("ERIKSSON", "ANNA MARIA", date(1974, 8, 12))


def test_tampered_mrz_is_rejected():
    td3 = build_td3(document_type="P", issuing_country="FRA", surname="Dupont", given_names="Jean", number="24FR81234",
                    nationality="FRA", date_of_birth=date(1984, 3, 14), sex="M", date_of_expiry=date(2034, 1, 31))
    tampered = td3.line2[:3] + ("9" if td3.line2[3] != "9" else "8") + td3.line2[4:]
    assert not parse_td3(td3.line1, tampered).checks_ok
    with pytest.raises(MRZError):
        parse_td3(td3.line1, tampered, strict=True)


def test_passport_from_mrz_explicit_fields_win():
    mrz = "noise\nP<FRADUPONT<<JEAN<PIERRE<<<<<<<<<<<<<<<<<<<<\n24FR812342FRA8403146M3401310<<<<<<<<<<<<<<06\n"
    assert find_td3(mrz)
    p = Passport.model_validate({"mrz": mrz, "date_of_issue": "2024-02-01", "given_names": "Jean-Pierre"})
    assert (p.surname, p.given_names, p.number, p.nationality, p.country_of_birth) == ("Dupont", "Jean-Pierre", "24FR81234", "FRA", "FRA")
    assert p.date_of_birth == date(1984, 3, 14) and p.date_of_expiry == date(2034, 1, 31)
    assert p.mrz().line2[:9] == "24FR81234"


# ------------------------------------------------------------- matching


@pytest.mark.parametrize("code, languages, options, expected", [
    ("TZA", ("en",), ["KENYA", "TANZANIA, UNITED REPUBLIC OF", "TOGO"], 1),
    ("USA", ("en",), ["UNITED STATES MINOR OUTLYING ISLANDS", "UNITED STATES OF AMERICA"], 1),
    ("USA", ("en",), ["UKRAINE", "UNITED STATES (USA)"], 1),
    ("DEU", ("en",), ["DENMARK (DNK)", "GERMANY (Deutschland) (D)"], 1),
    ("DEU", ("fr", "en"), ["Allemagne", "Autriche"], 0),
    ("ISR", ("fr", "en"), ["Inde", "Israël"], 1),
])
def test_country_option_matching(code, languages, options, expected):
    assert countries.best_option_match(countries.country_aliases(code, languages), options) == expected


def test_choice_prefers_fuzzy_primary_over_exact_fallback():
    options = [{"value": v, "label": v} for v in ("Accountant", "Engineer", "Other")]
    assert choose_option(options, Choice(["Software Engineer"], ["Other"]))["value"] == "Engineer"
    assert choose_option(options, Choice(["Astronaut"], ["Other"]))["value"] == "Other"


@pytest.mark.parametrize("text, amount, currency", [
    ("Amount: USD 50.00", "50.00", "USD"), ("Montant à payer : 150 USD", "150", "USD"),
    ("Payer 150,00 USD", "150.00", "USD"), ("Total $1,250.50 due", "1250.50", "USD"),
])
def test_find_amount(text, amount, currency):
    money = find_amount(text)
    assert money.amount == Decimal(amount) and money.currency == currency


# ----------------------------------------------------------------- cards


def test_card_validation_and_masking():
    assert luhn_ok("4111111111111111") and not luhn_ok("4111111111111112")
    c = card("4111 1111 1111 1111")
    assert "4111111111111111" not in repr(c) and "123" not in repr(c) and c.masked == "Visa **** 1111"
    with pytest.raises(ValidationError):
        CardDetails(holder_name="X", number="4111111111111112", exp_month=1, exp_year=2099, cvv="123")
    with pytest.raises(ValidationError):
        CardDetails(holder_name="X", number="4111111111111111", exp_month=1, exp_year=2001, cvv="123")


def test_prompt_card_retries_on_bad_input(tmp_path):
    batch = load_batch(EXAMPLES / "tanzania_family.json")
    answers = iter(["Dana Specimen", "13/30", "", "Dana Specimen", "12/30", ""])
    hidden = iter(["4111111111111111", "123", "4111111111111111", "123"])
    got = prompt_card(default_billing=batch.applicants[0].contact.address, input_fn=lambda _p: next(answers),
                      secret_fn=lambda _p: next(hidden), out=lambda _m: None)
    assert (got.exp_month, got.exp_year, got.billing_address.city) == (12, 2030, "Tel Aviv")


# ---------------------------------------------------- batches & documents


def test_examples_load_and_validate(tanzania_batch, srilanka_batch):
    assert get_site("tanzania").validate(tanzania_batch) == []
    assert get_site("srilanka").validate(srilanka_batch) == []
    lucas = srilanka_batch.applicants[2]
    assert lucas.contact.email == "jean.dupont@example.com"  # inherited from the batch contact
    assert lucas.resolved_title(srilanka_batch.trip.arrival_date) == "Master"
    assert [len(u) for u in get_site("srilanka").application_units(srilanka_batch)] == [3]
    assert [len(u) for u in get_site("tanzania").application_units(tanzania_batch)] == [1, 1, 1, 1]


def test_validation_catches_short_passport_and_group_on_tanzania(tanzania_batch):
    tanzania_batch.applicants[0].passport.date_of_expiry = tanzania_batch.trip.arrival_date + timedelta(days=30)
    tanzania_batch.mode = "group"
    problems = get_site("tanzania").validate(tanzania_batch)
    assert any("passport expires" in p for p in problems)
    assert any("no group applications" in p for p in problems)


def test_specimen_documents_fit_portal_limits(tmp_path, tanzania_batch):
    applicant = tanzania_batch.applicants[0]
    docs = generate_mock_documents(applicant, tanzania_batch.trip, tmp_path)
    assert docs.passport_scan.suffix == ".jpeg" and docs.passport_scan.stat().st_size <= 300 * 1024
    assert docs.return_ticket.read_bytes().startswith(b"%PDF")
    real = applicant.model_copy(update={"mock": False})
    with pytest.raises(ValueError):
        generate_mock_documents(real, tanzania_batch.trip, tmp_path)


def test_prepare_upload_renames_and_recompresses(tmp_path):
    big = tmp_path / "scan.jpg"
    Image.effect_noise((2400, 1700), 90).convert("RGB").save(big, "JPEG", quality=98)
    assert big.stat().st_size > 300 * 1024
    out = prepare_upload(big, DocumentRequirement("passport_scan", "Passport", ("jpeg", "png"), 300), tmp_path / "up")
    assert out.suffix == ".jpeg" and out.stat().st_size <= 300 * 1024


def test_mock_applicants_never_reach_a_production_portal(tanzania_batch):
    with pytest.raises(SafetyError, match="mock"):
        check_safety(get_site("tanzania"), tanzania_batch, RunOptions(allow_production=True))
    for applicant in tanzania_batch.applicants:
        applicant.mock = False
    with pytest.raises(SafetyError, match="--live"):
        check_safety(get_site("tanzania"), tanzania_batch, RunOptions())


def test_verbose_flag_is_accepted_before_or_after_the_subcommand():
    from evisa.cli import build_parser

    ap = build_parser()
    assert ap.parse_args(["-v", "apply", "b.yaml", "--live"]).verbose
    assert ap.parse_args(["apply", "b.yaml", "--live", "-v"]).verbose
    assert not ap.parse_args(["apply", "b.yaml"]).verbose
