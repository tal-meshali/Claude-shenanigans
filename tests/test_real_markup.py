"""Check the site profile against pages saved from the live portal (mock_site/portal_snapshot).

The saved HTML is served offline through Playwright request routing, so these
tests exercise the real markup (ids, read-only date pickers, "CODE|Label"
option values...) without touching the network."""

from pathlib import Path
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import sync_playwright

from srilanka_evisa.automation import (beneficiary_values, child_values, declaration_values, load_profile,
                                       trip_values)
from srilanka_evisa.forms import fill_fields, locate
from srilanka_evisa.mock_data import generate
from srilanka_evisa.models import load_application

FIXTURES = Path(__file__).parent.parent / "mock_site" / "portal_snapshot"
URL = "https://eta.gov.lk/etaslvisa/etaNavServ"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def open_fixture(browser):
    """Open a saved page with the portal's own JavaScript; POSTs are captured, never sent."""
    pages = []

    def _open(name):
        page = browser.new_page()
        page.posts, page.alerts = [], []
        html = (FIXTURES / name).read_text(encoding="utf-8", errors="replace")

        def handle(route):
            req = route.request
            if req.url == URL and req.method == "GET":
                return route.fulfill(body=html, content_type="text/html")
            if req.url.startswith(URL) and req.method == "POST":
                page.posts.append(parse_qs(req.post_data))
                return route.fulfill(body="<html>captured</html>", content_type="text/html")
            rel = req.url.split("/etaslvisa/")[-1].split("?")[0]
            if rel.startswith("js/") and (FIXTURES / rel).is_file():
                return route.fulfill(path=FIXTURES / rel, content_type="application/javascript")
            if "/dwr/interface/" in req.url:
                # Server-side AJAX checks (e.g. passport lookup): answer "no problem".
                obj = req.url.rsplit("/", 1)[-1].split(".")[0]
                # The member page also asks for its parameters (GMEM = max group size).
                return route.fulfill(content_type="application/javascript", body=(
                    f"var {obj} = new Proxy({{}}, {{get: (t, method) => function () {{"
                    " var cb = arguments[arguments.length - 1];"
                    " var answer = method === 'getActivParameters'"
                    " ? [{code: 'GMEM', value: 10}, {code: 'MDEP', value: 5}] : null;"
                    " if (typeof cb === 'function') setTimeout(() => cb(answer), 50); }});"))
            return route.abort()

        page.route("**/*", handle)
        page.on("dialog", lambda d: (page.alerts.append(d.message), d.accept()))
        page.goto(URL)
        pages.append(page)
        return page

    yield _open
    for p in pages:
        p.close()


@pytest.fixture
def app(tmp_path):
    return load_application(generate(tmp_path))


def _values(page, ids):
    return page.evaluate("""ids => Object.fromEntries(ids.map(id => {
        const e = document.getElementById(id);
        return [id, e.type === 'checkbox' || e.type === 'radio' ? e.checked : e.value];
    }))""", ids)


def _add_children(page, step, parent, date_format):
    """What EtaAutomation._add_children does: fill the child section and add, once per child."""
    spec = step["children"]
    for n, child in enumerate(parent.children, 1):
        assert set(fill_fields(page, spec["fields"], child_values(child), date_format)) == set(spec["fields"])
        locate(page, spec["add"]).click()
        page.wait_for_selector(spec["added"].format(n=n), state="attached", timeout=5000)


def test_terms_page_agree_radio(open_fixture):
    page = open_fixture("eta_terms.html")
    profile = load_profile()
    agree = locate(page, profile["steps"]["terms"]["click"])
    assert agree is not None and agree.get_attribute("value") == "yes"


