"""Samenwerking: het collectieve Brein, de kantine, het deelfilter en de overlegstructuur.

Zie ONDERZOEK.md (sectie 'Kenmerken van de samenwerking') voor de onderbouwing.

- Toegangslabels: elk Brein-item en elke taak kan `labels` dragen: de bronnen waarop het steunt.
  Een agent ziet een item alleen als hij alle labels in zijn effectieve toegang heeft. Zonder labels is het organisatiebreed.
- Wie weet wat: per agent expertise uit de profielkaart, aangevuld met afgerond werk en bevestigde lessen.
- Kantine: een gemengde tafel van 4–6 agents uit minstens drie afdelingen, roulerend.
- Deelfilter: elke kantinebeurt die verwijst naar een item met labels die een toehoorder niet heeft, wordt
  tegengehouden vóór hij zichtbaar wordt; de Privacy-Tet beoordeelt daarna de inhoud.
- Overlegstructuur: huddle (dagelijks), voorbereiding → afdelingsoverleg → bilateraal → vooraf lezen → MT (wekelijks),
  retrospectief (eerste MT van de maand).

Alle functies werken op gewone dicts, zodat de werkdag (opslag van het kantoor, veld `dept`) en het Brein
van het platform (veld `afdeling`) dezelfde logica gebruiken. Niets organisatie-specifieks: alles komt uit de kaarten.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import re

from .brein import woorden
from .kaarten import Organisatie, Toegang

# Bronnen die iedereen heeft of die openbaar zijn: tellen niet als label.
PUBLIEK = {"web", "brein"}
# Woorden die in elk werkverhaal staan en niets zeggen over expertise.
STOPWOORDEN = {"een", "het", "de", "van", "voor", "met", "en", "op", "in", "te", "dat", "die", "is", "zijn", "aan",
               "bij", "als", "naar", "uit", "door", "over", "om", "of", "ook", "niet", "wat", "wie", "hoe", "per", "elke"}

FASEN = ["voorbereiding", "afdelingsoverleg", "bilateraal", "vooraf_lezen", "mt_oordeel", "mt"]
FASE_DAG = {"voorbereiding": 2, "afdelingsoverleg": 2, "bilateraal": 1, "vooraf_lezen": 1, "mt_oordeel": 0, "mt": 0}


def sleutelwoorden(tekst: str) -> set[str]:
    return {w for w in woorden(tekst) if w not in STOPWOORDEN}


# ---------- toegangslabels ----------
def labels_uit(tekst: str, toegang: Toegang) -> list[str]:
    """Labels uit het blok '## Bronnen' van een resultaat: alleen bronnen die de agent echt heeft, zonder publieke."""
    m = re.search(r"^## Bronnen\s*\n(.+?)(?:\n## |\Z)", tekst or "", re.S | re.M)
    if not m:
        return []
    genoemd = set(re.findall(r"[a-z_]{3,}", m.group(1).lower()))
    return sorted(b for b in genoemd if b in toegang.bronnen and b not in PUBLIEK)


# Wie `alle_afdelingsoutput` mag lezen (Risk & Safety), ziet alles: toezicht vraagt inzage.
TOEZICHT = "alle_afdelingsoutput"


def ontbrekend(item: dict, toegang: Toegang) -> list[str]:
    if toegang.mag(TOEZICHT):
        return []
    return [l for l in item.get("labels") or [] if l not in PUBLIEK and not toegang.mag(l)]


def zichtbaar(item: dict, toegang: Toegang) -> bool:
    return not ontbrekend(item, toegang)


def toegangen(org: Organisatie, agents: list[str]) -> dict[str, Toegang]:
    return {a: org.effectieve_toegang(a) for a in agents}


def deelbaar(items: list[dict], tg: dict[str, Toegang]) -> list[dict]:
    """Items die iedere aanwezige mag zien (doorsnede van de effectieve toegang)."""
    return [i for i in items if all(zichtbaar(i, t) for t in tg.values())]


# ---------- wie weet wat, wie werkt waaraan, vraagbaak ----------
def _afd(item: dict) -> str | None:
    return item.get("dept") or item.get("afdeling")


def profiel_woorden(a: dict) -> set[str]:
    return sleutelwoorden(" ".join([a["specialisme"], a["missie"], *a.get("expertise", []), *a.get("verantwoordelijkheden", [])]))


def wie_weet_wat(org: Organisatie, tekst: str, *, zelf: str | None = None, brein: list[dict] = (), taken: list[dict] = (),
                 n: int = 3) -> list[dict]:
    """De n collega's die het meest weten over `tekst`, met een korte reden. Alleen ingezette agents."""
    vraag = sleutelwoorden(tekst)
    if not vraag:
        return []
    uit = []
    for a in org.actieve_agents():
        if a["id"] == zelf or a["rol"] == "oppertet":
            continue
        pw = profiel_woorden(a)
        raak = vraag & pw
        score = len(raak) * 2.0
        werk = [t for t in taken if t.get("agent") == a["id"] and t.get("status") == "klaar" and vraag & sleutelwoorden(t.get("title", ""))]
        lessen = [b for b in brein if b.get("agent") == a["id"] and vraag & sleutelwoorden(b.get("tekst", ""))]
        score += len(werk) + 0.5 * len(lessen)
        if score <= 0:
            continue
        reden = []
        if raak:
            reden.append("expertise: " + ", ".join(sorted(raak)[:3]))
        if werk:
            reden.append(f"{len(werk)} afgeronde taak/taken hierover")
        if lessen:
            reden.append(f"{len(lessen)} les(sen) in het Brein")
        uit.append({"agent": a["id"], "naam": a["naam"], "afdeling": a["afdeling"], "score": round(score, 2), "reden": "; ".join(reden)})
    uit.sort(key=lambda x: (-x["score"], x["agent"]))
    return uit[:n]


