"""Local stand-in for the Sri Lanka ETA portal (https://eta.gov.lk).

The terms page, the visa-type/mode selection, the individual form and the
group travel/contact page mirror markup observed on the live portal in
September 2026: captions in table cells (no <label>s), fields identified by
`name`, mm-dd-yyyy dates with "re-enter" copies, three yes/no questions, a
confirmation box, a CAPTCHA and JavaScript alert() validation. Group member
pages, review, payment options and the card gateway could not be observed
without submitting real data; they are plausible stand-ins.
"""

from __future__ import annotations

import secrets
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pycountry

from .gateway import MockCardGateway
from .server import MockApp, Request, Response, esc

FEE_PER_TRAVELLER = Decimal(50)
TITLES = [("07|DR", "DR"), ("05|MASTER", "MASTER"), ("03|MISS", "MISS"), ("01|MR", "MR"), ("02|MRS", "MRS"), ("04|MS", "MS"), ("06|REV", "REV")]
PURPOSES = [
    ("V10|M.I.C.E Tourism", "M.I.C.E Tourism (Meetings, Incentives, Conferences & Exhibitions/Events)"),
    ("V03|Medical treatment", "Medical treatment including Ayurvedic (herbal)"),
    ("V14|Art, Music, Dance", "Participate in Art, Music, and Dance Events"),
    ("V12|Pilgrimages", "Participate in Pilgrimages"),
    ("V13|Sport Events", "Participate in Sport Events"),
    ("V11|Weddings", "Participate in Weddings"),
    ("V01|Sightseeing or Holidaying", "Sightseeing or Holidaying"),
    ("V02|Visiting friends and relatives", "Visiting friends and relatives"),
]
QUESTIONS = [
    ("QN1", "Do you have a valid residence visa to Sri Lanka?"),
    ("QN2", "Are you currently in Sri Lanka with a valid ETA or obtained an extension of visa?"),
    ("QN3", "Do you have a multiple entry visa to Sri Lanka?"),
]
APP_TYPES = {"1": ("Tourist", "individual"), "2": ("Tourist", "group"), "21": ("Business", "individual"),
             "32": ("Business", "group"), "5": ("Transit", "individual"), "6": ("Transit", "group")}


def _country_options() -> list[tuple[str, str]]:
    opts = []
    for c in sorted(pycountry.countries, key=lambda c: c.name):
        code = "D" if c.alpha_3 == "DEU" else c.alpha_3
        label = "GERMANY (Deutschland) (D)" if code == "D" else f"{c.name.upper()} ({code})"
        opts.append((f"{code}|{label}", label))
    return opts


COUNTRIES = _country_options()

_STYLE = """
body{font-family:Verdana,Arial,sans-serif;font-size:12px;background:#f2f2f2;margin:0}
.head{background:#8a1538;color:#fff;padding:12px 20px;font-size:18px}
.box{width:800px;margin:16px auto;background:#fff;padding:16px;border:1px solid #ccc}
td{padding:3px 6px;vertical-align:middle}.inner_text_1{width:220px}.sec{background:#eee;font-weight:bold}
input[type=text],select,textarea{width:280px}
"""

# Client-side validation in the style of the live portal: problems are reported with alert().
_JS = """
function submitform(el){ el.form.submit(); }
function submitformApp(a, formName){ var f=document.forms[formName]; f.appType.value=a.id; f.submit(); }
function val(n){ var e=document.getElementsByName(n)[0]; return e ? e.value.trim() : ''; }
function checkAndSubmit(btn, action){
  var f = btn.form, req = (f.getAttribute('data-required')||'').split(',').filter(Boolean);
  for (var i=0;i<req.length;i++){ var v=val(req[i]); if(!v || v==='0X'){ alert('Please enter ' + req[i]); return; } }
  var pairs = (f.getAttribute('data-repeat')||'').split(',').filter(Boolean);
  for (var j=0;j<pairs.length;j++){ var p=pairs[j].split(':'); if(val(p[0]).toUpperCase()!==val(p[1]).toUpperCase()){ alert(p[1] + ' does not match'); return; } }
  var qs = (f.getAttribute('data-questions')||'').split(',').filter(Boolean);
  for (var k=0;k<qs.length;k++){ if(!f.querySelector('input[name='+qs[k]+']:checked')){ alert('Please answer question ' + qs[k]); return; } }
  if (f.conf && !f.conf.checked){ alert('Please confirm the information is correct'); return; }
  if (f.captcha && !f.captcha.checked){ alert('Please verify that you are not a robot'); return; }
  if (f.action_) f.action_.value = action || 'next';
  f.submit();
}
"""


