"""De directie: de Oppertet met zijn assistent (rol `assistent_oppertet`), de escalatieroute en het besluitenregister.

Zie ONDERZOEK.md ('Een extra laag versnelt, filtert niet'). De assistent is een chief of staff:
- vertaalt MT-besluiten door naar opdrachten per afdeling (één eigenaar, reden, deadline);
- houdt het besluitenregister bij (Brein, soort `register`) en meldt de opvolging in het volgende MT;
- is eerste lijn voor operationele escalaties van Hoofdtets en zet de rest met samenvatting en voorstel door;
- houdt dagelijks een directiehuddle met de Oppertet.

Geen filter: een escalatie met een soort uit `directe_lijn` (config/beleid.yaml) gaat rechtstreeks naar de Oppertet,
met alleen een kopie naar de assistent; het origineel gaat altijd ongewijzigd mee. Is de assistent niet ingezet,
dan werkt alles zoals daarvoor. Niets organisatie-specifieks: wie de assistent is, volgt uit de kaarten.
"""
from __future__ import annotations

import datetime as dt
import statistics

from .kaarten import Organisatie

SOORTEN = ("operationeel", "risico", "integriteit", "oneens_assistent")


def directe_lijn(org: Organisatie) -> set[str]:
    return set(org.beleid.get("directe_lijn") or [])


def escalatieroute(org: Organisatie, van: str, soort: str = "operationeel") -> dict:
    """Route van een escalatie door een Hoofdtet.

    Zonder actieve assistent: Hoofdtet -> Raad (zoals daarvoor, de Oppertet ziet het bij de Raad).
    Met actieve assistent: operationeel -> assistent -> Oppertet -> Raad; soorten van de directe lijn -> Oppertet -> Raad,
    met een kopie aan de assistent."""
    ass = org.assistent()
    soort = soort if soort in SOORTEN else "operationeel"
    top = org.agent(van)["rapporteert_aan"] if van in org.agents else "oppertet"
    if not ass:
        return {"naar": "raad", "kopie": [], "route": [van, "raad"], "direct": False, "soort": soort}
    if soort in directe_lijn(org):
        return {"naar": top, "kopie": [ass["id"]], "route": [van, top, "raad"], "direct": True, "soort": soort}
    return {"naar": ass["id"], "kopie": [], "route": [van, ass["id"], top, "raad"], "direct": False, "soort": soort}


# ---------- meten (vóór en na het inzetten van de assistent) ----------
def _mediaan_uren(waarden: list[float]) -> float | None:
    return round(statistics.median(waarden) / 3.6e6, 1) if waarden else None


def _eerste_keer_goed(taken: list[dict]) -> float | None:
    klaar = [t for t in taken if t.get("status") == "klaar"]
    return round(sum(1 for t in klaar if not t.get("afkeuringen") and not t.get("herkansingen")) / len(klaar), 2) if klaar else None


def meting(org: Organisatie, grootboek: list[dict], brein: list[dict], taken: list[dict]) -> dict:
    """Meetwaarden van de directielaag. 'Vóór' en 'na' splitsen op het eerste event van de assistent.

    - escalatie_uren: mediane doorlooptijd van escalatie (event `escalatie.route`) tot afhandeling (`escalatie.afgehandeld`);
    - besluit_tot_opdracht_uren: van een besluit in het register tot de eerste doorvertaalde opdracht;
    - op_tijd: aandeel registerbesluiten met een verstreken deadline dat op tijd is afgerond;
    - beurten_assistent: aantal modelbeurten van de assistent (coördinatiekosten in beurten) en geboekte kosten;
    - via_directe_lijn: escalaties die rechtstreeks naar de Oppertet gingen (stijgt dit, dan filtert de tussenlaag mogelijk);
    - eerste_keer_goed per afdeling, vóór en na."""
    ass = next((a for a in org.agents.values() if a["rol"] == "assistent_oppertet"), None)
    aid = ass["id"] if ass else None
    start = min((e.get("ts", 0) for e in grootboek if aid and e.get("agent") == aid), default=None)
    na = lambda ts: start is not None and (ts or 0) >= start

    open_esc, duur = {}, {"voor": [], "na": []}
    for e in grootboek:
        if e.get("type") == "escalatie.route" and e.get("taak"):
            open_esc.setdefault(e["taak"], e.get("ts", 0))
        elif e.get("type") == "escalatie.afgehandeld" and e.get("taak") in open_esc:
            begin = open_esc.pop(e["taak"])
            duur["na" if na(begin) else "voor"].append(e.get("ts", 0) - begin)
    register = [b for b in brein if b.get("soort") == "register"]
    doorvertaald = [b["doorvertaald_ts"] - b["ts"] for b in register if b.get("doorvertaald_ts") and b.get("ts")]
    vandaag = dt.date.today().isoformat()
    verlopen = [b for b in register if b.get("deadline") and str(b["deadline"])[:10] < vandaag or b.get("status") == "afgerond"]
    op_tijd = [b for b in verlopen if b.get("status") == "afgerond" and (not b.get("deadline") or str(b.get("afgerond_op", ""))[:10] <= str(b["deadline"])[:10])]
    beurten = [e for e in grootboek if aid and e.get("agent") == aid and e.get("type") == "model.aanroep"]
    etkg = {}
    for d in org.afdelingen:
        mijn = [t for t in taken if t.get("dept") == d]
        etkg[d] = {"voor": _eerste_keer_goed([t for t in mijn if not na(t.get("created"))]),
                   "na": _eerste_keer_goed([t for t in mijn if na(t.get("created"))]) if start is not None else None}
    return {
        "assistent": aid, "actief": bool(org.assistent()), "sinds": start,
        "escalatie_uren": {k: _mediaan_uren(v) for k, v in duur.items()},
        "besluit_tot_opdracht_uren": _mediaan_uren(doorvertaald),
        "op_tijd": round(len(op_tijd) / len(verlopen), 2) if verlopen else None,
        "register_open": sum(1 for b in register if b.get("status", "open") != "afgerond"),
        "beurten_assistent": len(beurten),
        "kosten_assistent": round(sum(float(e.get("kosten_eur") or 0) for e in grootboek if aid and e.get("agent") == aid), 4),
        "via_directe_lijn": sum(1 for e in grootboek if e.get("type") == "escalatie.route" and (e.get("data") or {}).get("direct")),
        "eerste_keer_goed": etkg,
    }


