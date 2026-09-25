"""Sri Lanka ETA portal profile (https://eta.gov.lk).

Observed on the live portal (read-only, September 2026):

    /etaslvisa/etaNavServ?payType=1    Terms & Conditions: "I Agree" radio submits
    etaNavServ (selection)             Tourist / Business / Transit x Individual / Group / Third party
                                       links with fixed ids (1/2, 21/32, 5/6)
    individual form                    one page: applicant, travel, contact, 3 yes/no questions,
                                       confirmation box, reCAPTCHA, "Next"; dates mm-dd-yyyy,
                                       validation by JavaScript alert()
    group form                         page 1 = travel + contact (different field names),
                                       then one page per member

Captions sit in table cells, not <label>s, so fields are located by their
`name`/`id`. Everything after the application form (review, payment options,
card gateway) needs a real submission to observe and is NOT verified; those
steps use generic button/regex locators and may need `--selectors` tuning.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page

from ...core import countries
from ...core.checkout import ResultPatterns, capture_checkout_url, pay_by_card
from ...core.fields import Field, FieldKind, FormError, click, fill_form, find, submit_and_verify
from ...core.models import Applicant, ApplicationBatch, PaymentLink, PaymentOutcome, Purpose, Trip
from ...core.payment import CardDetails, find_amount, open_external_checkout
from ...core.site import Step, StepContext, VisaSite

T, S, D, C, R = FieldKind.TEXT, FieldKind.SELECT, FieldKind.DATE, FieldKind.CHECKBOX, FieldKind.RADIO
OPTIONAL = dict(required=False)
DATE_FORMAT = "%m-%d-%Y"

TERMS_PATH = "/etaslvisa/etaNavServ?payType=1"
APPLICATION_TYPE_LINKS = {
    ("tourist", "individual"): "1", ("tourist", "group"): "2",
    ("business", "individual"): "21", ("business", "group"): "32",
    ("transit", "individual"): "5", ("transit", "group"): "6",
}
PURPOSE_LABELS = {
    Purpose.TOURISM: ["Sightseeing or Holidaying", "Sightseeing", "Holiday"],
    Purpose.VISITING_FAMILY: ["Visiting friends and relatives"],
    Purpose.CONFERENCE: ["M.I.C.E Tourism", "Meetings, Incentives, Conferences"],
    Purpose.MEDICAL: ["Medical treatment including Ayurvedic", "Medical treatment"],
    Purpose.BUSINESS: ["Business", "M.I.C.E Tourism"],
    Purpose.TRANSIT: ["Transit"],
    Purpose.OTHER: ["Sightseeing or Holidaying"],
}
REFERENCE_RE = re.compile(r"(?:reference|application)\s*(?:no\.?|number|id)?\s*[:#]?\s*([A-Z]{2,4}[-_ ]?[A-Z0-9]{6,})", re.I)
RESULT_PATTERNS = ResultPatterns(
    paid=re.compile(r"payment\s+(?:was\s+|has\s+been\s+)?(?:successful|approved|accepted|received)|paiement\s+(?:réussi|accepté)", re.I),
    declined=re.compile(r"declined|payment\s+failed|transaction\s+failed|unsuccessful|refus[ée]|échec", re.I),
    receipt=re.compile(r"(?:receipt|transaction|reference)\s*(?:no\.?|number|id)?\s*[:#]\s*([A-Z0-9-]{6,})", re.I),
)
NEXT = ("#submitButton", "input[type='button'][name='next']", "input[type='button'][value='Next']", "button/=^\\s*(Next|Suivant)\\b")


def _countries(code_of):
    return lambda c: list(countries.country_aliases(code_of(c), c.site.languages))


def _visa_days(c: StepContext) -> list[str]:
    return ["30"] if c.trip.duration_days <= 30 else ["90"]


def _sl_address(c: StepContext) -> str:
    acc = c.trip.accommodation
    return ", ".join(p for p in (acc.name, acc.address, acc.city) if p)


def _member_fields() -> list[Field]:
    """Passport-holder fields. Group member pages may use `id`-prefixed names like
    the group travel page does (idArrivalDate), so both spellings are tried."""

    def loc(name: str, *extra: str) -> tuple[str, ...]:
        names = [name, f"id{name[0].upper()}{name[1:]}"]
        return (*(f"[name='{n}']" for n in names), *(f"#{n}" for n in names), *extra)

    applicant = lambda c: c.state["member"]  # noqa: E731
    return [
        Field("title", S, loc("title"), lambda c: [applicant(c).resolved_title(c.trip.arrival_date).upper(), applicant(c).resolved_title()]),
        Field("surname", T, loc("surname"), lambda c: applicant(c).passport.surname.upper()),
        Field("given_names", T, loc("othernames", "[name='otherNames']"), lambda c: applicant(c).passport.given_names.upper()),
        Field("date_of_birth", D, loc("bdate"), lambda c: applicant(c).passport.date_of_birth, date_format=DATE_FORMAT),
        Field("date_of_birth_again", D, loc("reenteredbdate"), lambda c: applicant(c).passport.date_of_birth, date_format=DATE_FORMAT, **OPTIONAL),
        Field("sex", S, loc("gender"), lambda c: [applicant(c).passport.sex.label]),
        Field("nationality", S, loc("national", "[name='nationality']"), _countries(lambda c: applicant(c).passport.nationality), settle_ms=200),
        Field("country_of_birth", S, loc("conbirth"), _countries(lambda c: applicant(c).passport.country_of_birth), **OPTIONAL),
        Field("occupation", T, loc("occupation"), lambda c: applicant(c).occupation, **OPTIONAL),
        Field("passport_number", T, loc("passportno"), lambda c: applicant(c).passport.number),
        Field("passport_number_again", T, loc("reenteredpassportno"), lambda c: applicant(c).passport.number, **OPTIONAL),
        Field("passport_issue_date", D, loc("pidate"), lambda c: applicant(c).passport.date_of_issue, date_format=DATE_FORMAT),
        Field("passport_expiry_date", D, loc("pedate"), lambda c: applicant(c).passport.date_of_expiry, date_format=DATE_FORMAT),
    ]


def _travel_fields(*, group: bool) -> list[Field]:
    arrival = ("[name='arrivalDate']", "#idArrivalDate") if group else ("[name='iadate']", "#iadate")
    return [
        Field("been_in_last_14_days", S, ("[name='fromDeparture']",), _countries(lambda c: c.trip.departure_country)),
        Field("visa_days", S, ("[name='RequestedVisaDays']",), _visa_days, **OPTIONAL),
        Field("arrival_date", D, arrival, lambda c: c.trip.arrival_date, date_format=DATE_FORMAT),
        Field("purpose", S, ("[name='puofvisit']",), lambda c: PURPOSE_LABELS[c.trip.purpose]),
        Field("departure_city", T, ("[name='depcity']",), lambda c: c.trip.departure_city, **OPTIONAL),
        Field("carrier", T, ("[name='airline']",), lambda c: c.trip.carrier, **OPTIONAL),
        Field("flight", T, ("[name='flightno']",), lambda c: c.trip.arrival_flight, **OPTIONAL),
    ]


def _contact_fields(*, group: bool) -> list[Field]:
    def n(individual_name: str, group_name: str) -> tuple[str, ...]:
        return (f"[name='{group_name if group else individual_name}']",)

    contact = lambda c: c.applicant.contact  # noqa: E731
    return [
        Field("address_1", T, n("addone", "conAddOne"), lambda c: contact(c).address.line1),
        Field("address_2", T, n("addtwo", "contAddTwo"), lambda c: contact(c).address.line2, **OPTIONAL),
        Field("city", T, n("city", "contCity"), lambda c: contact(c).address.city),
        # The portal requires a state; fall back to the city where there is none.
        Field("state", T, n("state", "contState"), lambda c: contact(c).address.state or contact(c).address.city),
        Field("postal_code", T, n("zipcode", "contZipCode"), lambda c: contact(c).address.postal_code, **OPTIONAL),
        Field("country", S, n("adcountry", "conCountry"), _countries(lambda c: contact(c).address.country)),
        Field("address_in_sri_lanka", T, n("addinsl", "contactAddSL"), _sl_address),
        Field("email", T, n("email", "contEmail"), lambda c: contact(c).email),
        Field("email_again", T, n("reenteremail", "reEnterEmail"), lambda c: contact(c).email),
        Field("telephone", T, n("telephon", "contPhoneNo"), lambda c: contact(c).phone),
        Field("mobile", T, n("mobileno", "contMobileno"), lambda c: contact(c).phone, **OPTIONAL),
    ]


def _question_fields() -> list[Field]:
    """QN1 residence visa? QN2 already in Sri Lanka on an ETA/extension? QN3 multiple-entry visa?"""
    def answer(q: str):
        return lambda c: "Yes" if str(c.site_extra("questions", {}).get(q, "no")).lower() in ("yes", "y", "true", "1") else "No"
    return [Field(q.lower(), R, (f"input[type='radio'][name='{q}']",), answer(q), **OPTIONAL) for q in ("QN1", "QN2", "QN3")]


CONFIRM = Field("confirm", C, ("input[type='checkbox'][name='conf']", "label/=confirm the above information"), True, **OPTIONAL)


class SriLankaSite(VisaSite):
    key = "srilanka"
    name = "Sri Lanka"
    default_base_url = "https://eta.gov.lk"
    production_hosts = frozenset({"eta.gov.lk", "www.eta.gov.lk"})
    supports_group = True
    prefers_group = True
    min_passport_validity_months = 6
    document_requirements = ()  # the live ETA form asks for no uploads

    # ------------------------------------------------------------- planning

    def _visa_type(self, batch: ApplicationBatch) -> str:
        return (batch.trip.visa_type or "tourist").lower()

    def validate(self, batch: ApplicationBatch) -> list[str]:
        problems = super().validate(batch)
        visa = self._visa_type(batch)
        if visa not in ("tourist", "business", "transit"):
            problems.append(f"trip.visa_type must be tourist, business or transit for Sri Lanka, not {visa!r}")
        for applicant in batch.applicants:
            trip = batch.trip_for(applicant)
            if trip.duration_days > 90:
                problems.append(f"{applicant.ref}: an ETA covers at most 90 days (trip is {trip.duration_days})")
        return problems

    # ------------------------------------------------------------------ steps

    def steps(self) -> list[Step]:
        return [
            Step("terms", self._terms),
            Step("application-type", self._application_type),
            Step("application-form", self._application_form),
            Step("review", self._review),  # dry runs stop here: nothing submitted yet
            Step("submit", self._submit),
        ]

    def _fill(self, ctx: StepContext, fields: list[Field]) -> None:
        fill_form(ctx.page, fields, ctx, overrides=self.overrides)

    def _terms(self, ctx: StepContext) -> None:
        ctx.page.goto(self.url(TERMS_PATH))
        submit_and_verify(ctx.page, ("input[type='radio'][name='terms'][onclick*='submit']", "label=I Agree", "label/=^\\s*I Agree"),
                          what="terms and conditions")

    def _application_type(self, ctx: StepContext) -> None:
        mode = "group" if len(ctx.applicants) > 1 else "individual"
        link = APPLICATION_TYPE_LINKS[(self._visa_type(ctx.batch), mode)]
        text = "Apply for an Individual" if mode == "individual" else "Apply for (a )?Group"
        submit_and_verify(ctx.page, (f"a[id='{link}']", f"button/=^\\s*{text}"), what=f"{mode} application type")

    def _application_form(self, ctx: StepContext) -> None:
        if len(ctx.applicants) == 1:
            ctx.state["member"] = ctx.applicant
            self._fill(ctx, _member_fields() + _travel_fields(group=False) + _contact_fields(group=False) + _question_fields() + [CONFIRM])
            ctx.options.captcha_handler()(ctx.page)
            submit_and_verify(ctx.page, NEXT, what="application form")
            return
        # Group: page 1 is travel + contact, then one page per member.
        self._fill(ctx, _travel_fields(group=True) + _contact_fields(group=True))
        ctx.options.captcha_handler()(ctx.page)
        submit_and_verify(ctx.page, NEXT, what="group travel and contact details")
        for i, member in enumerate(ctx.applicants, 1):
            ctx.state["member"] = member
            self._fill(ctx, _member_fields() + _question_fields() + [CONFIRM])
            ctx.options.captcha_handler()(ctx.page)
            last = i == len(ctx.applicants)
            buttons = NEXT if last else ("button/=Add (another |next )?(member|applicant|person|traveller)", "button/=^\\s*Add\\b")
            submit_and_verify(ctx.page, buttons, what=f"group member {i}/{len(ctx.applicants)}")
            ctx.notify(f"member {i}/{len(ctx.applicants)} {member.full_name} added")

    def _review(self, ctx: StepContext) -> None:
        # Unverified page: accept any page that is no longer the form.
        if find(ctx.page, ("#submitButton",)) and find(ctx.page, ("[name='surname']",)):
            raise FormError("still on the application form after 'Next'")

    def _submit(self, ctx: StepContext) -> None:
        declaration = find(ctx.page, ("input[type='checkbox'][name*='decl' i]", "input[type='checkbox'][name='conf']",
                                      "label/=(declare|confirm|certify)"), require_visible=False)
        if declaration:
            declaration[0].check(force=True)
        ctx.options.captcha_handler()(ctx.page)
        submit_and_verify(ctx.page, ("button/=^\\s*(Confirm|Submit)", "input[type='submit'][value*='Confirm' i]",
                                     "input[type='button'][value*='Confirm' i]"), what="confirm application")
        match = REFERENCE_RE.search(ctx.page.inner_text("body"))
        if match:
            ctx.result.application_id = match.group(1)
            ctx.notify(f"reference {ctx.result.application_id}")

    # ---------------------------------------------------------------- payment

    def _open_checkout(self, ctx: StepContext) -> Page:
        method = Field("payment_option", S, ("[name*='payment' i]", "[name*='payType' i]", "label/=(credit|debit|card)"),
                       ["Credit Card", "Credit/Debit Card", "Visa", "Card"], required=False)
        fill_form(ctx.page, [method], ctx, overrides=self.overrides, timeout_ms=1_000)
        return open_external_checkout(ctx.page, lambda: click(
            ctx.page, ("button/=^\\s*(Pay|Proceed|Continue)", "input[type='submit'][value*='Pay' i]"), what="pay button"))

    def payment_link(self, ctx: StepContext, *, open_checkout: bool) -> PaymentLink:
        amount = find_amount(ctx.page.inner_text("body")) or ctx.result.fee
        portal_url = ctx.page.url
        return PaymentLink(
            portal_url=portal_url,
            gateway_url=capture_checkout_url(ctx, lambda: self._open_checkout(ctx)) if open_checkout else "",
            amount=amount,
            resume={"Reference": ctx.result.application_id, "Passport number": ctx.applicant.passport.number,
                    "Email": ctx.applicant.contact.email},
            instructions="Pay from the checkout link soon (gateway sessions are short-lived). If it expired, use "
                         "'Check Status' on eta.gov.lk with the reference and passport number.",
        )

    def pay_by_card(self, ctx: StepContext, card: CardDetails) -> PaymentOutcome:
        return pay_by_card(ctx, card, open_checkout=lambda: self._open_checkout(ctx), patterns=RESULT_PATTERNS,
                           portal_amount=find_amount(ctx.page.inner_text("body")))
