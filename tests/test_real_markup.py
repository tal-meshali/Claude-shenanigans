"""Check the site profile against pages saved from the live portal (mock_site/portal_snapshot).

The saved HTML is served offline through Playwright request routing, so these
tests exercise the real markup (ids, read-only date pickers, "CODE|Label"
option values...) without touching the network."""

from pathlib import Path
from urllib.parse import parse_qs

import pytest
from playwright.sync_api import sync_playwright

from srilanka_evisa.automation import beneficiary_values, declaration_values, load_profile, trip_values
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
                return route.fulfill(content_type="application/javascript", body=(
                    f"var {obj} = new Proxy({{}}, {{get: () => function () {{"
                    " var cb = arguments[arguments.length - 1];"
                    " if (typeof cb === 'function') setTimeout(() => cb(null), 50); }});"))
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
