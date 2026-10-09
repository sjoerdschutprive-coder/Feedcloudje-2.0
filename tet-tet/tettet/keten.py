"""De keten: Raad -> Oppertet -> Hoofdtet -> Tet -> Control Tet, met taakloop en afdelingsloop.

Het Kantoor bevat de hele organisatie in werking. Een doelstelling van de Raad wordt door de Oppertet
vertaald naar afdelingsdoelen, door Hoofdtets naar taken, door Tets uitgevoerd en door Control Tets getoetst.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from . import BASIS
from .beleid import Beleidsmotor, Budget, BudgetOverschreden, Geweigerd
from .brein import Brein, als_regel
from .grootboek import Grootboek
from .kaarten import Organisatie
from .runtime import Agent, laad_instellingen, lees_json, maak_client
from .taken import Taak, Takenmarkt


@dataclass
class Doelstelling:
    naam: str
    omschrijving: str = ""
    deadline: str | None = None
    id: str = field(default_factory=lambda: "D-" + time.strftime("%Y%m%d%H%M%S"))


@dataclass
class Afdelingsdoel:
    afdeling: str
    doel: str
    hoofdlijnen: list[str]
    waarom: str = ""


MEETBAARHEID = ("klant", "product", "periode", "kpi")

PROTOCOL_OPPERTET = """Toets eerst of de doelstelling meetbaar is op vier punten: klant (voor wie), product (wat er moet liggen), periode (tot wanneer) en KPI (waaraan succes te meten is). Gebruik naam, omschrijving en deadline; vul niets zelf in.
Ontbreekt er één, zet dan "meetbaar": false, noem wat ontbreekt en stel precies één verduidelijkingsvraag aan de Raad. Zet in dat geval alleen afdelingsdoelen voor werk dat in elk geval nodig is (zoals de kostenmeting per taak), of geen.
Is de doelstelling meetbaar, vertaal haar dan naar afdelingsdoelen. Zet alleen afdelingen in die echt iets bijdragen, en geef elk doel 1 tot 4 hoofdlijnen (deelresultaten).
Antwoord uitsluitend met JSON in deze vorm:
{"meetbaar": true, "ontbreekt": ["klant|product|periode|kpi"], "vraag_aan_raad": "<één vraag, of null>", "afdelingsdoelen": [{"afdeling": "<id>", "doel": "<één zin>", "hoofdlijnen": ["<deelresultaat>"], "waarom": "<één zin>"}]}"""


def verduidelijking_uit(plan: dict) -> dict | None:
    """Verduidelijkingsvraag van de Oppertet als de doelstelling niet meetbaar is, anders None."""
    if not isinstance(plan, dict) or plan.get("meetbaar") is not False:
        return None
    ontbreekt = [str(x).lower() for x in plan.get("ontbreekt") or [] if str(x).lower() in MEETBAARHEID]
    vraag = str(plan.get("vraag_aan_raad") or "").strip() or "Kun je de doelstelling meetbaar maken (klant, product, periode, KPI)?"
    return {"vraag": vraag[:500], "ontbreekt": ontbreekt, "door": "oppertet"}

PROTOCOL_HOOFDTET = """Maak per hoofdlijn één taak voor een Tet uit je afdeling. Geef context, geen stappenplan: wat moet er liggen en wanneer is het goed.
Gebruik "toets": "feiten" als de taak vooral cijfers of bronnen oplevert, anders "kwaliteit".
Antwoord uitsluitend met JSON in deze vorm:
{"taken": [{"opdracht": "<wat>", "acceptatiecriteria": ["<toetsbaar criterium>"], "toegewezen": "<tet-id>", "budget_eur": <getal>, "toets": "kwaliteit|feiten"}]}"""

PROTOCOL_TET = """Voer de taak uit binnen je toegang. Antwoord in vier delen:
## Resultaat
<het werk zelf, conclusie eerst>
## Zelfcheck
<per acceptatiecriterium: voldaan of niet, en waarom>
## Zekerheid
<hoog, middel of laag, met de reden als het niet hoog is>
## Les
<één concrete les voor de volgende keer>
Werk vanuit het Brein: gebruik de lessen, de wie-weet-wat-gids en de open vragen hierboven. Voeg zo nodig deze blokken toe (weglaten mag):
## Bronnen
<de bronnen uit jouw toegang waarop dit werk steunt, bijvoorbeeld: boekhouding, klantsysteem; alleen wie die bronnen ook mag zien, ziet je les>
## Vragen aan het Brein
- [aan: <afdeling-id of agent-id>] <vraag die een collega kan beantwoorden>
## Signalen
- [voor: <afdeling-id>, <afdeling-id>] <bevinding die andere afdelingen raakt>
## Antwoorden
- [<vraag-id>] <antwoord op een open vraag uit het Brein>"""

PROTOCOL_CONTROLTET = """Beoordeel het resultaat zelfstandig, op twee niveaus: de details (criteria, bronnen, berekeningen) en het doel (beantwoordt het de opdracht?). Toets ook op de waarden uit de cultuurkaarten.
Keur af met concrete bevindingen: wat, waarom, en wat er moet veranderen.
Noem bij een afkeuring de faalwijze uit de MAST-indeling als die duidelijk van toepassing is, anders null.
Antwoord uitsluitend met JSON: {"oordeel": "goedgekeurd|afgekeurd", "score": <0-10>, "bevindingen": ["<bevinding>"], "faalwijze": "<MAST-faalwijze of null>"}"""


def afkeurles(titel: str, control_naam: str, bevindingen: list[str], faalwijze: str | None, escalatie: bool) -> str:
    """Tekst van de les of het incident na een afkeuring (blameless: over het werk, niet over de agent)."""
    kop = "Geëscaleerd na afkeuring" if escalatie else "Afgekeurd"
    tekst = f"{kop} door {control_naam} bij '{titel}': " + ("; ".join(bevindingen) or "geen bevindingen genoemd")
    if faalwijze and str(faalwijze).lower() not in ("null", "none", "-"):
        tekst += f" (MAST: {faalwijze})"
    return tekst[:500]


PROTOCOL_VOORSTELLEN = """Je kijkt als R&D naar hoe Tet Tet zelf werkt. Doe 1 tot 3 verbetervoorstellen die de organisatie aantoonbaar beter, sneller of betrouwbaarder maken: aan kaarten, werkwijze, platform of het kantoor. Alleen voorstellen met een concreet knelpunt, een benoemde oorzaak en een begrensd nadeel. Kritisch op hype.
Antwoord uitsluitend met JSON:
{"voorstellen": [{"titel": "<kort>", "toelichting": "<knelpunt, oorzaak, voorstel, verwacht effect>", "soort": "kaart|werkwijze|platform|kantoor"}]}"""


PROTOCOL_ESCALATIE = """Een taak uit jouw afdeling is na herhaalde afkeuring door een Control Tet bij jou geëscaleerd. Lees de opdracht, het laatste resultaat en de bevindingen, en besluit als eigenaar:
- "herformuleer": de opdracht of criteria waren het probleem; geef een scherpere opdracht, toetsbare criteria en kies de Tet die het moet doen.
- "naar_raad": het vraagt een besluit of informatie die alleen de Raad heeft; leg uit wat er nodig is.
Antwoord uitsluitend met JSON:
{"besluit": "herformuleer|naar_raad", "opdracht": "<nieuwe opdracht>", "acceptatiecriteria": ["<toetsbaar>"], "toegewezen": "<tet-id>", "toelichting": "<één of twee zinnen>"}"""

PROTOCOL_ROUTINE = """Dit is je vaste ronde. Kijk naar de cijfers hieronder vanuit jouw rol. Benoem maximaal drie concrete bevindingen, conclusie eerst. Doe hooguit één verbetervoorstel, alleen als er een concreet knelpunt met een benoemde oorzaak is.
Antwoord uitsluitend met JSON:
{"bevindingen": ["<bevinding>"], "voorstel": {"titel": "<kort>", "toelichting": "<knelpunt, oorzaak, voorstel, effect>", "soort": "kaart|werkwijze|platform|kantoor"} of null}"""

PROTOCOL_DAGVERSLAG = """Schrijf het verslag van deze werkdag voor Sjoerd (de Raad). Kort en direct: wat is er gedaan, wat staat er, wat heb je van de Raad nodig. Benoem de grootste afhankelijkheid. Maximaal 12 regels, geen opvulling, eindig niet met een vraag als 'kan ik nog ergens mee helpen'.
Antwoord met platte tekst, geen JSON."""


class Kantoor:
    def __init__(self, *, mock: bool | None = None, opslaan: bool = False, client=None, instellingen: dict | None = None,
                 org: Organisatie | None = None):
        self.inst = instellingen or laad_instellingen()
        self.org = org or Organisatie()
        opslag = self.inst["opslag"]
        self.gb = Grootboek(BASIS / opslag["grootboek"] if opslaan else None)
        self.brein = Brein(BASIS / opslag["brein"] if opslaan else None,
                           drempel=float(self.inst.get("brein", {}).get("overlap_drempel", 0.6)))
        self.markt = Takenmarkt(self.gb, self.inst["taken"]["max_afkeuringen"])
        self.beleid = Beleidsmotor(self.org, self.gb)
        self.budget = Budget(self.gb)
        self.client = client or maak_client(self.inst, mock)
        self._agents: dict[str, Agent] = {}
        self.doelstelling: Doelstelling | None = None
        self.afdelingsdoelen: list[Afdelingsdoel] = []
        self.verduidelijking: dict | None = None

    def agent(self, agent_id: str) -> Agent:
        if agent_id not in self._agents:
            self._agents[agent_id] = Agent(self.org, agent_id, self.client, self.gb, self.inst)
        return self._agents[agent_id]

    # ---------- Raad ----------
    def stel_doelstelling_in(self, doel: Doelstelling) -> Doelstelling:
        self.doelstelling = doel
        self.gb.schrijf("doelstelling.ingesteld", "raad", vars(doel))
        return doel

    # ---------- Oppertet ----------
    def plan_oppertet(self, afdelingen: list[str] | None = None) -> list[Afdelingsdoel]:
        d = self.doelstelling
        if not d:
            raise RuntimeError("De Raad heeft nog geen doelstelling ingesteld.")
        toegestaan = afdelingen or list(self.org.afdelingen)
        bericht = "\n".join([
            "# Doelstelling van de Raad", f"Naam: {d.naam}", f"Omschrijving: {d.omschrijving or '-'}",
            f"Deadline: {d.deadline or 'geen'}", "", "# Afdelingen die je mag inzetten",
            *[f"- {a} ({self.org.afdelingen[a]['naam']}): {self.org.afdelingen[a]['missie']}" for a in toegestaan],
            "", "# Opdracht", PROTOCOL_OPPERTET])
        self.beleid.eis("oppertet", "opdrachten.van_raad_vertalen", d.naam)
        plan = lees_json(self.agent("oppertet").vraag(bericht, doel="afdelingsdoelen"))
        self.verduidelijking = verduidelijking_uit(plan)
        if self.verduidelijking:
            self.gb.schrijf("doelstelling.verduidelijking_gevraagd", "oppertet", self.verduidelijking)
        self.afdelingsdoelen = [Afdelingsdoel(x["afdeling"], x["doel"], list(x.get("hoofdlijnen", [])), x.get("waarom", ""))
                                for x in plan["afdelingsdoelen"] if x.get("afdeling") in toegestaan]
        for ad in self.afdelingsdoelen:
            self.gb.schrijf("afdelingsdoel.ingesteld", "oppertet", vars(ad))
        return self.afdelingsdoelen

    # ---------- Hoofdtet ----------
    def plan_hoofdtet(self, ad: Afdelingsdoel) -> list[Taak]:
        h = self.org.hoofdtet(ad.afdeling)
        tets = self.org.tets(ad.afdeling)
        bericht = "\n".join([
            f"# Afdelingsdoel {self.org.afdelingen[ad.afdeling]['naam']}", f"Doel: {ad.doel}",
            f"Doelstelling: {self.doelstelling.naam}", *[f"- Hoofdlijn: {x}" for x in ad.hoofdlijnen], "",
            "# Jouw Tets", *[f"- {t['id']} ({t['naam']}): {t['specialisme']}" for t in tets], "",
            "# Opdracht", PROTOCOL_HOOFDTET])
        self.beleid.eis(h["id"], "taken.verdelen_binnen_afdeling", ad.doel)
        plan = lees_json(self.agent(h["id"]).vraag(bericht, doel="taken"))
        taken = []
        geldige_tets = {t["id"] for t in tets}
        for i, x in enumerate(plan.get("taken", []), start=1):
            toegewezen = x.get("toegewezen") if x.get("toegewezen") in geldige_tets else (tets[0]["id"] if tets else None)
            taak = Taak(id=f"{self.doelstelling.id}-{ad.afdeling}-{i}", doel_id=self.doelstelling.id,
                        opdracht=x["opdracht"], acceptatiecriteria=list(x.get("acceptatiecriteria") or ["Beantwoordt de opdracht"]),
                        eigenaar=ad.afdeling, budget_eur=float(x.get("budget_eur") or 2.0),
                        deadline=self.doelstelling.deadline, toegewezen=toegewezen,
                        control_tet=self._kies_control_tet(ad.afdeling, x.get("toets", "kwaliteit")))
            taken.append(self.markt.publiceer(taak, h["id"]))
        return taken

    def _kies_control_tet(self, afdeling: str, toets: str) -> str:
        """Control Tets beoordelen nooit hun eigen afdeling; werk van Risk & Safety gaat naar de Raad."""
        kandidaten = [c for c in self.org.control_tets() if c["afdeling"] != afdeling]
        if not kandidaten:
            return "raad"
        voorkeur = [c for c in kandidaten if toets in c["specialisme"].lower()]
        return (voorkeur or kandidaten)[0]["id"]

    # ---------- Tet + Control Tet (taakloop) ----------
    def voer_uit(self, taak: Taak) -> str:
        tet = taak.toegewezen
        if not tet:
            raise Geweigerd(f"{taak.id}: geen Tet beschikbaar in {taak.eigenaar}")
        self.beleid.eis(tet, "taak.uitvoeren", taak.id)
        self.markt.claim(taak, tet)
        self.markt.start(taak, tet)
        while True:
            lessen = self.brein.lessen_voor(taak.eigenaar, toegang=self.org.effectieve_toegang(tet))
            bericht = "\n\n".join(filter(None, [
                taak.contract(),
                "# Lessen uit het Brein\n" + "\n".join(f"- {als_regel(l)}" for l in lessen) if lessen else "",
                "# Bevindingen van de vorige beoordeling\n" + "\n".join(f"- {b}" for b in taak.bevindingen) if taak.bevindingen else "",
                "# Werkwijze\n" + PROTOCOL_TET]))
            try:
                resultaat = self.agent(tet).vraag(bericht, taak=taak.id, doel="uitvoeren")
                self.budget.controleer(taak.id, taak.budget_eur)
            except BudgetOverschreden as e:
                self.gb.schrijf("budget.overschreden", tet, {"melding": str(e)}, taak=taak.id)
                self.markt._naar(taak, "geëscaleerd", tet, {"reden": "budget"})
                return taak.status
            self.markt.lever_op(taak, tet, resultaat)
            if taak.control_tet == "raad":
                self.beleid.inbox.append({"agent": tet, "handeling": "output.beoordelen", "context": taak.id, "status": "open"})
                self.gb.schrijf("goedkeuring.gevraagd", tet, {"reden": "eigen afdeling Risk & Safety"}, taak=taak.id)
                return taak.status
            status = self._beoordeel(taak)
            if status == "afgerond":
                self._leer(taak)
                return status
            self._leer_van_afkeuring(taak, escalatie=status == "geëscaleerd")
            if status == "geëscaleerd":
                self.gb.schrijf("escalatie", taak.control_tet, {"naar": self.org.hoofdtet(taak.eigenaar)["id"],
                                                               "bevindingen": taak.bevindingen}, taak=taak.id)
                return status

    def _beoordeel(self, taak: Taak) -> str:
        ct = taak.control_tet
        self.beleid.eis(ct, "output.toetsen", taak.id)
        self.beleid.gebruik_bron(ct, "alle_afdelingsoutput", "r", taak.id)
        bericht = "\n\n".join([taak.contract(), "# Resultaat van de Tet\n" + (taak.resultaat or ""), "# Werkwijze\n" + PROTOCOL_CONTROLTET])
        try:
            oordeel = lees_json(self.agent(ct).vraag(bericht, taak=taak.id, doel="toetsen"))
        except ValueError:
            oordeel = {"oordeel": "afgekeurd", "score": None, "bevindingen": ["Beoordeling was niet leesbaar; opnieuw toetsen."]}
        self._laatste_oordeel = oordeel
        return self.markt.beoordeel(taak, ct, oordeel.get("oordeel") == "goedgekeurd",
                                    list(oordeel.get("bevindingen", [])), oordeel.get("score"))

    def _leer(self, taak: Taak):
        m = re.search(r"## Les\s*\n(.+?)(?:\n##|\Z)", taak.resultaat or "", re.S)
        zeker = re.search(r"## Zekerheid\s*\n\s*(\w+)", taak.resultaat or "")
        if m:
            self.brein.schrijf("les", taak.toegewezen, taak.eigenaar, m.group(1).strip(), taak=taak.id,
                               zekerheid=zeker.group(1).lower() if zeker else None)
        h = self.org.hoofdtet(taak.eigenaar)["id"]
        self.gb.schrijf("output.geaccordeerd", h, {"door_control_tet": taak.control_tet}, taak=taak.id)

    def _leer_van_afkeuring(self, taak: Taak, escalatie: bool):
        """Bijna-fouten tellen mee: elke afkeuring of escalatie wordt een les of incident in het Brein,
        met zekerheid laag zolang de Hoofdtet de afkeuring niet heeft bevestigd."""
        oordeel = getattr(self, "_laatste_oordeel", {}) or {}
        tekst = afkeurles(taak.opdracht, self.org.agent(taak.control_tet)["naam"], list(taak.bevindingen),
                          oordeel.get("faalwijze"), escalatie)
        self.brein.schrijf("incident" if escalatie else "les", taak.control_tet, taak.eigenaar, tekst, taak=taak.id,
                           bron="afkeuring", zekerheid="laag")
        self.gb.schrijf("brein.afkeurles", taak.control_tet, {"escalatie": escalatie}, taak=taak.id)

    # ---------- alles achter elkaar ----------
    def draai(self, doel: Doelstelling, afdelingen: list[str] | None = None) -> str:
        self.stel_doelstelling_in(doel)
        for ad in self.plan_oppertet(afdelingen):
            for taak in self.plan_hoofdtet(ad):
                self.voer_uit(taak)
        return self.verslag()

    def verslag(self) -> str:
        d = self.doelstelling
        regels = [f"# Verslag: {d.naam}", f"Doelstelling {d.id} · deadline {d.deadline or 'geen'}", ""]
        for ad in self.afdelingsdoelen:
            taken = [t for t in self.markt.taken.values() if t.eigenaar == ad.afdeling]
            regels += [f"## {self.org.afdelingen[ad.afdeling]['naam']}: {ad.doel}"]
            for t in taken:
                kosten = self.gb.kosten(taak=t.id)
                regels.append(f"- {t.opdracht} · {self.org.agent(t.toegewezen)['naam'] if t.toegewezen else '-'} · "
                              f"{t.status} · {t.afkeuringen}× afgekeurd · {kosten:.4f} euro")
            regels.append("")
        overtredingen = len(self.gb.zoek(type="beleid.overtreding"))
        regels += ["## Totaal", f"- Taken per status: {self.markt.per_status()}",
                   f"- Kosten: {self.gb.kosten():.4f} euro"
                   + (" (geschat; mockmodus doet geen echte aanroepen)" if type(self.client).__name__ == "MockClient" else ""),
                   f"- Beleidsovertredingen: {overtredingen}",
                   f"- Open in de goedkeuringsinbox: {sum(1 for i in self.beleid.inbox if i['status'] == 'open')}",
                   f"- Lessen in het Brein: {sum(1 for i in self.brein.items if i['soort'] == 'les')}",
                   f"- Grootboek intact: {'ja' if not self.gb.controleer() else 'NEE'} ({len(self.gb.events)} events)"]
        return "\n".join(regels)
