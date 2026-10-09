"""HR-logica zonder werkdag: evaluaties normaliseren, onboarding-checklist, Brein-curatie, cultuurkloof en HR-cijfers.

Zie ONDERZOEK.md, 'Kenmerken van de HR-afdeling'. Alles werkt op gewone dicts in het formaat van het kantoor.
Niets organisatie-specifieks: wie wat mag komt uit de kaarten en `config/`.
"""
from __future__ import annotations

import datetime as dt
import re
import statistics

from .beleid import Geweigerd
from .brein import overlap
from . import samenwerking as sw

TOEKOMSTVRAGEN = [
    "Ik zou deze agent de belangrijkste taak van mijn afdeling toevertrouwen.",
    "Ik wil deze agent altijd in mijn team.",
    "Deze agent loopt risico op ondermaatse prestaties.",
    "Deze agent is klaar voor een hoger autonomieniveau.",
]
VAAG = re.compile(r"\b(doe je best|beter worden|meer inzet|harder werken|goed bezig|blijf zo doorgaan)\b", re.I)
OVER_DE_AGENT = re.compile(r"\b(je bent|jij bent|hij is|zij is|je persoonlijkheid|je karakter|lui|slim|dom)\b", re.I)
DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------- evaluaties ----------
def _datum(x, standaard: str) -> tuple[str, bool]:
    s = str(x or "").strip()[:10]
    return (s, False) if DATUM.match(s) else (standaard, True)


def doel(x, eigenaar: str, standaard_datum: str) -> dict:
    """Een doel is specifiek en heeft een datum en een eigenaar. Ontbreekt de datum: de volgende evaluatie (gemarkeerd)."""
    x = x if isinstance(x, dict) else {"doel": str(x or "")}
    tekst = str(x.get("doel") or x.get("tekst") or "").strip()[:300]
    datum, aangevuld = _datum(x.get("datum"), standaard_datum)
    return {"doel": tekst, "meetbaar": str(x.get("meetbaar") or "").strip()[:200], "datum": datum, "datum_aangevuld": aangevuld,
            "eigenaar": eigenaar, "specifiek": len(re.findall(r"\w+", tekst)) >= 5 and not VAAG.search(tekst)}


def normaliseer_evaluatie(o: dict, agent: str, evaluator: str, standaard_datum: str) -> dict:
    """Uitkomst van een evaluatiegesprek, zoals hij in `evaluaties` komt."""
    vragen = []
    for i, tekst in enumerate(TOEKOMSTVRAGEN, 1):
        x = next((v for v in o.get("toekomstvragen") or [] if str(v.get("nr")) == str(i)), {})
        s = x.get("score")
        vragen.append({"nr": i, "vraag": tekst, "score": int(s) if str(s).isdigit() and 1 <= int(s) <= 5 else None,
                       "toelichting": str(x.get("toelichting") or "")[:240]})
    feedback, weg = [], 0
    for f in (o.get("feedback") or [])[:5]:
        f = str(f)[:300]
        if OVER_DE_AGENT.search(f):
            weg += 1      # feedback gaat over de taak, nooit over de agent
        else:
            feedback.append(f)
    acties = []
    for a in (o.get("actieplan") or [])[:5]:
        a = a if isinstance(a, dict) else {"actie": str(a)}
        if a.get("actie"):
            datum, aangevuld = _datum(a.get("datum"), standaard_datum)
            acties.append({"actie": str(a["actie"])[:200], "eigenaar": str(a.get("eigenaar") or evaluator), "datum": datum,
                           "datum_aangevuld": aangevuld, "status": "open"})
    if not acties:
        acties.append({"actie": "Prestatiedoel en leerdoel bespreken in de volgende check-in", "eigenaar": evaluator, "datum": standaard_datum,
                       "datum_aangevuld": True, "status": "open"})
    plan = o.get("ontwikkelplan")
    if isinstance(plan, dict) and plan.get("onderdelen"):
        plan = {"onderdelen": [str(x)[:200] for x in plan["onderdelen"][:5]], "toelichting": str(plan.get("toelichting") or "")[:300]}
    else:
        plan = None
    return {"toekomstvragen": vragen, "feedback": feedback, "feedback_over_agent_weggelaten": weg,
            "prestatiedoel": doel(o.get("prestatiedoel"), agent, standaard_datum),
            "leerdoel": doel(o.get("leerdoel"), agent, standaard_datum), "actieplan": acties, "ontwikkelplan": plan}


def zelfkalibratie(schatting: dict | None, profiel: dict | None) -> dict:
    """Verschil tussen zelfbeeld en meting (positief = de agent schat zichzelf hoger in)."""
    uit = {}
    for c, v in (schatting or {}).items():
        meting = ((profiel or {}).get("dimensies", {}).get(c) or {})
        if isinstance(v, (int, float)) and meting.get("status") == "ok" and meting.get("waarde") is not None:
            uit[c] = round(float(v) - meting["waarde"], 3)
    return uit


