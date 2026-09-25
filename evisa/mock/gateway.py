"""Mock hosted card checkout, shared by every mock portal.

Behaves like a typical hosted payment page: served from another host, card
inputs inside an iframe, Cybersource-style field names, optional 3-D Secure.

Test cards (any future expiry, any 3-digit CVV):
    4111 1111 1111 1111   approved
    5555 5555 5555 4444   approved (Mastercard)
    4000 0000 0000 3220   3-D Secure challenge, one-time code 123456
    4000 0000 0000 0002   declined
Only the last four digits are ever stored.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import pycountry

from ..core.payment import card_brand, luhn_ok
from .server import MockApp, Request, Response, esc, with_query

THREE_DS_CARD = "4000000000003220"
DECLINED_SUFFIX = "0002"
OTP = "123456"

_STYLE = """
body{font-family:system-ui,sans-serif;background:#f4f5f7;margin:0}
.bar{background:#1b2a4a;color:#fff;padding:14px 24px;font-weight:600}
.card{max-width:520px;margin:28px auto;background:#fff;border-radius:10px;padding:24px;box-shadow:0 2px 10px #0002}
label{display:block;margin-top:12px;font-size:14px;color:#333}
input,select{width:100%;padding:8px;margin-top:4px;box-sizing:border-box}
.row{display:flex;gap:12px}.row>div{flex:1}
button{margin-top:18px;width:100%;padding:12px;background:#0b6bcb;color:#fff;border:0;border-radius:6px;font-size:16px}
.err{color:#b00020;font-weight:600}
iframe{width:100%;height:640px;border:0}
"""


@dataclass
class CheckoutSession:
    token: str
    merchant: str
    reference: str
    amount: Decimal
    currency: str
    return_url: str
    status: str = "pending"  # pending | challenge | approved | declined
    last4: str = ""
    brand: str = ""
    auth_code: str = ""
    attempts: list[str] = field(default_factory=list)


class MockCardGateway(MockApp):
    session_cookie = "gateway_session"

    def __init__(self) -> None:
        super().__init__()
        self.sessions: dict[str, CheckoutSession] = {}
        self.route("GET", r"/checkout/(?P<token>\w+)", self._checkout)
        self.route("GET", r"/checkout/(?P<token>\w+)/card", self._card_frame)
        self.route("POST", r"/checkout/(?P<token>\w+)/pay", self._pay)
        self.route("GET", r"/acs/(?P<token>\w+)", self._acs)
        self.route("POST", r"/acs/(?P<token>\w+)", self._acs_submit)

    # In-process API used by mock portals (a real portal would call the PSP server-to-server).
    def create_session(self, *, merchant: str, reference: str, amount: Decimal, currency: str, return_url: str) -> CheckoutSession:
        token = secrets.token_hex(12)
        session = CheckoutSession(token, merchant, reference, amount, currency, return_url)
        self.sessions[token] = session
        return session

    def checkout_url(self, session: CheckoutSession) -> str:
        return f"{self.base_url}/checkout/{session.token}"

    def _page(self, title: str, inner: str) -> Response:
        return Response(f"<!doctype html><html><head><title>{esc(title)}</title><style>{_STYLE}</style></head>"
                        f"<body><div class='bar'>MockPay Secure Checkout</div>{inner}</body></html>")

    def _get(self, req: Request) -> CheckoutSession | None:
        return self.sessions.get(req.params["token"])

    def _checkout(self, req: Request) -> Response:
        s = self._get(req)
        if not s:
            return self._page("Expired", "<div class='card'><p class='err'>This payment session has expired.</p></div>")
        if s.status == "approved":
            return Response.redirect(with_query(s.return_url, token=s.token))
        frame_src = f"/checkout/{s.token}/card"
        if req.query.get("error"):
            frame_src = with_query(frame_src, error=req.query["error"])
        return self._page("Checkout", f"""
            <div class='card'>
              <h2>{esc(s.merchant)}</h2>
              <p>Reference <b>{esc(s.reference)}</b></p>
              <p>Amount due: <b id='amount'>{esc(s.currency)} {s.amount:.2f}</b></p>
              <iframe name='card-frame' title='Card details' src='{esc(frame_src)}'></iframe>
            </div>""")

    def _card_frame(self, req: Request) -> Response:
        s = self._get(req)
        if not s:
            return Response("expired", 404)
        error = f"<p class='err'>{esc(req.query['error'])}</p>" if req.query.get("error") else ""
        months = "".join(f"<option value='{m:02d}'>{m:02d}</option>" for m in range(1, 13))
        this_year = date.today().year
        years = "".join(f"<option value='{y}'>{y}</option>" for y in range(this_year, this_year + 15))
        country_opts = "".join(f"<option value='{c.alpha_2}'>{esc(c.name)}</option>" for c in sorted(pycountry.countries, key=lambda c: c.name))
        return Response(f"""<!doctype html><html><head><style>{_STYLE} body{{background:#fff}}</style></head><body>
            <form method='post' action='/checkout/{s.token}/pay' target='_top'>
              {error}
              <fieldset style='border:0;padding:0'><legend>Card type</legend>
                <label style='display:inline'><input type='radio' name='card_type' value='001' style='width:auto'> Visa</label>
                <label style='display:inline;margin-left:16px'><input type='radio' name='card_type' value='002' style='width:auto'> Mastercard</label>
              </fieldset>
              <label for='card_number'>Card number</label>
              <input id='card_number' name='card_number' inputmode='numeric' autocomplete='cc-number' required>
              <div class='row'>
                <div><label for='card_expiry_month'>Expiry month</label>
                  <select id='card_expiry_month' name='card_expiry_month'><option value=''>MM</option>{months}</select></div>
                <div><label for='card_expiry_year'>Expiry year</label>
                  <select id='card_expiry_year' name='card_expiry_year'><option value=''>YYYY</option>{years}</select></div>
                <div><label for='card_cvn'>CVN</label><input id='card_cvn' name='card_cvn' maxlength='4' autocomplete='cc-csc' required></div>
              </div>
              <div class='row'>
                <div><label for='bill_to_forename'>First name</label><input id='bill_to_forename' name='bill_to_forename' required></div>
                <div><label for='bill_to_surname'>Last name</label><input id='bill_to_surname' name='bill_to_surname' required></div>
              </div>
              <label for='bill_to_address_line1'>Billing address</label><input id='bill_to_address_line1' name='bill_to_address_line1' required>
              <div class='row'>
                <div><label for='bill_to_address_city'>City</label><input id='bill_to_address_city' name='bill_to_address_city' required></div>
                <div><label for='bill_to_address_postal_code'>Postal code</label>
                  <input id='bill_to_address_postal_code' name='bill_to_address_postal_code'></div>
              </div>
              <label for='bill_to_address_country'>Country</label>
              <select id='bill_to_address_country' name='bill_to_address_country'><option value=''>Select country</option>{country_opts}</select>
              <button type='submit'>Pay {esc(s.currency)} {s.amount:.2f}</button>
            </form></body></html>""")

    def _pay(self, req: Request) -> Response:
        s = self._get(req)
        if not s:
            return Response("expired", 404)
        f = req.form
        number = "".join(ch for ch in f.get("card_number", "") if ch.isdigit())
        problems = []
        if not (12 <= len(number) <= 19 and luhn_ok(number)):
            problems.append("Card number is invalid")
        try:
            month, year = int(f.get("card_expiry_month", "")), int(f.get("card_expiry_year", ""))
            if (year, month) < (date.today().year, date.today().month):
                problems.append("Card has expired")
        except ValueError:
            problems.append("Expiry date is required")
        if not f.get("card_cvn", "").isdigit() or len(f.get("card_cvn", "")) not in (3, 4):
            problems.append("CVN is invalid")
        for key in ("bill_to_forename", "bill_to_surname", "bill_to_address_line1", "bill_to_address_city", "bill_to_address_country"):
            if not f.get(key):
                problems.append(f"{key.replace('bill_to_', '').replace('_', ' ')} is required")
        if problems:
            return Response.redirect(with_query(f"/checkout/{s.token}", error="; ".join(problems)))
        s.last4, s.brand = number[-4:], card_brand(number)
        s.attempts.append(s.last4)
        if number.endswith(DECLINED_SUFFIX):
            s.status = "declined"
            return self._page("Declined", f"""<div class='card'><h2 class='err'>Payment declined</h2>
                <p>Your bank declined the transaction ({esc(s.brand)} ending {esc(s.last4)}).</p>
                <p><a href='{esc(with_query(s.return_url, token=s.token))}'>Return to merchant</a></p></div>""")
        if number == THREE_DS_CARD:
            s.status = "challenge"
            return Response.redirect(f"/acs/{s.token}")
        return self._approve(s)

    def _approve(self, s: CheckoutSession) -> Response:
        s.status = "approved"
        s.auth_code = secrets.token_hex(3).upper()
        return Response.redirect(with_query(s.return_url, token=s.token))

    def _acs(self, req: Request) -> Response:
        s = self._get(req)
        if not s or s.status != "challenge":
            return Response("no challenge", 404)
        error = "<p class='err'>Incorrect code, try again.</p>" if req.query.get("error") else ""
        return self._page("3-D Secure", f"""<div class='card'><h2>Verify it's you</h2>
            <p>Your bank sent a one-time code to the phone number on file for card ending {esc(s.last4)}.</p>{error}
            <form method='post'><label for='otp'>One-time code</label><input id='otp' name='otp' autocomplete='one-time-code'>
            <button type='submit'>Verify</button></form></div>""")

    def _acs_submit(self, req: Request) -> Response:
        s = self._get(req)
        if not s or s.status != "challenge":
            return Response("no challenge", 404)
        if req.form.get("otp", "").strip() != OTP:
            return Response.redirect(f"/acs/{s.token}?error=1")
        return self._approve(s)