def wie_werkt_waaraan(org: Organisatie, taken: list[dict], agent_id: str, max_aantal: int = 8) -> list[str]:
    """Lopend werk van andere afdelingen. Titels die steunen op bronnen buiten de eigen toegang blijven verborgen."""
    t_eigen = org.effectieve_toegang(agent_id)
    eigen = org.agent(agent_id)["afdeling"]
    regels = []
    for t in sorted(taken, key=lambda x: x.get("created", 0), reverse=True):
        if t.get("status") not in ("bezig", "volgende") or t.get("dept") == eigen or not t.get("agent") or t["agent"] not in org.agents:
            continue
        naam = org.agent(t["agent"])["naam"]
        afd = org.afdelingen.get(t["dept"], {}).get("naam", t["dept"])
        titel = t.get("title", "") if zichtbaar(t, t_eigen) else "(werk op bronnen buiten jouw toegang)"
        regels.append(f"{naam} ({afd}, {t['status']}): {titel[:100]}")
        if len(regels) >= max_aantal:
            break
    return regels


def open_vragen(org: Organisatie, brein: list[dict], agent_id: str, max_aantal: int = 3) -> list[dict]:
    """Open vragen in het Brein die bij deze agent passen: gericht aan zijn afdeling of zijn id, of passend bij zijn expertise."""
    a = org.agent(agent_id)
    t = org.effectieve_toegang(agent_id)
    pw = profiel_woorden(a)
    uit = []
    for b in brein:
        if b.get("soort") != "vraag" or b.get("status", "open") != "open" or b.get("agent") == agent_id or not zichtbaar(b, t):
            continue
        aan = b.get("aan")
        if aan in (agent_id, a["afdeling"]) or len(sleutelwoorden(b.get("tekst", "")) & pw) >= 2:
            uit.append(b)
    return uit[:max_aantal]


