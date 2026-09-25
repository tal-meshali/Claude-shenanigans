"""Tanzania e-visa portal profile (https://visa.immigration.go.tz).

Portal flow, as documented by the Immigration Department's guidelines and
applicant walkthroughs:

    /start            email, passport number, passport issue country,
                      security question + answer, reCAPTCHA
                      -> "Start New Application" issues an Application ID
    tabs              Personal Information -> Travel Information ->
                      Attachments -> Declaration -> Payment
    /continueapplication?ReturnUrl=/payment
                      resume with Application ID + email + security Q/A

Every locator below lists several candidates (label text first, then likely
ASP.NET MVC names) because the portal changes its markup from time to time.
If the live portal differs, run `evisa inspect` on the page and put the right
selector in a `--selectors` JSON file; no code change needed.
"""

from __future__ import annotations

import re
import secrets
from decimal import Decimal
from functools import partial

from playwright.sync_api import Page

from ...core import countries
from ...core.checkout import ResultPatterns, capture_checkout_url, pay_by_card
from ...core.documents import DocumentRequirement
from ...core.fields import (
    Choice, Field, FieldKind, FieldNotFound, FormError, choose_option, click, fill_form, find, read_options, submit_and_verify,
)
from ...core.models import Applicant, Money, PaymentLink, PaymentOutcome, Trip
from ...core.payment import CardDetails, find_amount, open_external_checkout
from ...core.site import Step, StepContext, VisaSite
from . import data

T, S, D, C, R, F = FieldKind.TEXT, FieldKind.SELECT, FieldKind.DATE, FieldKind.CHECKBOX, FieldKind.RADIO, FieldKind.FILE
OPTIONAL = dict(required=False)

SAVE_AND_CONTINUE = (
    "role=button:Save and Continue", "text=Save and Continue", "input[type='submit'][value*='Save' i]",
    "role=button:Save & Continue", "role=button:Next", "role=button:Continue",
)

APPLICATION_ID_RE = re.compile(r"Application\s*(?:ID|No\.?|Number|Reference)\s*(?:is)?\s*[:#]?\s*([A-Z0-9][A-Z0-9/-]{5,})", re.I)
RESULT_PATTERNS = ResultPatterns(
    paid=re.compile(r"payment\s+(?:was\s+|has\s+been\s+)?(?:successful|received|completed|confirmed)"
                    r"|payment\s+status\s*:?\s*paid|successfully\s+paid", re.I),
    declined=re.compile(r"declined|payment\s+failed|transaction\s+failed|unsuccessful|could not be processed|insufficient funds", re.I),
    receipt=re.compile(r"(?:receipt|reference|transaction)\s*(?:no\.?|number|id)?\s*[:#]\s*([A-Z0-9-]{6,})", re.I),
)


def _given(ctx: StepContext) -> str:
    return ctx.applicant.passport.given_names


def _address_in_tanzania(ctx: StepContext) -> str:
    acc = ctx.trip.accommodation
    return ", ".join(p for p in (acc.name, acc.address, acc.city) if p)


# ------------------------------------------------------------------ field maps

SECURITY_QUESTION = ("label~=Security Question", "select[name*='Question' i]")
PASSPORT_NUMBER = ("label~=Passport Number", "label~=Passport No", "[name*='PassportNumber' i]", "[name*='PassportNo' i]")

START_FIELDS = [
    Field("email", T, ("label=Email", "label~=Email Address", "input[type='email']", "[name='Email' i]"), lambda c: c.applicant.contact.email),
    Field("email_confirm", T, ("label~=Confirm Email", "[name*='ConfirmEmail' i]"), lambda c: c.applicant.contact.email, **OPTIONAL),
    Field("passport_number", T, PASSPORT_NUMBER, lambda c: c.applicant.passport.number),
    Field("passport_country", S, ("label~=Passport Issue Country", "label~=Passport Issuing Country", "label~=Country of Issue",
                                  "label~=Issuing Country", "select[name*='IssueCountry' i]", "select[name*='Country' i]"),
          lambda c: list(countries.country_aliases(c.applicant.passport.issuing_country, c.site.languages)), settle_ms=300),
    Field("security_answer", T, ("label~=Security Answer", "label=Answer", "[name*='SecurityAnswer' i]", "[name*='Answer' i]"),
          lambda c: c.state["security_answer"]),
]

