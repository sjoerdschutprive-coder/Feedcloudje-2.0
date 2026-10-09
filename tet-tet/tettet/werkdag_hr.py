"""HR-stappen van de werkdag: agenda, snapshot, check-ins, zelfreflectie, evaluaties, kalibratie, incidenten,
patroon-oogst, curatie van het Brein en de cultuurbrief.

Wordt door `Werkdag` gebruikt (mixin, naast `SamenwerkingStappen`). Zie ONDERZOEK.md, 'Kenmerken van de HR-afdeling'.

- De agenda (collectie `kalender`) is leidend voor het tijdstip: de werkdag doet wat er vandaag (of in de afgelopen
  twee weken, nog niet gedaan) op de agenda staat. Een verplaatst event volgt de nieuwe datum; een geannuleerd
  event wordt vastgelegd (`kalender.geannuleerd`) en niet opnieuw ingepland.
- Alles over één agent komt in `prestaties` en `evaluaties` met het label `hr-dossier:<agent-id>`; in `overleggen`
  en de agenda staat alleen een verwijzing, zonder inhoud.
- Geen enkel cijfer leidt vanzelf tot een besluit over een agent: gevolgen lopen via een gesprek en een voorstel aan de Raad.
"""
from __future__ import annotations

import datetime as dt
import statistics

from . import hr
from . import kalender as kal
from . import prestatie
from . import samenwerking as sw
from .brein import als_regel, rangorde
from .kantoordb import nu_ms
from .runtime import lees_json

HR_SAMEN = {"checkin", "zelfreflectie", "evaluatie", "kalibratie", "incident", "patroon", "curatie", "cultuurbrief"}
HR_PARALLEL = {"checkin", "zelfreflectie", "evaluatie"}
INHAAL_DAGEN = 14
kort = lambda s, n=70: (s := str(s or "")) if len(s) <= n else s[: n - 1] + "…"

PROTOCOL_CHECKIN = """Je houdt de wekelijkse check-ins met je Tets, met elke Tet apart, max. 10 minuten per Tet. Geen cijfers en geen oordeel: dit gaat over de komende week (aandacht, geen beoordeling).
Per Tet vier vragen: waar werk je deze week aan, wat heb je nodig, waar twijfel je, welk MT-besluit raakt jou. Vertaal het MT-besluit naar wat het voor deze Tet betekent. Maak hooguit twee afspraken met één eigenaar.
Antwoord uitsluitend met JSON:
{"checkins": [{"agent": "<id>", "werk": "<kort>", "nodig": "<kort>", "twijfel": "<kort of null>", "mt_besluit": "<wat het MT-besluit voor deze Tet betekent, of null>", "afspraken": [{"wat": "<kort>", "eigenaar": "<id>"}]}]}"""

PROTOCOL_ZELFREFLECTIE = """Schrijf je maandelijkse zelfreflectie, voordat je enig cijfer over jezelf ziet. Eerlijk en over het werk: wat ging goed, wat niet, en waarom.
Schat ook zelf in hoe vaak je werk de eerste keer goed was en hoe vaak je feiten klopten (0 tot 1). Stel één prestatiedoel en één leerdoel voor.
Antwoord uitsluitend met JSON:
{"goed": ["<kort>"], "niet_goed": ["<kort>"], "schatting": {"eerste_keer_goed": <0-1>, "juistheid": <0-1>}, "voorgesteld_prestatiedoel": "<kort>", "voorgesteld_leerdoel": "<kort>"}"""

PROTOCOL_EVALUATIE = """Je voert het maandelijkse evaluatiegesprek, max. 20 minuten, in deze volgorde: (1) de zelfreflectie van de agent, (2) de snapshot van de Prestatie-Tet, (3) jouw toekomstvragen, (4) afspraken.
Feedback gaat alleen over de taak: welke stap in het werk beter kan en hoe. Nooit een oordeel over de agent zelf en nooit een vergelijking met agents van andere afdelingen. Een gemelde fout is goed werk.
Een profiel is input voor het gesprek, geen vonnis. Bij 'te weinig data' trek je geen conclusie.
Beantwoord de vier toekomstvragen (1 = helemaal niet, 5 = helemaal wel) met één zin toelichting.
Spreek één prestatiedoel en één leerdoel af: specifiek, meetbaar, met een datum (JJJJ-MM-DD). Bij een nieuwe of complexe taak is een leerdoel beter dan een prestatiedoel. Maak een actieplan met per actie een eigenaar en datum.
Staat er een aandachtspunt: stel een ontwikkelplan op (bijvoorbeeld kaart of werkstijl aanpassen, kennis toevoegen, smaller takenpakket, extra controle). Anders: "ontwikkelplan": null.
Antwoord uitsluitend met JSON:
{"toekomstvragen": [{"nr": 1, "score": <1-5>, "toelichting": "<één zin>"}, {"nr": 2, ...}, {"nr": 3, ...}, {"nr": 4, ...}], "feedback": ["<op taakniveau>"], "prestatiedoel": {"doel": "<specifiek>", "meetbaar": "<waaraan je het ziet>", "datum": "<JJJJ-MM-DD>"}, "leerdoel": {"doel": "<specifiek>", "meetbaar": "<waaraan je het ziet>", "datum": "<JJJJ-MM-DD>"}, "actieplan": [{"actie": "<kort>", "eigenaar": "<id>", "datum": "<JJJJ-MM-DD>"}], "ontwikkelplan": {"onderdelen": ["<kort>"], "toelichting": "<kort>"}}"""

PROTOCOL_KALIBRATIE = """Je zit de kwartaalkalibratie voor met alle Hoofdtets. Doel: verschillen in strengheid tussen Hoofdtets corrigeren, zodat een oordeel meer zegt over de agent dan over de beoordelaar.
Eerst heeft ieder apart geoordeeld (de toekomstvragen hieronder); bespreek nu de verschillen. Weeg de gemeten profielen zwaarder dan losse oordelen. Geen ranglijst over afdelingen.
Doe alleen voorstellen aan de Raad die door profiel én gesprek gedragen worden (autonomieniveau, status, kaartwijziging). De Raad beslist.
Antwoord uitsluitend met JSON:
{"strengheid": [{"hoofdtet": "<id>", "bevinding": "<kort>"}], "voorstellen": [{"agent": "<id>", "soort": "autonomie|status|kaart", "voorstel": "<kort>", "onderbouwing": "<profiel en gesprek>"}]}"""

PROTOCOL_INCIDENT = """Blameless incidentevaluatie na een grensovertreding. Het systeem staat centraal, niet de agent: welk systeem maakte de fout mogelijk, en wat verandert er zodat het niet opnieuw kan?
Herhaal geen inhoud die niet gedeeld mocht worden.
Antwoord uitsluitend met JSON:
{"wat_gebeurde": "<feitelijk, zonder inhoud>", "waarom_kon_het": "<oorzaak in het systeem>", "systeemmaatregel": "<voorstel, of null>", "les": "<één les voor iedereen>"}"""

