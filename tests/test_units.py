from datetime import date, timedelta

import pytest

from srilanka_evisa.mock_data import generate
from srilanka_evisa.models import load_application
from srilanka_evisa.mrz import MRZError, build_td3, check_digit, parse_td3
from srilanka_evisa.payment import CardDetails, CardError, luhn_ok, prompt_card_details


def test_check_digit_icao_example():
    # ICAO 9303 part 3 worked example
    assert check_digit("L898902C3") == "6"
    assert check_digit("740812") == "2"


def test_td3_roundtrip():
    l1, l2 = build_td3(issuing_country="FRA", surname="Dupont", given_names="Jean Pierre",
                       passport_number="24FR81234", nationality="FRA", date_of_birth=date(1984, 3, 14),
                       sex="M", expiry_date=date(2034, 1, 31))
    assert len(l1) == len(l2) == 44
    m = parse_td3(l1, l2)
    assert (m.surname, m.given_names, m.passport_number) == ("DUPONT", "JEAN PIERRE", "24FR81234")
    assert m.date_of_birth == date(1984, 3, 14) and m.expiry_date == date(2034, 1, 31)
    tampered = l2[:3] + ("9" if l2[3] != "9" else "8") + l2[4:]
    with pytest.raises(MRZError):
        parse_td3(l1, tampered)


def test_mock_data_loads_and_validates(tmp_path):
    app = load_application(generate(tmp_path))
    assert app.mode == "group" and len(app.beneficiaries) == 3
    assert app.validate() == []
    lucas = app.beneficiaries[2]
    assert lucas.given_names == "LUCAS" and lucas.passport_image.is_file()


def test_validation_catches_short_passport_validity(tmp_path):
    app = load_application(generate(tmp_path))
    app.beneficiaries[0].passport_expiry_date = app.trip.arrival_date + timedelta(days=30)
    assert any("6 months" in p for p in app.validate())


def test_children_on_a_parents_passport(tmp_path):
    path = generate(tmp_path)
    app = load_application(path)
    [emma] = app.beneficiaries[1].children
    assert (emma.given_names, emma.surname, emma.sex) == ("EMMA", "DUPONT", "F")  # surname from the parent
    assert emma.date_of_birth == date(2021, 4, 18) and not app.validate()

    path.write_text(path.read_text().replace("2021-04-18", str(date.today().replace(year=date.today().year - 16))))
    assert any("16 or older" in p for p in load_application(path).validate())


def test_card_validation_and_masking():
    assert luhn_ok("4111111111111111") and not luhn_ok("4111111111111112")
    card = CardDetails(number="4111 1111 1111 1111", expiry_month=12, expiry_year=date.today().year % 100 + 2,
                       cvv="123", holder="Jean Dupont")
    assert "4111111111111111" not in repr(card) and "123" not in repr(card)
    assert card.masked.endswith("1111")
    with pytest.raises(CardError):
        CardDetails(number="4111111111111112", expiry_month=1, expiry_year=2099, cvv="123")
    with pytest.raises(CardError):
        CardDetails(number="4111111111111111", expiry_month=1, expiry_year=2001, cvv="123")


def test_prompt_card_details_retries_on_bad_input():
    answers = iter(["Jean Dupont", "13/30", "Jean Dupont", "12/30"])
    secrets = iter(["4111111111111111", "123", "4111111111111111", "123"])
    card = prompt_card_details(lambda _p: next(answers), lambda _p: next(secrets))
    assert (card.expiry_month, card.expiry_year) == (12, 2030)