def _parse(value: str) -> date | None:
    try:
        return datetime.strptime(value.strip(), "%m-%d-%Y").date()
    except ValueError:
        return None


class MockSriLankaPortal(MockApp):
    session_cookie = "JSESSIONID"

    def __init__(self, gateway: MockCardGateway) -> None:
        super().__init__()
        self.gateway = gateway
        self.applications: list[dict[str, Any]] = []
        self.route("GET", "/", self._center)
        self.route("GET", "/slvisa/visainfo/center.jsp", self._center)
        self.route("GET", "/etaslvisa/etaNavServ", self._terms)
        self.route("POST", "/etaslvisa/etaNavServ", self._nav)
        self.route("GET", "/etaslvisa/paymentResult", self._payment_result)

    # ---------------------------------------------------------------- html

    def _page(self, title: str, body: str, alert: str = "") -> Response:
        script = f"<script>alert({alert!r});</script>" if alert else ""
        return Response(f"<!doctype html><html><head><title>{esc(title)}</title><style>{_STYLE}</style><script>{_JS}</script></head>"
                        f"<body><div class='head'>Sri Lanka ETA - Online Visa Application (MOCK PORTAL)</div>"
                        f"<div class='box'>{body}</div>{script}</body></html>")

    @staticmethod
    def _row(caption: str, control: str, required: bool = True) -> str:
        star = "<font color='#FF0000'>*</font>" if required else ""
        return f"<tr><td class='inner_text_1'>{esc(caption)}{star}</td><td>{control}</td></tr>"

    @staticmethod
    def _input(name: str, id_: str = "", **attrs: str) -> str:
        extra = " ".join(f"{k}='{esc(v)}'" for k, v in attrs.items())
        return f"<input type='text' name='{name}' id='{id_ or name}' {extra}>"

    @staticmethod
    def _date(name: str, id_: str = "") -> str:
        return f"<input type='text' name='{name}' id='{id_ or name}' onclick='void(0)' title='mm-dd-yyyy'>"

    @staticmethod
    def _select(name: str, options: list[tuple[str, str]], id_: str = "", placeholder: str = "[Select Please]") -> str:
        opts = f"<option value='0X'>{esc(placeholder)}</option>" + "".join(f"<option value='{esc(v)}'>{esc(t)}</option>" for v, t in options)
        return f"<select name='{name}' id='{id_ or name}'>{opts}</select>"

    def _applicant_rows(self) -> str:
        r = self._row
        return "".join([
            "<tr><td colspan='2' class='sec'>Applicant Information</td></tr>",
            r("Surname/Family Name", self._input("surname")),
            r("Other/Given Names", self._input("othernames")),
            r("Title ", self._select("title", TITLES, placeholder="[Select Title]")),
            r("Date of Birth", self._date("bdate")),
            r("Re Enter Date of Birth", self._date("reenteredbdate")),
            r("Gender", self._select("gender", [("Male", "Male"), ("Female", "Female")], placeholder="[Select Gender]")),
            r("Nationality", self._select("national", COUNTRIES, placeholder="[Select Nationality]")),
            r("Country or Region of Birth", self._select("conbirth", COUNTRIES, placeholder="[Select Country or Region]")),
            r("Occupation", self._input("occupation"), required=False),
            r("Passport Number", self._input("passportno")),
            r("Re Enter Passport Number", self._input("reenteredpassportno")),
            r("Passport Issued Date", self._date("pidate")),
            r("Passport Expiry Date ", self._date("pedate")),
        ])

    def _travel_rows(self, *, group: bool) -> str:
        r = self._row
        arrival = self._date("arrivalDate", "idArrivalDate") if group else self._date("iadate")
        return "".join([
            "<tr><td colspan='2' class='sec'>Travel Information</td></tr>",
            r("Where you have been during last 14 days before this travel", self._select("fromDeparture", COUNTRIES, placeholder="[Select Departure Country]")),
            r("Visa Required Days ", self._select("RequestedVisaDays", [("30", "30"), ("90", "90")])),
            r("Intended Arrival Date", arrival),
            r("Purpose of Visit", self._select("puofvisit", PURPOSES)),
            r("Port of Departure", self._input("depcity"), required=False),
            r("Airline/Vessel", self._input("airline"), required=False),
            r("Flight/Vessel Number", self._input("flightno"), required=False),
        ])

    def _contact_rows(self, *, group: bool) -> str:
        r = self._row

        def n(individual_name: str, group_name: str) -> str:
            return group_name if group else individual_name

        return "".join([
            "<tr><td colspan='2' class='sec'>Contact Details</td></tr>",
            r("Address Line 1", self._input(n("addone", "conAddOne"))),
            r("Address Line 2", self._input(n("addtwo", "contAddTwo")), required=False),
            r("City", self._input(n("city", "contCity"))),
            r("State", self._input(n("state", "contState"))),
            r("Zip/Postal Code", self._input(n("zipcode", "contZipCode")), required=False),
            r("Country or Region", self._select(n("adcountry", "conCountry"), COUNTRIES, placeholder="[Select Country or Region]")),
            r("Address in Sri Lanka", f"<textarea name='{n('addinsl', 'contactAddSL')}'></textarea>"),
            r("Email Address ", self._input(n("email", "contEmail"))),
            r("Re Enter Email Address ", self._input(n("reenteremail", "reEnterEmail"))),
            r("Telephone Number", self._input(n("telephon", "contPhoneNo"))),
            r("Mobile Number", self._input(n("mobileno", "contMobileno")), required=False),
        ])

    @staticmethod
    def _question_rows() -> str:
        rows = "<tr><td colspan='2' class='sec'>Other Details</td></tr>"
        for i, (code, text) in enumerate(QUESTIONS, 1):
            rows += (f"<tr><td class='inner_text_1'>{i} . {esc(text)} <font color='#FF0000'> * </font></td><td>"
                     f"<input type='radio' name='{code}' id='vlrY{code}' value='1'> Yes "
                     f"<input type='radio' name='{code}' id='vlrN{code}' value='0'> No</td></tr>")
        return rows

    @staticmethod
    def _finish_rows(buttons: str) -> str:
        return (f"<tr><td colspan='2'><input name='conf' type='checkbox' value='conf'/> I would like to confirm the above information is correct."
                f" <font color='#FF0000'>*</font></td></tr>"
                f"<tr><td colspan='2' class='g-recaptcha-standin'><label><input type='checkbox' id='mock-captcha' name='captcha'> I'm not a robot</label></td></tr>"
                f"<tr><td></td><td>{buttons}</td></tr>")

    def _app(self, req: Request) -> dict[str, Any] | None:
        idx = req.session.get("app")
        return self.applications[idx] if idx is not None else None

    # --------------------------------------------------------------- pages

    def _center(self, req: Request) -> Response:
        return self._page("Online Visa Application", """
            <p>Home | <a href='#' onclick="window.open('/etaslvisa/etaNavServ?payType=1'); return false;">Apply</a> | Fees | Check Status</p>
            <p>An intended traveller planning a holiday visit, a short business trip or to transit through, needs to apply and obtain an ETA.</p>""")

    def _terms(self, req: Request) -> Response:
        req.session.clear()
        req.session["stage"] = "terms"
        return self._page("Online ETA Application", """
            <form name='form1' method='POST' action='etaNavServ'>
              <input type='hidden' name='payType' value='1'/><input type='hidden' name='appType' value='1000'/>
              <input type='hidden' name='pageNumber' value='1'/>
              <p>Please read the Terms &amp; Conditions before confirming your ETA application.</p>
              <table><tr><td>I Agree</td><td><input type='radio' name='terms' value='agree' onclick='submitform(this);'></td>
                <td>I do not Agree</td><td><input type='radio' name='terms' value='no' onclick='window.close()'></td></tr></table>
            </form>""")

    def _nav(self, req: Request) -> Response:
        page = req.form.get("pageNumber", "")
        handler = {"1": self._selection, "2": self._form, "3": self._individual_submit, "10": self._group_travel_submit,
                   "11": self._member_submit, "20": self._confirm, "30": self._pay}.get(page)
        if handler is None or (page != "1" and "stage" not in req.session):
            return self._page("Session", "", alert="Session Expired !!!!")
        return handler(req)

    def _selection(self, req: Request) -> Response:
        if req.form.get("terms") != "agree":
            return self._page("Terms", "", alert="Please accept the terms and conditions")
        req.session["stage"] = "selection"
        sections = ""
        for title, ids in (("Tourist ETA", ("1", "2", "9")), ("Business Purpose ETA", ("21", "32", "43")), ("Transit ETA", ("5", "6", "11"))):
            links = "".join(f"<li><a href='#' id='{i}' onclick=\"submitformApp(this,'appFormX');\">{t}</a></li>"
                            for i, t in zip(ids, ("Apply for an Individual", "Apply for a Group", "Apply for a Third Party")))
            sections += f"<h3>{title}</h3><ul>{links}</ul>"
        return self._page("Online Visa Application", f"""
            <form name='appFormX' method='POST' action='etaNavServ'>
              <input type='hidden' name='payType' value='1'/><input type='hidden' name='appType' value=''/>
              <input type='hidden' name='appSType' value='0'/><input type='hidden' name='pageNumber' value='2'/>
            </form>{sections}
            <p>1.Submit Application 2.Review Information 3.Payment Options 4.ETA Confirmation</p>""")

    def _form(self, req: Request) -> Response:
        app_type = req.form.get("appType", "")
        if app_type not in APP_TYPES:
            return self._page("Apply", "", alert="This category cannot be applied for online")
        visa, mode = APP_TYPES[app_type]
        self.applications.append({"visa": visa, "mode": mode, "members": [], "travel": {}, "contact": {}, "status": "draft",
                                  "reference": "", "payment": None})
        req.session["app"] = len(self.applications) - 1
        req.session["stage"] = "form"
        if mode == "individual":
            return self._individual_form()
        return self._group_travel_form()

    _APPLICANT_REQUIRED = "surname,othernames,title,bdate,reenteredbdate,gender,national,passportno,reenteredpassportno,pidate,pedate"

    def _individual_form(self) -> Response:
        required = self._APPLICANT_REQUIRED + ",fromDeparture,iadate,puofvisit,addone,city,state,adcountry,addinsl,email,reenteremail,telephon"
        buttons = "<input type='button' id='submitButton' onclick='checkAndSubmit(this)' value='Next'/>"
        return self._page("ETA - Online Visa Application", f"""
            <form name='form1' method='POST' action='etaNavServ' data-required='{required}'
                  data-repeat='bdate:reenteredbdate,passportno:reenteredpassportno,email:reenteremail' data-questions='QN1,QN2,QN3'>
              <input type='hidden' name='pageNumber' value='3'/>
              <p><b>Important - Tourist ETA can be used only for the purpose of Tourism.</b> All information should be entered as per the applicant's passport</p>
              <table>{self._applicant_rows()}{self._travel_rows(group=False)}{self._contact_rows(group=False)}{self._question_rows()}
              {self._finish_rows(buttons)}</table>
            </form>""")

    def _group_travel_form(self) -> Response:
        required = "fromDeparture,arrivalDate,puofvisit,conAddOne,contCity,contState,conCountry,contPhoneNo,contEmail,reEnterEmail"
        return self._page("ETA - Online Visa Application", f"""
            <form name='form1' method='POST' action='etaNavServ' data-required='{required}' data-repeat='contEmail:reEnterEmail'>
              <input type='hidden' name='pageNumber' value='10'/>
              <table>{self._travel_rows(group=True)}{self._contact_rows(group=True)}
              <tr><td></td><td><input type='button' name='next' value='Next' onclick='checkAndSubmit(this)'/></td></tr></table>
            </form>""")

    def _member_form(self, number: int) -> Response:
        buttons = ("<input type='button' value='Add Member' onclick=\"checkAndSubmit(this,'add')\"/> "
                   "<input type='button' id='submitButton' value='Next' onclick=\"checkAndSubmit(this,'next')\"/>")
        return self._page("ETA - Online Visa Application", f"""
            <h3>Group member {number}</h3>
            <form name='form1' method='POST' action='etaNavServ' data-required='{self._APPLICANT_REQUIRED}'
                  data-repeat='bdate:reenteredbdate,passportno:reenteredpassportno' data-questions='QN1,QN2,QN3'>
              <input type='hidden' name='pageNumber' value='11'/><input type='hidden' name='action_' value='next'/>
              <table>{self._applicant_rows()}{self._question_rows()}{self._finish_rows(buttons)}</table>
            </form>""")

    # ------------------------------------------------------------ validation

    @staticmethod
    def _check_applicant(f: dict[str, str]) -> str:
        dates = {k: _parse(f.get(k, "")) for k in ("bdate", "pidate", "pedate")}
        if any(v is None for v in dates.values()):
            return "Please enter dates as mm-dd-yyyy"
        if f.get("bdate") != f.get("reenteredbdate") or f.get("passportno") != f.get("reenteredpassportno"):
            return "Re-entered values do not match"
        if not dates["bdate"] < dates["pidate"] <= date.today() < dates["pedate"]:
            return "Please Insert Valid Passport Issued Date"
        if f.get("national", "0X") == "0X" or f.get("title", "0X") == "0X":
            return "Please select nationality and title"
        return ""

    @staticmethod
    def _check_travel(f: dict[str, str], arrival_key: str) -> str:
        arrival = _parse(f.get(arrival_key, ""))
        if arrival is None or arrival <= date.today():
            return "Please Insert Valid Intended Arrival Date"
        if f.get("puofvisit", "0X") == "0X":
            return "Please select the purpose of visit"
        return ""

    def _member_record(self, f: dict[str, str]) -> dict[str, str]:
        keys = ("title", "surname", "othernames", "bdate", "gender", "national", "conbirth", "occupation", "passportno",
                "pidate", "pedate", "QN1", "QN2", "QN3")
        return {k: f.get(k, "") for k in keys}

    def _individual_submit(self, req: Request) -> Response:
        app, f = self._app(req), req.form
        problem = self._check_applicant(f) or self._check_travel(f, "iadate")
        if problem or f.get("conf") != "conf" or f.get("captcha") != "on":
            return self._page("Error", "<p>Please go back and correct the form.</p>", alert=problem or "Please confirm and verify")
        app["members"] = [self._member_record(f)]
        app["travel"] = {k: f.get(k, "") for k in ("fromDeparture", "RequestedVisaDays", "iadate", "puofvisit", "depcity", "airline", "flightno")}
        app["contact"] = {k: f.get(k, "") for k in ("addone", "addtwo", "city", "state", "zipcode", "adcountry", "addinsl", "email", "telephon")}
        return self._review(req)

    def _group_travel_submit(self, req: Request) -> Response:
        app, f = self._app(req), req.form
        problem = self._check_travel(f, "arrivalDate")
        if problem:
            return self._page("Error", "", alert=problem)
        app["travel"] = {k: f.get(k, "") for k in ("fromDeparture", "RequestedVisaDays", "arrivalDate", "puofvisit", "depcity", "airline", "flightno")}
        app["contact"] = {k: f.get(k, "") for k in ("conAddOne", "contCity", "contState", "conCountry", "contactAddSL", "contEmail", "contPhoneNo")}
        return self._member_form(1)

    def _member_submit(self, req: Request) -> Response:
        app, f = self._app(req), req.form
        problem = self._check_applicant(f)
        if problem or f.get("conf") != "conf" or f.get("captcha") != "on":
            return self._page("Error", "", alert=problem or "Please confirm and verify")
        app["members"].append(self._member_record(f))
        if f.get("action_") == "add":
            return self._member_form(len(app["members"]) + 1)
        if len(app["members"]) < 2:
            return self._page("Error", "", alert="A group needs at least two members")
        return self._review(req)

    # ------------------------------------------------------ review and pay

    def _review(self, req: Request) -> Response:
        app = self._app(req)
        req.session["stage"] = "review"
        rows = "".join(f"<tr><td>{esc(m['surname'])}</td><td>{esc(m['othernames'])}</td><td>{esc(m['passportno'])}</td></tr>" for m in app["members"])
        return self._page("Review Information", f"""
            <h3>Review Information</h3>
            <table border='1'><tr><th>Surname</th><th>Other Names</th><th>Passport</th></tr>{rows}</table>
            <form name='form1' method='POST' action='etaNavServ'><input type='hidden' name='pageNumber' value='20'/>
              <p><input type='submit' value='Confirm'/> <input type='button' value='Edit' onclick='history.back()'/></p>
            </form>""")

    def _confirm(self, req: Request) -> Response:
        app = self._app(req)
        if req.session.get("stage") != "review":
            return self._page("Session", "", alert="Session Expired !!!!")
        app["reference"] = "ETA" + "".join(secrets.choice("0123456789") for _ in range(10))
        app["status"] = "submitted"
        req.session["stage"] = "payment"
        return self._payment_options(app)

    def _payment_options(self, app: dict[str, Any]) -> Response:
        total = FEE_PER_TRAVELLER * len(app["members"])
        return self._page("Payment Options", f"""
            <h3>Payment Options</h3>
            <p>Your application has been received. Reference No: <b>{esc(app['reference'])}</b></p>
            <p>Travellers: {len(app['members'])} - Amount to pay: USD {total:.2f}</p>
            <form name='form1' method='POST' action='etaNavServ'><input type='hidden' name='pageNumber' value='30'/>
              <p><label><input type='radio' name='paymentOption' value='card'> Credit/Debit Card</label>
                 <label><input type='radio' name='paymentOption' value='agent'> Travel agent account</label></p>
              <p><input type='submit' value='Pay Now'/></p>
            </form>""")

    def _pay(self, req: Request) -> Response:
        app = self._app(req)
        if req.form.get("paymentOption") != "card":
            return self._page("Payment", "", alert="Please select a payment option")
        session = self.gateway.create_session(
            merchant="Department of Immigration & Emigration, Sri Lanka (mock)", reference=app["reference"],
            amount=FEE_PER_TRAVELLER * len(app["members"]), currency="USD", return_url=f"{self.base_url}/etaslvisa/paymentResult",
        )
        app["payment"] = {"token": session.token, "status": "pending"}
        return Response.redirect(self.gateway.checkout_url(session))

    def _payment_result(self, req: Request) -> Response:
        token = req.query.get("token", "")
        app = next((a for a in self.applications if a["payment"] and a["payment"]["token"] == token), None)
        session = self.gateway.sessions.get(token)
        if app is None or session is None:
            return self._page("Payment", "<p>Unknown payment.</p>")
        app["payment"]["status"] = session.status
        if session.status == "approved":
            app["status"] = "paid"
            return self._page("ETA Confirmation", f"""<h3>Payment successful</h3>
                <p>Transaction No: {esc(session.auth_code)}{esc(session.token[:6].upper())}</p>
                <p>Reference No: {esc(app['reference'])}. Your ETA confirmation will be emailed to you.</p>""")
        return self._page("Payment", "<h3>Payment failed</h3><p>The transaction was declined by the issuing bank.</p>")
