"""Full runs against the local Tanzania mock portal + mock card gateway."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evisa.core.models import ApplicationStatus
from evisa.core.payment import PaymentMode
from evisa.core.runner import SafetyError, run_batch
from evisa.mock.gateway import complete_mock_3ds
from evisa.mock.tanzania import COUNTRY_BY_ID, VISA_TYPES
from evisa.sites import get_site

from .conftest import card, options

pytestmark = pytest.mark.e2e


def _apps(env, results):
    return [env.portal.applications[r.application_id] for r in results]


def test_every_beneficiary_gets_an_application_and_a_payment_link(tmp_path, tanzania_env, tanzania_batch):
    report = run_batch(get_site("tanzania", base_url=tanzania_env.base_url), tanzania_batch, options(tmp_path))

    assert [r.status for r in report.results] == [ApplicationStatus.AWAITING_PAYMENT] * 4, [r.error for r in report.results]
    assert len({r.application_id for r in report.results}) == 4
    for r in report.results:
        assert r.payment_link.gateway_url.startswith(tanzania_env.gateway.base_url + "/checkout/")
        assert r.payment_link.portal_url.endswith("/continueapplication?ReturnUrl=/payment")
        assert r.payment_link.resume["Application ID"] == r.application_id
        assert r.payment_link.resume["Security answer"] == "Specimen Kid"
        assert r.payment_link.resume["Security question"] == "What was your childhood nickname?"

    dana, _, maya, sam = _apps(tanzania_env, report.results)
    assert dana["status"] == "Submitted - awaiting payment"
    assert dana["personal"]["OccupationId"] == "Engineer"  # "Software Engineer" fuzzy-matched, not "Other"
    assert dana["personal"]["MotherName"] == "Rina Specimen" and dana["personal"]["DateOfBirth"] == "12/04/1988"
    assert COUNTRY_BY_ID[dana["personal"]["NationalityId"]][1] == "ISR"
    assert maya["personal"]["Gender"] == "F"
    assert VISA_TYPES[sam["travel"]["VisaTypeId"]][0] == "Multiple Entry Visa"  # US citizens
    assert {f["filename"] for f in dana["files"].values()} == {"passport_scan.jpeg", "photo.jpeg", "return_ticket.pdf", "accommodation_proof.pdf"}

    saved = json.loads((Path(report.run_dir) / "report.json").read_text())
    assert saved["results"][0]["payment_link"]["gateway_url"] == report.results[0].payment_link.gateway_url


def test_card_is_asked_once_and_every_application_is_paid(tmp_path, tanzania_env, tanzania_batch):
    tanzania_batch.applicants = [tanzania_batch.applicants[0], tanzania_batch.applicants[3]]
    asked, confirmed = [], []
    opts = options(tmp_path, PaymentMode.CARD, card_provider=lambda a: asked.append(1) or card(),
                   confirm=lambda lines, total: confirmed.append((lines, total)) or True)
    report = run_batch(get_site("tanzania", base_url=tanzania_env.base_url), tanzania_batch, opts)

    assert [r.status for r in report.results] == [ApplicationStatus.PAID] * 2, [r.error for r in report.results]
    assert len(asked) == 1 and len(confirmed) == 1  # one prompt, one up-front confirmation of the total
    assert str(confirmed[0][1]) == "USD 150.00"  # 50 ordinary + 100 multiple-entry
    assert all(r.payment.reference.startswith("TZR-") for r in report.results)
    apps = _apps(tanzania_env, report.results)
    assert [a["payment"]["last4"] for a in apps] == ["1111", "1111"]
    assert [a["status"] for a in apps] == ["Under processing"] * 2  # submitted after payment, as the guidelines ask
    text = (Path(report.run_dir) / "report.json").read_text()
    assert "4111111111111111" not in text and "checkout-page" not in text  # no card data, no card-form screenshots


def test_three_d_secure_challenge_is_completed(tmp_path, tanzania_env, tanzania_batch):
    tanzania_batch.applicants = tanzania_batch.applicants[:1]
    opts = options(tmp_path, PaymentMode.CARD, card_provider=lambda a: card("4000000000003220"), three_ds=complete_mock_3ds)
    [result] = run_batch(get_site("tanzania", base_url=tanzania_env.base_url), tanzania_batch, opts).results
    assert result.status is ApplicationStatus.PAID, result.error


def test_declined_card_leaves_a_payment_link(tmp_path, tanzania_env, tanzania_batch):
    tanzania_batch.applicants = tanzania_batch.applicants[:1]
    opts = options(tmp_path, PaymentMode.CARD, card_provider=lambda a: card("4000000000000002"))
    [result] = run_batch(get_site("tanzania", base_url=tanzania_env.base_url), tanzania_batch, opts).results
    assert result.status is ApplicationStatus.PAYMENT_DECLINED
    assert result.payment_link and result.payment_link.resume["Application ID"] == result.application_id


def test_refusing_the_charge_submits_nothing(tmp_path, tanzania_env, tanzania_batch):
    before = len(tanzania_env.portal.applications)
    opts = options(tmp_path, PaymentMode.CARD, card_provider=lambda a: card(), confirm=lambda lines, total: False)
    with pytest.raises(SafetyError):
        run_batch(get_site("tanzania", base_url=tanzania_env.base_url), tanzania_batch, opts)
    assert len(tanzania_env.portal.applications) == before