PERSONAL_FIELDS = [
    Field("surname", T, ("label=Surname", "label~=Surname", "label~=Last Name", "label~=Family Name", "[name*='Surname' i]", "[name*='LastName' i]"),
          lambda c: c.applicant.passport.surname),
    Field("given_names", T, ("label~=Given Name", "label~=Other Names", "label~=Forenames", "[name^='GivenName' i]", "[name^='OtherName' i]", "[name^='Forename' i]"),
          _given, **OPTIONAL),
    Field("first_name", T, ("label=First Name", "label~=First Name", "[name*='FirstName' i]"), lambda c: c.applicant.passport.first_name, **OPTIONAL),
    Field("middle_name", T, ("label~=Middle Name", "[name*='MiddleName' i]"), lambda c: c.applicant.passport.middle_names, **OPTIONAL),
    Field("sex", S, ("label=Gender", "label=Sex", "label~=Gender", "select[name*='Gender' i]", "select[name*='Sex' i]",
                     "input[type='radio'][name*='Gender' i]", "input[type='radio'][name*='Sex' i]"),
          lambda c: [c.applicant.passport.sex.label, c.applicant.passport.sex.value]),
    Field("date_of_birth", D, ("label~=Date of Birth", "[name*='DateOfBirth' i]", "[name*='BirthDate' i]", "[name*='DOB' i]"),
          lambda c: c.applicant.passport.date_of_birth),
    Field("place_of_birth", T, ("label~=Place of Birth", "label~=City of Birth", "[name*='PlaceOfBirth' i]", "[name*='BirthPlace' i]"),
          lambda c: c.applicant.passport.place_of_birth),
    Field("country_of_birth", S, ("label~=Country of Birth", "select[name*='BirthCountry' i]", "select[name*='CountryOfBirth' i]"),
          lambda c: list(countries.country_aliases(c.applicant.passport.country_of_birth, c.site.languages)), **OPTIONAL),
    Field("nationality", S, ("label=Nationality", "label~=Current Nationality", "label~=Nationality", "label~=Citizenship",
                             "select[name*='Nationality' i]"),
          lambda c: list(countries.country_aliases(c.applicant.passport.nationality, c.site.languages)), settle_ms=300),
    Field("marital_status", S, ("label~=Marital Status", "select[name*='Marital' i]", "input[type='radio'][name*='Marital' i]"),
          lambda c: c.applicant.marital_status.label, **OPTIONAL),
    Field("occupation", S, ("label~=Occupation", "label~=Profession", "[name*='Occupation' i]", "[name*='Profession' i]"),
          lambda c: Choice([c.applicant.occupation], ["Other", "Others"])),
    Field("father_name", T, ("label~=Father", "[name*='Father' i]"), lambda c: c.applicant.father_name, **OPTIONAL),
    Field("mother_name", T, ("label~=Mother", "[name*='Mother' i]"), lambda c: c.applicant.mother_name, **OPTIONAL),
    Field("phone", T, ("label~=Mobile", "label~=Phone", "label~=Telephone", "input[type='tel']", "[name*='Phone' i]", "[name*='Mobile' i]"),
          lambda c: c.applicant.contact.phone),
    Field("residential_address", T, ("label~=Residential Address", "label~=Home Address", "label~=Permanent Address",
                                     "[name*='ResidentialAddress' i]", "[name*='HomeAddress' i]"),
          lambda c: c.applicant.contact.address.one_line(), **OPTIONAL),
    Field("country_of_residence", S, ("label~=Country of Residence", "select[name*='Residence' i]"),
          lambda c: list(countries.country_aliases(c.applicant.contact.address.country, c.site.languages)), **OPTIONAL),
    Field("passport_type", S, ("label~=Passport Type", "label~=Type of Passport", "select[name*='PassportType' i]"),
          ["Ordinary", "Regular", "Normal", "P"], **OPTIONAL),
    Field("passport_issue_date", D, ("label~=Date of Issue", "label~=Issue Date", "label~=Issued Date", "[name*='IssueDate' i]",
                                     "[name*='DateOfIssue' i]"),
          lambda c: c.applicant.passport.date_of_issue),
    Field("passport_expiry_date", D, ("label~=Date of Expiry", "label~=Expiry Date", "label~=Expiration Date", "[name*='ExpiryDate' i]",
                                      "[name*='DateOfExpiry' i]"),
          lambda c: c.applicant.passport.date_of_expiry),
    Field("passport_authority", T, ("label~=Issuing Authority", "label~=Place of Issue", "[name*='IssuingAuthority' i]", "[name*='PlaceOfIssue' i]"),
          lambda c: c.applicant.passport.issuing_authority, **OPTIONAL),
]

