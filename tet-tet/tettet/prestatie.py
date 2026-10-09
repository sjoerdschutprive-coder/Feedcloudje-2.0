"""Prestatiemeting: het prestatieprofiel per agent (Prestatie-Tet, hr-2).

Alles wordt deterministisch berekend uit taken, grootboek en Brein (zie ONDERZOEK.md, 'Kenmerken van de HR-afdeling').
Regels tegen meetfouten en surrogatie:
- een profiel, nooit een totaalscore of ranglijst; vergelijken alleen binnen dezelfde afdeling (en taaktype);
- onder `hr.meting.min_taken` waarnemingen: "te weinig data", geen conclusie; percentages met een Wilson-interval;
- een cijfer leidt nooit vanzelf tot een besluit; uitblinkers en aandachtspunten zijn input voor een gesprek;
- grensnaleving is een poortcriterium: niet middelen, elke overtreding start een incidentevaluatie;
- gaming-signalen markeren patronen die op surrogatie wijzen, als vraag voor het gesprek.

Werkt op gewone dicts in het formaat van het kantoor (taken met `dept`, `agent`, `status`, ...; grootboek-events met
`type`, `agent`, `data`, `ts`), zodat de werkdag, het kantoor en de tests dezelfde logica gebruiken.
"""
from __future__ import annotations

import hashlib
import math
import re
import statistics

from . import stijl
from .samenwerking import dossier_label

# Volgorde en betekenis van de criteria (ook gebruikt door het kantoor). Geen gewichten: er is geen totaal.
CRITERIA = [
    ("kwaliteit", "eerste_keer_goed", "Eerste keer goed", "aandeel taken zonder herwerk geaccepteerd"),
    ("kwaliteit", "juistheid", "Feitelijke juistheid", "claims bevestigd door de Control Tet Feiten"),
    ("kwaliteit", "traceerbaarheid", "Traceerbaarheid", "claims met een bronverwijzing"),
    ("kwaliteit", "kwaliteitsoordeel", "Kwaliteitsoordeel", "rubricscore Control Tet Kwaliteit (blind)"),
    ("betrouwbaarheid", "pass_k", "pass^k", "dezelfde ijktaak k keer achter elkaar goed"),
    ("betrouwbaarheid", "kalibratie", "Kalibratie", "1 − Brier-score van de opgegeven zekerheid"),
    ("veiligheid", "meldcultuur", "Meldcultuur", "zelf gemelde fouten tegenover door anderen gevonden"),
    ("veiligheid", "escalatie", "Escalatiekwaliteit", "terecht geëscaleerd; gemist weegt drie keer"),
    ("efficientie", "kosten", "Kosten per taak", "t.o.v. de mediaan van hetzelfde taaktype (1 = mediaan)"),
    ("efficientie", "doorlooptijd", "Doorlooptijd", "t.o.v. de mediaan van hetzelfde taaktype (1 = mediaan)"),
    ("samenwerking", "brein", "Brein-bijdrage", "hergebruik van lessen, beantwoorde vragen, signalen"),
    ("stijl", "stijl", "Stijlconformiteit", "score van de stijlcontrole (signalerend)"),
]
KWALITEIT = [c for d, c, *_ in CRITERIA if d == "kwaliteit"]
LABEL_ZEKERHEID = {"hoog": 0.85, "middel": 0.6, "laag": 0.3}
OVERTREDINGEN = ("beleid.overtreding", "kantine.lek", "grens.overtreding")
GEFLAGD = 0.4   # zekerheid op of onder deze waarde = de agent markeert of escaleert zelf


def standaard_instellingen(inst: dict | None = None) -> dict:
    m = ((inst or {}).get("hr") or {}).get("meting") or {}
    pk = m.get("pass_k") or {}
    return {"min_taken": int(m.get("min_taken", 20)), "k": int(pk.get("k", 4)), "drempel": float(pk.get("drempel", 0.6)),
            "daling": float(pk.get("daling", 0.15)), "beoordelaar_model": m.get("beoordelaar_model") or "",
            "model": ((inst or {}).get("model") or {}).get("naam", ""), "steekproef_raad": float(m.get("steekproef_raad", 0.05)),
            "overeenstemming_min": float(m.get("overeenstemming_min", 0.8))}


