"""A local stand-in for the Sri Lanka ETA portal and its payment gateway.

It mimics the flow (French locale) closely enough to exercise the automation
end to end without touching the real government site:

  center.jsp -> apply.jsp (visa type, individual/group, terms)
  -> trip & contact -> one form per traveller (+ "add another member")
  -> review -> confirmation with reference -> external payment gateway
  (card form inside an iframe) -> payment result.

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
from email.parser import BytesParser
from email.policy import HTTP
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

FEE_USD = 50
COUNTRIES = [("250", "FRA", "France"), ("276", "DEU", "Allemagne"), ("826", "GBR", "Royaume-Uni"),
             ("840", "USA", "États-Unis"), ("376", "ISR", "Israël"), ("356", "IND", "Inde"),
             ("724", "ESP", "Espagne"), ("380", "ITA", "Italie")]

SESSIONS: dict[str, dict] = {}
PAYMENTS: dict[str, dict] = {}
LOCK = threading.Lock()


def esc(v: object) -> str:
    return html.escape(str(v))


def page(title: str, body: str, error: str = "") -> str:
    err = f'<div class="error" role="alert">{esc(error)}</div>' if error else ""
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{esc(title)}</title>
<style>body{{font-family:sans-serif;max-width:760px;margin:2em auto}} label{{display:block;margin-top:.7em}}
.error{{background:#fdd;border:1px solid #c00;padding:.6em}} .upload input{{position:absolute;opacity:0;width:1px}}
.upload span{{border:1px solid #888;padding:.2em .6em}}</style></head>
<body><h1>{esc(title)}</h1>{err}{body}</body></html>"""


def text_input(name: str, label: str, value: str = "", tag: str = "input") -> str:
    if tag == "textarea":
        return f'<label for="{name}">{label}</label><textarea id="{name}" name="{name}">{esc(value)}</textarea>'
    return f'<label for="{name}">{label}</label><input id="{name}" name="{name}" value="{esc(value)}">'


def select(name: str, label: str, options: list[tuple[str, str]]) -> str:
    opts = '<option value="">-- Choisir --</option>' + "".join(
        f'<option value="{esc(v)}">{esc(t)}</option>' for v, t in options)
    return f'<label for="{name}">{label}</label><select id="{name}" name="{name}">{opts}</select>'


def country_select(name: str, label: str) -> str:
    # Values are numeric codes so the automation must match on the visible French name.
    return select(name, label, [(num, fr) for num, _, fr in COUNTRIES])


def parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError:
        return None