TRAVEL_FIELDS = [
    Field("visa_type", S, ("label~=Visa Type", "label~=Type of Visa", "label~=Visa Category", "select[name*='VisaType' i]",
                           "select[name*='VisaCategory' i]"),
          lambda c: list(data.visa_type_for(c.applicant, c.trip).labels), settle_ms=300),
    Field("purpose", S, ("label~=Purpose of Visit", "label~=Purpose of Travel", "label~=Purpose", "select[name*='Purpose' i]"),
          lambda c: list(data.PURPOSE_LABELS[c.trip.purpose])),
    Field("arrival_date", D, ("label~=Arrival Date", "label~=Date of Arrival", "label~=Intended Date of Entry", "label~=Expected Date of Arrival",
                              "[name*='ArrivalDate' i]", "[name*='EntryDate' i]"),
          lambda c: c.trip.arrival_date),
    Field("departure_date", D, ("label~=Departure Date", "label~=Date of Departure", "[name*='DepartureDate' i]"),
          lambda c: c.trip.departure_date, **OPTIONAL),
    Field("duration", T, ("label~=Duration", "label~=Days of Stay", "label~=Length of Stay", "[name*='Duration' i]"),
          lambda c: str(c.trip.duration_days), **OPTIONAL),
    Field("port_of_entry", S, ("label~=Port of Entry", "label~=Entry Point", "label~=Point of Entry", "select[name*='PortOfEntry' i]",
                               "select[name*='EntryPort' i]"),
          lambda c: data.port_labels(c.trip.port_of_entry)),
    Field("port_of_exit", S, ("label~=Port of Exit", "label~=Exit Point", "label~=Port of Departure", "select[name*='PortOfExit' i]",
                              "select[name*='ExitPort' i]"),
          lambda c: data.port_labels(c.trip.port_of_exit or c.trip.port_of_entry), **OPTIONAL),
    Field("departure_country", S, ("label~=Travelling From", "label~=Country of Departure", "label~=Coming From",
                                   "label~=Country of Embarkation", "select[name*='DepartureCountry' i]", "select[name*='FromCountry' i]"),
          lambda c: list(countries.country_aliases(c.trip.departure_country, c.site.languages)), **OPTIONAL),
    Field("carrier", T, ("label~=Airline", "label~=Carrier", "label~=Means of Transport", "[name*='Airline' i]", "[name*='Carrier' i]"),
          lambda c: c.trip.carrier, **OPTIONAL),
    Field("flight", T, ("label~=Flight Number", "label~=Flight No", "label~=Vessel", "[name*='Flight' i]"),
          lambda c: c.trip.arrival_flight, **OPTIONAL),
    Field("address_in_tanzania", T, ("label~=Physical Address in Tanzania", "label~=Address in Tanzania", "label~=Physical Address",
                                     "label~=Address During Stay", "[name*='PhysicalAddress' i]", "[name*='AddressInTanzania' i]"),
          _address_in_tanzania),
    Field("hotel_name", T, ("label~=Hotel Name", "label~=Name of Hotel", "label~=Accommodation", "label~=Place of Stay", "[name*='Hotel' i]"),
          lambda c: c.trip.accommodation.name, **OPTIONAL),
    Field("region", T, ("label~=Region", "label~=City/Town", "[name*='Region' i]"), lambda c: c.trip.accommodation.city, **OPTIONAL),
    Field("host_name", T, ("label~=Host Name", "label~=Name of Host", "label~=Contact Person", "[name*='HostName' i]"),
          lambda c: c.trip.host.name if c.trip.host else c.trip.accommodation.name, **OPTIONAL),
    Field("host_phone", T, ("label~=Host Phone", "label~=Host Telephone", "label~=Contact Phone in Tanzania", "[name*='HostPhone' i]"),
          lambda c: (c.trip.host.phone if c.trip.host else "") or c.trip.accommodation.phone, **OPTIONAL),
]