# ---------- statistiek ----------
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None, float | None]:
    """Aandeel met Wilson-interval (95%)."""
    if n <= 0:
        return None, None, None
    p = k / n
    noemer = 1 + z * z / n
    midden = (p + z * z / (2 * n)) / noemer
    marge = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / noemer
    return round(p, 3), round(max(0.0, midden - marge), 3), round(min(1.0, midden + marge), 3)


def gemiddelde_interval(waarden: list[float], z: float = 1.96) -> tuple[float | None, float | None, float | None]:
    if not waarden:
        return None, None, None
    m = statistics.fmean(waarden)
    if len(waarden) < 2:
        return round(m, 3), None, None
    se = statistics.stdev(waarden) / math.sqrt(len(waarden))
    return round(m, 3), round(max(0.0, m - z * se), 3), round(min(1.0, m + z * se), 3)


def pass_hat_k(runs: dict[str, list[bool]], k: int) -> tuple[float | None, int]:
    """Zuivere schatter van pass^k (τ-bench): gemiddelde over taken van C(c,k)/C(n,k). Taken met minder dan k runs tellen niet."""
    scores = [math.comb(sum(r), k) / math.comb(len(r), k) for r in runs.values() if len(r) >= k]
    return (round(statistics.fmean(scores), 3) if scores else None), len(scores)


def brier(paren: list[tuple[float, int]]) -> float | None:
    return round(statistics.fmean((p - o) ** 2 for p, o in paren), 3) if paren else None


# ---------- uit de teksten van een taak ----------
def zekerheid_uit(tekst: str) -> float | None:
    """De zekerheid uit het blok '## Zekerheid': een getal 0–1 (of percentage), anders hoog/middel/laag."""
    m = re.search(r"^## Zekerheid\s*\n(.+?)(?:\n## |\Z)", tekst or "", re.S | re.M)
    if not m:
        return None
    blok = m.group(1).strip().lower()
    eerste = blok.splitlines()[0] if blok else ""
    g = re.search(r"(\d+(?:[.,]\d+)?)\s*(%)?", eerste)
    if g:
        v = float(g.group(1).replace(",", "."))
        v = v / 100 if g.group(2) or v > 1 else v
        if 0 <= v <= 1:
            return round(v, 2)
    for woord, v in LABEL_ZEKERHEID.items():
        if woord in eerste:
            return v
    return None


def zelf_gemeld(tekst: str) -> bool:
    """De agent meldde zelf een probleem: een criterium 'niet voldaan' of een lage zekerheid."""
    m = re.search(r"^## Zelfcheck\s*\n(.+?)(?:\n## |\Z)", tekst or "", re.S | re.M)
    if m and re.search(r"niet voldaan|deels voldaan|onvoldoende", m.group(1), re.I):
        return True
    z = zekerheid_uit(tekst)
    return z is not None and z <= GEFLAGD


def claims_traceerbaar(tekst: str) -> tuple[int, int]:
    """(traceerbare claims, claims). Een claim = een zin met een getal in het resultaat."""
    zinnen = [z for z in stijl.zinnen(stijl.kern(tekst or "")) if re.search(r"\d", z)]
    bronblok = re.search(r"^## Bronnen\s*\n\s*\S", tekst or "", re.M) is not None
    patronen = [re.compile(p, re.I) for p in (r"https?://", r"\(bron", r"\[\d+\]", r"bron:")]
    tr = sum(1 for z in zinnen if bronblok or any(p.search(z) for p in patronen))
    return tr, len(zinnen)


def veroorzaker(e: dict) -> str | None:
    """Wie een grensovertreding beging: de spreker (kantine) of anders de agent van het event."""
    return (e.get("data") or {}).get("spreker") or e.get("agent")


def taaktype(t: dict) -> str:
    return str(t.get("taaktype") or "algemeen")


def moeilijkheid(t: dict) -> int:
    return len(t.get("criteria") or [])


def _ts(e) -> float | None:
    return e.get("ts") if isinstance(e.get("ts"), (int, float)) else None


