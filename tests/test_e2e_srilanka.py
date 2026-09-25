"""Full runs against the local Sri Lanka ETA mock portal + mock card gateway."""

from __future__ import annotations

import pytest

from evisa.core.models import ApplicationStatus
from evisa.core.payment import PaymentMode
from evisa.core.runner import run_batch
from evisa.sites import get_site

from .conftest import card, options

pytestmark = pytest.mark.e2e


def _run(env, batch, opts):
    return run_batch(get_site("srilanka", base_url=env.base_url), batch, opts).results


def test_dry_run_stops_at_review_without_submitting(tmp_path, srilanka_env, srilanka_batch):
    results = _run(srilanka_env, srilanka_batch, options(tmp_path, stop_after="review"))
    assert [r.status for r in results] == [ApplicationStatus.STOPPED] * 3, [r.error for r in results]
    app = srilanka_env.portal.applications[-1]
    assert app["status"] == "draft" and not app["reference"]


def test_group_application_returns_one_payment_link(tmp_path, srilanka_env, srilanka_batch):
    results = _run(srilanka_env, srilanka_batch, options(tmp_path))
    assert [r.status for r in results] == [ApplicationStatus.AWAITING_PAYMENT] * 3, [r.error for r in results]
    assert len({r.application_id for r in results}) == 1 and results[0].application_id.startswith("ETA")
    assert len({r.payment_link.gateway_url for r in results}) == 1
    assert str(results[0].payment_link.amount) == "USD 150.00"

    app = next(a for a in srilanka_env.portal.applications if a["reference"] == results[0].application_id)
    assert app["mode"] == "group" and app["status"] == "submitted"
    jean, marie, lucas = app["members"]
    assert (jean["title"], jean["othernames"], jean["bdate"], jean["gender"]) == ("01|MR", "JEAN PIERRE", "03-14-1984", "Male")
    assert (marie["title"], marie["gender"], lucas["title"]) == ("02|MRS", "Female", "05|MASTER")
    assert jean["national"].startswith("FRA|") and jean["QN1"] == "0"
    assert app["travel"]["puofvisit"].startswith("V01|") and app["contact"]["contEmail"] == "jean.dupont@example.com"


def test_individual_applications_are_paid_with_one_card(tmp_path, srilanka_env, srilanka_batch):
    srilanka_batch.mode = "individual"
    asked, confirmations = [], []
    opts = options(tmp_path, PaymentMode.CARD, card_provider=lambda a: asked.append(1) or card(),
                   confirm=lambda lines, total: confirmations.append(str(total)) or True)
    results = _run(srilanka_env, srilanka_batch, opts)
    assert [r.status for r in results] == [ApplicationStatus.PAID] * 3, [r.error for r in results]
    assert len(asked) == 1
    # fee unknown up front ("None"), then each charge confirmed with the portal's amount
    assert confirmations == ["None", "USD 50.00", "USD 50.00", "USD 50.00"]
    paid = [a for a in srilanka_env.portal.applications if a["reference"] in {r.application_id for r in results}]
    assert [a["status"] for a in paid] == ["paid"] * 3


def test_declined_card_is_reported(tmp_path, srilanka_env, srilanka_batch):
    results = _run(srilanka_env, srilanka_batch, options(tmp_path, PaymentMode.CARD, card_provider=lambda a: card("4000000000000002")))
    assert {r.status for r in results} == {ApplicationStatus.PAYMENT_DECLINED}
    assert results[0].application_id


def test_not_authorising_the_portal_amount_keeps_the_link(tmp_path, srilanka_env, srilanka_batch):
    answers = iter([True, False])  # yes up front, then no once the portal shows USD 150
    opts = options(tmp_path, PaymentMode.CARD, card_provider=lambda a: card(), confirm=lambda lines, total: next(answers))
    results = _run(srilanka_env, srilanka_batch, opts)
    assert {r.status for r in results} == {ApplicationStatus.AWAITING_PAYMENT}
    assert results[0].payment.status.value == "not_authorised" and results[0].payment_link is not None
