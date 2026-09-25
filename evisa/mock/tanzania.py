"""Local stand-in for https://visa.immigration.go.tz, used for demos and tests.

/start and /continueapplication mirror the live forms (field names, labels,
security questions and country spellings observed in September 2026). The
tabs behind them follow the Immigration Department's guidelines (Personal,
Travel, Attachments, Declaration, Payment; card payment on an external
checkout; "upon successful payment, submit your application") and
deliberately mix markup styles (radios, readonly datepickers, native date
inputs, unlabeled inputs, uploads that reject ".jpg") so the automation's
fallbacks are exercised. They are not copies of the real tabs.
"""

from __future__ import annotations

import secrets
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pycountry

from ..sites.tanzania.data import PORTS_OF_ENTRY
from .gateway import MockCardGateway
from .server import MockApp, Request, Response, esc, with_query

# As on the live portal, including its spelling.
SECURITY_QUESTIONS = [
    "In what city/town/village you were  born?",
    "what is the name of the hospital you ware born?",
    "what is the name of the street you grew up?",
    "What was your childhood nickname?",
]
VISA_TYPES = {"1": ("Ordinary Visa", Decimal(50)), "2": ("Multiple Entry Visa", Decimal(100)),
              "3": ("Business Visa", Decimal(250)), "4": ("Transit Visa", Decimal(30))}
PURPOSES = ["Holiday / Tourism", "Business", "Visiting Family / Friends", "Conference / Meeting", "Medical Treatment", "Transit", "Study", "Other"]
MARITAL = ["Single", "Married", "Divorced", "Widowed"]
OCCUPATIONS = ["Accountant", "Architect", "Business Person", "Doctor", "Engineer", "Farmer", "Lawyer", "Nurse", "Pilot",
               "Retired", "Student", "Teacher", "Unemployed", "Other"]
TABS = [("personal", "Personal Information"), ("travel", "Travel Information"), ("attachments", "Attachments"),
        ("declaration", "Declaration"), ("payment", "Payment")]
UPLOADS = {
    "PassportBioPage": ("Passport Bio Data Page (JPEG/PNG, max 300 KB)", ("jpeg", "png"), 300),
    "Photo": ("Passport Size Photo (JPEG, max 500 KB)", ("jpeg",), 500),
    "ReturnTicket": ("Return Ticket (PDF, max 1 MB)", ("pdf",), 1024),
    "HotelBooking": ("Hotel Booking / Invitation Letter (PDF/JPEG/PNG, max 1 MB)", ("pdf", "jpeg", "png"), 1024),
}
_MAGIC = {"jpeg": b"\xff\xd8\xff", "png": b"\x89PNG", "pdf": b"%PDF"}

# Upper-case labels with numeric ids, spelled like the live portal where known.
_LIVE_SPELLING = {"USA": "UNITED STATES OF AMERICA", "TZA": "TANZANIA, THE UNITED REPUBLIC", "GBR": "UNITED KINGDOM"}
COUNTRIES = [(str(i + 1), _LIVE_SPELLING.get(c.alpha_3, c.name.upper()), c.alpha_3)
             for i, c in enumerate(sorted(pycountry.countries, key=lambda c: c.name))]
COUNTRY_BY_ID = {cid: (label, a3) for cid, label, a3 in COUNTRIES}

