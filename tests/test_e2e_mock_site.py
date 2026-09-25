"""End-to-end runs of the automation against the local mock ETA portal."""

import json
import socket
import urllib.request
from datetime import date

import pytest

from mock_site.server import serve
from srilanka_evisa.automation import EtaAutomation
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


def _card(number="4111111111111111"):
    return CardDetails(number=number, expiry_month=12, expiry_year=date.today().year + 2, cvv="123",
                       holder="Jean Dupont")


def _bot(base_url, tmp_path, submit=True):
    return EtaAutomation(base_url=base_url, out_dir=tmp_path / "out", submit=submit, log=lambda _m: None)


def test_dry_run_stops_at_review(base_url, app, tmp_path):
    results = _bot(base_url, tmp_path, submit=False).run(app)
    assert [r.status for r in results] == ["ready_for_submission"]
    assert results[0].payment_url is None


def test_group_application_returns_payment_link(base_url, app, tmp_path):
    [result] = _bot(base_url, tmp_path).run(app)
    assert result.status == "payment_link", result.error
    assert result.reference.startswith("ETA-")
    assert "/ipg/pay?session=" in result.payment_url

    session = next(s for s in _state(base_url)["sessions"].values() if s.get("reference") == result.reference)
    assert session["app_type"] == "GROUP"
    members = session["members"]
    assert [m["otherNames"] for m in members] == ["Jean Pierre", "Marie Claire", "Lucas"]
    assert members[0]["dob"] == "14/03/1984" and members[0]["gender"] == "1" and members[0]["nationality"] == "250"
    assert members[1]["title"] == "MRS" and members[1]["gender"] == "2"
    assert all(set(m["files"]) == {"passportCopy", "photo"} for m in members)
    # results.json never contains card data and lists the link
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
    out = (tmp_path / "out" / "results.json").read_text()
    assert "4111111111111111" not in out


def test_declined_card_is_reported(base_url, app, tmp_path):
    [result] = _bot(base_url, tmp_path).run(app, card_provider=lambda: _card("4000000000000002"))
    assert result.status == "declined"
    assert result.reference


def test_payment_not_confirmed_leaves_link(base_url, app, tmp_path):
    [result] = _bot(base_url, tmp_path).run(app, card_provider=_card, confirm_payment=lambda _m: False)
    assert result.status == "payment_unconfirmed"
    assert result.payment_url
