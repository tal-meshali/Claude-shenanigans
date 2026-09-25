"""A local stand-in for the Sri Lanka ETA portal (eta.gov.lk/etaslvisa) and a
payment gateway, for exercising the automation without touching the real site.

Pages saved from the live portal (mock_site/portal_snapshot/) are served with
the portal's own JavaScript, so its client-side validation really runs:

  termnconuser.jsp -> terms ("I Agree")            [real page]
  -> category links (Tourist Individual / Group)   [rebuilt from the real page]
  -> individual form                                [real page]
     or group travel & contact form                 [real page]
        -> member form(s), "Add Member" / "Next"    [stand-in]
  -> review with confirmForm() dialogs              [stand-in]
  -> reference + payment options -> gateway         [stand-in]

The portal's server-side AJAX checks (DWR) are stubbed to "OK"; passport
number "REJECT123" is refused, to test that path.
Test cards: 4111 1111 1111 1111 is approved, 4000 0000 0000 0002 is declined.
State for assertions is exposed as JSON at /__state.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import secrets
import threading
from datetime import date, datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SNAPSHOT = Path(__file__).parent / "portal_snapshot"
FEE_USD = 50
NAV = "/etaslvisa/etaNavServ"
CATEGORY_IDS = {"1": ("tourist", "INDIVIDUAL"), "2": ("tourist", "GROUP"), "21": ("business", "INDIVIDUAL"),
                "32": ("business", "GROUP"), "5": ("transit", "INDIVIDUAL"), "6": ("transit", "GROUP")}
COUNTRIES = [("FRA", "FRANCE (FRA)"), ("DEU", "GERMANY (DEU)"), ("GBR", "UNITED KINGDOM (GBR)"),
             ("USA", "UNITED STATES (USA)"), ("ISR", "ISRAEL (ISR)"), ("IND", "INDIA (IND)")]

SESSIONS: dict[str, dict] = {}
PAYMENTS: dict[str, dict] = {}
LOCK = threading.Lock()

DWR_STUB = """var %(obj)s = new Proxy({}, {get: function (t, method) { return function () {
  var args = Array.prototype.slice.call(arguments), cb = args[args.length - 1];
  var answer = (method === 'validateIndPassport' && args[0] === 'REJECT123')
      ? 'This passport number is not allowed' : null;
  if (typeof cb === 'function') setTimeout(function () { cb(answer); }, 50);
}; }});"""


def esc(v: object) -> str:
    return html.escape(str(v))


def page(title: str, body: str, error: str = "", scripts: str = "") -> str:
    err = f'<span class="error" style="color:red">{esc(error)}</span>' if error else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{esc(title)}</title>{scripts}
<style>body{{font-family:sans-serif;max-width:820px;margin:2em auto}} td{{padding:3px 6px}}</style></head>
<body><h2>{esc(title)}</h2>{err}{body}</body></html>"""