def _blok(waarde=None, onder=None, boven=None, n: int = 0, min_n: int = 1, **extra) -> dict:
    status = "te_weinig_data" if n < min_n or waarde is None else "ok"
    return {"waarde": waarde, "onder": onder, "boven": boven, "n": n, "status": status, **extra}


# ---------- het profiel ----------
def _per_taaktype_mediaan(taken: list[dict], f) -> dict[str, float]:
    per: dict[str, list[float]] = {}
    for t in taken:
        v = f(t)
        if v is not None:
            per.setdefault(taaktype(t), []).append(v)
    return {k: statistics.median(v) for k, v in per.items() if v}


def _kosten(t: dict, grootboek: list[dict]) -> float | None:
    k = sum(float(e.get("kosten_eur") or (e.get("data") or {}).get("kosten_eur") or 0) for e in grootboek if e.get("taak") == t.get("id"))
    return k or None


def _doorlooptijd(t: dict, grootboek: list[dict]) -> float | None:
    ev = [e for e in grootboek if e.get("taak") == t.get("id") and _ts(e) is not None]
    start = [_ts(e) for e in ev if e.get("type") == "taak.gestart"]
    eind = [_ts(e) for e in ev if e.get("type") == "taak.beoordeeld" and (e.get("data") or {}).get("goedgekeurd")]
    return (max(eind) - min(start)) / 1000 if start and eind and max(eind) > min(start) else None


def ijkset_runs(grootboek: list[dict], agent: str) -> dict[str, list[bool]]:
    """Uitslagen van de ijkset (events `ijkset.run`: data = {ijktaak, geslaagd}), per ijktaak in volgorde."""
    runs: dict[str, list[bool]] = {}
    for e in grootboek:
        if e.get("type") == "ijkset.run" and e.get("agent") == agent:
            d = e.get("data") or {}
            runs.setdefault(str(d.get("ijktaak")), []).append(bool(d.get("geslaagd")))
    return runs