def test_individual_form_is_fully_filled(open_fixture, app):
    page = open_fixture("eta_individual_form.html")
    profile = load_profile()
    step = profile["steps"]["individual_form"]
    person = app.beneficiaries[0]
    values = {**beneficiary_values(person), **trip_values(app), **declaration_values(app)}
    filled = fill_fields(page, step["fields"], values, profile["date_format"])

    assert set(filled) == set(step["fields"]) - {"address_line2", "mobile"}  # empty in the mock data
    v = _values(page, [
        "surname", "othernames", "title", "bdate", "reenteredbdate", "gender", "national", "conbirth",
        "occupation", "passportno", "reenteredpassportno", "pidate", "pedate", "fromDeparture",
        "RequestedVisaDays", "iadate", "puofvisit", "depcity", "airline", "flightno", "addone", "city",
        "state", "zipcode", "adcountry", "addinsl", "email", "reenteremail", "telephon",
        "vlrNQN1", "vlrNQN2", "vlrNQN3", "vlrYQN1",
    ])
    assert v["surname"] == "DUPONT" and v["othernames"] == "JEAN PIERRE"
    assert v["title"] == "01|MR" and v["gender"] == "Male"
    assert v["bdate"] == v["reenteredbdate"] == "03-14-1984"  # mm-dd-yyyy, read-only picker
    assert v["pidate"] == "02-01-2024" and v["pedate"] == "01-31-2034"
    assert v["iadate"] == app.trip.arrival_date.strftime("%m-%d-%Y")
    assert v["national"].startswith("FRA|") and v["conbirth"].startswith("FRA|")
    assert v["adcountry"].startswith("FRA") and v["fromDeparture"].startswith("FRA")
    assert v["passportno"] == v["reenteredpassportno"] == "24FR81234"
    assert v["RequestedVisaDays"] == "30" and v["puofvisit"].startswith("V01")
    assert v["email"] == v["reenteremail"] == "jean.dupont@example.com"
    assert v["vlrNQN1"] and v["vlrNQN2"] and v["vlrNQN3"] and not v["vlrYQN1"]
    assert page.locator("input[name='conf']").is_checked()
    assert page.locator("#idHiddenPassOk").input_value() == "1"  # passport check passed

    # The portal's own validation accepts the form and submits it (captured locally).
    locate(page, step["next"]).click()
    page.wait_for_timeout(1500)
    [posted] = page.posts
    assert posted["surname"] == ["DUPONT"] and posted["bdate"] == ["03-14-1984"]
    assert posted["national"] == ["FRA|FRANCE (FRA)"] and posted["conf"] == ["conf"]
    assert not [a for a in page.alerts if "valid for 30 days" not in a]  # only the informational notice


def test_group_trip_form_is_fully_filled(open_fixture, app):
    page = open_fixture("eta_group_trip_form.html")
    profile = load_profile()
    step = profile["steps"]["group_form"]
    filled = fill_fields(page, step["fields"], trip_values(app), profile["date_format"])
    assert set(filled) == set(step["fields"]) - {"address_line2", "mobile"}  # empty in the mock data
    v = _values(page, ["idfromDeparture", "RequestedVisaDays", "idArrivalDate", "idPuofvisit", "idAirline",
                       "idContAddOne", "idContCity", "idConCountry", "idContPhoneNo", "idContEmail",
                       "idReEnterEmail", "idContactAddSL"])
    assert v["idfromDeparture"] == "FRA" and v["idConCountry"] == "FRA"
    assert v["idArrivalDate"] == app.trip.arrival_date.strftime("%m-%d-%Y")
    assert v["idPuofvisit"] == "V01" and v["RequestedVisaDays"] == "30"
    assert v["idContEmail"] == v["idReEnterEmail"] == "jean.dupont@example.com"
    assert "GALLE FACE" in v["idContactAddSL"].upper()

    locate(page, step["next"]).click()
    page.wait_for_timeout(1500)
    [posted] = page.posts
    assert posted["appType"] == ["2"] and posted["contEmail"] == ["jean.dupont@example.com"]
    assert posted["conAddOne"] == ["12 RUE DE LA PAIX"]  # the site upper-cases as you type
    assert not [a for a in page.alerts if "valid for 30 days" not in a]