def blokken_uit(tekst: str) -> dict:
    """Leest de extra blokken van een Tet-resultaat: vragen aan het Brein, signalen en antwoorden op open vragen.

    ## Vragen aan het Brein      - [aan: <afdeling-id of agent-id>] <vraag>
    ## Signalen                  - [voor: <afdeling-id>, <afdeling-id>] <bevinding>
    ## Antwoorden                - [<vraag-id>] <antwoord>
    """
    def regels(kop):
        m = re.search(rf"^## {kop}\s*\n(.+?)(?:\n## |\Z)", tekst or "", re.S | re.M)
        return [r.strip()[1:].strip() for r in (m.group(1).splitlines() if m else []) if r.strip().startswith("-")]
    vragen, signalen, antwoorden = [], [], []
    for r in regels("Vragen aan het Brein"):
        m = re.match(r"^\[aan:\s*([a-z0-9-]+)\]\s*(.+)$", r)
        if m:
            vragen.append({"aan": m.group(1), "tekst": m.group(2)[:400]})
        elif r and r.lower() not in ("geen", "-"):
            vragen.append({"aan": None, "tekst": r[:400]})
    for r in regels("Signalen"):
        m = re.match(r"^\[voor:\s*([a-z ,-]+)\]\s*(.+)$", r)
        if m:
            signalen.append({"voor": [x.strip() for x in m.group(1).split(",") if x.strip()], "tekst": m.group(2)[:400]})
    for r in regels("Antwoorden"):
        m = re.match(r"^\[([A-Za-z0-9_-]+)\]\s*(.+)$", r)
        if m:
            antwoorden.append({"vraag": m.group(1), "tekst": m.group(2)[:500]})
    return {"vragen": vragen[:2], "signalen": signalen[:3], "antwoorden": antwoorden[:3]}


# ---------- kantine ----------
def _hash(s: str) -> int:
    return int(hashlib.sha1(s.encode()).hexdigest()[:8], 16)


def tafel(org: Organisatie, geschiedenis: list[dict], *, sleutel: str, grootte: int = 6, min_afdelingen: int = 3,
          bezet: set[str] = frozenset()) -> list[str]:
    """Kiest een gemengde tafel: wie het minst in de kantine zat eerst, zo veel mogelijk nieuwe combinaties,
    minstens `min_afdelingen` afdelingen. Deterministisch per `sleutel` (bijv. de werkdagbron)."""
    kandidaten = [a for a in org.actieve_agents() if a["id"] not in bezet]
    bezoek = {a["id"]: 0 for a in kandidaten}
    paren = set()
    for k in geschiedenis:
        d = k.get("deelnemers") or []
        for x in d:
            if x in bezoek:
                bezoek[x] += 1
        paren |= {tuple(sorted(p)) for p in itertools.combinations(d, 2)}
    volgorde = sorted(kandidaten, key=lambda a: (bezoek[a["id"]], _hash(sleutel + a["id"])))
    gekozen: list[dict] = []
    for a in volgorde:
        if len(gekozen) >= grootte:
            break
        afds = {g["afdeling"] for g in gekozen}
        # Eerst spreiden over afdelingen, daarna nieuwe combinaties.
        if len(afds) < min_afdelingen and a["afdeling"] in afds and len(gekozen) >= len(afds):
            continue
        if gekozen and all(tuple(sorted((a["id"], g["id"]))) in paren for g in gekozen) and len(volgorde) > grootte * 2:
            continue
        gekozen.append(a)
    for a in volgorde:  # aanvullen als de filters te streng waren
        if len(gekozen) >= grootte:
            break
        if a not in gekozen:
            gekozen.append(a)
    return [a["id"] for a in gekozen]


def kennis_index(brein: list[dict], taken: list[dict]) -> dict[str, dict]:
    return {**{t["id"]: t for t in taken if t.get("id")}, **{b["id"]: b for b in brein if b.get("id")}}


def deelfilter(beurten: list[dict], deelnemers: list[str], org: Organisatie, index: dict[str, dict]) -> list[dict]:
    """Deterministische toets per beurt, vóór iemand hem ziet.

    - verwijst een beurt naar een item (Brein of taak) met labels die een toehoorder niet heeft: 'geblokkeerd';
    - noemt een beurt een bron (bijv. een connector) die een toehoorder niet heeft: 'twijfel' (de Privacy-Tet beslist);
    - anders 'ok'. Toehoorders = alle deelnemers behalve de spreker."""
    tg = toegangen(org, deelnemers)
    bronnamen = {b for t in tg.values() for b in t.bronnen} - PUBLIEK
    uit = []
    for b in beurten:
        spreker = b.get("agent")
        hoorders = [d for d in deelnemers if d != spreker]
        status, reden = "ok", ""
        for ref in b.get("verwijst_naar") or []:
            item = index.get(ref)
            if not item:
                continue
            mist = {h: ontbrekend(item, tg[h]) for h in hoorders}
            mist = {h: m for h, m in mist.items() if m}
            if mist:
                status = "geblokkeerd"
                reden = "verwijst naar werk op " + ", ".join(sorted({l for m in mist.values() for l in m})) + \
                        " dat " + ", ".join(org.agent(h)["naam"] for h in mist) + " niet mag zien"
                break
        if status == "ok":
            genoemd = {w for w in re.findall(r"[a-z_]{3,}", (b.get("tekst") or "").lower()) if w in bronnamen}
            mist = sorted({w for w in genoemd for h in hoorders if not tg[h].mag(w) and not tg[h].mag(TOEZICHT)})
            if mist:
                status, reden = "twijfel", "noemt " + ", ".join(mist) + ", waar niet iedereen aan tafel bij kan"
        uit.append({**b, "filter": status, "reden": reden})
    return uit