# ---------- onboarding ----------
def checklist(org, agent_id: str, grootboek: list[dict]) -> list[dict]:
    """Onboarding-checklist voor een nieuwe agent: kaart compleet, mandaat, toegang getoetst door Risk, ijkset gedraaid."""
    a = org.agent(agent_id)
    velden = ["werkstijl", "samenwerking", "mandaat", "kpis", "verantwoordelijkheden", "persoonlijkheid"]
    getoetst = any(e.get("type") == "toegang.getoetst" and (e.get("data") or {}).get("agent") == agent_id for e in grootboek)
    ijk = any(e.get("type") == "ijkset.run" and e.get("agent") == agent_id for e in grootboek)
    return [{"punt": "Profielkaart compleet", "klaar": all(a.get(v) for v in velden)},
            {"punt": "Mandaat en toegangskaart", "klaar": bool(a["mandaat"].get("toegangskaart"))},
            {"punt": "Toegang getoetst door Risk & Safety", "klaar": getoetst},
            {"punt": "Ijkset gedraaid", "klaar": ijk}]


# ---------- Brein-curatie ----------
CURATIE_VELDEN = {"vervangen_door", "herzien_op", "tags", "curatie"}


def curatie_velden(velden: dict) -> dict:
    """Wat de Governance-Tet aan een Brein-item mag wijzigen: alleen markeren. Labels en verwijderen nooit."""
    verboden = set(velden) - CURATIE_VELDEN
    if verboden:
        raise Geweigerd("curatie mag alleen markeren (vervangen_door, herzien_op, tags); niet: " + ", ".join(sorted(verboden)))
    return velden


def curatie_kandidaten(brein: list[dict], toegang, drempel: float = 0.5, oud_dagen: int = 60, nu_ms: int = 0) -> dict:
    """Kandidaten voor de curatieronde, alleen binnen de toegang van de curator. Items daarbuiten worden alleen geteld."""
    zichtbaar = [b for b in brein if sw.zichtbaar(b, toegang) and not sw.is_dossier(b)]
    verborgen: dict[str, int] = {}
    for b in brein:
        if b not in zichtbaar and not sw.is_dossier(b):
            d = b.get("dept") or b.get("afdeling") or "?"
            verborgen[d] = verborgen.get(d, 0) + 1
    actief = [b for b in zichtbaar if not b.get("vervangen_door") and (b.get("soort") or "les") in ("les", "incident", "besluit", "patroon")]
    dubbel = []
    for i, x in enumerate(actief):
        for y in actief[i + 1:]:
            o = overlap(x.get("tekst", ""), y.get("tekst", ""))
            if o >= drempel and (x.get("soort") or "les") == (y.get("soort") or "les"):
                dubbel.append({"ids": [x["id"], y["id"]], "overlap": round(o, 2)})
    oud = [b for b in actief if isinstance(b.get("ts"), (int, float)) and nu_ms and nu_ms - b["ts"] > oud_dagen * 864e5
           and int(b.get("bevestigd") or 1) <= 1 and not b.get("herzien_op")]
    strijdig = []
    for i, x in enumerate(actief):
        for y in actief[i + 1:]:
            o = overlap(x.get("tekst", ""), y.get("tekst", ""))
            ontkenning = bool(re.search(r"\b(niet|nooit|geen)\b", x.get("tekst", ""), re.I)) != bool(re.search(r"\b(niet|nooit|geen)\b", y.get("tekst", ""), re.I))
            if 0.3 <= o < drempel and ontkenning:
                strijdig.append({"ids": [x["id"], y["id"]]})
    return {"zichtbaar": len(zichtbaar), "dubbel": dubbel[:10], "verouderd": [b["id"] for b in oud][:10], "strijdig": strijdig[:5],
            "verborgen_per_afdeling": verborgen}


# ---------- cultuurkloof en HR-cijfers ----------
def _aandeel(teller: int, noemer: int) -> float | None:
    return round(teller / noemer, 2) if noemer else None