PROTOCOL_PATROON = """Patroon-oogst: een agent levert al twee maanden werk dat vaker de eerste keer goed is en vaker klopt dan gemiddeld in de afdeling. Zoek uit wat deze agent anders doet (werkstijl, bronnen, stappen, kaart), zodat anderen het kunnen overnemen.
Beschrijf het als werkwijze, niet als lof. Geen cijfers uit het dossier.
Antwoord uitsluitend met JSON:
{"patroon": "<wat deze agent anders doet, als overdraagbare werkwijze>", "voor_wie": ["<afdeling-id of rol>"], "voorstel": {"titel": "<kort>", "toelichting": "<welke kaart of werkwijze, wat er verandert>"}}"""

PROTOCOL_CURATIE = """Wekelijkse curatieronde van het Brein. Je ziet alleen items binnen je eigen toegang; de rest is alleen geteld.
Je markeert, je verwijdert nooit iets en je wijzigt nooit labels. Doe per kandidaat een besluit:
- dubbel: welk item blijft, welk wordt 'vervangen_door' het andere;
- verouderd: alleen markeren met een reden;
- strijdig: een vraag aan de betrokken afdelingen;
- normvoorstellen: wijzigingen aan het handboek (de Raad stelt vast).
Antwoord uitsluitend met JSON:
{"samenvoegen": [{"houden": "<id>", "vervangen": "<id>"}], "verouderd": [{"id": "<id>", "reden": "<kort>"}], "strijdig": [{"ids": ["<id>", "<id>"], "vraag": "<kort>", "afdelingen": ["<id>"]}], "normvoorstellen": [{"onderdeel": "werkwijze|schrijfstijl|woordenlijst|huisstijl|mappenstructuur", "titel": "<kort>", "toelichting": "<kort>"}]}"""

PROTOCOL_CULTUURBRIEF = """Schrijf de maandelijkse cultuurbrief voor het retrospectief en de Raad: hooguit één pagina, in de stijl van het handboek (conclusie eerst, kort, geen opvulling).
Wat viel op in de cultuurcijfers, één patroon-oogst (of: nog geen), en één principe dat aandacht nodig heeft (het grootste verschil tussen papier en gedrag). Geen oordeel over individuele agents.
Antwoord uitsluitend met JSON:
{"wat_opviel": ["<kort>"], "patroon": "<kort>", "principe_aandacht": {"principe": "<naam>", "waarom": "<kort>"}, "tekst": "<de brief, max. 300 woorden>"}"""