def test_group_member_form_adds_every_member(open_fixture, app):
    """The member page is reused per member: "Add Member" keeps each one in hidden inputs
    on the page, and the "Next" button it then shows posts them all at once."""
    page = open_fixture("eta_group_member_form.html")
    profile = load_profile()
    step = profile["steps"]["member_form"]
    for i, member in enumerate(app.beneficiaries, 1):
        values = {**beneficiary_values(member), **declaration_values(app), "country_of_address": app.contact.country}
        filled = fill_fields(page, step["fields"], values, profile["date_format"])
        assert set(filled) == set(step["fields"])
        _add_children(page, step, member, profile["date_format"])
        locate(page, step["add"]).click()
        page.wait_for_selector(step["added"].format(n=i), state="attached", timeout=5000)
        assert page.locator("#idSurname").input_value() == ""  # the portal clears the form for the next one

    locate(page, step["next"]).click()
    page.wait_for_timeout(1500)
    [posted] = page.posts
    assert posted["hiddenOtherNames"] == ["JEAN PIERRE", "MARIE CLAIRE", "LUCAS"]
    assert posted["hiddenPassportNo"] == posted["hiddenReEnteredPassportNo"] == ["24FR81234", "23FR55120", "25FR00731"]
    assert posted["hiddenDobDate"] == posted["hiddenReEnteredDobDate"] == ["03-14-1984", "11-02-1987", "07-30-2014"]
    assert posted["hiddenTitle"] == ["01", "02", "05"] and posted["hiddenGender"] == ["M", "F", "M"]
    assert posted["hiddenNationality"] == posted["hiddenCoa"] == ["FRA"] * 3
    assert posted["hiddenPassExDate"][0] == "01-31-2034"
    assert sorted(posted["otherDecQuesAns"]) == sorted(
        f"{n}|QN{q}|0" for n in posted["hiddenPassportNo"] for q in (1, 2, 3))  # three "No" answers each
    # Emma, on her mother's (member 2) passport
    assert posted["hiddenDPassportNo"] == ["23FR55120"] and posted["hiddenDMemberNo"] == ["2"]
    assert (posted["hiddenDSurname"], posted["hiddenDOtherNames"]) == (["DUPONT"], ["EMMA"])
    assert posted["hiddenDDobDate"] == ["04-18-2021"] and posted["hiddenDGender"] == ["F"]
    assert posted["hiddenDRealationShip"] == ["03"]
    assert not [a for a in page.alerts if "maximum number of members" not in a]


@pytest.mark.parametrize("fixture, actiontype, dialogs", [
    ("eta_group_review.html", "3", 1),       # #idConform -> submittionOfForm3Group(this, '3')
    ("eta_individual_review.html", "2", 2),  # confirmForm(): "Are you sure...", fraud declaration
])
def test_review_confirm_button(open_fixture, fixture, actiontype, dialogs):
    page = open_fixture(fixture)
    confirm = locate(page, load_profile()["steps"]["review"]["submit"])
    assert confirm is not None and "Confirm" in confirm.get_attribute("value")
    confirm.click()
    page.wait_for_timeout(1000)
    [posted] = page.posts  # captured locally, never sent
    assert posted["actiontype"] == [actiontype]
    assert len(page.alerts) == dialogs and "Are you sure to confirm" in page.alerts[0]


def test_individual_form_adds_child_on_parents_passport(open_fixture, app):
    page = open_fixture("eta_individual_form.html")
    profile = load_profile()
    step = profile["steps"]["individual_form"]
    mother = app.beneficiaries[1]
    fill_fields(page, step["fields"], {**beneficiary_values(mother), **trip_values(app), **declaration_values(app)},
                profile["date_format"])
    _add_children(page, step, mother, profile["date_format"])
    assert page.locator("#dSurname").input_value() == ""  # cleared for the next child

    locate(page, step["next"]).click()
    page.wait_for_timeout(1500)
    [posted] = page.posts
    assert posted["depValues"] == ["DUPONT|EMMA|04-18-2021|Female|03"]  # 03 = Child
    assert posted["passportno"] == ["23FR55120"]
    assert not [a for a in page.alerts if "valid for 30 days" not in a]