def indicator(naam: str, st, org) -> float | None:
    """Gedragsindicator per principe, uit grootboek en collecties. `st` heeft taken, brein, overleggen, kantine, grootboek, evaluaties."""
    taken = list(st.taken.values()) if isinstance(st.taken, dict) else st.taken
    ov, br, gb = st.overleggen, st.brein, st.grootboek
    ev = getattr(st, "evaluaties", [])
    if naam == "taken_met_criteria":
        return _aandeel(sum(1 for t in taken if t.get("criteria")), len(taken))
    if naam == "besluiten_met_eigenaar":
        b = [x for o in ov for x in o.get("besluiten") or []]
        return _aandeel(sum(1 for x in b if x.get("eigenaar")), len(b))
    if naam == "mt_oordelen_vooraf":
        mts = [o for o in ov if o.get("soort") == "mt"]
        return _aandeel(sum(1 for m in mts if any(o.get("soort") == "mt_oordeel" and o.get("cyclus") == m.get("cyclus") for o in ov)), len(mts))
    if naam == "taken_getoetst":
        klaar = [t for t in taken if t.get("status") == "klaar"]
        return _aandeel(sum(1 for t in klaar if t.get("score") is not None or t.get("control") == "raad"), len(klaar))
    if naam == "afkeuringen_met_les":
        afg = [t for t in taken if t.get("afkeuringen")]
        return _aandeel(sum(1 for t in afg if any(b.get("taak") == t.get("id") and b.get("bron") == "afkeuring" for b in br)), len(afg))
    if naam == "lessen_per_taak":
        klaar = [t for t in taken if t.get("status") == "klaar"]
        return _aandeel(sum(1 for t in klaar if any(b.get("taak") == t.get("id") and (b.get("soort") or "les") == "les" for b in br)), len(klaar))
    if naam == "kantine_verkenning":
        return sw.cultuur(org, st.kantine, [], [])["verkenning"]
    if naam == "vragen_beantwoord":
        v = [b for b in br if b.get("soort") == "vraag"]
        return _aandeel(sum(1 for b in v if b.get("status") == "beantwoord"), len(v))
    if naam == "alleen_wij_weten_gevuld":
        m = [o for o in ov if o.get("soort") == "afdelingsoverleg"]
        return _aandeel(sum(1 for o in m if (o.get("memo") or {}).get("alleen_wij_weten")), len(m))
    if naam == "lekken_voorkomen_aandeel":
        v = sum(1 for e in gb if e.get("type") == "kantine.lek_voorkomen")
        lek = sum(1 for e in gb if e.get("type") == "kantine.lek")
        return _aandeel(v, v + lek)
    if naam == "checkins_gehouden":
        gepland = [k for k in getattr(st, "kalender", []) if k.get("soort") == "checkin" and k.get("status") != "geannuleerd"
                   and k.get("datum", "9999") <= dt.date.today().isoformat()]
        gedaan = {e.get("uid") for e in ev if e.get("soort") == "checkin"}
        return _aandeel(sum(1 for k in gepland if k["uid"] in gedaan), len(gepland))
    if naam == "doelen_specifiek":
        e = [x for x in ev if x.get("soort") in ("evaluatie", "proefperiode")]
        ok = lambda x: all((x.get(d) or {}).get("specifiek") and not (x.get(d) or {}).get("datum_aangevuld") for d in ("prestatiedoel", "leerdoel"))
        return _aandeel(sum(1 for x in e if ok(x)), len(e))
    if naam == "zelf_gemeld_aandeel":
        z = sum(1 for t in taken if t.get("eerste_oordeel") and t.get("zelf_gemeld_eerste"))
        a = sum(1 for t in taken if t.get("eerste_oordeel") == "afgekeurd" and not t.get("zelf_gemeld_eerste"))
        return _aandeel(z, z + a)
    return None


def cultuurkloof(org, st) -> list[dict]:
    """Per principe uit de organisatiekaart: de norm op papier, het gedrag uit de data en het verschil."""
    uit = []
    for p in org.organisatie.get("edge_principes", []):
        if not p.get("indicator"):
            continue
        w = indicator(p["indicator"], st, org)
        norm = float(p.get("norm", 1))
        uit.append({"principe": p["principe"], "indicator": p["indicator"], "norm": norm, "gedrag": w,
                    "kloof": None if w is None else round(max(0.0, norm - w), 2)})
    return uit


def hr_per_afdeling(org, evaluaties: list[dict], brein: list[dict], grootboek: list[dict]) -> dict[str, dict]:
    """Geaggregeerd en zonder namen: voor het retrospectief en het HR-blok in het MT-memo."""
    afd = {a["id"]: a["afdeling"] for a in org.agents.values()}
    uit = {d: {"open_ontwikkelplannen": 0, "patroon_oogsten": 0, "incidenten": 0} for d in org.afdelingen}
    laatste: dict[str, dict] = {}
    for e in evaluaties:
        if e.get("soort") in ("evaluatie", "proefperiode") and e.get("agent"):
            laatste[e["agent"]] = e
    for a, e in laatste.items():
        if e.get("ontwikkelplan") and afd.get(a) in uit:
            uit[afd[a]]["open_ontwikkelplannen"] += 1
    for b in brein:
        if b.get("soort") == "patroon" and afd.get(b.get("over")) in uit:
            uit[afd[b["over"]]]["patroon_oogsten"] += 1
    for e in evaluaties:
        if e.get("soort") == "incident" and afd.get(e.get("agent")) in uit:
            uit[afd[e["agent"]]]["incidenten"] += 1
    return uit


def strengheid(evaluaties: list[dict]) -> dict[str, dict]:
    """Per evaluator het gemiddelde per toekomstvraag: verschillen in strengheid voor de kalibratie."""
    per: dict[str, dict[int, list[int]]] = {}
    for e in evaluaties:
        if e.get("soort") not in ("evaluatie", "proefperiode"):
            continue
        for v in e.get("toekomstvragen") or []:
            if v.get("score"):
                per.setdefault(e.get("evaluator"), {}).setdefault(v["nr"], []).append(v["score"])
    return {k: {nr: round(statistics.fmean(s), 2) for nr, s in v.items()} for k, v in per.items()}