ATTACHMENT_LOCATORS: dict[str, tuple[str, ...]] = {
    "passport_scan": ("label~=Passport Bio", "label~=Bio Data", "label~=Biodata", "label~=Passport Copy", "label~=Copy of Passport",
                      "input[type='file'][name*='PassportCopy' i]", "input[type='file'][name*='Bio' i]"),
    "photo": ("label~=Passport Size Photo", "label~=Photograph", "label~=Passport Photo", "label~=Photo",
              "input[type='file'][name*='Photo' i]", "input[type='file'][name*='Picture' i]"),
    "return_ticket": ("label~=Return Ticket", "label~=Flight Ticket", "label~=Ticket", "label~=Itinerary",
                      "input[type='file'][name*='Ticket' i]"),
    "accommodation_proof": ("label~=Hotel Booking", "label~=Hotel Reservation", "label~=Accommodation", "label~=Booking",
                            "input[type='file'][name*='Hotel' i]", "input[type='file'][name*='Accommodation' i]"),
    "invitation_letter": ("label~=Invitation", "label~=Letter", "input[type='file'][name*='Invitation' i]"),
}

DECLARATION_CHECKBOX = (
    "label~=I declare", "label~=I hereby declare", "label~=I have read", "label~=I confirm", "label~=I agree",
    "input[type='checkbox'][name*='Declar' i]", "input[type='checkbox'][name*='Agree' i]", "input[type='checkbox'][name*='Confirm' i]",
)

PAYMENT_METHOD = ("label~=Payment Method", "label~=Payment Option", "select[name*='PaymentMethod' i]",
                  "input[type='radio'][name*='PaymentMethod' i]", "input[type='radio'][name*='PaymentOption' i]")
CARD_METHOD_LABELS = ["Visa/Mastercard", "Visa / MasterCard", "Visa", "Mastercard", "Credit Card", "Card"]
PAY_BUTTONS = ("role=button:Pay Now", "role=button:Make Payment", "role=button:Proceed to Payment", "role=link:Pay Now",
               "role=button:Pay", "input[type='submit'][value*='Pay' i]")

TAB_MARKERS = {
    "personal": ("label~=Surname", "label~=Last Name", "[name*='Surname' i]"),
    "travel": ("label~=Port of Entry", "label~=Visa Type", "label~=Arrival Date"),
    "attachments": ("input[type='file']",),
    "declaration": DECLARATION_CHECKBOX,
    "payment": PAY_BUTTONS + PAYMENT_METHOD,
}


def _on_tab(page: Page, tab: str) -> bool:
    return find(page, TAB_MARKERS[tab]) is not None