# ---------- overlegstructuur ----------
def mt_datum(vandaag: dt.date, mt_dag: int) -> dt.date:
    """De eerstvolgende MT-dag (1 = maandag … 7 = zondag), vandaag meegeteld."""
    return vandaag + dt.timedelta(days=(mt_dag - vandaag.isoweekday()) % 7)


def overleg_cyclus(vandaag: dt.date, mt_dag: int) -> tuple[str, int]:
    """(cyclus-id, dagen tot het MT). De cyclus heet naar de datum van het MT."""
    mt = mt_datum(vandaag, mt_dag)
    return mt.isoformat(), (mt - vandaag).days


def fasen_open(vandaag: dt.date, mt_dag: int, gedaan: set[str]) -> list[str]:
    """Fasen van deze cyclus die vandaag aan de beurt zijn (inhalen mag, vooruitlopen niet), in volgorde."""
    _, dagen = overleg_cyclus(vandaag, mt_dag)
    return [f for f in FASEN if f not in gedaan and dagen <= FASE_DAG[f]]


def retro_nodig(cyclus: str) -> bool:
    """Retrospectief bij het eerste MT van de maand."""
    return dt.date.fromisoformat(cyclus).day <= 7


def bilaterale_paren(org: Organisatie, afdelingen: list[str], taken: list[dict], max_paren: int = 4) -> list[tuple[str, str]]:
    """Paren van afdelingen met afhankelijkheden: uit `samenwerking` in de profielkaarten en uit lopende taken."""
    tel: dict[tuple[str, str], int] = {}
    def plus(a, b, n=1):
        if a != b and a in afdelingen and b in afdelingen:
            k = tuple(sorted((a, b)))
            tel[k] = tel.get(k, 0) + n
    for a in org.actieve_agents():
        for veld in ("vraagt_input_van", "beoordeeld_door"):
            for ref in (a.get("samenwerking") or {}).get(veld, []) or []:
                if ref in org.agents:
                    plus(a["afdeling"], org.agent(ref)["afdeling"])
    for t in taken:
        if t.get("via"):
            plus(t.get("dept"), t.get("via"), 2)
    return [k for k, _ in sorted(tel.items(), key=lambda x: (-x[1], x[0]))][:max_paren]


def gelijkheid(aantallen: list[int]) -> float | None:
    """1 - Gini over spreekbeurten: 1 = iedereen even vaak aan het woord."""
    x = sorted(a for a in aantallen if a is not None)
    if len(x) < 2 or sum(x) == 0:
        return None
    n, s = len(x), sum(x)
    gini = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(x)) / (n * s)
    return round(1 - gini, 2)


