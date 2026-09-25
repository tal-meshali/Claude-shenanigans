"""End-to-end runs of the automation against the local mock ETA portal, which
serves pages saved from the real portal together with its own JavaScript."""

import json
import socket
import urllib.request
from datetime import date

import pytest

from mock_site.server import serve
from srilanka_evisa.automation import EtaAutomation, load_profile
from srilanka_evisa.mock_data import generate
from srilanka_evisa.models import load_application
from srilanka_evisa.payment import CardDetails


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def base_url():
    port = _free_port()
    server = serve(port)
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture
def app(tmp_path):
    return load_application(generate(tmp_path / "mock"))


def _state(base_url):
    with urllib.request.urlopen(base_url + "/__state") as r:
        return json.load(r)


def _session(base_url, reference):
    return next(s for s in _state(base_url)["sessions"].values() if s.get("reference") == reference)


def _card(number="4111111111111111"):
    return CardDetails(number=number, expiry_month=12, expiry_year=date.today().year + 2, cvv="123",
                       holder="Jean Dupont")


def _bot(base_url, tmp_path, submit=True):
    return EtaAutomation(base_url=base_url, out_dir=tmp_path / "out", submit=submit, log=lambda _m: None)


def test_dry_run_stops_at_review(base_url, app, tmp_path):
    results = _bot(base_url, tmp_path, submit=False).run(app)
    assert [r.status for r in results] == ["ready_for_submission"], results[0].error
    assert results[0].payment_url is None
    # runs first in this module: nothing may have been submitted
    assert not any(s.get("status") == "submitted" for s in _state(base_url)["sessions"].values())


def test_group_application_returns_payment_link(base_url, app, tmp_path):
    [result] = _bot(base_url, tmp_path).run(app)
    assert result.status == "payment_link", result.error
    assert result.reference.startswith("LK")
    assert "/ipg/pay?session=" in result.payment_url

    session = _session(base_url, result.reference)
    assert session["app_type"] == "GROUP" and session["visa_type"] == "tourist"
    assert session["trip"]["arrivalDate"] == app.trip.arrival_date.strftime("%m-%d-%Y")
    assert session["trip"]["conCountry"] == "FRA"
    members = session["members"]
    assert [m["othernames"] for m in members] == ["JEAN PIERRE", "MARIE CLAIRE", "LUCAS"]
    assert (members[0]["dobYear"], members[0]["dobMonth"], members[0]["dobDate"]) == ("1984", "03", "14")
    assert members[1]["title"] == "02|MRS" and members[1]["gender"] == "Female"
    assert members[2]["relationship"] == "03" and members[2]["nationality"] == "FRA"
    # The review page's two confirm() dialogs were accepted and recorded.
    assert any("Are you sure to confirm" in m for m in result.site_messages)
    saved = json.loads((tmp_path / "out" / "results.json").read_text())
    assert saved[0]["payment_url"] == result.payment_url


def test_individual_applications_are_paid_with_one_card(base_url, app, tmp_path):
    app.mode = "individual"
    asked = []
    results = _bot(base_url, tmp_path).run(app, card_provider=lambda: asked.append(1) or _card())
    assert [r.status for r in results] == ["paid"] * 3, [r.error for r in results]
    assert len(asked) == 1  # card requested once, reused for each application
    payments = {p["ref"]: p for p in _state(base_url)["payments"].values()}
    assert all(payments[r.reference]["status"] == "paid" for r in results)
    assert all(payments[r.reference]["amount"] == 50 for r in results)

    first = _session(base_url, results[0].reference)["members"][0]
    assert first["surname"] == "DUPONT" and first["bdate"] == "03-14-1984"
    assert first["national"] == "FRA|FRANCE (FRA)" and first["QN1"] == "0"
    assert "4111111111111111" not in (tmp_path / "out" / "results.json").read_text()


def test_declined_card_is_reported(base_url, app, tmp_path):
    [result] = _bot(base_url, tmp_path).run(app, card_provider=lambda: _card("4000000000000002"))
    assert result.status == "declined"
    assert result.reference


def test_payment_not_confirmed_leaves_link(base_url, app, tmp_path):
    [result] = _bot(base_url, tmp_path).run(app, card_provider=_card, confirm_payment=lambda _m: False)
    assert result.status == "payment_unconfirmed"
    assert result.payment_url


def test_rejected_passport_is_reported(base_url, app, tmp_path):
    app.mode = "individual"
    app.beneficiaries = app.beneficiaries[:1]
    app.beneficiaries[0].passport_number = "REJECT123"
    bot = _bot(base_url, tmp_path)
    bot.profile = load_profile()
    bot.profile["steps"]["individual_form"]["fields"]["passport_number"]["wait_ms"] = 3000
    bot.steps = bot.profile["steps"]
    [result] = bot.run(app)
    assert result.status == "error"
    assert "passport_number" in result.error
    assert any("not allowed" in m for m in result.site_messages)