class TanzaniaSite(VisaSite):
    key = "tanzania"
    name = "Tanzania"
    default_base_url = "https://visa.immigration.go.tz"
    production_hosts = frozenset({"visa.immigration.go.tz", "eservices.immigration.go.tz"})
    min_passport_validity_months = 6
    document_requirements = (
        DocumentRequirement("passport_scan", "Passport bio-data page", ("jpeg", "png"), 300),
        DocumentRequirement("photo", "Passport-size photo", ("jpeg", "png"), 300),
        DocumentRequirement("return_ticket", "Return / onward ticket", ("pdf",), 1024),
        DocumentRequirement("accommodation_proof", "Hotel booking or invitation", ("pdf", "jpeg", "png"), 1024),
        DocumentRequirement("invitation_letter", "Invitation letter", ("pdf", "jpeg", "png"), 1024, required=False),
    )

    # --------------------------------------------------------------- planning

    def validate(self, batch) -> list[str]:
        problems = super().validate(batch)
        for applicant in batch.applicants:
            trip = batch.trip_for(applicant)
            if not applicant.passport.place_of_birth:
                problems.append(f"{applicant.ref}: passport.place_of_birth is required by the Tanzania form")
            if not trip.port_of_entry:
                problems.append(f"{applicant.ref}: trip.port_of_entry is required (e.g. Kilimanjaro International Airport)")
            try:
                vt = data.visa_type_for(applicant, trip)
            except ValueError as exc:
                problems.append(f"{applicant.ref}: {exc}")
                continue
            if vt.key != "multiple" and trip.duration_days > 90:
                problems.append(f"{applicant.ref}: stays over 90 days need a different visa (trip is {trip.duration_days} days)")
        return problems

    def required_documents(self, applicant: Applicant, trip: Trip):
        reqs = [r for r in self.document_requirements if r.required]
        if data.visa_type_for(applicant, trip).key == "business":
            reqs.append(next(r for r in self.document_requirements if r.kind == "invitation_letter"))
        return reqs

    def fee(self, applicants: list[Applicant], trip: Trip) -> Money:
        total = sum((data.visa_type_for(a, trip).fee_usd for a in applicants), Decimal(0))
        return Money(amount=total, currency="USD")

    # ------------------------------------------------------------------ steps

    def steps(self) -> list[Step]:
        return [
            Step("start-application", self._start),
            Step("personal-information", self._personal),
            Step("travel-information", self._travel),
            Step("attachments", self._attachments),
            Step("declaration", self._declaration),
        ]

    def _fill(self, ctx: StepContext, fields: list[Field]) -> list[str]:
        report = fill_form(ctx.page, fields, ctx, overrides=self.overrides)
        for record in report.filled:
            ctx.state.setdefault("filled", {})[record.key] = record.locator
        return [r.key for r in report.filled]

    def _start(self, ctx: StepContext) -> None:
        page = ctx.page
        wanted_question = ctx.site_extra("security_question", data.DEFAULT_SECURITY_QUESTION)
        ctx.state["security_answer"] = ctx.site_extra("security_answer") or f"evisa-{secrets.token_hex(4)}"

        page.goto(self.url("/start"))
        if not find(page, PASSPORT_NUMBER, timeout_ms=5_000):
            page.goto(self.base_url)
            click(page, ("role=link:New Application", "role=button:New Application", "text=Apply Now", "text=New Application"),
                  what="new application")
        ctx.state["security_question"] = self._choose_security_question(page, wanted_question)
        self._fill(ctx, START_FIELDS)

        declaration = find(page, ("input[type='checkbox'][name*='Agree' i]", "label~=I agree", "label~=I accept"))
        if declaration:
            declaration[0].check()
        ctx.options.captcha_handler()(page)

        start_buttons = ("role=button:Start New Application", "text=Start New Application", "input[type='submit'][value*='Start' i]",
                         "role=button:Start")
        submit_and_verify(page, start_buttons, arrived=lambda: bool(APPLICATION_ID_RE.search(page.inner_text("body"))) or _on_tab(page, "personal"),
                          what="start application")
        match = APPLICATION_ID_RE.search(page.inner_text("body"))
        if match:
            ctx.result.application_id = match.group(1)
            ctx.notify(f"application ID {ctx.result.application_id}")
        if not _on_tab(page, "personal"):
            click(page, ("role=button:Continue", "role=link:Continue", "role=button:Proceed", "role=link:Proceed",
                         "role=link:Personal Information"), what="continue to the form")
            page.wait_for_load_state()

    def _choose_security_question(self, page: Page, wanted: str) -> str:
        """Pick the configured question, or the portal's first one; return it as the portal words it."""
        found = find(page, [*self.overrides.get("security_question", []), *SECURITY_QUESTION], require_visible=False, timeout_ms=3_000)
        if not found:
            raise FieldNotFound("security_question", SECURITY_QUESTION, page.url)
        select = found[0]
        options = read_options(select)
        chosen = choose_option(options, Choice([wanted], [o["label"] for o in options]))
        if chosen is None:
            raise FormError("security question dropdown has no options")
        select.select_option(value=chosen["value"])
        return chosen["label"]

    def _personal(self, ctx: StepContext) -> None:
        filled = self._fill(ctx, PERSONAL_FIELDS)
        if not {"given_names", "first_name"} & set(filled):
            raise FieldNotFound("given_names/first_name", PERSONAL_FIELDS[1].locators + PERSONAL_FIELDS[2].locators, ctx.page.url)
        submit_and_verify(ctx.page, SAVE_AND_CONTINUE, arrived=partial(_on_tab, ctx.page, "travel"), what="personal information")

    def _travel(self, ctx: StepContext) -> None:
        self._fill(ctx, TRAVEL_FIELDS)
        submit_and_verify(ctx.page, SAVE_AND_CONTINUE, arrived=partial(_on_tab, ctx.page, "attachments"), what="travel information")

    def _attachments(self, ctx: StepContext) -> None:
        files = self.prepared_documents(ctx)
        required = {r.kind for r in self.required_documents(ctx.applicant, ctx.trip)}
        fields = [Field(kind, F, ATTACHMENT_LOCATORS[kind], path, required=kind in required) for kind, path in files.items()]
        uploaded = self._fill(ctx, fields)
        ctx.notify(f"uploaded {', '.join(uploaded)}")
        submit_and_verify(ctx.page, SAVE_AND_CONTINUE, arrived=partial(_on_tab, ctx.page, "declaration"), what="attachments", timeout_ms=60_000)

    def _declaration(self, ctx: StepContext) -> None:
        page = ctx.page
        found = find(page, DECLARATION_CHECKBOX, require_visible=False, timeout_ms=5_000)
        if not found:
            raise FieldNotFound("declaration", DECLARATION_CHECKBOX, page.url)
        found[0].check(force=not found[0].is_visible())
        submit_and_verify(page, SAVE_AND_CONTINUE + ("role=button:Submit", "role=button:Submit Application"),
                          arrived=partial(_on_tab, page, "payment"), what="declaration")

    # ---------------------------------------------------------------- payment

    def _open_checkout(self, ctx: StepContext) -> Page:
        method = Field("payment_method", S, PAYMENT_METHOD, CARD_METHOD_LABELS, required=False)
        fill_form(ctx.page, [method], ctx, overrides=self.overrides, timeout_ms=1_000)
        return open_external_checkout(ctx.page, lambda: click(ctx.page, PAY_BUTTONS, what="pay button"))

    def payment_link(self, ctx: StepContext, *, open_checkout: bool) -> PaymentLink:
        amount = find_amount(ctx.page.inner_text("body")) or ctx.result.fee
        return PaymentLink(
            portal_url=self.url("/continueapplication?ReturnUrl=/payment"),
            gateway_url=capture_checkout_url(ctx, lambda: self._open_checkout(ctx)) if open_checkout else "",
            amount=amount,
            resume={
                "Application ID": ctx.result.application_id,
                "Email": ctx.applicant.contact.email,
                "Security question": ctx.state.get("security_question", ""),
                "Security answer": ctx.state.get("security_answer", ""),
            },
            instructions="Open the portal link, sign in with the details above, choose Visa/Mastercard and pay. "
                         "The checkout link is a live payment session and can expire; the portal link always works.",
        )

    def pay_by_card(self, ctx: StepContext, card: CardDetails) -> PaymentOutcome:
        return pay_by_card(
            ctx, card,
            open_checkout=lambda: self._open_checkout(ctx),
            patterns=RESULT_PATTERNS,
            portal_amount=find_amount(ctx.page.inner_text("body")),
        )