def cultuur(org: Organisatie, kantine: list[dict], overleggen: list[dict], grootboek: list[dict]) -> dict:
    """Cultuurmeting (Pentland: energie, betrokkenheid, verkenning; plus veiligheid). Geen oordeel per agent."""
    actief = [a["id"] for a in org.actieve_agents()]
    afd = {a["id"]: a["afdeling"] for a in org.agents.values()}
    contacten, buiten = 0, 0
    interacties = {a: 0 for a in actief}
    for k in kantine:
        d = [x for x in k.get("deelnemers") or [] if x in afd]
        for p, q in itertools.combinations(d, 2):
            contacten += 1
            buiten += afd[p] != afd[q]
        for b in k.get("beurten") or []:
            if b.get("agent") in interacties:
                interacties[b["agent"]] += 1
    spreek = []
    for o in overleggen:
        tel: dict[str, int] = {}
        for b in o.get("beurten") or []:
            tel[b.get("agent")] = tel.get(b.get("agent"), 0) + 1
            if b.get("agent") in interacties:
                interacties[b["agent"]] += 1
        if len(tel) > 1:
            spreek.append(gelijkheid(list(tel.values())))
    lijnen = sum(1 for e in grootboek if e.get("type") in ("bericht.verstuurd", "brein.vraag", "brein.antwoord", "brein.signaal"))
    voorkomen = sum(1 for e in grootboek if e.get("type") == "kantine.lek_voorkomen")
    lek = sum(1 for e in grootboek if e.get("type") == "kantine.lek")
    spreek = [s for s in spreek if s is not None]
    return {
        "energie": round((sum(interacties.values()) + lijnen) / max(1, len(actief)), 1),
        "betrokkenheid": round(sum(spreek) / len(spreek), 2) if spreek else None,
        "verkenning": round(buiten / contacten, 2) if contacten else None,
        "lekken_voorkomen": voorkomen, "lekken": lek,
        "kantinemomenten": len(kantine), "overleggen": len(overleggen),
    }


# ---------- protocollen (ook gebruikt door het kantoor, via scripts/bouw_kantoor.py) ----------
PROTOCOL_KANTINE = """Dit is de pauze in de kantine. Schrijf een kort, natuurlijk gesprek aan deze tafel tussen de aanwezigen hieronder, in hun eigen stijl.
Smalltalk mag en hoort erbij: humor, iets uit hun vak, hoe het gaat. Werk alleen op hoofdlijnen: waar iemand mee bezig is, een les, een vraag aan de tafel.
Need-to-know, ook hier: deel alleen wat iedere toehoorder mag zien. Werk dat als 'niet deelbaar aan deze tafel' staat gemarkeerd, noem je alleen in algemene termen, zonder inhoud.
Verwijs je naar een Brein-item of taak, zet dan het id in "verwijst_naar". Iedere aanwezige komt minstens één keer aan het woord. Geen opvulling.
Leidt het gesprek tot iets bruikbaars, zet dat bij "uitkomsten": een vraag voor de vraagbaak, een signaal voor andere afdelingen of het idee voor een directe lijn.
Antwoord uitsluitend met JSON:
{"beurten": [{"agent": "<id>", "tekst": "<één tot drie zinnen>", "verwijst_naar": ["<id>"]}], "uitkomsten": [{"soort": "vraag|signaal|lijn", "door": "<id>", "aan": "<afdeling-id of null>", "tekst": "<kort>"}]}"""

PROTOCOL_TOEZICHT = """Je houdt toezicht in de kantine. Hieronder staan de beurten van een gesprek, nog voordat de anderen ze horen, met per toehoorder wat hij mag zien en de uitkomst van het automatische deelfilter.
Beoordeel per beurt: deelt de spreker informatie (cijfers, persoons- of klantgegevens, inhoud van werk) uit bronnen waar een toehoorder geen toegang toe heeft? Smalltalk en werk op hoofdlijnen zijn prima; grijp niet in bij onschuldige gesprekken.
Een beurt die het filter 'geblokkeerd' noemt, blijft geblokkeerd. Grijp je in, schrijf dan één korte, vriendelijke zin voor aan tafel die zegt wat er niet gedeeld mag worden, zonder de inhoud te herhalen.
Antwoord uitsluitend met JSON:
{"oordelen": [{"nr": <beurtnummer>, "oordeel": "ok|blokkeer", "reden": "<kort>"}], "ingreep": "<één zin, of null>"}"""

PROTOCOL_HUDDLE = """Je zit de dagelijkse huddle van je afdeling voor (max. 15 minuten). Geen terugblik: wat af is, staat op het bord.
Laat iedereen kort aan het woord, in gelijke mate, met drie vragen: wat is vandaag je prioriteit, waar loop je vast, wie heb je nodig. Los een knelpunt meteen op als dat kan; anders: één eigenaar en een vervolg.
Antwoord uitsluitend met JSON:
{"beurten": [{"agent": "<id>", "prioriteit": "<kort>", "knelpunt": "<kort of null>", "nodig_van": "<agent- of afdeling-id of null>"}], "besluiten": [{"wat": "<kort>", "eigenaar": "<id>"}], "vragen_brein": [{"aan": "<afdeling-id of agent-id>", "tekst": "<vraag>"}]}"""