def parse_mdy(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%m-%d-%Y").date()
    except ValueError:
        return None


def select(id_: str, name: str, options: list[tuple[str, str]]) -> str:
    opts = '<option value="0X">[Select Please]</option>' + "".join(
        f'<option value="{esc(v)}">{esc(t)}</option>' for v, t in options)
    return f'<select id="{id_}" name="{name}">{opts}</select>'


def row(label: str, control: str) -> str:
    return f'<tr><td class="inner_text_1">{label}<font color="#FF0000">*</font></td><td>{control}</td></tr>'


def date_parts(prefix: str, name: str, years: range) -> str:
    return (select(f"id{prefix}Year", f"{name}Year", [(str(y), str(y)) for y in years])
            + select(f"id{prefix}Month", f"{name}Month", [(f"{m:02d}", f"{m:02d}") for m in range(1, 13)])
            + select(f"id{prefix}Date", f"{name}Date", [(f"{d:02d}", f"{d:02d}") for d in range(1, 32)]))


def parts_date(f: dict[str, str], name: str) -> date | None:
    try:
        return date(int(f[f"{name}Year"]), int(f[f"{name}Month"]), int(f[f"{name}Date"]))
    except (KeyError, ValueError):
        return None


class Handler(BaseHTTPRequestHandler):
    server_version = "MockETA/2.0"

    def log_message(self, fmt: str, *args: object) -> None:  # quiet
        pass

    # --------------------------------------------------------------- plumbing
    def session(self) -> tuple[str, dict]:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        sid = cookie["JSESSIONID"].value if "JSESSIONID" in cookie else ""
        with LOCK:
            if sid not in SESSIONS:
                sid = secrets.token_hex(8)
                SESSIONS[sid] = {"members": [], "status": "new"}
            return sid, SESSIONS[sid]

    def send(self, body: str | bytes, status: int = 200, sid: str | None = None, ctype: str = "text/html") -> None:
        data = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if sid:
            self.send_header("Set-Cookie", f"JSESSIONID={sid}; Path=/; HttpOnly")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str, sid: str | None = None) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        if sid:
            self.send_header("Set-Cookie", f"JSESSIONID={sid}; Path=/; HttpOnly")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def form(self) -> dict[str, str]:
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8", "replace")
        return {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}

    def snapshot(self, name: str, sid: str) -> None:
        self.send((SNAPSHOT / name).read_bytes(), sid=sid)

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:
        url = urlparse(self.path)
        path, query = url.path, parse_qs(url.query)
        sid, s = self.session()

        if path == "/__state":
            return self.send(json.dumps({"sessions": SESSIONS, "payments": PAYMENTS}, default=str),
                             ctype="application/json")
        if path == "/etaslvisa/pages/termnconuser.jsp":
            s.update(members=[], status="new")
            return self.redirect(f"{NAV}?payType=1", sid)
        if path == NAV:
            return self.snapshot("eta_terms.html", sid)
        if path.startswith("/etaslvisa/js/"):
            file = (SNAPSHOT / path.removeprefix("/etaslvisa/")).resolve()
            if SNAPSHOT in file.parents and file.is_file():
                return self.send(file.read_bytes(), ctype="application/javascript")
        if path.startswith("/etaslvisa/dwr/interface/"):
            return self.send(DWR_STUB % {"obj": Path(path).stem}, ctype="application/javascript")
        if path == "/etaslvisa/dwr/engine.js":
            return self.send("", ctype="application/javascript")
        if path == "/ipg/pay":
            return self.send(self.gateway_page(query.get("session", [""])[0]))
        if path == "/ipg/card-frame":
            return self.send(self.card_frame(query.get("session", [""])[0]))
        if path == "/ipg/result":
            p = PAYMENTS.get(query.get("session", [""])[0], {})
            if p.get("status") == "paid":
                return self.send(page("Payment Successful",
                    f"<p>Transaction approved for ETA {esc(p['ref'])}. Amount: {p['amount']}.00 USD.</p>"))
            return self.send(page("Payment Failed", "<p>Transaction declined by the issuing bank.</p>"))
        self.send(page("404", "<p>Not found</p>"), status=404)

    # ----------------------------------------------------------------- POST
    def do_POST(self) -> None:  # noqa: C901 - a router
        path = urlparse(self.path).path
        sid, s = self.session()
        f = self.form()

        if path == NAV:
            if f.get("terms") == "yes":
                s["status"] = "terms"
                return self.send(self.category_page(), sid=sid)
            if f.get("pageNumber") == "2" and f.get("appType") in CATEGORY_IDS:
                if s.get("status") != "terms":
                    return self.send(self.expired(), sid=sid)
                s["visa_type"], s["app_type"] = CATEGORY_IDS[f["appType"]]
                s["status"] = "form"
                return self.snapshot("eta_individual_form.html" if s["app_type"] == "INDIVIDUAL"
                                     else "eta_group_trip_form.html", sid)
            if "surname" in f and s.get("app_type") == "INDIVIDUAL":
                error = self.validate_individual(f)
                if error:
                    return self.send(page("Error", f"<p>{esc(error)}</p>"), sid=sid, status=400)
                s["trip"] = {k: f.get(k, "") for k in ("fromDeparture", "RequestedVisaDays", "iadate", "puofvisit",
                             "depcity", "airline", "flightno", "addone", "city", "state", "adcountry",
                             "addinsl", "email", "telephon")}
                s["members"] = [{k: f.get(k, "") for k in ("title", "surname", "othernames", "bdate", "gender",
                                 "national", "conbirth", "passportno", "pidate", "pedate", "QN1", "QN2", "QN3")}]
                s["status"] = "review"
                return self.send(self.review_page(s), sid=sid)
            if "conAddOne" in f and s.get("app_type") == "GROUP":
                missing = [k for k in ("fromDeparture", "arrivalDate", "puofvisit", "conAddOne", "contCity",
                                       "contState", "conCountry", "contPhoneNo", "contEmail") if f.get(k, "0X") in ("", "0X")]
                if missing or not parse_mdy(f["arrivalDate"]) or f["contEmail"] != f.get("reEnterEmail"):
                    return self.send(page("Error", f"<p>Invalid group details {missing}</p>"), sid=sid, status=400)
                s["trip"] = f
                s["members"] = []
                return self.send(self.member_page(s), sid=sid)
            if f.get("memberAction") in ("add", "next") and s.get("app_type") == "GROUP":
                if f["memberAction"] == "add":
                    error = self.validate_member(f)
                    if error:
                        return self.send(self.member_page(s, error), sid=sid)
                    s["members"].append({k: v for k, v in f.items() if k != "memberAction"})
                    return self.send(self.member_page(s), sid=sid)
                if len(s["members"]) < 2:
                    return self.send(self.member_page(s, "A group needs at least two members."), sid=sid)
                s["status"] = "review"
                return self.send(self.review_page(s), sid=sid)
            if f.get("actiontype") == "2" and s.get("status") == "review":
                s["reference"] = "LK" + secrets.token_hex(5).upper()
                s["status"] = "submitted"
                return self.send(self.payment_options_page(s), sid=sid)
            return self.send(self.expired(), sid=sid)

        if path == "/ipg/checkout":
            if s.get("status") != "submitted" or f.get("ref") != s.get("reference"):
                return self.send(page("Error", "<p>Invalid payment session.</p>"), status=400)
            if f.get("payMethod") != "CARD":
                return self.send(page("Error", "<p>Please select a payment method.</p>"), status=400)
            token = secrets.token_urlsafe(12)
            PAYMENTS[token] = {"ref": s["reference"], "amount": FEE_USD * len(s["members"]), "status": "pending"}
            return self.redirect(f"/ipg/pay?session={token}")

        if path == "/ipg/submit":
            token = f.get("session", "")
            p = PAYMENTS.get(token)
            if not p or p["status"] != "pending":
                return self.send(page("Error", "<p>Session expired.</p>"), status=400)
            number = f.get("cardNumber", "").replace(" ", "")
            valid = (re.fullmatch(r"\d{13,19}", number) and f.get("expMonth") and f.get("expYear")
                     and re.fullmatch(r"\d{3,4}", f.get("cvc", "")))
            p["status"] = "paid" if valid and number == "4111111111111111" else "declined"
            p["card_last4"] = number[-4:]
            return self.redirect(f"/ipg/result?session={token}")

        self.send(page("404", "<p>Not found</p>"), status=404)

    # ------------------------------------------------------------- validation
    def validate_individual(self, f: dict[str, str]) -> str:
        required = ["surname", "othernames", "title", "bdate", "gender", "national", "conbirth", "passportno",
                    "pidate", "pedate", "fromDeparture", "RequestedVisaDays", "iadate", "puofvisit", "addone",
                    "city", "state", "adcountry", "addinsl", "email", "telephon", "QN1", "QN2", "QN3", "conf"]
        missing = [k for k in required if f.get(k, "0X") in ("", "0X")]
        if missing:
            return f"missing: {missing}"
        if not all(parse_mdy(f[k]) for k in ("bdate", "pidate", "pedate", "iadate")):
            return "dates must be mm-dd-yyyy"
        if f["bdate"] != f.get("reenteredbdate") or f["passportno"] != f.get("reenteredpassportno"):
            return "re-entered values differ"
        return ""

    def validate_member(self, f: dict[str, str]) -> str:
        required = ["title", "surname", "othernames", "gender", "nationality", "cob", "passportNo"]
        missing = [k for k in required if f.get(k, "0X") in ("", "0X")]
        if missing:
            return f"Please fill: {', '.join(missing)}"
        dob, issued, expiry = parts_date(f, "dob"), parts_date(f, "passIsue"), parts_date(f, "passExp")
        if not (dob and issued and expiry):
            return "Please select valid dates"
        if expiry <= date.today():
            return "Passport has expired"
        return ""

    # ----------------------------------------------------------- stand-in pages
    def expired(self) -> str:
        return page("ETA", '<script>alert("Session Expired !!!!"); window.close();</script>')

    def category_page(self) -> str:
        links = "".join(
            f'<li><a href="#" onclick="submitformApp(this,\'appFormX\');" id="{i}" class="inner_text_1">'
            f'{vt.title()} ETA - Apply for {"an Individual" if kind == "INDIVIDUAL" else "a Group"}</a></li>'
            for i, (vt, kind) in CATEGORY_IDS.items())
        return page("Online Visa Application", f"""
<form method="POST" action="etaNavServ" name="appFormX"><ul>{links}</ul>
<input type="hidden" name="payType" value="1"/><input type="hidden" name="appType" id='idAppType' />
<input type="hidden" name="appSType" id='idAppType' value="0"/>
<input type="hidden" name="pageNumber" id='idpageNumber' value="2" /></form>""",
            scripts='<script src="js/com/etafunctional.js"></script>')

    def member_page(self, s: dict, error: str = "") -> str:
        members = "".join(f"<tr><td>{esc(m['surname'])}</td><td>{esc(m['othernames'])}</td>"
                          f"<td>{esc(m['passportNo'])}</td></tr>" for m in s["members"])
        countries = [(f"{c}", t) for c, t in COUNTRIES]
        this_year = date.today().year
        return page(f"Group Application - Member {len(s['members']) + 1}", f"""
<table border="1"><tr><th>Surname</th><th>Other Names</th><th>Passport</th></tr>{members}</table>
<form method="post" action="etaNavServ" name="form1"><table>
{row('Title', select('idTitle', 'title', [('01|MR', 'MR'), ('02|MRS', 'MRS'), ('03|MISS', 'MISS'),
                                          ('04|MS', 'MS'), ('05|MASTER', 'MASTER')]))}
{row('Surname/Family Name', '<input id="idSurname" name="surname" oninput="limitInput(this);">')}
{row('Other/Given Names', '<input id="idOthernames" name="othernames" oninput="limitInput(this);">')}
{row('Date of Birth', date_parts('Dob', 'dob', range(this_year, 1900, -1)))}
{row('Gender', select('idGender', 'gender', [('Male', 'Male'), ('Female', 'Female')]))}
{row('Nationality', select('idNatinality', 'nationality', countries))}
{row('Country or Region of Birth', select('idCOB', 'cob', countries))}
{row('Occupation', '<input id="idOccupation" name="occupation">')}
{row('Relationship', select('idRelationShip', 'relationship', [('01', 'Self'), ('02', 'Spouse'), ('03', 'Child'),
                                                               ('04', 'Parent'), ('05', 'Friend')]))}
{row('Passport Number', '<input id="idPassportNo" name="passportNo" oninput="limitInput(this);">')}
{row('Passport Issued Date', date_parts('PassIsue', 'passIsue', range(this_year, this_year - 12, -1)))}
{row('Passport Expiry Date', date_parts('PassExp', 'passExp', range(this_year, this_year + 12)))}
</table><input type="hidden" name="memberAction" id="idMemberAction" value="">
<input type="button" name="add" value="Add Member"
  onclick="document.getElementById('idMemberAction').value='add'; this.form.submit();">
<input type="button" name="next" value="Next"
  onclick="document.getElementById('idMemberAction').value='next'; this.form.submit();">
</form>""", error, scripts='<script src="js/grp/validateBusinessUI.js"></script>')

    def review_page(self, s: dict) -> str:
        rows = "".join(
            f"<tr><td>{esc(m.get('surname'))}</td><td>{esc(m.get('othernames'))}</td>"
            f"<td>{esc(m.get('passportno') or m.get('passportNo'))}</td></tr>" for m in s["members"])
        return page("Review Information", f"""
<p>Please review your application and confirm.</p>
<table border="1"><tr><th>Surname</th><th>Other Names</th><th>Passport</th></tr>{rows}</table>
<form method="post" action="etaNavServ" name="form2">
<input type="hidden" name="actiontype" id="idActiontype" value="1">
<input type="button" value="Edit" onclick="history.back()">
<input type="button" value="Confirm" onclick="confirmForm(this);">
</form>""", scripts='<script src="js/com/etafunctional.js"></script>')

    def payment_options_page(self, s: dict) -> str:
        total = FEE_USD * len(s["members"])
        return page("Payment Options", f"""
<p>Your application has been submitted. ETA Reference No : <strong>{esc(s['reference'])}</strong></p>
<p>Applicants: {len(s['members'])} &mdash; Amount due: {total}.00 USD</p>
<form method="post" action="/ipg/checkout"><input type="hidden" name="ref" value="{esc(s['reference'])}">
<input type="radio" id="pmCard" name="payMethod" value="CARD"><label for="pmCard">Visa / Master Card</label>
<input type="submit" value="Pay Now"></form>""")

    def gateway_page(self, token: str) -> str:
        p = PAYMENTS.get(token)
        if not p:
            return page("Error", "<p>Unknown payment session.</p>")
        return page("Secure Payment Gateway", f"""
<p>Merchant: Department of Immigration &amp; Emigration &mdash; Ref. {esc(p['ref'])} &mdash; {p['amount']}.00 USD</p>
<iframe src="/ipg/card-frame?session={esc(token)}" width="100%" height="420" title="Card"></iframe>""")

    def card_frame(self, token: str) -> str:
        p = PAYMENTS.get(token, {"amount": 0})
        months = "".join(f'<option value="{m:02d}">{m:02d}</option>' for m in range(1, 13))
        years = "".join(f'<option value="{y}">{y}</option>' for y in range(date.today().year, date.today().year + 12))
        return f"""<!doctype html><html><body><form method="post" action="/ipg/submit" target="_top">
<input type="hidden" name="session" value="{esc(token)}">
<label for="holder">Cardholder name</label><input id="holder" name="cardHolder" autocomplete="cc-name">
<label for="num">Card number</label><input id="num" name="cardNumber" autocomplete="cc-number">
<label for="mm">Month</label><select id="mm" name="expMonth"><option value="">MM</option>{months}</select>
<label for="yy">Year</label><select id="yy" name="expYear"><option value="">YYYY</option>{years}</select>
<label for="cvc">CVV</label><input id="cvc" name="cvc" autocomplete="cc-csc">
<button type="submit">Pay {p['amount']}.00 USD</button></form></body></html>"""


def serve(port: int = 8765, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Mock ETA portal on http://127.0.0.1:{args.port}/etaslvisa/pages/termnconuser.jsp?ucode=123")
    server.serve_forever()


if __name__ == "__main__":
    main()