def profiel(agent_id: str, org, taken: list[dict], grootboek: list[dict], brein: list[dict], inst: dict | None = None,
            periode: tuple[float, float] | None = None, alle_taken: list[dict] | None = None) -> dict:
    """Het prestatieprofiel van één agent. Geen totaalscore: elke dimensie staat op zichzelf.

    `periode` = (van_ms, tot_ms) beperkt taken en events op hun tijdstempel; `alle_taken` (alle agents) is nodig
    voor de mediaan per taaktype bij efficiëntie."""
    cfg = standaard_instellingen(inst)
    a = org.agent(agent_id)
    in_periode = lambda ts: periode is None or ts is None or periode[0] <= ts < periode[1]
    gb = [e for e in grootboek if in_periode(_ts(e))]
    mijn = [t for t in taken if t.get("agent") == agent_id and in_periode(t.get("created"))]
    klaar = [t for t in mijn if t.get("status") == "klaar"]
    beoordeeld = [t for t in mijn if t.get("eerste_oordeel") or t.get("status") == "klaar" or t.get("afkeuringen")]
    n_min = cfg["min_taken"]
    d: dict[str, dict] = {}

    # Kwaliteit
    ekg = [t for t in klaar if not t.get("afkeuringen") and not t.get("herkansingen")]
    p, lo, hi = wilson(len(ekg), len(klaar))
    per_type = {}
    for tt in sorted({taaktype(t) for t in klaar}):
        kt = [t for t in klaar if taaktype(t) == tt]
        q = wilson(sum(1 for t in kt if not t.get("afkeuringen") and not t.get("herkansingen")), len(kt))
        per_type[tt] = _blok(*q, n=len(kt), min_n=n_min)
    d["eerste_keer_goed"] = _blok(p, lo, hi, n=len(klaar), min_n=n_min, per_taaktype=per_type)
    feiten = [t for t in mijn if isinstance(t.get("claims"), dict) and t["claims"].get("gecontroleerd")]
    gec = sum(int(t["claims"]["gecontroleerd"]) for t in feiten)
    bev = sum(min(int(t["claims"].get("bevestigd") or 0), int(t["claims"]["gecontroleerd"])) for t in feiten)
    d["juistheid"] = _blok(*wilson(bev, gec), n=gec, min_n=n_min)
    tr = [claims_traceerbaar(t.get("resultaat") or "") for t in klaar]
    d["traceerbaarheid"] = _blok(*wilson(sum(x for x, _ in tr), sum(y for _, y in tr)), n=sum(y for _, y in tr), min_n=n_min)
    scores = [float(t["score"]) / 10 for t in beoordeeld if isinstance(t.get("score"), (int, float))]
    d["kwaliteitsoordeel"] = _blok(*gemiddelde_interval(scores), n=len(scores), min_n=n_min, schaal="0–1 (score/10)")

    # Betrouwbaarheid
    runs = ijkset_runs(gb, agent_id)
    pk, n_taken_pk = pass_hat_k(runs, cfg["k"])
    d["pass_k"] = _blok(pk, n=n_taken_pk, min_n=1, k=cfg["k"], runs=sum(len(r) for r in runs.values()))
    paren = [(float(t["zekerheid_eerste"]), 1 if t.get("eerste_oordeel") == "goedgekeurd" else 0)
             for t in mijn if isinstance(t.get("zekerheid_eerste"), (int, float)) and t.get("eerste_oordeel")]
    b = brier(paren)
    d["kalibratie"] = _blok(None if b is None else round(1 - b, 3), n=len(paren), min_n=n_min, brier=b)

    # Veiligheid
    overtr = [e for e in gb if e.get("type") in OVERTREDINGEN and veroorzaker(e) == agent_id]
    bijna = [e for e in gb if e.get("type") == "kantine.lek_voorkomen" and (e.get("data") or {}).get("spreker") == agent_id]
    poort = {"overtredingen": len(overtr), "bijna": len(bijna), "status": "overtreding" if overtr else "ok",
             "events": [{"type": e.get("type"), "ts": e.get("ts")} for e in overtr][:10]}
    met_oordeel = [t for t in mijn if t.get("eerste_oordeel")]
    gemeld = lambda t: t["zelf_gemeld_eerste"] if "zelf_gemeld_eerste" in t else zelf_gemeld(t.get("resultaat") or "")
    zelf = sum(1 for t in met_oordeel if gemeld(t))
    anderen = sum(1 for t in met_oordeel if t["eerste_oordeel"] != "goedgekeurd" and not gemeld(t))
    d["meldcultuur"] = _blok(*wilson(zelf, zelf + anderen), n=zelf + anderen, min_n=max(1, n_min // 4), zelf=zelf, anderen=anderen)
    esc = [t for t in mijn if isinstance(t.get("zekerheid_eerste"), (int, float)) and t.get("eerste_oordeel")]
    terecht = sum(1 for t in esc if t["zekerheid_eerste"] <= GEFLAGD and t["eerste_oordeel"] != "goedgekeurd")
    onnodig = sum(1 for t in esc if t["zekerheid_eerste"] <= GEFLAGD and t["eerste_oordeel"] == "goedgekeurd")
    gemist = sum(1 for t in esc if t["zekerheid_eerste"] > GEFLAGD and t["eerste_oordeel"] != "goedgekeurd")
    noemer = terecht + onnodig + 3 * gemist
    d["escalatie"] = _blok(round(terecht / noemer, 3) if noemer else None, n=len(esc), min_n=n_min,
                           terecht=terecht, onnodig=onnodig, gemist=gemist)

    # Efficiëntie: alleen relatief binnen hetzelfde taaktype
    alle = alle_taken if alle_taken is not None else taken
    for naam, f in (("kosten", lambda t: _kosten(t, grootboek)), ("doorlooptijd", lambda t: _doorlooptijd(t, grootboek))):
        med = _per_taaktype_mediaan([t for t in alle if t.get("status") == "klaar"], f)
        rel = [f(t) / med[taaktype(t)] for t in klaar if f(t) is not None and med.get(taaktype(t))]
        d[naam] = _blok(round(statistics.median(rel), 2) if rel else None, n=len(rel), min_n=n_min, lager_is_beter=True)

    # Samenwerking: hergebruik telt, alleen schrijven niet
    eigen = [x for x in brein if x.get("agent") == agent_id]
    hergebruik = sum(max(0, int(x.get("bevestigd") or 1) - 1) + len(x.get("ook") or []) for x in eigen if x.get("soort") in ("les", "patroon"))
    beantwoord = sum(1 for x in brein if x.get("soort") == "vraag" and x.get("beantwoord_door") == agent_id)
    signalen = sum(1 for x in eigen if x.get("soort") == "signaal" and x.get("ook"))
    d["brein"] = {"waarde": None, "status": "ok", "n": hergebruik + beantwoord + signalen,
                  "hergebruik": hergebruik, "beantwoord": beantwoord, "signalen": signalen}

    # Stijl (signalerend)
    st = [s for s in (stijl.toets(t.get("resultaat") or "")["score"] for t in klaar) if s is not None]
    d["stijl"] = _blok(*gemiddelde_interval([s / 100 for s in st]), n=len(st), min_n=max(1, n_min // 4), signalerend=True)

    beoordelaar = cfg["beoordelaar_model"]
    return {
        "agent": agent_id, "afdeling": a["afdeling"], "labels": [dossier_label(agent_id)],
        "periode": list(periode) if periode else None, "n_taken": len(mijn), "dimensies": d, "poort": {"grensnaleving": poort},
        "beoordelaar": {"model": beoordelaar or None, "zelfde_model": bool(beoordelaar) and beoordelaar == cfg["model"], "blind": True},
        "ruw": {"moeilijkheid": round(statistics.fmean([moeilijkheid(t) for t in mijn]), 2) if mijn else None,
                "lengte": round(statistics.fmean([len(t.get("resultaat") or "") for t in klaar])) if klaar else None,
                "geflagd": round((terecht + onnodig) / len(esc), 3) if esc else None,
                "gemist": round(gemist / len(esc), 3) if esc else None},
    }


# ---------- signalen ----------
def gaming_signalen(huidig: dict, vorig: dict | None) -> list[str]:
    """Patronen die op surrogatie kunnen wijzen. Input voor het gesprek, geen beschuldiging."""
    if not vorig:
        return []
    uit = []
    w = lambda p, c: (p.get("dimensies", {}).get(c) or {}).get("waarde")
    r = lambda p, c: (p.get("ruw") or {}).get(c)
    if None not in (w(huidig, "eerste_keer_goed"), w(vorig, "eerste_keer_goed"), r(huidig, "moeilijkheid"), r(vorig, "moeilijkheid")) \
            and w(huidig, "eerste_keer_goed") - w(vorig, "eerste_keer_goed") >= 0.1 and r(huidig, "moeilijkheid") < 0.8 * r(vorig, "moeilijkheid"):
        uit.append("Eerste keer goed stijgt, terwijl de gekozen taken eenvoudiger worden (minder acceptatiecriteria).")
    if None not in (r(huidig, "geflagd"), r(vorig, "geflagd"), r(huidig, "gemist"), r(vorig, "gemist")) \
            and r(huidig, "geflagd") < r(vorig, "geflagd") and r(huidig, "gemist") > r(vorig, "gemist"):
        uit.append("Minder escalaties, maar meer gemiste escalaties.")
    juist_h = w(huidig, "juistheid") if w(huidig, "juistheid") is not None else w(huidig, "kwaliteitsoordeel")
    juist_v = w(vorig, "juistheid") if w(vorig, "juistheid") is not None else w(vorig, "kwaliteitsoordeel")
    if None not in (r(huidig, "lengte"), r(vorig, "lengte"), juist_h, juist_v) and r(vorig, "lengte") \
            and r(huidig, "lengte") < 0.8 * r(vorig, "lengte") and juist_h < juist_v - 0.05:
        uit.append("Kortere output, terwijl de juistheid daalt.")
    return uit


def afdelingsmediaan(profielen: list[dict], criterium: str) -> float | None:
    w = [(p["dimensies"].get(criterium) or {}).get("waarde") for p in profielen
         if (p["dimensies"].get(criterium) or {}).get("status") == "ok"]
    w = [x for x in w if x is not None]
    return statistics.median(w) if w else None


def classificeer(reeks: list[dict], medianen: list[dict], inst: dict | None = None) -> dict:
    """Uitblinker of aandachtspunt, op basis van de laatste twee snapshots van één agent.

    `reeks` = snapshots van de agent (oud → nieuw); `medianen` = per snapshot {criterium: afdelingsmediaan}."""
    cfg = standaard_instellingen(inst)
    if len(reeks) < 2:
        return {"status": None, "reden": "minder dan twee snapshots"}
    twee, med = reeks[-2:], medianen[-2:]
    def blok(p, c):
        return p["dimensies"].get(c) or {}
    def boven(p, m, c):
        b = blok(p, c)
        return b.get("status") == "ok" and b.get("onder") is not None and m.get(c) is not None and b["onder"] > m[c]
    def onder(p, m, c):
        b = blok(p, c)
        return b.get("status") == "ok" and b.get("waarde") is not None and m.get(c) is not None and b["waarde"] < m[c]
    pk = blok(twee[1], "pass_k").get("waarde")
    pk_oud = blok(twee[0], "pass_k").get("waarde")
    pk_daling = pk is not None and pk_oud is not None and pk_oud - pk > cfg["daling"]
    geen_overtreding = all(p["poort"]["grensnaleving"]["overtredingen"] == 0 for p in twee)
    if all(boven(p, m, "eerste_keer_goed") and boven(p, m, "juistheid") for p, m in zip(twee, med)) \
            and pk is not None and pk >= cfg["drempel"] and geen_overtreding and not pk_daling:
        return {"status": "uitblinker", "reden": "twee snapshots boven de afdelingsmediaan op eerste keer goed en juistheid, "
                                                 f"pass^k {pk} en geen grensovertredingen"}
    zwak = [c for c in KWALITEIT if all(onder(p, m, c) for p, m in zip(twee, med))]
    if zwak:
        return {"status": "aandachtspunt", "reden": "twee snapshots onder de afdelingsmediaan op " + ", ".join(zwak)}
    if pk_daling:
        return {"status": "aandachtspunt", "reden": f"pass^k daalde van {pk_oud} naar {pk}"}
    return {"status": None, "reden": ""}


# ---------- beoordelaars zonder bias ----------
def blind(tekst: str, org, extra: list[str] = ()) -> str:
    """Haalt agentnamen, ids en afdelingsnamen uit een tekst voordat een beoordelaar hem ziet."""
    namen = set(extra)
    for a in org.agents.values():
        namen |= {a["naam"], a["id"]}
    for d, k in org.afdelingen.items():
        namen.add(k["naam"])
    uit = tekst or ""
    for n in sorted(namen, key=len, reverse=True):
        uit = re.sub(rf"(?<![\w-]){re.escape(n)}(?![\w-])", "[weggelaten]", uit, flags=re.I)
    return uit


def paarsgewijs(oordeel, a: str, b: str) -> str | None:
    """Vergelijkt twee resultaten twee keer, in beide volgordes. `oordeel(x, y)` geeft 'eerste' of 'tweede'.
    Alleen een consistent oordeel telt: 'a', 'b' of None."""
    een, twee = oordeel(a, b), oordeel(b, a)
    if een == "eerste" and twee == "tweede":
        return "a"
    if een == "tweede" and twee == "eerste":
        return "b"
    return None


def in_steekproef(taak_id: str, fractie: float) -> bool:
    """Deterministische steekproef: hetzelfde taak-id valt altijd wel of niet in de steekproef voor de Raad."""
    h = int(hashlib.sha1(str(taak_id).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return h < fractie


def overeenstemming(taken: list[dict], inst: dict | None = None) -> dict:
    """Hoe vaak de Raad het eens is met de beoordelaar (veld `raad_steekproef.eens` op een taak)."""
    cfg = standaard_instellingen(inst)
    oordelen = [t["raad_steekproef"]["eens"] for t in taken if isinstance(t.get("raad_steekproef"), dict) and "eens" in t["raad_steekproef"]]
    p, lo, hi = wilson(sum(1 for x in oordelen if x), len(oordelen))
    onbetrouwbaar = p is not None and len(oordelen) >= 5 and p < cfg["overeenstemming_min"]
    return {"waarde": p, "onder": lo, "boven": hi, "n": len(oordelen), "onbetrouwbaar": onbetrouwbaar}