_STYLE = """
body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#eef2f0;color:#222}
header{background:#0b5d3b;color:#fff;padding:14px 28px}header h1{margin:0;font-size:22px}
nav.tabs{display:flex;gap:4px;padding:10px 28px;background:#dfe9e4}
nav.tabs span{padding:8px 14px;border-radius:6px 6px 0 0;background:#c9d9d1}nav.tabs span.active{background:#fff;font-weight:600}
nav.tabs span.done:after{content:' \\2714';color:#0b5d3b}
main{max-width:860px;margin:18px auto;background:#fff;padding:24px 32px;border-radius:8px}
.form-group{margin:12px 0}.form-group label{display:block;font-weight:600;margin-bottom:4px}
input[type=text],input[type=email],input[type=tel],input[type=date],select,textarea{width:100%;padding:7px;box-sizing:border-box}
.field-validation-error{color:#c00;font-size:13px}.validation-summary-errors{color:#c00}
button,.btn{background:#0b5d3b;color:#fff;border:0;padding:10px 18px;border-radius:5px;font-size:15px;text-decoration:none;display:inline-block}
table.summary td{padding:3px 10px;border-bottom:1px solid #eee}.appid{background:#fff8d6;padding:10px;border-radius:6px}
"""


def _parse_dmy(value: str) -> date | None:
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _parse_iso(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


class MockTanzaniaPortal(MockApp):
    session_cookie = "tz_evisa_session"

    def __init__(self, gateway: MockCardGateway) -> None:
        super().__init__()
        self.gateway = gateway
        self.applications: dict[str, dict[str, Any]] = {}
        r = self.route
        r("GET", "/", self._home)
        r("GET", "/start", self._start_form)
        r("POST", "/start", self._start_submit)
        r("GET", "/continueapplication", self._continue_form)
        r("POST", "/continueapplication", self._continue_submit)
        r("GET", "/application/(?P<tab>personal|travel|attachments|declaration)", self._tab)
        r("POST", "/application/(?P<tab>personal|travel|attachments|declaration)", self._tab_submit)
        r("GET", "/payment", self._payment)
        r("POST", "/payment", self._payment_submit)
        r("GET", "/payment/callback", self._payment_callback)
        r("POST", "/application/submit", self._submit_after_payment)

    # ------------------------------------------------------------ rendering

    def _layout(self, title: str, body: str, app: dict | None = None, tab: str | None = None) -> Response:
        tabs = ""
        if app is not None:
            spans = "".join(
                f"<span class='{'active' if key == tab else ''} {'done' if key in app['done'] else ''}'>{label}</span>" for key, label in TABS
            )
            tabs = f"<nav class='tabs'>{spans}</nav>"
            body = f"<p class='appid'>Application ID: <b>{esc(app['id'])}</b></p>" + body
        return Response(f"<!doctype html><html><head><meta charset='utf-8'><title>Tanzania eVisa - {esc(title)}</title>"
                        f"<style>{_STYLE}</style></head><body><header><h1>Tanzania eVisa (MOCK PORTAL)</h1>"
                        f"<small>Local test double - no data leaves this machine</small></header>{tabs}<main>{body}</main></body></html>")

    @staticmethod
    def _err(errors: dict[str, str], name: str) -> str:
        return f"<span class='field-validation-error'>{esc(errors[name])}</span>" if name in errors else ""

    def _text(self, label: str, name: str, values: dict, errors: dict, *, kind: str = "text", attrs: str = "") -> str:
        return (f"<div class='form-group'><label for='{name}'>{esc(label)}</label>"
                f"<input type='{kind}' id='{name}' name='{name}' value='{esc(values.get(name, ''))}' {attrs}>{self._err(errors, name)}</div>")

    def _textarea(self, label: str, name: str, values: dict, errors: dict) -> str:
        return (f"<div class='form-group'><label for='{name}'>{esc(label)}</label>"
                f"<textarea id='{name}' name='{name}' rows='2'>{esc(values.get(name, ''))}</textarea>{self._err(errors, name)}</div>")

    def _select(self, label: str, name: str, options: list[tuple[str, str]], values: dict, errors: dict) -> str:
        opts = "<option value=''>-- Select --</option>" + "".join(
            f"<option value='{esc(v)}' {'selected' if values.get(name) == v else ''}>{esc(t)}</option>" for v, t in options)
        return (f"<div class='form-group'><label for='{name}'>{esc(label)}</label>"
                f"<select id='{name}' name='{name}'>{opts}</select>{self._err(errors, name)}</div>")

    def _datepicker(self, label: str, name: str, values: dict, errors: dict) -> str:
        # Readonly text + JS picker: typing is impossible, like many jQuery datepickers.
        return self._text(label, name, values, errors, attrs="readonly class='datepicker' placeholder='dd/mm/yyyy' "
                          "onclick=\"this.removeAttribute('readonly')\"")

    def _app(self, req: Request) -> dict | None:
        app_id = req.session.get("app_id")
        return self.applications.get(app_id) if app_id else None

    def _require(self, req: Request) -> dict | Response:
        app = self._app(req)
        if app is None:
            return Response.redirect(with_query("/continueapplication", ReturnUrl=req.path))
        return app

    # ------------------------------------------------------------ start / resume

    def _home(self, req: Request) -> Response:
        return self._layout("Welcome", """
            <h2>Welcome to the Tanzania eVisa (mock)</h2>
            <p>Fill in the online form, make payment and submit your application online.</p>
            <p><a class='btn' href='/start'>New Application</a>
               <a class='btn' href='/continueapplication'>Continue an existing Application</a></p>""")

    def _start_form(self, req: Request, values: dict | None = None, errors: dict | None = None) -> Response:
        values, errors = values or {}, errors or {}
        countries = [(cid, label) for cid, label, _ in COUNTRIES]
        questions = [(str(i + 1), q) for i, q in enumerate(SECURITY_QUESTIONS)]
        summary = "<div class='validation-summary-errors'><ul><li>Please correct the errors below.</li></ul></div>" if errors else ""
        return self._layout("Start", f"""
            <h2>Start New Application</h2>{summary}
            <form method='post' action='/start'>
              {self._text("Email", "Email", values, errors, kind="email")}
              {self._text("Passport Number", "PassportNumber", values, errors)}
              {self._select("Passport Issue Country", "IssuedCountryID", countries, values, errors)}
              {self._select("Security Question", "SecurityQuestion", questions, values, errors)}
              {self._text("Security Answer", "SecurityAnswer", values, errors)}
              <div class='form-group mock-captcha'><label><input type='checkbox' id='mock-captcha' name='captcha'> I'm not a robot</label>
                {self._err(errors, 'ReCaptcha')}</div>
              <button type='submit' name='submitPI'>Start New Application <span>|</span></button>
            </form>""")

    def _start_submit(self, req: Request) -> Response:
        f = req.form
        errors = {}
        for name in ("Email", "PassportNumber", "IssuedCountryID", "SecurityQuestion", "SecurityAnswer"):
            if not f.get(name, "").strip():
                errors[name] = "This field is required."
        if f.get("captcha") != "on":
            errors["ReCaptcha"] = "Please confirm you are not a robot."
        if errors:
            return self._start_form(req, f, errors)
        app_id = "TZEV" + "".join(secrets.choice("0123456789") for _ in range(8))
        self.applications[app_id] = {
            "id": app_id, "email": f["Email"], "passport_number": f["PassportNumber"],
            "issue_country": COUNTRY_BY_ID[f["IssuedCountryID"]][1],
            "question": SECURITY_QUESTIONS[int(f["SecurityQuestion"]) - 1], "answer": f["SecurityAnswer"],
            "personal": {}, "travel": {}, "files": {}, "done": set(), "status": "Draft", "payment": None,
        }
        req.session["app_id"] = app_id
        return self._layout("Application created", f"""
            <h2>Application created</h2>
            <p>Your Application ID is <b id='application-id'>{app_id}</b>. It has also been sent to {esc(f['Email'])}.</p>
            <p>Keep it together with your security question and answer: you need them to continue or check your application.</p>
            <a class='btn' href='/application/personal'>Continue</a>""")

    def _continue_form(self, req: Request, error: str = "") -> Response:
        questions = [(str(i + 1), q) for i, q in enumerate(SECURITY_QUESTIONS)]
        err = f"<div class='validation-summary-errors'>{esc(error)}</div>" if error else ""
        return_url = req.query.get("ReturnUrl", "/application/personal")
        return self._layout("Continue an existing Application", f"""
            <h2>Continue an existing Application</h2>{err}
            <form method='post' action='{esc(with_query('/continueapplication', ReturnUrl=return_url))}'>
              {self._text("Application ID", "UserID", {}, {})}
              {self._text("Email", "Email", {}, {}, kind="email")}
              {self._select("Security Question", "SecurityQuestion", questions, {}, {})}
              {self._text("Security Answer", "SecurityAnswer", {}, {})}
              <button type='submit' name='submitPI'>Continue Application <span>|</span></button>
            </form>""")

    def _continue_submit(self, req: Request) -> Response:
        f = req.form
        app = self.applications.get(f.get("UserID", "").strip())
        qid = f.get("SecurityQuestion", "")
        ok = (app is not None and app["email"].lower() == f.get("Email", "").strip().lower()
              and qid.isdigit() and SECURITY_QUESTIONS[int(qid) - 1] == app["question"]
              and app["answer"].strip().lower() == f.get("SecurityAnswer", "").strip().lower())
        if not ok:
            return self._continue_form(req, "The details you entered do not match any application.")
        req.session["app_id"] = app["id"]
        target = req.query.get("ReturnUrl", "/application/personal")
        return Response.redirect(target if target.startswith("/") else "/application/personal")

    # -------------------------------------------------------------------- tabs

    def _tab(self, req: Request, errors: dict | None = None, values: dict | None = None) -> Response:
        app = self._require(req)
        if isinstance(app, Response):
            return app
        tab = req.params["tab"]
        errors = errors or {}
        values = values if values is not None else app.get(tab, {}) if tab in ("personal", "travel") else {}
        body = getattr(self, f"_render_{tab}")(app, values, errors)
        summary = "<div class='validation-summary-errors'><ul><li>Please correct the highlighted fields.</li></ul></div>" if errors else ""
        enctype = "enctype='multipart/form-data'" if tab == "attachments" else ""
        return self._layout(dict(TABS)[tab], f"<h2>{dict(TABS)[tab]}</h2>{summary}<form method='post' {enctype}>{body}"
                            f"<button type='submit'>Save and Continue</button></form>", app, tab)

    def _render_personal(self, app: dict, v: dict, e: dict) -> str:
        countries = [(cid, label) for cid, label, _ in COUNTRIES]
        gender = "".join(
            f"<label style='display:inline;font-weight:normal;margin-right:14px'><input type='radio' name='Gender' value='{code}' "
            f"{'checked' if v.get('Gender') == code else ''}> {label}</label>" for code, label in (("M", "Male"), ("F", "Female")))
        return f"""
            {self._text("Surname", "Surname", v, e)}
            {self._text("First Name", "FirstName", v, e)}
            {self._text("Middle Name", "MiddleName", v, e)}
            <div class='form-group'><fieldset style='border:0;padding:0'><legend><b>Gender</b></legend>{gender}</fieldset>{self._err(e, 'Gender')}</div>
            {self._datepicker("Date of Birth", "DateOfBirth", v, e)}
            {self._text("Place of Birth", "PlaceOfBirth", v, e)}
            {self._select("Country of Birth", "CountryOfBirthId", countries, v, e)}
            {self._select("Nationality", "NationalityId", countries, v, e)}
            {self._select("Marital Status", "MaritalStatusId", [(m, m) for m in MARITAL], v, e)}
            {self._select("Occupation", "OccupationId", [(o, o) for o in OCCUPATIONS], v, e)}
            {self._text("Father's Full Name", "FatherName", v, e)}
            {self._text("Mother's Full Name", "MotherName", v, e)}
            {self._text("Mobile Number", "MobileNumber", v, e, kind="tel")}
            {self._textarea("Residential Address", "ResidentialAddress", v, e)}
            {self._select("Passport Type", "PassportTypeId", [(t, t) for t in ("Ordinary", "Diplomatic", "Service")], v, e)}
            {self._text("Passport Issue Date", "PassportIssueDate", v, e, kind="date")}
            {self._text("Passport Expiry Date", "PassportExpiryDate", v, e, kind="date")}
            {self._text("Issuing Authority", "IssuingAuthority", v, e)}"""

    def _render_travel(self, app: dict, v: dict, e: dict) -> str:
        nationality = COUNTRY_BY_ID.get(app["personal"].get("NationalityId", ""), ("", ""))[1]
        visa_types = [("2", VISA_TYPES["2"][0])] if nationality == "USA" else [(k, t) for k, (t, _) in VISA_TYPES.items()]
        ports = [(p, p) for p in PORTS_OF_ENTRY]
        countries = [(cid, label) for cid, label, _ in COUNTRIES]
        return f"""
            {self._select("Visa Type", "VisaTypeId", visa_types, v, e)}
            {self._select("Purpose of Visit", "PurposeId", [(p, p) for p in PURPOSES], v, e)}
            {self._datepicker("Intended Date of Arrival", "ArrivalDate", v, e)}
            {self._datepicker("Intended Date of Departure", "DepartureDate", v, e)}
            {self._text("Duration of Stay (days)", "Duration", v, e)}
            {self._select("Port of Entry", "PortOfEntryId", ports, v, e)}
            {self._select("Port of Exit", "PortOfExitId", ports, v, e)}
            {self._select("Country of Departure", "DepartureCountryId", countries, v, e)}
            {self._text("Airline / Carrier", "Airline", v, e)}
            <div class='form-group'><input type='text' name='FlightNumber' placeholder='Flight number' value='{esc(v.get('FlightNumber', ''))}'></div>
            {self._textarea("Physical Address in Tanzania", "PhysicalAddress", v, e)}
            {self._text("Name of Hotel or Host", "HotelName", v, e)}
            {self._text("Contact Phone in Tanzania", "ContactPhone", v, e, kind="tel")}"""

    def _render_attachments(self, app: dict, v: dict, e: dict) -> str:
        rows = []
        for name, (label, formats, _) in UPLOADS.items():
            accept = ",".join(f".{f}" for f in formats)
            have = app["files"].get(name)
            note = f"<small>Uploaded: {esc(have['filename'])}</small>" if have else ""
            rows.append(f"<div class='form-group'><label for='{name}'>{esc(label)}</label>"
                        f"<input type='file' id='{name}' name='{name}' accept='{accept}'>{note}{self._err(e, name)}</div>")
        return "".join(rows)

    def _render_declaration(self, app: dict, v: dict, e: dict) -> str:
        p, t = app["personal"], app["travel"]
        rows = [
            ("Name", f"{p.get('FirstName', '')} {p.get('MiddleName', '')} {p.get('Surname', '')}"),
            ("Passport", app["passport_number"]), ("Nationality", COUNTRY_BY_ID.get(p.get("NationalityId", ""), ("",))[0]),
            ("Visa type", VISA_TYPES.get(t.get("VisaTypeId", ""), ("",))[0]), ("Arrival", t.get("ArrivalDate", "")),
            ("Port of entry", t.get("PortOfEntryId", "")), ("Documents", ", ".join(f["filename"] for f in app["files"].values())),
        ]
        table = "".join(f"<tr><td>{esc(k)}</td><td>{esc(val)}</td></tr>" for k, val in rows)
        return f"""<table class='summary'>{table}</table>
            <div class='form-group'><label><input type='checkbox' name='Declaration' value='true'>
              I hereby declare that the information I have given in this application is true and correct.</label>{self._err(e, 'Declaration')}</div>"""

    def _tab_submit(self, req: Request) -> Response:
        app = self._require(req)
        if isinstance(app, Response):
            return app
        tab = req.params["tab"]
        errors = getattr(self, f"_validate_{tab}")(app, req)
        if errors:
            return self._tab(req, errors, dict(req.form))
        app["done"].add(tab)
        if tab == "declaration":
            app["status"] = "Submitted - awaiting payment"
            return Response.redirect("/payment")
        next_tab = TABS[[k for k, _ in TABS].index(tab) + 1][0]
        return Response.redirect(f"/application/{next_tab}")

    @staticmethod
    def _required(form: dict, names: list[str]) -> dict[str, str]:
        return {n: "This field is required." for n in names if not form.get(n, "").strip()}

    def _validate_personal(self, app: dict, req: Request) -> dict[str, str]:
        f = req.form
        e = self._required(f, ["Surname", "FirstName", "Gender", "DateOfBirth", "PlaceOfBirth", "NationalityId", "OccupationId",
                               "MobileNumber", "PassportIssueDate", "PassportExpiryDate"])
        if f.get("DateOfBirth") and not _parse_dmy(f["DateOfBirth"]):
            e["DateOfBirth"] = "Use dd/mm/yyyy."
        issue, expiry = _parse_iso(f.get("PassportIssueDate", "")), _parse_iso(f.get("PassportExpiryDate", ""))
        if f.get("PassportIssueDate") and not issue:
            e["PassportIssueDate"] = "Invalid date."
        if issue and expiry and expiry <= issue:
            e["PassportExpiryDate"] = "Expiry date must be after the issue date."
        if not e:
            app["personal"] = dict(f)
        return e

    def _validate_travel(self, app: dict, req: Request) -> dict[str, str]:
        f = req.form
        e = self._required(f, ["VisaTypeId", "PurposeId", "ArrivalDate", "PortOfEntryId", "PhysicalAddress"])
        arrival = _parse_dmy(f.get("ArrivalDate", ""))
        if f.get("ArrivalDate") and not arrival:
            e["ArrivalDate"] = "Use dd/mm/yyyy."
        elif arrival and arrival <= date.today():
            e["ArrivalDate"] = "Arrival date must be in the future."
        departure = _parse_dmy(f.get("DepartureDate", "")) if f.get("DepartureDate") else None
        if arrival and departure and departure < arrival:
            e["DepartureDate"] = "Departure must be after arrival."
        expiry = _parse_iso(app["personal"].get("PassportExpiryDate", ""))
        if arrival and expiry and (expiry - arrival).days < 182:
            e["ArrivalDate"] = "Passport must be valid for at least six months from the date of arrival."
        nationality = COUNTRY_BY_ID.get(app["personal"].get("NationalityId", ""), ("", ""))[1]
        if nationality == "USA" and f.get("VisaTypeId") not in ("2", ""):
            e["VisaTypeId"] = "Citizens of the United States must apply for a Multiple Entry Visa."
        if not e:
            app["travel"] = dict(f)
        return e

    def _validate_attachments(self, app: dict, req: Request) -> dict[str, str]:
        e: dict[str, str] = {}
        for name, (label, formats, max_kb) in UPLOADS.items():
            upload = req.files.get(name)
            if upload is None:
                if name not in app["files"]:
                    e[name] = "Please attach this document."
                continue
            ext = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
            if ext not in formats:
                e[name] = f"Only {', '.join('.' + f for f in formats)} files are allowed."
            elif not upload.content.startswith(_MAGIC[ext]):
                e[name] = "The file content does not match its extension."
            elif len(upload.content) > max_kb * 1024:
                e[name] = f"The file must not exceed {max_kb} KB."
            else:
                app["files"][name] = {"filename": upload.filename, "size": len(upload.content)}
        return e

    def _validate_declaration(self, app: dict, req: Request) -> dict[str, str]:
        return {} if req.form.get("Declaration") == "true" else {"Declaration": "You must accept the declaration."}

    # ----------------------------------------------------------------- payment

    def _fee(self, app: dict) -> tuple[str, Decimal]:
        return VISA_TYPES.get(app["travel"].get("VisaTypeId", "1"), VISA_TYPES["1"])

    def _payment(self, req: Request) -> Response:
        app = self._require(req)
        if isinstance(app, Response):
            return app
        if "declaration" not in app["done"]:
            return Response.redirect("/application/personal")
        visa, fee = self._fee(app)
        if app["payment"] and app["payment"]["status"] == "approved":
            return self._paid_page(app)
        methods = "".join(
            f"<label style='display:block;font-weight:normal'><input type='radio' name='PaymentMethod' value='{v}'> {t}</label>"
            for v, t in (("card", "Visa/Mastercard"), ("bank", "Bank Deposit")))
        return self._layout("Payment", f"""
            <h2>Payment</h2>
            <p>Visa Type: {esc(visa)}</p><p>Amount: <b id='amount'>USD {fee:.2f}</b></p><p>Payment Status: Pending</p>
            <form method='post' action='/payment' target='_blank'>
              <div class='form-group'><fieldset style='border:0;padding:0'><legend><b>Payment Method</b></legend>{methods}</fieldset></div>
              <button type='submit'>Pay Now</button>
            </form>
            <p><small>If your payment is unsuccessful, contact your bank and try again.</small></p>""", app, "payment")

    def _payment_submit(self, req: Request) -> Response:
        app = self._require(req)
        if isinstance(app, Response):
            return app
        if req.form.get("PaymentMethod") != "card":
            return self._layout("Payment", "<p class='field-validation-error'>Please choose Visa/Mastercard.</p>", app, "payment")
        _, fee = self._fee(app)
        session = self.gateway.create_session(
            merchant="Tanzania Immigration Services Department (mock)", reference=app["id"], amount=fee, currency="USD",
            return_url=f"{self.base_url}/payment/callback",
        )
        app["payment"] = {"token": session.token, "status": "pending", "receipt": ""}
        return Response.redirect(self.gateway.checkout_url(session))

    def _paid_page(self, app: dict) -> Response:
        if app["status"].startswith("Submitted") or app["status"].startswith("Under processing"):
            tail = f"<p>Application {esc(app['id'])} has been submitted for processing.</p>"
        else:
            tail = ("<form method='post' action='/application/submit'><p>Upon successful payment, submit your application.</p>"
                    "<button type='submit'>Submit Application</button></form>")
        return self._layout("Payment", f"""<h2>Payment successful</h2><p>Payment Status: <b>PAID</b></p>
            <p>Receipt No: <b>{esc(app['payment']['receipt'])}</b></p>{tail}""", app, "payment")

    def _submit_after_payment(self, req: Request) -> Response:
        app = self._require(req)
        if isinstance(app, Response):
            return app
        if not (app["payment"] and app["payment"]["status"] == "approved"):
            return self._layout("Payment", "<p class='field-validation-error'>Please pay before submitting.</p>", app, "payment")
        app["status"] = "Under processing"
        return self._paid_page(app)

    def _payment_callback(self, req: Request) -> Response:
        token = req.query.get("token", "")
        app = next((a for a in self.applications.values() if a["payment"] and a["payment"]["token"] == token), None)
        session = self.gateway.sessions.get(token)
        if app is None or session is None:
            return self._layout("Payment", "<p class='field-validation-error'>Unknown payment.</p>")
        if session.status == "approved":
            if app["payment"]["status"] != "approved":
                app["payment"].update(status="approved", receipt=f"TZR-{secrets.token_hex(4).upper()}", last4=session.last4)
                app["status"] = "Paid - not yet submitted"
            return self._paid_page(app)
        app["payment"]["status"] = session.status
        return self._layout("Payment", "<h2 class='field-validation-error'>Payment failed: your card was declined.</h2>"
                            "<p><a href='/payment'>Try again</a></p>", app, "payment")
