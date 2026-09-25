from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from evisa.core.captcha import LoopbackCheckboxCaptcha
from evisa.core.models import Address, ApplicationBatch, load_batch
from evisa.core.payment import CardDetails, PaymentMode
from evisa.core.runner import RunOptions
from evisa.mock import start_mock

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def future_trip(batch: ApplicationBatch, *, days_ahead: int = 45, nights: int = 14) -> ApplicationBatch:
    """Examples carry fixed dates; move the trip into the future so tests never expire."""
    batch.trip.arrival_date = date.today() + timedelta(days=days_ahead)
    batch.trip.departure_date = batch.trip.arrival_date + timedelta(days=nights)
    return batch


@pytest.fixture
def tanzania_batch() -> ApplicationBatch:
    return future_trip(load_batch(EXAMPLES / "tanzania_family.json"))


@pytest.fixture
def srilanka_batch() -> ApplicationBatch:
    return future_trip(load_batch(EXAMPLES / "srilanka_family.yaml"))


@pytest.fixture(scope="module")
def tanzania_env():
    with start_mock("tanzania") as env:
        yield env


@pytest.fixture(scope="module")
def srilanka_env():
    with start_mock("srilanka") as env:
        yield env


def card(number: str = "4111111111111111") -> CardDetails:
    return CardDetails(
        holder_name="Dana Specimen", number=number, exp_month=12, exp_year=date.today().year + 2, cvv="123",
        billing_address=Address(line1="1 Example Street", city="Tel Aviv", postal_code="6100001", country="ISR"),
    )


def options(tmp_path: Path, payment: PaymentMode = PaymentMode.LINK, **kw) -> RunOptions:
    kw.setdefault("confirm", lambda lines, total: True)
    return RunOptions(payment=payment, out_dir=tmp_path, captcha=LoopbackCheckboxCaptcha(), notify=lambda _m: None, **kw)