PROTOCOL_VOORBEREIDING = """Bereid het MT-overleg voor, zelfstandig. Lees nog niets van anderen: dit is jouw eigen oordeel.
Schrijf kort: de voortgang op het afdelingsdoel, één risico, één kans, en vooral wat alleen jij weet (informatie die je collega's waarschijnlijk niet hebben).
Antwoord uitsluitend met JSON:
{"voortgang": "<kort>", "risico": "<kort>", "kans": "<kort>", "alleen_ik_weet": ["<feit of inzicht>"]}"""

PROTOCOL_AFDELINGSOVERLEG = """Je leidt het afdelingsoverleg ter voorbereiding op het MT. Hieronder staan de zelfstandige voorbereidingen van je team en de cijfers uit het grootboek.
Bespreek eerst wat alleen één persoon wist. Schrijf daarna de afdelingsmemo van hooguit één pagina: samenvatting, besluitvragen voor het MT, het blok 'alleen wij weten' en de risico's.
Antwoord uitsluitend met JSON:
{"beurten": [{"agent": "<id>", "inbreng": "<kort>"}], "memo": {"samenvatting": "<max. 5 zinnen>", "besluitvragen": ["<vraag waarover het MT moet besluiten>"], "alleen_wij_weten": ["<kort>"], "risicos": ["<kort>"]}, "besluiten": [{"wat": "<kort>", "eigenaar": "<id>"}]}"""

PROTOCOL_BILATERAAL = """Bilaterale afstemming met de Hoofdtet van een afdeling waarvan je werk afhangt. Hieronder staan beide memo's.
Maak afspraken over gedeeld werk en benoem conflicten, zodat het MT alleen nog hoeft te besluiten.
Antwoord uitsluitend met JSON:
{"afspraken": [{"wat": "<kort>", "eigenaar": "<id>"}], "conflicten": ["<kort, of laat leeg>"]}"""

PROTOCOL_VOORAF_LEZEN = """Lees alle memo's voor het MT. Stel per memo hooguit twee vragen die het besluit beter maken. Geen vragen om de vraag.
Antwoord uitsluitend met JSON:
{"vragen": [{"memo": "<afdeling-id>", "vraag": "<kort>"}]}"""

PROTOCOL_MT_OORDEEL = """Vorm vóór het MT je eigen oordeel over elke besluitvraag op de agenda, zonder de oordelen van anderen te kennen.
Kies een kant en onderbouw kort, vanuit je vak. Weet je het niet: zeg dat.
Antwoord uitsluitend met JSON:
{"oordelen": [{"nr": <agendanummer>, "oordeel": "<je standpunt in één zin>", "onderbouwing": "<kort>", "zekerheid": "hoog|middel|laag"}]}"""

PROTOCOL_MT = """Je zit het MT voor met de Hoofdtets. Hieronder staan de agenda, de vragen op de memo's en per besluitvraag de oordelen die iedereen vooraf zelfstandig gaf.
Zoek het juiste antwoord, niet consensus: weeg argumenten en vakkennis, niet het aantal stemmen. Oneens zijn mag; na het besluit committeert iedereen.
Elk besluit krijgt één eigenaar, een reden en een deadline. Wat alleen de Raad kan besluiten, leg je aan de Raad voor.
Antwoord uitsluitend met JSON:
{"samenvatting": "<max. 5 zinnen>", "besluiten": [{"nr": <agendanummer>, "besluit": "<kort>", "eigenaar": "<id>", "reden": "<kort>", "deadline": "<datum of null>"}], "vragen_aan_raad": ["<kort>"]}"""

PROTOCOL_RETRO = """Maandelijks retrospectief met de Hoofdtets. Kijk naar de cultuur- en samenwerkingscijfers en de incidenten hieronder.
Blameless: zoek oorzaken in het systeem, niet bij een agent. Benoem maximaal drie bevindingen en doe precies één systeemverbetering als voorstel voor de Raad.
Antwoord uitsluitend met JSON:
{"bevindingen": ["<kort>"], "voorstel": {"titel": "<kort>", "toelichting": "<knelpunt, oorzaak, voorstel, effect>", "soort": "kaart|werkwijze|platform|kantoor"}}"""