class Handler(BaseHTTPRequestHandler):
    server_version = "MockETA/1.0"

    def log_message(self, fmt: str, *args: object) -> None:  # quiet
        pass

    # --------------------------------------------------------------- plumbing
    def session(self) -> tuple[str, dict]:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        sid = cookie["SID"].value if "SID" in cookie else ""
        with LOCK:
            if sid not in SESSIONS:
                sid = secrets.token_hex(8)
                SESSIONS[sid] = {"members": [], "status": "new"}
            return sid, SESSIONS[sid]

    def send(self, body: str, status: int = 200, sid: str | None = None, ctype: str = "text/html") -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if sid:
            self.send_header("Set-Cookie", f"SID={sid}; Path=/")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str, sid: str | None = None) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        if sid:
            self.send_header("Set-Cookie", f"SID={sid}; Path=/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def form(self) -> tuple[dict[str, str], dict[str, tuple[str, bytes]]]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        ctype = self.headers.get("Content-Type", "")
        if ctype.startswith("multipart/form-data"):
            msg = BytesParser(policy=HTTP).parsebytes(
                f"Content-Type: {ctype}\r\n\r\n".encode() + raw)
            fields, files = {}, {}
            for part in msg.iter_parts():
                name = part.get_param("name", header="content-disposition")
                filename = part.get_filename()
                payload = part.get_payload(decode=True) or b""
                if filename is not None:
                    files[name] = (filename, payload)
                else:
                    fields[name] = payload.decode()
            return fields, files
        return {k: v[0] for k, v in parse_qs(raw.decode(), keep_blank_values=True).items()}, {}

    # ------------------------------------------------------------------ pages
    def do_GET(self) -> None:  # noqa: C901 - a router
        url = urlparse(self.path)
        path, query = url.path, parse_qs(url.query)
        sid, s = self.session()

        if path == "/__state":
            return self.send(json.dumps({"sessions": SESSIONS, "payments": PAYMENTS}, default=str),
                             ctype="application/json")
        if path in ("/", "/slvisa/visainfo/center.jsp"):
            return self.send(page("Centre ETA — Sri Lanka",
                '<p>Bienvenue sur le système ETA.</p><ul>'
                '<li><a href="/slvisa/visainfo/apply.jsp?locale=fr_FR">Demander un visa</a></li>'
                '<li><a href="/slvisa/visainfo/status.jsp">Vérifier le statut</a></li></ul>'), sid=sid)
        if path == "/slvisa/visainfo/apply.jsp":
            return self.send(self.apply_page(), sid=sid)
        if path == "/slvisa/eta/trip":
            return self.send(self.trip_page(), sid=sid)
        if path == "/slvisa/eta/member":
            return self.send(self.member_page(s), sid=sid)
        if path == "/slvisa/eta/review":
            return self.send(self.review_page(s), sid=sid)
        if path == "/slvisa/eta/confirmation":
            return self.send(self.confirmation_page(s), sid=sid)
        if path == "/ipg/pay":
            return self.send(self.gateway_page(query.get("session", [""])[0]))
        if path == "/ipg/card-frame":
            return self.send(self.card_frame(query.get("session", [""])[0]))
        if path == "/ipg/result":
            p = PAYMENTS.get(query.get("session", [""])[0], {})
            if p.get("status") == "paid":
                return self.send(page("Paiement accepté",
                    f"<p>Paiement réussi pour la demande {esc(p['ref'])}. Montant : {p['amount']} USD.</p>"))
            return self.send(page("Paiement refusé", "<p>Transaction refusée par la banque émettrice.</p>"))
        self.send(page("404", "<p>Introuvable</p>"), status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        sid, s = self.session()
        fields, files = self.form()

        if path == "/slvisa/eta/start":
            errors = []
            if fields.get("visaType") != "TOURIST":
                errors.append("Veuillez choisir le type de visa.")
            if fields.get("appType") not in ("INDIVIDUAL", "GROUP"):
                errors.append("Veuillez choisir le type de demande.")
            if fields.get("agree") != "on":
                errors.append("Vous devez accepter les conditions.")
            if errors:
                return self.send(self.apply_page(" ".join(errors)), sid=sid)
            s.update(visa_type=fields["visaType"], app_type=fields["appType"], members=[], status="draft")
            return self.redirect("/slvisa/eta/trip", sid)

        if path == "/slvisa/eta/trip":
            required = ["purpose", "arrivalDate", "stayDays", "travelMode", "addressSL", "email", "emailConfirm",
                        "mobile"]
            missing = [k for k in required if not fields.get(k)]
            arrival = parse_date(fields.get("arrivalDate", ""))
            if missing:
                return self.send(self.trip_page(f"Champs obligatoires manquants : {', '.join(missing)}"), sid=sid)
            if not arrival or arrival < date.today():
                return self.send(self.trip_page("Date d'arrivée invalide (JJ/MM/AAAA)."), sid=sid)
            if fields["email"] != fields["emailConfirm"]:
                return self.send(self.trip_page("Les adresses e-mail ne correspondent pas."), sid=sid)
            if not fields["stayDays"].isdigit() or not 1 <= int(fields["stayDays"]) <= 30:
                return self.send(self.trip_page("Durée du séjour invalide."), sid=sid)
            s["trip"] = fields
            return self.redirect("/slvisa/eta/member", sid)

        if path == "/slvisa/eta/member":
            error = self.validate_member(fields, files)
            if error:
                return self.send(self.member_page(s, error), sid=sid)
            member = dict(fields)
            member.pop("action", None)
            member["files"] = {k: {"filename": v[0], "size": len(v[1])} for k, v in files.items()}
            s["members"].append(member)
            if fields.get("action") == "add":
                if s.get("app_type") != "GROUP":
                    return self.send(self.member_page(s, "Ajout impossible : demande individuelle."), sid=sid)
                return self.redirect("/slvisa/eta/member", sid)
            return self.redirect("/slvisa/eta/review", sid)

        if path == "/slvisa/eta/submit":
            if fields.get("declaration") != "on":
                return self.send(self.review_page(s, "Veuillez cocher la déclaration."), sid=sid)
            if s.get("app_type") == "GROUP" and len(s["members"]) < 2:
                return self.send(self.review_page(s, "Un groupe doit compter au moins deux membres."), sid=sid)
            s["reference"] = "ETA-" + secrets.token_hex(5).upper()
            s["status"] = "submitted"
            return self.redirect("/slvisa/eta/confirmation", sid)

        if path == "/ipg/checkout":
            if s.get("status") != "submitted" or fields.get("ref") != s.get("reference"):
                return self.send(page("Erreur", "<p>Session de paiement invalide.</p>"), status=400)
            token = secrets.token_urlsafe(12)
            PAYMENTS[token] = {"ref": s["reference"], "amount": FEE_USD * len(s["members"]), "status": "pending"}
            return self.redirect(f"/ipg/pay?session={token}")

        if path == "/ipg/submit":
            token = fields.get("session", "")
            p = PAYMENTS.get(token)
            if not p or p["status"] != "pending":
                return self.send(page("Erreur", "<p>Session expirée.</p>"), status=400)
            number = fields.get("cardNumber", "").replace(" ", "")
            valid = (re.fullmatch(r"\d{13,19}", number) and fields.get("expMonth") and fields.get("expYear")
                     and re.fullmatch(r"\d{3,4}", fields.get("cvc", "")))
            p["status"] = "paid" if valid and number == "4111111111111111" else "declined"
            p["card_last4"] = number[-4:]
            return self.redirect(f"/ipg/result?session={token}")

        self.send(page("404", "<p>Introuvable</p>"), status=404)

    # --------------------------------------------------------------- builders
    def apply_page(self, error: str = "") -> str:
        return page("Demande d'ETA", f"""
<form method="post" action="/slvisa/eta/start">
{select("visaType", "Type de visa", [("TOURIST", "ETA Touriste"), ("BUSINESS", "ETA Affaires"),
                                      ("TRANSIT", "ETA Transit")])}
<fieldset><legend>Type de demande</legend>
<input type="radio" id="t1" name="appType" value="INDIVIDUAL"><label for="t1">Individuelle</label>
<input type="radio" id="t2" name="appType" value="GROUP"><label for="t2">Groupe (famille, voyage organisé)</label>
</fieldset>
<input type="checkbox" id="agree" name="agree"><label for="agree">J'accepte les conditions générales</label>
<p><button type="submit">Suivant</button></p></form>""", error)

    def trip_page(self, error: str = "") -> str:
        return page("Voyage et coordonnées", f"""
<form method="post" action="/slvisa/eta/trip">
{select("purpose", "Motif du séjour", [("SIGHTSEEING", "Tourisme"), ("VISIT", "Visite familiale"),
                                        ("MEDICAL", "Soins médicaux")])}
{text_input("arrivalDate", "Date prévue d'arrivée (JJ/MM/AAAA)")}
{text_input("stayDays", "Durée du séjour (jours)")}
{select("travelMode", "Moyen de transport", [("AIR", "Avion"), ("SEA", "Mer")])}
{text_input("departurePort", "Port de départ")}
{text_input("flightNo", "Numéro de vol")}
{text_input("addressSL", "Adresse au Sri Lanka", tag="textarea")}
{text_input("email", "Adresse e-mail")}
{text_input("emailConfirm", "Confirmez l'adresse e-mail")}
{text_input("mobile", "Téléphone mobile")}
{text_input("postalAddress", "Adresse postale", tag="textarea")}
<p><button type="submit">Continuer</button></p></form>""", error)

    def member_page(self, s: dict, error: str = "") -> str:
        n = len(s["members"]) + 1
        add = ('<button type="submit" name="action" value="add">Ajouter un autre membre</button> '
               if s.get("app_type") == "GROUP" else "")
        return page(f"Voyageur n° {n}", f"""
<form method="post" action="/slvisa/eta/member" enctype="multipart/form-data">
{select("title", "Titre", [("MR", "M."), ("MRS", "Mme"), ("MS", "Mlle"), ("MSTR", "Master")])}
{text_input("surname", "Nom de famille")}
{text_input("otherNames", "Prénoms")}
{text_input("dob", "Date de naissance (JJ/MM/AAAA)")}
{select("gender", "Sexe", [("1", "Masculin"), ("2", "Féminin")])}
{country_select("nationality", "Nationalité")}
{country_select("birthCountry", "Pays de naissance")}
{text_input("occupation", "Profession")}
{text_input("passportNo", "Numéro du passeport")}
{country_select("issueCountry", "Pays de délivrance")}
{text_input("issueDate", "Date de délivrance (JJ/MM/AAAA)")}
{text_input("expiryDate", "Date d'expiration (JJ/MM/AAAA)")}
{text_input("homeAddress", "Adresse du domicile", tag="textarea")}
<label class="upload" for="passportCopy">Copie de la page du passeport
 <input type="file" id="passportCopy" name="passportCopy" accept="image/*,.pdf"><span>Parcourir…</span></label>
<label class="upload" for="photo">Photo d'identité
 <input type="file" id="photo" name="photo" accept="image/*"><span>Parcourir…</span></label>
<p>{add}<button type="submit" name="action" value="next">Continuer</button></p></form>""", error)

    def validate_member(self, f: dict[str, str], files: dict[str, tuple[str, bytes]]) -> str:
        required = ["title", "surname", "otherNames", "dob", "gender", "nationality", "passportNo",
                    "issueDate", "expiryDate"]
        missing = [k for k in required if not f.get(k)]
        if missing:
            return f"Champs obligatoires manquants : {', '.join(missing)}"
        for key in ("dob", "issueDate", "expiryDate"):
            if not parse_date(f[key]):
                return f"Format de date invalide pour {key} (JJ/MM/AAAA)."
        if parse_date(f["expiryDate"]) <= date.today():
            return "Le passeport a expiré."
        if not re.fullmatch(r"[A-Z0-9]{6,12}", f["passportNo"]):
            return "Numéro de passeport invalide."
        for key in ("passportCopy", "photo"):
            _, data = files.get(key, ("", b""))
            if not (data.startswith(b"\x89PNG") or data.startswith(b"\xff\xd8") or data.startswith(b"%PDF")):
                return f"Fichier manquant ou invalide : {key}"
        return ""

    def review_page(self, s: dict, error: str = "") -> str:
        rows = "".join(f"<tr><td>{esc(m['surname'])}</td><td>{esc(m['otherNames'])}</td>"
                       f"<td>{esc(m['passportNo'])}</td></tr>" for m in s["members"])
        return page("Vérification", f"""
<table border="1"><tr><th>Nom</th><th>Prénoms</th><th>Passeport</th></tr>{rows}</table>
<p>Arrivée : {esc(s.get('trip', {}).get('arrivalDate', ''))}</p>
<form method="post" action="/slvisa/eta/submit">
<input type="checkbox" id="declaration" name="declaration">
<label for="declaration">Je déclare que les informations fournies sont exactes</label>
<p><button type="submit">Confirmer et soumettre</button></p></form>""", error)

    def confirmation_page(self, s: dict) -> str:
        if s.get("status") != "submitted":
            return page("Erreur", "<p>Aucune demande soumise.</p>")
        total = FEE_USD * len(s["members"])
        return page("Demande enregistrée", f"""
<p>Votre demande a été enregistrée. Numéro de référence : <strong>{esc(s['reference'])}</strong></p>
<p>Nombre de voyageurs : {len(s['members'])} — Montant à payer : {total} USD</p>
<form method="post" action="/ipg/checkout"><input type="hidden" name="ref" value="{esc(s['reference'])}">
<button type="submit">Payer maintenant</button></form>""")

    def gateway_page(self, token: str) -> str:
        p = PAYMENTS.get(token)
        if not p:
            return page("Erreur", "<p>Session de paiement inconnue.</p>")
        return page("Passerelle de paiement sécurisée", f"""
<p>Marchand : Department of Immigration &amp; Emigration — Réf. {esc(p['ref'])} — {p['amount']} USD</p>
<iframe src="/ipg/card-frame?session={esc(token)}" width="100%" height="420" title="Carte"></iframe>""")

    def card_frame(self, token: str) -> str:
        p = PAYMENTS.get(token, {"amount": 0})
        months = "".join(f'<option value="{m:02d}">{m:02d}</option>' for m in range(1, 13))
        years = "".join(f'<option value="{y}">{y}</option>' for y in range(date.today().year, date.today().year + 12))
        return f"""<!doctype html><html><body><form method="post" action="/ipg/submit" target="_top">
<input type="hidden" name="session" value="{esc(token)}">
<label for="holder">Titulaire de la carte</label><input id="holder" name="cardHolder" autocomplete="cc-name">
<label for="num">Numéro de carte</label><input id="num" name="cardNumber" autocomplete="cc-number">
<label for="mm">Mois</label><select id="mm" name="expMonth"><option value="">MM</option>{months}</select>
<label for="yy">Année</label><select id="yy" name="expYear"><option value="">AAAA</option>{years}</select>
<label for="cvc">Cryptogramme (CVV)</label><input id="cvc" name="cvc" autocomplete="cc-csc">
<button type="submit">Payer {p['amount']},00 USD</button></form></body></html>"""


def serve(port: int = 8765, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Mock ETA portal on http://127.0.0.1:{args.port}/slvisa/visainfo/center.jsp")
    server.serve_forever()


if __name__ == "__main__":
    main()