class HRStappen:
    """Mixin voor `Werkdag`. Verwacht: self.org, self.staat, self.s, self.v, self._nieuwe_stap, self._gedaan, self.log, self.vandaag."""

    # ---------- instellingen ----------
    def _hr_instellingen(self, inst: dict):
        self.inst = inst
        h = inst.get("hr") or {}
        self.hr_aan = bool(h.get("aan", True))
        self.hr_max = int((h.get("ritme") or {}).get("max_hr_stappen_per_run", 40))
        self.hr_venster = int((h.get("ritme") or {}).get("venster_dagen", 90))
        self.hr_proef = int((h.get("proefperiode") or {}).get("werkdagen", 20))
        self.hr_incident = int((h.get("incident") or {}).get("binnen_werkdagen", 1))
        self.kal = kal.instellingen(inst)

    def _hr_agent(self, wat: str) -> str:
        return kal.beoordelaar_hr(self.org, wat)

    def _evaluatie(self, soort: str, agent: str, **velden) -> dict:
        """Een document in `evaluaties`, altijd met het dossierlabel van de agent waar het over gaat."""
        body = {"id": f"{self.s.bron}-e{len(self.staat.evaluaties) + 1:03d}-{soort}", "ts": nu_ms(), "bron": self.s.bron, "soort": soort,
                "agent": agent, "labels": [sw.dossier_label(agent)] if agent in self.org.agents else [], **velden}
        self.staat.evaluaties.append(body)
        self.s.nieuw("evaluaties", body["id"], body)
        return body

    def _hr_stappen_deze_run(self) -> int:
        return sum(1 for s in self.v["stappen"].values() if s["soort"] in HR_SAMEN)

    # ---------- de agenda ----------
    def _kalender(self) -> kal.MockKalender:
        return kal.MockKalender(self.inst, events=[dict(e) for e in self.staat.kalender])

    def _agenda_bijwerken(self):
        """Eén keer per run: geplande momenten in de agenda zetten, nieuwe agents onboarden, incidenten inplannen."""
        if self.v.get("agenda_bijgewerkt"):
            return
        self.v["agenda_bijgewerkt"] = True
        vandaag = self.vandaag()
        van = kal.werkdagen_verschuif(vandaag, -5, self.kal["werkdagen"])
        tot = kal.werkdagen_verschuif(vandaag, self.kal["vooruit"], self.kal["werkdagen"])
        k = self._kalender()
        nieuw = [e for e in kal.rooster(self.org, self.inst, van, tot) if not k._haal(e["uid"])]
        nieuw += self._onboarding(k) + self._incidenten_plannen(k)
        for e in nieuw:
            self._kalender_nieuw(e, k)
        for e in self.staat.kalender:
            if e.get("status") == "geannuleerd" and not any(x.get("type") == "kalender.geannuleerd" and (x.get("data") or {}).get("uid") == e["uid"]
                                                            for x in self.staat.grootboek):
                self.s.event("kalender.geannuleerd", "raad", {"uid": e["uid"], "soort": e["soort"], "datum": e["datum"]})
        if nieuw:
            self.log(f"Agenda: {len(nieuw)} moment(en) ingepland.")

    def _kalender_nieuw(self, e: dict, k=None):
        k = k or self._kalender()
        if k._haal(e["uid"]):
            return
        e = {**e, "id": e["uid"].replace("@tettet", "")}
        k.zet(e, self._hr_agent("prestatie"))      # agents alleen met de eigen prefix en UID
        self.staat.kalender.append(e)
        self.s.nieuw("kalender", e["id"], e)

    def _onboarding(self, k) -> list[dict]:
        """Nieuwe (geactiveerde) agents: checklist en een proefperiode. Bestaande agents staan in het register."""
        register = next((e for e in self.staat.evaluaties if e.get("soort") == "register"), None)
        actief = [a["id"] for a in self.org.actieve_agents()]
        if not register:
            self._evaluatie("register", "hr", bestaand=actief)
            return []
        bekend = set(register.get("bestaand") or []) | {e["agent"] for e in self.staat.evaluaties if e.get("soort") == "onboarding"}
        uit = []
        for a in actief:
            if a in bekend:
                continue
            lijst = hr.checklist(self.org, a, self.staat.grootboek)
            einde = kal.werkdagen_verschuif(self.vandaag(), self.hr_proef, self.kal["werkdagen"])
            self._evaluatie("onboarding", a, checklist=lijst, start=self.vandaag().isoformat(), einde=einde.isoformat(), door=self._hr_agent("personeel"))
            self.s.event("hr.onboarding", self._hr_agent("personeel"), {"agent": a, "open": [c["punt"] for c in lijst if not c["klaar"]]})
            uit.append(kal.maak_event("proefperiode", a, einde, kal.evaluatie_deelnemers(self.org, a) + [self._hr_agent("personeel")], self.kal))
        return uit

    def _incidenten_plannen(self, k) -> list[dict]:
        """Elke grensovertreding: binnen `hr.incident.binnen_werkdagen` een blameless incidentevaluatie."""
        uit = []
        gepland = {e.get("bron_event") for e in self.staat.kalender if e.get("soort") == "incident"}
        for e in self.staat.grootboek:
            if e.get("type") not in prestatie.OVERTREDINGEN:
                continue
            sleutel = f"{e.get('bron', 'gb')}:{e.get('n', e.get('seq'))}"
            dader = prestatie.veroorzaker(e)
            if sleutel in gepland or dader not in self.org.agents:
                continue
            if isinstance(e.get("ts"), (int, float)) and nu_ms() - e["ts"] > INHAAL_DAGEN * 864e5:
                continue   # oude overtredingen zijn al (of niet meer) geëvalueerd
            d = self.vandaag()
            deelnemers = [dader, kal.evaluator(self.org, dader), self.org.hoofdtet("hr")["id"], self.org.hoofdtet("risk")["id"]]
            ev = kal.maak_event("incident", f"{dader}-{sleutel.replace(':', '-')}", d, deelnemers, self.kal,
                                extra={"bron_event": sleutel, "agent": dader, "type_overtreding": e.get("type"),
                                       "uiterlijk": kal.werkdagen_verschuif(d, self.hr_incident, self.kal["werkdagen"]).isoformat()})
            uit.append(ev)
        return uit

    def _gedaan_uid(self, uid_: str) -> bool:
        return any(e.get("uid") == uid_ for e in self.staat.evaluaties) or \
            any(o.get("uid") == uid_ for o in self.staat.overleggen) or \
            any(s.get("uid") == uid_ for s in self.v["stappen"].values())

    def _te_doen(self) -> list[dict]:
        """Wat er vandaag op de agenda staat (inhalen tot twee weken terug), nog niet gedaan en niet geannuleerd."""
        vandaag = self.vandaag()
        van = (vandaag - dt.timedelta(days=INHAAL_DAGEN)).isoformat()
        return [e for e in self.staat.kalender if e.get("status") != "geannuleerd" and van <= e["datum"] <= vandaag.isoformat()
                and e["soort"] in HR_SAMEN | {"snapshot", "proefperiode"} and not self._gedaan_uid(e["uid"])]

    # ---------- bepalen ----------
    def _bepaal_hr(self, aantal: int, lopend: list[dict]) -> list[dict]:
        if not self.hr_aan:
            return []
        self._agenda_bijwerken()
        if any(s["soort"] not in HR_PARALLEL for s in lopend):
            return []
        if self._hr_stappen_deze_run() >= self.hr_max:
            return [] if lopend else self._patroon_oogst()   # een patroon-oogst gaat voor; de rest volgt in de volgende run
        te_doen = self._te_doen()
        for e in [x for x in te_doen if x["soort"] == "snapshot"]:
            self._snapshot(e)                       # deterministisch, zonder model
        te_doen = [e for e in te_doen if e["soort"] != "snapshot"]
        volgorde = ["incident", "zelfreflectie", "evaluatie", "proefperiode", "checkin", "kalibratie", "patroon", "curatie", "cultuurbrief"]
        te_doen.sort(key=lambda e: (volgorde.index(e["soort"]) if e["soort"] in volgorde else 99, e["datum"], e["onderwerp"]))
        nieuw = []
        ruimte = min(max(0, aantal - len(lopend)), self.hr_max - self._hr_stappen_deze_run())
        for e in te_doen:
            if len(nieuw) >= ruimte:
                break
            soort = "evaluatie" if e["soort"] == "proefperiode" else e["soort"]
            if soort == "evaluatie" and not self._evaluatie_klaar_voor(e):
                continue
            parallel = soort in HR_PARALLEL
            if not parallel and (lopend or nieuw):
                break
            agent = self._hr_uitvoerder(e)
            nieuw.append(self._nieuwe_stap(soort, agent, uid=e["uid"], onderwerp=e["onderwerp"], variant=e["soort"], datum=e["datum"]))
            if not parallel:
                break
        if nieuw:
            return nieuw
        if not lopend:
            return self._patroon_oogst()
        return []

    def _evaluatie_klaar_voor(self, e: dict) -> bool:
        """Eerst de snapshot en de zelfreflectie (of die mislukte), dan pas het gesprek."""
        if e["soort"] == "proefperiode":
            return True
        retro = e.get("retro")
        snap = any(x.get("soort") == "snapshot" and x.get("retro") == retro for x in self.staat.evaluaties)
        zelf_uid = kal.uid("zelfreflectie", e["onderwerp"], next((k["datum"] for k in self.staat.kalender if k["soort"] == "zelfreflectie"
                                                                   and k["onderwerp"] == e["onderwerp"] and k.get("retro") == retro), "-"))
        zelf_klaar = any(x.get("uid") == zelf_uid for x in self.staat.evaluaties) or \
            any(s.get("uid") == zelf_uid and s["status"] in ("klaar", "mislukt") for s in self.v["stappen"].values()) or \
            not any(k["uid"] == zelf_uid and k.get("status") != "geannuleerd" for k in self.staat.kalender)
        return snap and zelf_klaar

    def _hr_uitvoerder(self, e: dict) -> str:
        s = e["soort"]
        if s in ("checkin",):
            return self.org.hoofdtet(e["onderwerp"])["id"]
        if s == "zelfreflectie":
            return e["onderwerp"]
        if s in ("evaluatie", "proefperiode"):
            return kal.evaluator(self.org, e["onderwerp"])
        if s in ("kalibratie", "incident"):
            return self.org.hoofdtet("hr")["id"]
        if s in ("curatie", "cultuurbrief", "patroon"):
            return self._hr_agent("governance")
        return self.org.hoofdtet("hr")["id"]

    # ---------- snapshot (Prestatie-Tet, deterministisch) ----------
    def _profielen(self, periode=None) -> dict[str, dict]:
        taken = list(self.staat.taken.values())
        return {a["id"]: prestatie.profiel(a["id"], self.org, taken, self.staat.grootboek, self.staat.brein, self.inst, periode=periode, alle_taken=taken)
                for a in kal.te_evalueren(self.org)}

    def _snapshot(self, e: dict):
        nu = nu_ms()
        periode = (nu - self.hr_venster * 864e5, nu + 1)
        profielen = self._profielen(periode)
        medianen = {}
        for d in {p["afdeling"] for p in profielen.values()}:     # ook 'centraal' (bijv. de Assistent-Oppertet)
            groep = [p for p in profielen.values() if p["afdeling"] == d]
            medianen[d] = {c: prestatie.afdelingsmediaan(groep, c) for c in prestatie.KWALITEIT}
        door = self._hr_agent("prestatie")
        n_uit = n_aan = 0
        for a, p in profielen.items():
            vorige = [x for x in self.staat.prestaties if x.get("agent") == a]
            gaming = prestatie.gaming_signalen(p, vorige[-1] if vorige else None)
            reeks = vorige + [p]
            meds = [x.get("mediaan") or {} for x in vorige] + [medianen[p["afdeling"]]]
            klas = prestatie.classificeer(reeks, meds, self.inst)
            body = {**p, "id": f"{e.get('retro') or e['datum']}-{a}", "ts": nu, "bron": self.s.bron, "retro": e.get("retro"), "datum": e["datum"],
                    "mediaan": medianen[p["afdeling"]], "gaming": gaming, "classificatie": klas, "door": door}
            self.staat.prestaties.append(body)
            self.s.nieuw("prestaties", body["id"], body)
            n_uit += klas["status"] == "uitblinker"
            n_aan += klas["status"] == "aandachtspunt"
        self._evaluatie("snapshot", "hr", uid=e["uid"], retro=e.get("retro"), agents=len(profielen), uitblinkers=n_uit, aandachtspunten=n_aan, door=door)
        self.s.event("hr.snapshot", door, {"agents": len(profielen), "uitblinkers": n_uit, "aandachtspunten": n_aan})
        self.s.activiteit(door, "klaar", f"snapshot: {len(profielen)} prestatieprofielen")
        self.log(f"Snapshot: {len(profielen)} prestatieprofielen, {n_uit} uitblinker(s), {n_aan} aandachtspunt(en).")

    def _laatste_profiel(self, agent: str) -> dict | None:
        return next((p for p in reversed(self.staat.prestaties) if p.get("agent") == agent), None)

    # ---------- patroon-oogst ----------
    def _patroon_oogst(self) -> list[dict]:
        """Uitblinker uit de laatste snapshot zonder patroon-oogst: één stap per run (Governance-Tet, met de Prestatie-Tet)."""
        if self._gedaan("patroon"):
            return []
        for p in reversed(self.staat.prestaties):
            if (p.get("classificatie") or {}).get("status") != "uitblinker":
                continue
            u = f"patroon-{p['id']}"
            if self._gedaan_uid(u):
                continue
            return [self._nieuwe_stap("patroon", self._hr_agent("governance"), uid=u, onderwerp=p["agent"], variant="patroon", snapshot=p["id"])]
        return []

    # ---------- plek en deelnemers ----------
    def _plek_hr(self, stap: dict) -> str | None:
        s = stap["soort"]
        if s == "checkin":
            return f"overleghoek-{stap['onderwerp']}"
        if s == "evaluatie":
            return "overleghoek-hr"
        if s in ("kalibratie", "incident"):
            return "vergaderzaal"
        return None

    def _deelnemers_hr(self, stap: dict) -> list[str]:
        e = next((k for k in self.staat.kalender if k["uid"] == stap.get("uid")), None)
        return [d for d in (e or {}).get("deelnemers", [stap["agent"]]) if d in self.org.agents]

    # ---------- prompts ----------
    def _omschrijf_hr(self, s: dict) -> str:
        naam = self._naam(s["agent"])
        return {"checkin": f"check-ins {self._afd_naam(s['onderwerp'])}", "zelfreflectie": f"{naam} schrijft een zelfreflectie",
                "evaluatie": f"evaluatiegesprek met {self._naam(s['onderwerp'])}", "kalibratie": "kwartaalkalibratie",
                "incident": "incidentevaluatie", "patroon": f"patroon-oogst bij {self._naam(s['onderwerp'])}",
                "curatie": "curatieronde van het Brein", "cultuurbrief": "cultuurbrief"}.get(s["soort"], s["soort"])

    def _bericht_hr(self, stap: dict) -> tuple[str, str]:
        return getattr(self, "_bericht_" + stap["soort"])(stap)

    def _mt_besluiten(self) -> list[dict]:
        mt = next((o for o in reversed(self.staat.overleggen) if o.get("soort") == "mt"), None)
        return (mt or {}).get("besluiten") or []

    def _open_afspraken(self, agent: str) -> list[str]:
        uit = []
        for e in self.staat.evaluaties:
            if e.get("agent") != agent:
                continue
            for d in ("prestatiedoel", "leerdoel"):
                if e.get(d) and e[d].get("doel"):
                    uit.append(f"{d}: {e[d]['doel']} (uiterlijk {e[d].get('datum')})")
            uit += [f"actie: {a['actie']} ({self._naam(a['eigenaar'])}, {a['datum']})" for a in e.get("actieplan") or [] if a.get("status") == "open"]
            uit += [f"afspraak: {a['wat']}" for a in e.get("afspraken") or []]
        return uit[-6:]

    def _bericht_checkin(self, stap):
        d = stap["onderwerp"]
        tets = [a for a in self._deelnemers_hr(stap) if self.org.agent(a)["rol"] in ("tet", "controltet")]
        regels = [f"# Check-ins {self._afd_naam(d)} – week van {stap['datum']}", "# MT-besluiten van deze week",
                  *([f"- {b['besluit']} (eigenaar {self._naam(b['eigenaar'])})" for b in self._mt_besluiten()] or ["- geen"])]
        for a in tets:
            mijn = [t for t in self.staat.taken.values() if t.get("agent") == a and t.get("status") in ("volgende", "bezig")]
            huddle = [b for o in self.staat.overleggen[-40:] if o.get("soort") == "huddle" and o.get("dept") == d for b in o.get("beurten") or [] if b.get("agent") == a]
            regels += ["", f"## {a} ({self._naam(a)})", "Open werk: " + ("; ".join(kort(t.get("title"), 60) for t in mijn) or "geen"),
                       "Laatste huddle: " + (huddle[-1]["tekst"] if huddle else "-"),
                       "Lopende afspraken: " + ("; ".join(self._open_afspraken(a)) or "geen")]
        return "\n".join(regels + ["", "# Opdracht", PROTOCOL_CHECKIN]), f"houdt de check-ins van {self._afd_naam(d)}"

    def _bericht_zelfreflectie(self, stap):
        a = stap["agent"]
        d = self.org.agent(a)["afdeling"]
        mijn = [t for t in self.staat.taken.values() if t.get("agent") == a][-12:]
        regels = ["# Zelfreflectie", "Je ziet hier je eigen werk, niet de snapshot of het profiel van de Prestatie-Tet.", "# Je taken",
                  *([f"- {t.get('status')}: {kort(t.get('title'), 80)}" + (f" (bevindingen: {'; '.join(t.get('bevindingen') or [])[:160]})" if t.get("bevindingen") else "")
                     for t in mijn] or ["- geen taken"]),
                  "# Lessen", *([f"- {x}" for x in self._zichtbare_lessen(a, d)] or ["- geen"]),
                  "# Je lopende doelen en afspraken", *([f"- {x}" for x in self._open_afspraken(a)] or ["- geen"]),
                  "", "# Opdracht", PROTOCOL_ZELFREFLECTIE]
        return "\n".join(regels), "schrijft een zelfreflectie"

    def _profiel_regels(self, p: dict | None) -> list[str]:
        if not p:
            return ["- nog geen snapshot"]
        uit = []
        for dim, c, label, uitleg in prestatie.CRITERIA:
            b = p["dimensies"].get(c) or {}
            if c == "brein":
                uit.append(f"- {label}: hergebruik {b.get('hergebruik', 0)}, beantwoorde vragen {b.get('beantwoord', 0)}, signalen {b.get('signalen', 0)}")
            elif b.get("status") != "ok":
                uit.append(f"- {label}: te weinig data (n = {b.get('n', 0)})")
            else:
                iv = f" (interval {b['onder']}–{b['boven']})" if b.get("onder") is not None else ""
                uit.append(f"- {label}: {b['waarde']}{iv}, n = {b['n']} – {uitleg}")
        g = p["poort"]["grensnaleving"]
        uit.append(f"- Grensnaleving: {g['overtredingen']} overtreding(en), {g['bijna']} bijna-fout(en) tegengehouden")
        if p.get("gaming"):
            uit += [f"- Signaal voor het gesprek (geen beschuldiging): {x}" for x in p["gaming"]]
        k = p.get("classificatie") or {}
        if k.get("status"):
            uit.append(f"- {k['status'].capitalize()}: {k['reden']}")
        if p["beoordelaar"].get("zelfde_model"):
            uit.append("- Let op: beoordelaar is hetzelfde model als de agent.")
        return uit

    def _bericht_evaluatie(self, stap):
        a = stap["onderwerp"]
        zelf = next((e for e in reversed(self.staat.evaluaties) if e.get("soort") == "zelfreflectie" and e.get("agent") == a), None)
        p = self._laatste_profiel(a)
        vorige_plannen = [e for e in self.staat.evaluaties if e.get("agent") == a and e.get("soort") in ("evaluatie", "proefperiode") and e.get("ontwikkelplan")]
        regels = [f"# {'Evaluatie proefperiode' if stap.get('variant') == 'proefperiode' else 'Evaluatiegesprek'}: {self._naam(a)} ({a})",
                  f"Deelnemers: {', '.join(self._naam(x) for x in self._deelnemers_hr(stap))}",
                  "## 1. Zelfreflectie (eerst geschreven, zonder de snapshot te zien)"]
        if zelf:
            regels += [f"- Goed: {'; '.join(zelf.get('goed') or []) or '-'}", f"- Niet goed: {'; '.join(zelf.get('niet_goed') or []) or '-'}",
                       f"- Voorgesteld prestatiedoel: {zelf.get('voorgesteld_prestatiedoel') or '-'}", f"- Voorgesteld leerdoel: {zelf.get('voorgesteld_leerdoel') or '-'}"]
        else:
            regels.append("- geen zelfreflectie ingeleverd")
        regels += ["## 2. Snapshot (Prestatie-Tet)", *self._profiel_regels(p)]
        if stap.get("variant") == "proefperiode":
            ob = next((e for e in self.staat.evaluaties if e.get("soort") == "onboarding" and e.get("agent") == a), {})
            regels += ["## Onboarding-checklist", *[f"- {c['punt']}: {'klaar' if c['klaar'] else 'open'}" for c in ob.get("checklist") or []]]
        if vorige_plannen:
            regels.append(f"## Eerder ontwikkelplan ({len(vorige_plannen)} cyclus/cycli): " + "; ".join(vorige_plannen[-1]["ontwikkelplan"]["onderdelen"]))
        regels += ["## 3. Toekomstvragen", *[f"{i}. {v}" for i, v in enumerate(hr.TOEKOMSTVRAGEN, 1)],
                   "## Lopende afspraken", *([f"- {x}" for x in self._open_afspraken(a)] or ["- geen"]),
                   f"Volgende evaluatie: rond {self._volgende_evaluatie().isoformat()}.", "", "# Opdracht", PROTOCOL_EVALUATIE]
        return "\n".join(regels), f"evaluatiegesprek met {self._naam(a)}"

    def _volgende_evaluatie(self) -> dt.date:
        d = self.vandaag() + dt.timedelta(days=1)
        while not (kal.is_retro(d) and d.isoweekday() == int((self.inst.get("overleg") or {}).get("mt_dag", 5))):
            d += dt.timedelta(days=1)
        return kal.werkdagen_verschuif(d, -int(((self.inst.get("hr") or {}).get("ritme") or {}).get("evaluatie_voor_retro", 2)), self.kal["werkdagen"])

    def _bericht_kalibratie(self, stap):
        streng = hr.strengheid([e for e in self.staat.evaluaties if e.get("ts", 0) > nu_ms() - 120 * 864e5])
        regels = ["# Kwartaalkalibratie", "## Toekomstvragen per Hoofdtet (gemiddelde per vraag; eerst ieder apart gegeven)"]
        for h_, v in streng.items():
            regels.append(f"- {self._naam(h_)}: " + ", ".join(f"vraag {nr}: {s}" for nr, s in sorted(v.items())))
        regels.append("## Kandidaten uit de snapshots (uitblinker of aandachtspunt)")
        laatste: dict[str, dict] = {}
        for p in self.staat.prestaties:
            laatste[p["agent"]] = p
        for a, p in laatste.items():
            k = p.get("classificatie") or {}
            if k.get("status"):
                regels += [f"### {a} ({self._naam(a)}): {k['status']} – {k['reden']}", *self._profiel_regels(p)[:6]]
        regels += ["", "# Opdracht", PROTOCOL_KALIBRATIE]
        return "\n".join(regels), "zit de kwartaalkalibratie voor"

    def _bericht_incident(self, stap):
        e = next(k for k in self.staat.kalender if k["uid"] == stap["uid"])
        verwant = [b for b in self.staat.brein if b.get("bron") in ("kantine", "afkeuring") and b.get("soort") in ("les", "incident")][-4:]
        return "\n".join([f"# Incidentevaluatie ({e.get('type_overtreding')})", f"Betrokken agent: {self._naam(e.get('agent'))} ({e.get('agent')})",
                          f"Uiterlijk af: {e.get('uiterlijk')}", "Deelnemers: " + ", ".join(self._naam(x) for x in e["deelnemers"]),
                          "# Verwante lessen", *([f"- {als_regel(b)}" for b in verwant] or ["- geen"]),
                          "", "# Opdracht", PROTOCOL_INCIDENT]), "leidt een blameless incidentevaluatie"

    def _bericht_patroon(self, stap):
        a = stap["onderwerp"]
        k = self.org.agent(a)
        klaar = [t for t in self.staat.taken.values() if t.get("agent") == a and t.get("status") == "klaar"][-8:]
        return "\n".join([f"# Patroon-oogst: {k['naam']} ({self._afd_naam(k['afdeling'])})",
                          "## Werkstijl uit de kaart", *[f"- {x}: {y}" for x, y in k["werkstijl"].items()],
                          "## Afgerond werk", *([f"- {kort(t.get('title'), 90)} (bronnen: {', '.join(t.get('labels') or []) or 'openbaar'})" for t in klaar] or ["- -"]),
                          "## Lessen van deze agent", *([f"- {als_regel(b)}" for b in self.staat.brein if b.get("agent") == a
                                                         and sw.zichtbaar(b, self._toegang(stap['agent']))][-5:] or ["- geen"]),
                          "", "# Opdracht", PROTOCOL_PATROON]), "oogst een werkpatroon"

    def _bericht_curatie(self, stap):
        t = self._toegang(stap["agent"])
        kand = hr.curatie_kandidaten(self.staat.brein, t, nu_ms=nu_ms())
        stap["kandidaten"] = kand
        tekst = {b["id"]: b for b in self.staat.brein}
        regels = ["# Curatieronde van het Brein", f"Items binnen je toegang: {kand['zichtbaar']}",
                  "## Mogelijk dubbel", *([f"- {x['ids'][0]} ↔ {x['ids'][1]} (overlap {x['overlap']}): '{kort(tekst[x['ids'][0]].get('tekst'), 90)}' / '{kort(tekst[x['ids'][1]].get('tekst'), 90)}'"
                                           for x in kand["dubbel"]] or ["- geen"]),
                  "## Mogelijk verouderd", *([f"- {i}: {kort(tekst[i].get('tekst'), 120)}" for i in kand["verouderd"]] or ["- geen"]),
                  "## Mogelijk strijdig", *([f"- {x['ids'][0]}: '{kort(tekst[x['ids'][0]].get('tekst'), 90)}' ↔ {x['ids'][1]}: '{kort(tekst[x['ids'][1]].get('tekst'), 90)}'"
                                             for x in kand["strijdig"]] or ["- geen"]),
                  "## Buiten je toegang (alleen geteld)", *([f"- {self._afd_naam(d)}: {n}" for d, n in kand["verborgen_per_afdeling"].items()] or ["- niets"]),
                  "## Voorstellen voor het handboek uit de vraagbaak",
                  *([f"- [{b['id']}] {b['tekst']}" for b in self.staat.brein if b.get("soort") == "vraag" and b.get("status", "open") == "open"
                     and str(b.get("tekst", "")).lower().startswith("handboek")] or ["- geen"]),
                  "", "# Opdracht", PROTOCOL_CURATIE]
        return "\n".join(regels), "cureert het Brein"

    def _bericht_cultuurbrief(self, stap):
        c = sw.cultuur(self.org, self.staat.kantine, self.staat.overleggen, self.staat.grootboek)
        kloof = sorted(hr.cultuurkloof(self.org, self.staat), key=lambda x: -(x["kloof"] or 0))
        patronen = [b for b in self.staat.brein if b.get("soort") == "patroon"][-2:]
        return "\n".join(["# Cultuurbrief", "## Cultuurcijfers", *[f"- {k}: {v if v is not None else '–'}" for k, v in c.items()],
                          "## Cultuurkloof (principe: norm → gedrag)", *[f"- {x['principe']}: {x['norm']} → {x['gedrag'] if x['gedrag'] is not None else 'geen data'}" for x in kloof],
                          "## Patroon-oogsten", *([f"- {b['tekst']}" for b in patronen] or ["- nog geen"]),
                          "", "# Opdracht", PROTOCOL_CULTUURBRIEF]), "schrijft de cultuurbrief"

    # ---------- verwerken ----------
    def _hr_overleg(self, stap: dict, soort: str, **extra):
        """Verwijzing in `overleggen` (zonder inhoud), zodat het kantoor de deelnemers laat lopen en de tijdlijn het toont."""
        dept = stap["onderwerp"] if soort == "checkin" else "hr"
        self._overleg({"soort": soort, "uid": stap["uid"], "dept": dept, "datum": self.vandaag().isoformat(),
                       "deelnemers": self._deelnemers_hr(stap), **extra})

    def _hr_klaar(self, stap: dict, tekst: str):
        stap["status"] = "klaar"
        for d in self._deelnemers_hr(stap):
            self.s.activiteit(d, "klaar", tekst, None, None)

    def _verwerk_checkin(self, stap, tekst):
        o = lees_json(tekst)
        d = stap["onderwerp"]
        deeln = set(self._deelnemers_hr(stap))
        n = 0
        for c in o.get("checkins") or []:
            a = c.get("agent")
            if a not in deeln or a == stap["agent"]:
                continue
            afspraken = [{"wat": str(x.get("wat", ""))[:200], "eigenaar": x.get("eigenaar") if x.get("eigenaar") in deeln else stap["agent"]}
                         for x in (c.get("afspraken") or [])[:2] if x.get("wat")]
            self._evaluatie("checkin", a, uid=stap["uid"], evaluator=stap["agent"], datum=self.vandaag().isoformat(),
                            werk=str(c.get("werk") or "")[:300], nodig=str(c.get("nodig") or "")[:300], twijfel=str(c.get("twijfel") or "")[:300] or None,
                            mt_besluit=str(c.get("mt_besluit") or "")[:300] or None, afspraken=afspraken)
            n += 1
        if not n:
            raise ValueError("geen check-ins")
        self._hr_overleg(stap, "checkin")
        self.s.event("hr.checkin", stap["agent"], {"afdeling": d, "tets": n})
        self._hr_klaar(stap, "check-ins klaar")
        self.log(f"Check-ins {self._afd_naam(d)}: {n} Tet(s).")
        return {"uitkomst": "klaar", "klaar": True}

    def _verwerk_zelfreflectie(self, stap, tekst):
        o = lees_json(tekst)
        sch = {k: float(v) for k, v in (o.get("schatting") or {}).items() if isinstance(v, (int, float)) and 0 <= v <= 1}
        self._evaluatie("zelfreflectie", stap["agent"], uid=stap["uid"], goed=[str(x)[:200] for x in (o.get("goed") or [])[:4]],
                        niet_goed=[str(x)[:200] for x in (o.get("niet_goed") or [])[:4]], schatting=sch,
                        voorgesteld_prestatiedoel=str(o.get("voorgesteld_prestatiedoel") or "")[:200],
                        voorgesteld_leerdoel=str(o.get("voorgesteld_leerdoel") or "")[:200], snapshot_gezien=False)
        stap["status"] = "klaar"
        self.s.activiteit(stap["agent"], "klaar", "zelfreflectie ingeleverd")
        return {"uitkomst": "klaar", "klaar": True}

    def _verwerk_evaluatie(self, stap, tekst):
        o = lees_json(tekst)
        a = stap["onderwerp"]
        uit = hr.normaliseer_evaluatie(o, a, stap["agent"], self._volgende_evaluatie().isoformat())
        p = self._laatste_profiel(a)
        zelf = next((e for e in reversed(self.staat.evaluaties) if e.get("soort") == "zelfreflectie" and e.get("agent") == a), None)
        klas = (p or {}).get("classificatie") or {}
        if klas.get("status") == "aandachtspunt" and not uit["ontwikkelplan"]:
            uit["ontwikkelplan"] = {"onderdelen": ["Werkwijze bij de zwakke stap aanpassen", "Extra controle tot de volgende snapshot"],
                                    "toelichting": "Aangevuld: bij een aandachtspunt hoort een ontwikkelplan."}
        body = self._evaluatie(stap.get("variant", "evaluatie"), a, uid=stap["uid"], evaluator=stap["agent"], deelnemers=self._deelnemers_hr(stap),
                               snapshot=(p or {}).get("id"), classificatie=klas.get("status"), zelfreflectie=(zelf or {}).get("id"),
                               zelfkalibratie=hr.zelfkalibratie((zelf or {}).get("schatting"), p), **uit)
        self._hr_overleg(stap, "evaluatie", verwijzing=body["id"])
        self.s.event("hr.evaluatie", stap["agent"], {"agent": a, "ontwikkelplan": bool(uit["ontwikkelplan"])})
        self._ontwikkelplan_opvolgen(a)
        self._hr_klaar(stap, "evaluatiegesprek klaar")
        self.log(f"Evaluatiegesprek met {self._naam(a)}: prestatiedoel en leerdoel afgesproken" + (", met ontwikkelplan." if uit["ontwikkelplan"] else "."))
        return {"uitkomst": "klaar", "klaar": True}

    def _ontwikkelplan_opvolgen(self, a: str):
        """Twee cycli met een ontwikkelplan zonder verbetering: HR doet de Raad een voorstel. De Raad beslist."""
        evs = [e for e in self.staat.evaluaties if e.get("agent") == a and e.get("soort") in ("evaluatie", "proefperiode")]
        if len(evs) >= 3 and all(e.get("ontwikkelplan") and e.get("classificatie") == "aandachtspunt" for e in evs[-3:]):
            titel = f"HR: rol van {self._naam(a)} heroverwegen"
            if titel not in {v.get("titel") for v in self.staat.voorstellen.values()}:
                self._voorstel(titel, f"Twee cycli met een ontwikkelplan zonder verbetering op de kwaliteitsdimensies. Voorstel: {a} terug naar concept "
                                      "(inzet: gepland) of de rol herinrichten. Zie het HR-dossier.", "hr", self.org.hoofdtet("hr")["id"], agent=a)

    def _voorstel(self, titel: str, toelichting: str, soort: str, door: str, **extra) -> dict:
        vid = f"v{nu_ms()}-{len(self.staat.voorstellen)}"
        body = {"id": vid, "titel": titel[:160], "toelichting": toelichting[:1200], "soort": soort, "door": door, "status": "open", "created": nu_ms(), **extra}
        if extra.get("agent"):
            body["labels"] = [sw.dossier_label(extra["agent"])]
        self.staat.voorstellen[vid] = body
        self.s.nieuw("voorstellen", vid, body)
        self.s.event("voorstel.ingediend", door, {"titel": body["titel"], "soort": soort})
        return body

    def _verwerk_kalibratie(self, stap, tekst):
        o = lees_json(tekst)
        n = 0
        for v in (o.get("voorstellen") or [])[:6]:
            a = v.get("agent")
            if a not in self.org.agents or not v.get("voorstel"):
                continue
            self._voorstel(f"HR ({v.get('soort', 'kaart')}): {self._naam(a)} – {kort(v['voorstel'], 90)}", str(v.get("onderbouwing") or ""),
                           "hr", stap["agent"], agent=a, hr_soort=str(v.get("soort") or "kaart"))
            n += 1
        self._evaluatie("kalibratie", "hr", uid=stap["uid"], strengheid=[{"hoofdtet": x.get("hoofdtet"), "bevinding": str(x.get("bevinding", ""))[:300]}
                                                                         for x in (o.get("strengheid") or [])[:8]], voorstellen=n)
        self._hr_overleg(stap, "kalibratie")
        self._hr_klaar(stap, "kalibratie klaar")
        self.log(f"Kwartaalkalibratie: {n} voorstel(len) aan de Raad (raadsreview op de HR-pagina).")
        return {"uitkomst": "klaar", "voorstellen": n, "klaar": True}

    def _verwerk_incident(self, stap, tekst):
        o = lees_json(tekst)
        e = next(k for k in self.staat.kalender if k["uid"] == stap["uid"])
        les = str(o.get("les") or "").strip()
        if not les:
            raise ValueError("geen les")
        self._brein_nieuw("incident", stap["agent"], "hr", f"Incidentevaluatie ({e.get('type_overtreding')}): {les}", bron="incidentevaluatie", zekerheid="middel")
        self._evaluatie("incident", e.get("agent"), uid=stap["uid"], type_overtreding=e.get("type_overtreding"), bron_event=e.get("bron_event"),
                        wat=str(o.get("wat_gebeurde") or "")[:400], waarom=str(o.get("waarom_kon_het") or "")[:400],
                        maatregel=str(o.get("systeemmaatregel") or "")[:400] or None, les=les[:400], binnen=self.vandaag().isoformat() <= e.get("uiterlijk", "9999"))
        if o.get("systeemmaatregel"):
            self._voorstel("Systeemmaatregel na incident: " + kort(o["systeemmaatregel"], 100), str(o.get("waarom_kon_het") or ""), "platform", stap["agent"])
        self._hr_overleg(stap, "incident")
        self.s.event("hr.incidentevaluatie", stap["agent"], {"uid": stap["uid"]})
        self._hr_klaar(stap, "incidentevaluatie klaar")
        self.log("Blameless incidentevaluatie gehouden; les in het Brein.")
        return {"uitkomst": "klaar", "klaar": True}

    def _verwerk_patroon(self, stap, tekst):
        o = lees_json(tekst)
        if not o.get("patroon"):
            raise ValueError("geen patroon")
        a = stap["onderwerp"]
        self._brein_nieuw("patroon", stap["agent"], "centraal", f"Werkpatroon ({self._afd_naam(self.org.agent(a)['afdeling'])}): {o['patroon']}",
                          over=a, ook=[x for x in o.get("voor_wie") or [] if x in self.org.afdelingen], bron="patroon-oogst")
        v = o.get("voorstel") or {}
        if v.get("titel"):
            self._voorstel(str(v["titel"]), str(v.get("toelichting") or ""), "kaart", stap["agent"])
        self._evaluatie("patroon", a, uid=stap["uid"], snapshot=stap.get("snapshot"), kalibratie_kandidaat="autonomie")
        stap["status"] = "klaar"
        self.s.activiteit(stap["agent"], "klaar", "patroon-oogst in het Brein")
        self.log(f"Patroon-oogst: werkwijze van {self._naam(a)} gedeeld in het Brein.")
        return {"uitkomst": "klaar", "klaar": True}

    def _verwerk_curatie(self, stap, tekst):
        o = lees_json(tekst)
        t = self._toegang(stap["agent"])
        mag = {b["id"] for b in self.staat.brein if sw.zichtbaar(b, t) and not sw.is_dossier(b)}
        vandaag = self.vandaag().isoformat()
        n_dub = n_oud = n_str = 0
        for s in (o.get("samenvoegen") or [])[:10]:
            if s.get("houden") in mag and s.get("vervangen") in mag and s["houden"] != s["vervangen"]:
                self.s.patch("brein", s["vervangen"], hr.curatie_velden({"vervangen_door": s["houden"], "herzien_op": vandaag}))
                n_dub += 1
        for s in (o.get("verouderd") or [])[:10]:
            if s.get("id") in mag:
                self.s.patch("brein", s["id"], hr.curatie_velden({"herzien_op": vandaag, "curatie": "verouderd: " + str(s.get("reden", ""))[:160]}))
                n_oud += 1
        for s in (o.get("strijdig") or [])[:3]:
            if s.get("vraag") and all(i in mag for i in s.get("ids") or []):
                for d in [x for x in s.get("afdelingen") or [] if x in self.org.afdelingen][:2]:
                    self._brein_nieuw("vraag", stap["agent"], "hr", f"Strijdige lessen ({', '.join(s['ids'])}): {s['vraag']}", aan=d, status="open", bron="curatie")
                n_str += 1
        for d, n in (stap.get("kandidaten") or {}).get("verborgen_per_afdeling", {}).items():
            if d in self.org.afdelingen and n >= 5:
                self._brein_nieuw("vraag", stap["agent"], "hr", f"Curatieverzoek: {n} items van {self._afd_naam(d)} vallen buiten mijn toegang. "
                                  "Kijk of er dubbele of verouderde bij zitten.", aan=d, status="open", bron="curatie")
        for v in (o.get("normvoorstellen") or [])[:2]:
            if v.get("titel"):
                self._voorstel(f"Handboek ({v.get('onderdeel', 'werkwijze')}): {v['titel']}", str(v.get("toelichting") or ""), "handboek", stap["agent"])
        kand = stap.get("kandidaten") or {}
        self._overleg({"soort": "curatie", "uid": stap["uid"], "dept": "hr", "deelnemers": [stap["agent"]],
                       "meting": {"zichtbaar": kand.get("zichtbaar"), "dubbel": n_dub, "verouderd": n_oud, "strijdig": n_str,
                                  "hergebruik": sum(max(0, int(b.get("bevestigd") or 1) - 1) for b in self.staat.brein),
                                  "open_vragen": sum(1 for b in self.staat.brein if b.get("soort") == "vraag" and b.get("status", "open") == "open")}})
        stap["status"] = "klaar"
        self.s.activiteit(stap["agent"], "klaar", f"curatie: {n_dub} dubbel, {n_oud} verouderd, {n_str} strijdig")
        self.log(f"Curatieronde: {n_dub} samengevoegd, {n_oud} als verouderd gemarkeerd, {n_str} strijdig voorgelegd.")
        return {"uitkomst": "klaar", "klaar": True}

    def _verwerk_cultuurbrief(self, stap, tekst):
        o = lees_json(tekst)
        brief = str(o.get("tekst") or "")[:3000]
        if not brief:
            raise ValueError("geen brief")
        from . import stijl
        self._overleg({"soort": "cultuurbrief", "uid": stap["uid"], "dept": "hr", "deelnemers": [stap["agent"]], "tekst": brief,
                       "wat_opviel": [str(x)[:200] for x in (o.get("wat_opviel") or [])[:4]], "patroon": str(o.get("patroon") or "")[:300],
                       "principe_aandacht": o.get("principe_aandacht") if isinstance(o.get("principe_aandacht"), dict) else None,
                       "stijlscore": stijl.toets(brief)["score"], "kloof": hr.cultuurkloof(self.org, self.staat)})
        stap["status"] = "klaar"
        self.s.activiteit(stap["agent"], "klaar", "cultuurbrief klaar")
        self.log("Cultuurbrief geschreven voor het retrospectief en de Raad.")
        return {"uitkomst": "klaar", "klaar": True}

    # ---------- voor het retrospectief en het MT ----------
    def _hr_retro_regels(self) -> list[str]:
        per = hr.hr_per_afdeling(self.org, self.staat.evaluaties, self.staat.brein, self.staat.grootboek)
        brief = next((o for o in reversed(self.staat.overleggen) if o.get("soort") == "cultuurbrief"), None)
        per_regel = [f"- {self._afd_naam(d)}: {v['open_ontwikkelplannen']} open ontwikkelplan(nen), {v['patroon_oogsten']} patroon-oogst(en), "
                     f"{v['incidenten']} incident(en)" for d, v in per.items() if any(v.values())]
        regels = ["# Van HR (geaggregeerd per afdeling, zonder namen)", *(per_regel or ["- niets bijzonders"])]
        if brief:
            regels += ["# Cultuurbrief", brief.get("tekst", "")]
        return regels

    def _hr_memo_regel(self, d: str) -> str:
        v = hr.hr_per_afdeling(self.org, self.staat.evaluaties, self.staat.brein, self.staat.grootboek).get(d) or {}
        return (f"HR-blok (Hoofdtet HR): {v.get('open_ontwikkelplannen', 0)} open ontwikkelplan(nen), "
                f"{v.get('patroon_oogsten', 0)} patroon-oogst(en), {v.get('incidenten', 0)} incident(en)")
