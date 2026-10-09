"""Tests voor de directie: de Assistent-Oppertet, de escalatieroute met directe lijn, het besluitenregister en de fallback.

Alles in mockmodus, zonder API. De assistent is ingezet (`inzet: actief`); voor de fallback-tests wordt een kopie van de
kaarten gemaakt waarin hij weer op `inzet: gepland` staat.
"""
import datetime as dt
import json
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

from tettet import BASIS
from tettet import directie as dr
from tettet import samenwerking as sw
from tettet.beleid import Beleidsmotor
from tettet.grootboek import Grootboek
from tettet.kaarten import Organisatie
from tettet.validatie import valideer_lijn
from tettet.werkdag import Werkdag
from tests.test_samenwerking import antwoord as antwoord_samen, pas_batches_toe, schrijf_dump

ORG_ACTIEF = Organisatie()
ASS = "oppertet-a"
ORIGINEEL = "Leverancier X levert pas in week 50; dat raakt de klantbelofte. Origineel-7731."
UNIEK = "Alleen-wij-weten-{d}: de klant wil eigenlijk iets anders"


def org_zonder_assistent() -> Organisatie:
    """Kopie van de kaarten met de Assistent-Oppertet op gepland (fallback)."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    shutil.copytree(BASIS / "kaarten", tmp / "kaarten")
    pad = tmp / "kaarten" / "agents" / f"{ASS}.yaml"
    pad.write_text(pad.read_text(encoding="utf-8").replace("\ninzet: actief", "\ninzet: gepland"), encoding="utf-8")
    return Organisatie(tmp / "kaarten")


ORG = org_zonder_assistent()


def antwoord(stap: dict, prompt: str, escalatie_soort: str = "operationeel", assistent_handelt_af: bool = False) -> str:
    s = stap["soort"]
    if s == "escalatie":
        return json.dumps({"besluit": "naar_raad", "soort": escalatie_soort, "toelichting": ORIGINEEL})
    if s == "escalatie_triage":
        if stap["agent"] == ASS:
            return json.dumps({"besluit": "afhandelen" if assistent_handelt_af else "naar_oppertet", "afspraak": "Operations levert vóór vrijdag de planning aan Finance",
                               "eigenaar": "ops-h", "samenvatting": "Leverancier is laat.", "voorstel": "Prioriteit verschuiven"})
        return json.dumps({"besluit": "naar_raad", "toelichting": "Vraagt een besluit over de klantbelofte."})
    if s == "afdelingsoverleg":
        return json.dumps({"beurten": [], "memo": {"samenvatting": "Op schema.", "besluitvragen": [f"Prioriteit voor {stap['afdeling']}?"],
                                                   "alleen_wij_weten": [UNIEK.format(d=stap["afdeling"])], "risicos": []}, "besluiten": []})
    if s == "vooraf_lezen" and stap["agent"] == ASS:
        return json.dumps({"vragen": [{"memo": "fin", "vraag": "Wat is de deadline?"}], "volgorde": [2, 1], "zonder_alleen_wij_weten": []})
    if s == "mt":
        return json.dumps({"samenvatting": "Besloten.", "besluiten": [{"nr": 1, "besluit": "Finance gaat voor", "eigenaar": "fin-h", "reden": "afhankelijkheid",
                                                                      "deadline": "2026-11-20"}], "vragen_aan_raad": []})
    if s == "directiehuddle":
        return json.dumps({"beurten": [{"agent": "oppertet", "prioriteit": "MT voorbereiden", "knelpunt": None, "nodig_van": None},
                                       {"agent": ASS, "prioriteit": "register bijwerken", "knelpunt": None, "nodig_van": None}],
                           "besluiten": [{"wat": "Assistent bundelt de memo's", "eigenaar": ASS}]})
    if s == "doorvertalen":
        rid = stap["register"][0]
        return json.dumps({"opdrachten": [{"register": rid, "afdeling": "fin", "opdracht": "Plan Finance-werk eerst in", "eigenaar": "fin-h", "reden": "MT-besluit",
                                           "deadline": "2026-11-20"}], "vraag_aan_oppertet": None})
    if s == "opvolging":
        return json.dumps({"status": [{"register": r, "status": "achter", "toelichting": "nog geen taak", "zekerheid": "middel"} for r in stap["register"]],
                           "aanspreken": [{"eigenaar": "fin-h", "vraag": "Wanneer start het Finance-werk?"}]})
    return antwoord_samen(stap, prompt)


class Basis(unittest.TestCase):
    org = ORG

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.dump = self.tmp / "dump"
        org = self.org
        self.patch = mock.patch("tettet.werkdag.Organisatie", lambda: org)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.tmp)

    def stap(self, werk, verwacht: str, **kw) -> tuple[dict, str, dict]:
        """Eén stap: volgende -> prompt -> antwoord -> verwerk. Geeft (stap, prompt, uitkomst)."""
        uit = Werkdag(werk).volgende(1)
        self.assertTrue(uit["stappen"], f"geen stap, verwacht {verwacht}")
        stap = uit["stappen"][0]
        self.assertEqual(stap["soort"], verwacht)
        p = Werkdag(werk).prompt(stap["id"])
        prompt = pathlib.Path(p["prompt"]).read_text()
        s = json.loads((werk / "voortgang.json").read_text())["stappen"][stap["id"]]
        pathlib.Path(p["antwoord"]).write_text(antwoord(s, prompt, **kw))
        return s, prompt, Werkdag(werk).verwerk(stap["id"])

    def geescaleerde_taak(self):
        schrijf_dump(self.dump, {"staat": {"doel": {"naam": "", "deadline": ""}, "instellingen": {"modus": "mock"}},
                                 "taken": {"te": {"id": "te", "dept": "ops", "agent": "ops-1", "title": "Leverplanning", "status": "volgende", "approval": False,
                                                  "created": 1, "criteria": ["c"], "control": "risk-c1", "afkeuringen": 2, "geescaleerd": True,
                                                  "bevindingen": ["Planning ontbreekt"], "resultaat": "## Resultaat\nx"}}})
        werk = self.tmp / "werk"
        Werkdag.start(self.dump, werk)
        return werk


class KaartenEnLijnTest(unittest.TestCase):
    def test_kaart_gepland_en_toegang_deelverzameling(self):
        a = ORG.agent(ASS)
        self.assertEqual(a["rol"], "assistent_oppertet")
        self.assertEqual(ORG_ACTIEF.agent(ASS).get("inzet"), "actief")
        self.assertEqual(ORG_ACTIEF.assistent()["id"], ASS)
        self.assertIsNone(ORG.assistent())
        t, top = ORG.effectieve_toegang(ASS), ORG.effectieve_toegang("oppertet")
        for bron, recht in t.bronnen.items():
            self.assertTrue(top.mag(bron, recht), bron)
        self.assertNotIn("agentregister", t.bronnen)
        self.assertLess(ORG.niveau("oppertet"), ORG.niveau(ASS))
        self.assertLess(ORG.niveau(ASS), ORG.niveau("fin-h"))

    def test_geen_voorbehouden_besluiten(self):
        for h in ("prioriteiten.bepalen", "budget.verdelen", "escalaties.beslechten", "opdrachten.van_raad_vertalen", "kaarten.wijzigen"):
            self.assertFalse(ORG.mag_handeling(ASS, h), h)
        self.assertTrue(ORG.mag_handeling(ASS, "besluiten.doorvertalen"))

    def test_leidinggevende_volgt_inzet(self):
        self.assertEqual(ORG.leidinggevende("fin-h"), "oppertet")
        self.assertNotIn("heb je een directe lijn", ORG.systeemprompt("fin-h"))
        self.assertEqual(ORG_ACTIEF.leidinggevende("fin-h"), ASS)
        self.assertEqual(ORG_ACTIEF.leidinggevende("fin-1"), "fin-h")
        p = ORG_ACTIEF.systeemprompt("fin-h")
        self.assertIn("Je rapporteert aan Assistent-Oppertet", p)
        self.assertIn("directe lijn naar Oppertet", p)

    def test_validator_regels(self):
        rollen = {r: dict(ORG.rollen[r]) for r in ORG.rollen}
        agents = {k: dict(v) for k, v in ORG.agents.items()}
        self.assertEqual(valideer_lijn(agents, rollen, ORG.toegang), [])
        twee = {**agents, "x-a": {**agents[ASS], "id": "x-a"}}
        self.assertTrue(any("meer dan één" in f for f in valideer_lijn(twee, rollen, ORG.toegang)))
        fout_baas = {**agents, ASS: {**agents[ASS], "rapporteert_aan": "fin-h"}}
        self.assertTrue(any("rapporteert aan de oppertet" in f or "niet hoger" in f for f in valideer_lijn(fout_baas, rollen, ORG.toegang)))
        ruim = {**rollen, "rol-assistent-oppertet": {**rollen["rol-assistent-oppertet"], "mag": [*rollen["rol-assistent-oppertet"]["mag"], "budget.verdelen"]}}
        self.assertTrue(any("voorbehouden" in f for f in valideer_lijn(agents, ruim, ORG.toegang)))
        cirkel = {**agents, "oppertet": {**agents["oppertet"], "rapporteert_aan": ASS}}
        self.assertTrue(any("cirkel" in f for f in valideer_lijn(cirkel, rollen, ORG.toegang)))
        breed = {**agents, ASS: {**agents[ASS], "mandaat": {"toegangskaart": "toegang-fin", "inperkingen": []}}}
        self.assertTrue(any("gaat verder" in f for f in valideer_lijn(breed, rollen, ORG.toegang)))


class RouteTest(unittest.TestCase):
    def test_route_zonder_en_met_assistent(self):
        self.assertEqual(dr.escalatieroute(ORG, "fin-h")["naar"], "raad")
        op = dr.escalatieroute(ORG_ACTIEF, "fin-h", "operationeel")
        self.assertEqual(op["route"], ["fin-h", ASS, "oppertet", "raad"])
        risico = dr.escalatieroute(ORG_ACTIEF, "fin-h", "risico")
        self.assertEqual((risico["naar"], risico["kopie"], risico["direct"]), ("oppertet", [ASS], True))
        self.assertTrue(dr.escalatieroute(ORG_ACTIEF, "fin-h", "oneens_assistent")["direct"])

    def test_beleidsmotor_legt_route_vast(self):
        gb = Grootboek()
        route = Beleidsmotor(ORG_ACTIEF, gb).escaleer("ops-h", "integriteit", taak="t1", toelichting=ORIGINEEL)
        self.assertEqual(route["naar"], "oppertet")
        types = [e["type"] for e in gb.events]
        self.assertEqual(types, ["escalatie.route", "escalatie.kopie"])
        self.assertEqual(gb.events[0]["data"]["toelichting"], ORIGINEEL)


class FallbackTest(Basis):
    """Assistent gepland: een escalatie naar de Raad werkt exact zoals daarvoor."""

    def test_escalatie_naar_raad_zonder_assistent(self):
        werk = self.geescaleerde_taak()
        _, prompt, _ = self.stap(werk, "escalatie")
        self.assertNotIn("oneens_assistent", prompt)
        st = Werkdag(werk).staat
        t = st.taken["te"]
        self.assertTrue(t["approval"])
        self.assertEqual(t["raadsvraag"], ORIGINEEL)
        self.assertIsNone(t.get("escalatie_bij"))
        uit = Werkdag(werk).volgende(1)
        self.assertNotIn("escalatie_triage", [s["soort"] for s in uit["stappen"]])


class EscalatieViaDirectieTest(Basis):
    org = ORG_ACTIEF

    def test_operationeel_via_assistent_naar_oppertet_en_raad(self):
        werk = self.geescaleerde_taak()
        _, prompt, _ = self.stap(werk, "escalatie")
        self.assertIn("oneens_assistent", prompt)
        t = Werkdag(werk).staat.taken["te"]
        self.assertFalse(t["approval"])
        self.assertEqual(t["escalatie_bij"], ASS)
        s, p_ass, _ = self.stap(werk, "escalatie_triage")
        self.assertEqual(s["agent"], ASS)
        self.assertIn(ORIGINEEL, p_ass)
        s, p_opp, _ = self.stap(werk, "escalatie_triage")
        self.assertEqual(s["agent"], "oppertet")
        # het origineel staat vóór de samenvatting van de assistent, ongewijzigd
        self.assertLess(p_opp.index(ORIGINEEL), p_opp.index("Samenvatting en voorstel"))
        st = Werkdag(werk).staat
        t = st.taken["te"]
        self.assertTrue(t["approval"])
        self.assertTrue(t["raadsvraag"].startswith(ORIGINEEL))
        types = [e["type"] for e in st.grootboek]
        self.assertIn("escalatie.route", types)
        self.assertIn("escalatie.doorgezet", types)
        # de Hoofdtet liep naar het kantoortje van de Oppertet, de Tet eerder naar dat van zijn Hoofdtet
        plekken = {(a["agent"], a.get("plek")) for a in st.activiteit}
        self.assertIn(("ops-h", "kantoor-oppertet"), plekken)
        self.assertIn(("ops-1", "kantoor-ops-h"), plekken)

    def test_assistent_handelt_af(self):
        werk = self.geescaleerde_taak()
        self.stap(werk, "escalatie")
        self.stap(werk, "escalatie_triage", assistent_handelt_af=True)
        st = Werkdag(werk).staat
        t = st.taken["te"]
        self.assertEqual((t["status"], t["geescaleerd"], t.get("escalatie_bij")), ("volgende", False, None))
        self.assertTrue(any(e["type"] == "escalatie.afgehandeld" for e in st.grootboek))

    def test_risico_via_directe_lijn(self):
        werk = self.geescaleerde_taak()
        self.stap(werk, "escalatie", escalatie_soort="risico")
        st = Werkdag(werk).staat
        self.assertEqual(st.taken["te"]["escalatie_bij"], "oppertet")
        kopie = [e for e in st.grootboek if e["type"] == "escalatie.kopie"]
        self.assertEqual(kopie[0]["agent"], ASS)
        s, prompt, _ = self.stap(werk, "escalatie_triage")
        self.assertEqual(s["agent"], "oppertet")
        self.assertIn(ORIGINEEL, prompt)
        self.assertIn("directe lijn", prompt)
        self.assertEqual(Werkdag(werk).staat.taken["te"]["raadsvraag"].split("\n\n")[0], ORIGINEEL)


def draai(werk):
    batches = []
    for _ in range(300):
        uit = Werkdag(werk).volgende(4)
        batches += uit["batches"]
        if uit["klaar"]:
            break
        for stap in uit["stappen"]:
            for _ in range(6):
                p = Werkdag(werk).prompt(stap["id"])
                batches += p["batches"]
                prompt = pathlib.Path(p["prompt"]).read_text()
                s = json.loads((werk / "voortgang.json").read_text())["stappen"][stap["id"]]
                (werk / "gezien").mkdir(exist_ok=True)
                (werk / "gezien" / f"{s['soort']}-{stap['id']}.md").write_text(prompt)
                pathlib.Path(p["antwoord"]).write_text(antwoord(s, prompt))
                r = Werkdag(werk).verwerk(stap["id"])
                batches += r["batches"]
                if r.get("klaar"):
                    break
    batches += Werkdag(werk).einde()["batches"]
    return batches


class WeekMetAssistentTest(Basis):
    org = ORG_ACTIEF

    def dag(self, datum: dt.date):
        werk = self.tmp / f"werk-{datum.isoformat()}"
        with mock.patch.object(Werkdag, "vandaag", lambda self: datum):
            _, start = Werkdag.start(self.dump, werk)
            batches = start["batches"] + draai(werk)
        pas_batches_toe(self.dump, batches)
        return werk

    def test_week(self):
        schrijf_dump(self.dump, {"staat": {"doel": {"naam": "Test", "omschrijving": "o", "deadline": "2026-12-31"}, "instellingen": {"modus": "mock"}},
                                 "brein": {"bg": {"id": "bg", "soort": "les", "dept": "fin", "agent": "fin-2", "tekst": "Geheime kostprijsles",
                                                  "labels": ["boekhouding"], "ts": 1}}})
        werken = [self.dag(dt.date(2026, 11, d)) for d in range(2, 10) if dt.date(2026, 11, d).isoweekday() <= 5]   # ma 2 t/m ma 9 november
        st = Werkdag(werken[-1]).staat
        soorten = [o["soort"] for o in st.overleggen]
        self.assertGreaterEqual(soorten.count("directiehuddle"), 5)
        self.assertIn("opvolging", soorten)
        voor = [o for o in st.overleggen if o["soort"] == "vooraf_lezen" and o.get("agent") == ASS]
        self.assertEqual(voor[0]["volgorde"], [2, 1])
        mt = next(o for o in st.overleggen if o["soort"] == "mt")
        self.assertIn(ASS, mt["deelnemers"])
        self.assertTrue(any(b["agent"] == ASS and b["tekst"].startswith("opvolging") for b in mt["beurten"]))
        self.assertFalse(any(o["soort"] == "mt_oordeel" and o.get("agent") == ASS for o in st.overleggen))   # geen stem
        reg = [b for b in st.brein if b["soort"] == "register"]
        self.assertEqual(len(reg), 1)
        self.assertTrue(reg[0].get("doorvertaald_ts"))
        self.assertEqual(reg[0]["status"], "achter")
        opdracht = next(b for b in st.brein if b["soort"] == "opdracht")
        self.assertEqual((opdracht["dept"], opdracht["eigenaar"], opdracht["register"]), ("fin", "fin-h", reg[0]["id"]))
        self.assertTrue(any(b["soort"] == "vraag" and b.get("aan") == "fin-h" and b["agent"] == ASS for b in st.brein))
        self.assertTrue(any(e["type"] == "directie.doorvertaald" for e in st.grootboek))

        # 'alleen wij weten' komt ongewijzigd bij de Oppertet in het MT
        vrijdag = next(w for w in werken if w.name.endswith("2026-11-06"))
        mt_prompt = next((vrijdag / "gezien").glob("mt-*.md")).read_text()
        for d in ("ops", "fin", "mkt"):
            if d in {o["dept"] for o in st.overleggen if o["soort"] == "afdelingsoverleg"}:
                self.assertIn(UNIEK.format(d=d), mt_prompt)
        self.assertIn("Opvolging eerdere besluiten", mt_prompt)

        # de assistent ziet niets buiten zijn toegang: niet in zijn eigen prompts, niet in het Brein
        for w in werken:
            for f in (w / "gezien").glob("*.md"):
                tekst = f.read_text()
                if "Je bent nu Assistent-Oppertet" in tekst:
                    self.assertNotIn("Geheime kostprijsles", tekst, f.name)
        self.assertFalse(sw.zichtbaar(next(b for b in st.brein if b["id"] == "bg"), ORG_ACTIEF.effectieve_toegang(ASS)))

        # huddle van Finance kreeg de opdracht uit het MT mee
        huddles = [f.read_text() for w in werken for f in (w / "gezien").glob("huddle-*.md")]
        self.assertTrue(any("Opdrachten uit het MT" in h and "Plan Finance-werk eerst in" in h for h in huddles))

        m = dr.meting(ORG_ACTIEF, st.grootboek, st.brein, list(st.taken.values()))
        self.assertEqual(m["assistent"], ASS)
        self.assertTrue(m["actief"])
        self.assertIsNotNone(m["besluit_tot_opdracht_uren"])
        self.assertGreater(m["beurten_assistent"], 0)


class KantineTest(unittest.TestCase):
    def test_assistent_aan_tafel_krijgt_geen_extra_inzage(self):
        index = {"tf": {"id": "tf", "labels": ["boekhouding"]}}
        beurten = [{"agent": "fin-1", "tekst": "Mijn marge-analyse loopt", "verwijst_naar": ["tf"]}]
        uit = sw.deelfilter(beurten, ["fin-1", ASS, "mkt-1"], ORG_ACTIEF, index)
        self.assertEqual(uit[0]["filter"], "geblokkeerd")
        self.assertIn("Assistent-Oppertet", uit[0]["reden"])
        alleen_ass = sw.deelfilter(beurten, ["fin-1", ASS], ORG_ACTIEF, index)
        self.assertEqual(alleen_ass[0]["filter"], "geblokkeerd")
        self.assertIn(ASS, sw.tafel(ORG_ACTIEF, [], sleutel="a", grootte=40))
        self.assertNotIn(ASS, sw.tafel(ORG, [], sleutel="a", grootte=40))


if __name__ == "__main__":
    unittest.main()