# ---------- protocollen (ook gebruikt door het kantoor, via scripts/bouw_kantoor.py) ----------
PROTOCOL_ESCALATIE_SOORT = """Kies je "naar_raad", geef dan ook "soort": "operationeel" (gaat eerst langs de Assistent-Oppertet), of "risico", "integriteit" of "oneens_assistent" (gaat via je directe lijn rechtstreeks naar de Oppertet). Schrijf de toelichting volledig: die gaat ongewijzigd mee."""

PROTOCOL_DIRECTIEHUDDLE = """Directiehuddle met de Oppertet (max. 10 minuten). Geen terugblik: de stand staat hieronder.
Drie vragen, voor jullie allebei: wat is vandaag de prioriteit, waar loopt het vast, wie is er nodig. Strategische keuzes maakt de Oppertet; de assistent zegt wat hij oppakt.
Antwoord uitsluitend met JSON:
{"beurten": [{"agent": "<id>", "prioriteit": "<kort>", "knelpunt": "<kort of null>", "nodig_van": "<agent- of afdeling-id of null>"}], "besluiten": [{"wat": "<kort>", "eigenaar": "<id>"}]}"""

PROTOCOL_DOORVERTALEN = """Vertaal de MT-besluiten hieronder door naar opdrachten per afdeling. Per besluit één of meer opdrachten, elk met precies één eigenaar (de Hoofdtet van die afdeling), een reden en een deadline.
Je verandert niets aan het besluit zelf en neemt geen nieuwe besluiten: ontbreekt een eigenaar of deadline in het besluit, zet dan "vraag_aan_oppertet".
Antwoord uitsluitend met JSON:
{"opdrachten": [{"register": "<register-id>", "afdeling": "<afdeling-id>", "opdracht": "<kort>", "eigenaar": "<hoofdtet-id>", "reden": "<kort>", "deadline": "<datum of null>"}], "vraag_aan_oppertet": "<kort of null>"}"""

PROTOCOL_OPVOLGING = """Volg de besluiten in het register op. Kijk per besluit naar de opdrachten en het werk van de betrokken afdelingen hieronder en geef een status: op_schema, achter of afgerond.
Loopt iets achter, spreek dan de eigenaar aan met één concrete vraag. Zeg niets wat je niet in de gegevens ziet; weet je het niet, dan is de status 'achter' met de vraag.
Antwoord uitsluitend met JSON:
{"status": [{"register": "<register-id>", "status": "op_schema|achter|afgerond", "toelichting": "<kort>", "zekerheid": "hoog|middel|laag"}], "aanspreken": [{"eigenaar": "<hoofdtet-id>", "vraag": "<kort>"}]}"""

PROTOCOL_TRIAGE_ASSISTENT = """Een Hoofdtet escaleerde dit naar jou. Lees het origineel. Handel het af als het binnen je mandaat valt: coördinatie tussen afdelingen, een afspraak over wie wat wanneer levert, of een herkansing met hulp van een andere afdeling.
Raakt het een prioriteit, budget of een strategisch besluit, of twijfel je: zet het door naar de Oppertet met een korte samenvatting en een voorstel. Het origineel gaat altijd ongewijzigd mee; je houdt niets tegen.
Antwoord uitsluitend met JSON:
{"besluit": "afhandelen|naar_oppertet", "afspraak": "<wat er nu gebeurt, of null>", "eigenaar": "<agent-id of null>", "samenvatting": "<max. 3 zinnen>", "voorstel": "<kort of null>"}"""

PROTOCOL_TRIAGE_OPPERTET = """Deze escalatie ligt bij jou. Lees eerst het origineel van de Hoofdtet, daarna pas een eventuele samenvatting van de Assistent-Oppertet.
Besluit binnen je mandaat (prioriteit, verdeling, herkansing met een scherpere opdracht), of leg het voor aan de Raad als het een besluit of informatie vraagt die alleen de Raad heeft.
Antwoord uitsluitend met JSON:
{"besluit": "besluit|naar_raad", "toelichting": "<één of twee zinnen>", "opdracht": "<scherpere opdracht of null>"}"""

PROTOCOL_VOORAF_LEZEN_ASSISTENT = """Je bereidt het MT voor als Assistent-Oppertet. Lees alle memo's en stel per memo hooguit twee vragen die het besluit beter maken.
Stel een volgorde voor de agenda voor (de Oppertet stelt hem vast) en meld welke memo's geen blok 'alleen wij weten' hebben. Je verandert niets aan de memo's.
Antwoord uitsluitend met JSON:
{"vragen": [{"memo": "<afdeling-id>", "vraag": "<kort>"}], "volgorde": [<agendanummer>], "zonder_alleen_wij_weten": ["<afdeling-id>"]}"""
