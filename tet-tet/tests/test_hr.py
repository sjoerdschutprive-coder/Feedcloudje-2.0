"""Tests voor de HR-afdeling: prestatiemeting, dossiertoegang, evaluatiecyclus, agenda en governance (mockmodus, zonder API)."""
import datetime as dt
import json
import pathlib
import re
import shutil
import tempfile
import unittest
from unittest import mock

from tettet import hr, kalender as kal, prestatie, samenwerking as sw, stijl
from tettet.beleid import Geweigerd
from tettet.kaarten import Organisatie
from tettet.runtime import laad_instellingen
from tettet.werkdag import Werkdag
from tests.test_samenwerking import antwoord as antwoord_samen, pas_batches_toe, schrijf_dump

ORG = Organisatie()
INST = laad_instellingen()
GEHEIM_DOSSIER = "Ontwikkelplan: werkstijl bij bronnen aanscherpen"


def antwoord(stap: dict, prompt: str) -> str:
    """Speelt de agents, ook in de HR-beurten."""
    s = stap["soort"]
    if s == "checkin":
        ids = re.findall(r"^## ([a-z]+-[a-z0-9]+) \(", prompt, re.M)
        return json.dumps({"checkins": [{"agent": a, "werk": "taak afmaken", "nodig": "data", "twijfel": None, "mt_besluit": "Finance gaat voor",
                                         "afspraken": [{"wat": "Bronnen eerst", "eigenaar": a}]} for a in ids]})
    if s == "zelfreflectie":
        return json.dumps({"goed": ["Bronnen vermeld"], "niet_goed": ["Te laat gestart"], "schatting": {"eerste_keer_goed": 0.8, "juistheid": 0.9},
                           "voorgesteld_prestatiedoel": "Elke claim met bron", "voorgesteld_leerdoel": "Leren werken met de ijkset"})
    if s == "evaluatie":
        o = {"toekomstvragen": [{"nr": i, "score": 4, "toelichting": "Op basis van het werk."} for i in range(1, 5)],
             "feedback": ["Bij stap 2 (bronnen) eerst de bron noteren, dan de claim.", "Je bent te traag."],
             "prestatiedoel": {"doel": "Elke cijfermatige claim in het resultaat heeft een bron", "meetbaar": "traceerbaarheid", "datum": "2026-12-02"},
             "leerdoel": {"doel": "Leren hoe de ijkset van de eigen rol werkt en die twee keer draaien", "meetbaar": "twee runs", "datum": "2026-12-02"},
             "actieplan": [{"actie": "Ijkset draaien met de Experiment-Tet", "eigenaar": stap["agent"], "datum": "2026-11-20"}], "ontwikkelplan": None}
        if "Aandachtspunt:" in prompt:
            o["ontwikkelplan"] = {"onderdelen": ["Werkstijl bij bronnen aanscherpen", "Extra controle"], "toelichting": "Twee keer onder de mediaan."}
        return json.dumps(o)
    if s == "kalibratie":
        kand = re.findall(r"^### ([a-z]+-[a-z0-9]+) \(", prompt, re.M)
        return json.dumps({"strengheid": [{"hoofdtet": "fin-h", "bevinding": "Iets milder dan de rest."}],
                           "voorstellen": [{"agent": kand[0], "soort": "autonomie", "voorstel": "Autonomieniveau 3", "onderbouwing": "Profiel en gesprek"}] if kand else []})
    if s == "incident":
        return json.dumps({"wat_gebeurde": "Een beurt verwees naar werk buiten de toegang van de tafel.", "waarom_kon_het": "Het filter zag de verwijzing pas laat.",
                           "systeemmaatregel": None, "les": "Noem werk op bronnen buiten de toegang van de tafel alleen op hoofdlijnen."})
    if s == "patroon":
        return json.dumps({"patroon": "Schrijft eerst de acceptatiecriteria als checklist en toetst elk criterium vóór oplevering.", "voor_wie": ["fin", "mkt"],
                           "voorstel": {"titel": "Checklist vóór oplevering in de werkstijl", "toelichting": "Werkstijl aanvullen in alle Tet-kaarten."}})
    if s == "curatie":
        dub = re.findall(r"^- (b[\w-]+) ↔ (b[\w-]+)", prompt, re.M)
        return json.dumps({"samenvoegen": [{"houden": dub[0][0], "vervangen": dub[0][1]}] if dub else [], "verouderd": [], "strijdig": [],
                           "normvoorstellen": [{"onderdeel": "schrijfstijl", "titel": "Maximale zinslengte 20", "toelichting": "Korter leest beter."}]})
    if s == "cultuurbrief":
        return json.dumps({"wat_opviel": ["Veel contact tussen afdelingen"], "patroon": "nog geen", "principe_aandacht": {"principe": "Unieke informatie eerst", "waarom": "x"},
                           "tekst": "De kantine werkt: agents spreken vaker met andere afdelingen. Unieke informatie komt nog te weinig op tafel."})
    if s == "routine":
        return json.dumps({"bevindingen": ["ok"], "voorstel": None})
    return antwoord_samen(stap, prompt)


def draai(werk):
    batches = []
    for _ in range(400):
        uit = Werkdag(werk).volgende(6)
        batches += uit["batches"]
        if uit["klaar"]:
            break
        for stap in uit["stappen"]:
            for _ in range(6):
                p = Werkdag(werk).prompt(stap["id"])
                batches += p["batches"]
                prompt = pathlib.Path(p["prompt"]).read_text()
                s = json.loads((werk / "voortgang.json").read_text())["stappen"][stap["id"]]
                pathlib.Path(p["antwoord"]).write_text(antwoord(s, prompt))
                r = Werkdag(werk).verwerk(stap["id"])
                batches += r["batches"]
                if r.get("klaar"):
                    break
    batches += Werkdag(werk).einde()["batches"]
    return batches


def snel_inst() -> dict:
    """Sneller: kantine en huddles zijn elders getest."""
    inst = json.loads(json.dumps(INST))
    inst["kantine"]["aan"] = False
    inst["overleg"]["huddle"] = False
    return inst


def taak(i, agent="fin-1", dept="fin", **v):
    return {"id": f"t{i}", "agent": agent, "dept": dept, "title": f"Taak {i}", "status": "klaar", "criteria": ["a", "b"], "created": 1000 + i, **v}


class PrestatieTest(unittest.TestCase):
    def test_criteria_berekend(self):
        taken = [taak(i, score=8, eerste_oordeel="goedgekeurd", zekerheid_eerste=0.9, zelf_gemeld_eerste=False,
                      claims={"gecontroleerd": 2, "bevestigd": 2}, resultaat="## Resultaat\nDe marge is 12% (bron: boekhouding).\n## Les\nx") for i in range(18)]
        taken += [taak(i, score=4, afkeuringen=1, eerste_oordeel="afgekeurd", zekerheid_eerste=0.3, zelf_gemeld_eerste=True,
                       claims={"gecontroleerd": 2, "bevestigd": 1}, resultaat="## Resultaat\nOmzet 5 miljoen.") for i in range(18, 24)]
        gb = [{"type": "ijkset.run", "agent": "fin-1", "data": {"ijktaak": "tet-1", "geslaagd": True}} for _ in range(4)]
        gb += [{"type": "ijkset.run", "agent": "fin-1", "data": {"ijktaak": "tet-2", "geslaagd": g}} for g in (True, True, True, False)]
        p = prestatie.profiel("fin-1", ORG, taken, gb, [], INST)
        d = p["dimensies"]
        self.assertEqual(d["eerste_keer_goed"]["waarde"], 0.75)                 # 18 van 24
        self.assertLess(d["eerste_keer_goed"]["onder"], 0.75)                   # Wilson-interval
        self.assertEqual(d["juistheid"]["waarde"], round(42 / 48, 3))
        self.assertEqual(d["traceerbaarheid"]["waarde"], 0.75)
        self.assertEqual(d["pass_k"]["waarde"], 0.5)                           # tet-1 altijd goed, tet-2 niet 4x op rij
        self.assertEqual(d["meldcultuur"]["zelf"], 6)
        self.assertEqual(d["escalatie"]["terecht"], 6)
        self.assertAlmostEqual(d["kalibratie"]["brier"], round((18 * 0.01 + 6 * 0.09) / 24, 3))
        self.assertEqual(p["labels"], ["hr-dossier:fin-1"])

    def test_geen_conclusie_onder_minimale_steekproef(self):
        p = prestatie.profiel("fin-1", ORG, [taak(i) for i in range(5)], [], [], INST)
        self.assertEqual(p["dimensies"]["eerste_keer_goed"]["status"], "te_weinig_data")
        reeks = [p, p]
        self.assertIsNone(prestatie.classificeer(reeks, [{"eerste_keer_goed": 0.1}] * 2, INST)["status"])

    def test_geen_totaalscore(self):
        p = prestatie.profiel("fin-1", ORG, [taak(i) for i in range(25)], [], [], INST)
        tekst = json.dumps(p)
        for woord in ("totaal", "rang", "gemiddelde_score", "overall"):
            self.assertNotIn(woord, tekst)

    def test_grensovertreding_is_poort(self):
        gb = [{"type": "kantine.lek", "agent": "risk-2", "data": {"spreker": "fin-1"}}]
        p = prestatie.profiel("fin-1", ORG, [], gb, [], INST)
        self.assertEqual(p["poort"]["grensnaleving"]["overtredingen"], 1)
        self.assertEqual(prestatie.profiel("risk-2", ORG, [], gb, [], INST)["poort"]["grensnaleving"]["overtredingen"], 0)

    def test_gaming_signaal(self):
        vorig = {"dimensies": {"eerste_keer_goed": {"waarde": 0.6}}, "ruw": {"moeilijkheid": 4, "lengte": 2000, "geflagd": 0.3, "gemist": 0.1}}
        nu = {"dimensies": {"eerste_keer_goed": {"waarde": 0.8}}, "ruw": {"moeilijkheid": 2, "lengte": 2000, "geflagd": 0.1, "gemist": 0.2}}
        s = prestatie.gaming_signalen(nu, vorig)
        self.assertEqual(len(s), 2)
        self.assertIn("eenvoudiger", s[0])

    def test_uitblinker_en_aandachtspunt(self):
        def p(ekg_onder, ekg, juist_onder, juist, pk, overtr=0):
            return {"dimensies": {"eerste_keer_goed": {"status": "ok", "waarde": ekg, "onder": ekg_onder},
                                  "juistheid": {"status": "ok", "waarde": juist, "onder": juist_onder},
                                  "traceerbaarheid": {"status": "ok", "waarde": 0.9}, "kwaliteitsoordeel": {"status": "ok", "waarde": 0.8},
                                  "pass_k": {"status": "ok", "waarde": pk}}, "poort": {"grensnaleving": {"overtredingen": overtr}}}
        med = [{"eerste_keer_goed": 0.6, "juistheid": 0.7, "traceerbaarheid": 0.5, "kwaliteitsoordeel": 0.5}] * 2
        goed = p(0.7, 0.9, 0.8, 0.95, 0.8)
        self.assertEqual(prestatie.classificeer([goed, goed], med, INST)["status"], "uitblinker")
        self.assertIsNone(prestatie.classificeer([goed, p(0.7, 0.9, 0.8, 0.95, 0.8, overtr=1)], med, INST)["status"])
        zwak = p(0.3, 0.4, 0.5, 0.6, 0.5)
        self.assertEqual(prestatie.classificeer([zwak, zwak], med, INST)["status"], "aandachtspunt")
        self.assertEqual(prestatie.classificeer([p(0.7, 0.9, 0.8, 0.95, 0.9), p(0.7, 0.9, 0.8, 0.95, 0.6)], med, INST)["status"], "aandachtspunt")

    def test_pass_hat_k_en_paarsgewijs(self):
        self.assertEqual(prestatie.pass_hat_k({"a": [True] * 4}, 4), (1.0, 1))
        self.assertEqual(prestatie.pass_hat_k({"a": [True, True, False]}, 4), (None, 0))
        # positiebias: een beoordelaar die altijd de eerste kiest, levert geen consistent oordeel op
        self.assertIsNone(prestatie.paarsgewijs(lambda x, y: "eerste", "A", "B"))
        self.assertEqual(prestatie.paarsgewijs(lambda x, y: "eerste" if x == "A" else "tweede", "A", "B"), "a")

    def test_zekerheid_uit(self):
        self.assertEqual(prestatie.zekerheid_uit("## Zekerheid\n0,7\n- x: 0.9"), 0.7)
        self.assertEqual(prestatie.zekerheid_uit("## Zekerheid\nmiddel, want"), 0.6)
        self.assertEqual(prestatie.zekerheid_uit("## Zekerheid\n85%"), 0.85)

    def test_overeenstemming_raad(self):
        taken = [{"raad_steekproef": {"eens": i < 3}} for i in range(6)]
        o = prestatie.overeenstemming(taken, INST)
        self.assertEqual(o["waarde"], 0.5)
        self.assertTrue(o["onbetrouwbaar"])


class ToegangTest(unittest.TestCase):
    def test_dossier_zichtbaarheid(self):
        item = {"labels": [sw.dossier_label("fin-1")]}
        for a, mag in [("fin-1", True), ("fin-h", True), ("hr-h", True), ("hr-1", True), ("oppertet", True),
                       ("fin-2", False), ("mkt-h", False), ("risk-2", False), ("risk-h", False)]:
            self.assertEqual(sw.zichtbaar(item, ORG.effectieve_toegang(a)), mag, a)

    def test_dossier_nooit_in_de_kantine(self):
        index = {"e1": {"id": "e1", "labels": [sw.dossier_label("fin-1")]}}
        b = sw.deelfilter([{"agent": "fin-h", "tekst": "Over fin-1", "verwijst_naar": ["e1"]},
                           {"agent": "fin-h", "tekst": "Zijn ontwikkelplan loopt", "verwijst_naar": []}], ["fin-h", "fin-1", "hr-h"], ORG, index)
        self.assertEqual([x["filter"] for x in b], ["geblokkeerd", "twijfel"])   # ook als iedereen aan tafel het dossier mag zien
        tg = sw.toegangen(ORG, ["fin-h", "fin-1"])
        self.assertEqual(sw.deelbaar([index["e1"]], tg), [])


class HRWerkdagTest(unittest.TestCase):
    """De HR-cyclus in mockmodus: een volledige maand, plus gerichte scenario's."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.dump = self.tmp / "dump"
        schrijf_dump(self.dump, {"staat": {"doel": {"naam": "Test", "omschrijving": "o", "deadline": "2026-12-31"}, "instellingen": {"modus": "mock"}}})

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def dag(self, datum: dt.date, inst=None):
        werk = self.tmp / f"werk-{datum.isoformat()}"
        inst = inst or INST
        with mock.patch.object(Werkdag, "vandaag", lambda self: datum), mock.patch("tettet.werkdag.laad_instellingen", lambda: inst):
            _, start = Werkdag.start(self.dump, werk)
            batches = start["batches"] + draai(werk)
        pas_batches_toe(self.dump, batches)
        return werk, batches

    def staat(self, werk):
        with mock.patch("tettet.werkdag.laad_instellingen", lambda: self.inst):
            return Werkdag(werk).staat

    def test_maand(self):
        """November 2026, versneld (kalibratie elke maand): check-ins, snapshot, zelfreflecties, evaluaties, retro, kalibratie."""
        self.inst = snel_inst()
        self.inst["hr"]["ritme"]["kalibratie_elke_maanden"] = 1
        d, alle = dt.date(2026, 11, 2), []
        while d <= dt.date(2026, 11, 13):
            if d.isoweekday() <= 5:
                werk, b = self.dag(d, self.inst)
                alle.append(werk)
            d += dt.timedelta(days=1)
        st = self.staat(alle[-1])
        soorten = [e["soort"] for e in st.evaluaties]
        for s in ("register", "checkin", "snapshot", "zelfreflectie", "evaluatie", "kalibratie"):
            self.assertIn(s, soorten, s)
        self.assertTrue(any(o["soort"] == "retro" for o in st.overleggen))
        self.assertTrue(any(o["soort"] == "cultuurbrief" for o in st.overleggen))
        self.assertTrue(any(o["soort"] == "curatie" for o in st.overleggen))
        self.assertEqual(len({p["agent"] for p in st.prestaties}), len(kal.te_evalueren(ORG)))   # elke agent een profiel
        # check-ins nooit op een MT-dag
        mt_dag = self.inst["overleg"]["mt_dag"]
        for e in st.evaluaties:
            if e["soort"] == "checkin":
                self.assertNotEqual(dt.date.fromisoformat(e["datum"]).isoweekday(), mt_dag)
        # doelen specifiek, met datum en eigenaar; feedback over de agent is weggelaten
        evs = [e for e in st.evaluaties if e["soort"] == "evaluatie"]
        self.assertTrue(evs)
        for e in evs:
            for doel in ("prestatiedoel", "leerdoel"):
                self.assertTrue(e[doel]["specifiek"] and re.match(r"\d{4}-\d{2}-\d{2}", e[doel]["datum"]) and e[doel]["eigenaar"] == e["agent"])
            self.assertTrue(all(a["eigenaar"] and a["datum"] for a in e["actieplan"]))
            self.assertEqual(e["feedback_over_agent_weggelaten"], 1)
            self.assertEqual(e["labels"], [sw.dossier_label(e["agent"])])
        # de zelfreflectie kwam vóór het gesprek, zonder snapshot
        for e in evs:
            z = next(x for x in st.evaluaties if x["soort"] == "zelfreflectie" and x["agent"] == e["agent"])
            self.assertLess(z["ts"], e["ts"])
            self.assertFalse(z["snapshot_gezien"])
        # verwijzingen in overleggen en agenda zonder dossierinhoud
        openbaar = json.dumps([st.overleggen, st.kalender], ensure_ascii=False)
        self.assertNotIn("Elke cijfermatige claim", openbaar)
        self.assertTrue(any(o["soort"] == "evaluatie" and o.get("verwijzing") for o in st.overleggen))

    def test_zelfreflectie_ziet_geen_snapshot(self):
        self.inst = INST
        werk = self.tmp / "werk"
        with mock.patch.object(Werkdag, "vandaag", lambda self: dt.date(2026, 11, 3)):
            Werkdag.start(self.dump, werk)
            wd = Werkdag(werk)
            stap = wd._nieuwe_stap("zelfreflectie", "fin-1", uid="x", onderwerp="fin-1", variant="zelfreflectie", datum="2026-11-03")
            wd.staat.prestaties.append({"agent": "fin-1", "id": "p", "dimensies": {}, "classificatie": {"status": "aandachtspunt", "reden": "GEHEIM-PROFIEL"}})
            wd.klaar_met({})
            prompt = pathlib.Path(Werkdag(werk).prompt(stap["id"])["prompt"]).read_text()
        opdracht = prompt.split("======== OPDRACHT ========")[1]
        self.assertNotIn("GEHEIM-PROFIEL", opdracht)
        self.assertNotIn("Eerste keer goed", opdracht)

    def _scenario(self, status: str):
        """Twee snapshots met een uitblinker of aandachtspunt voor fin-1, en een evaluatiegesprek."""
        self.inst = snel_inst()
        prest = {f"p{i}": {"id": f"p{i}", "agent": "fin-1", "afdeling": "fin", "ts": i, "dimensies": {}, "poort": {"grensnaleving": {"overtredingen": 0, "bijna": 0}},
                           "beoordelaar": {}, "classificatie": {"status": status, "reden": "geïnjecteerd"}} for i in (1, 2)}
        schrijf_dump(self.dump, {"prestaties": prest})
        werk = self.tmp / "werk"
        with mock.patch.object(Werkdag, "vandaag", lambda self: dt.date(2026, 11, 4)), mock.patch("tettet.werkdag.laad_instellingen", lambda: self.inst):
            Werkdag.start(self.dump, werk)
            wd = Werkdag(werk)
            ev = kal.maak_event("evaluatie", "fin-1", dt.date(2026, 11, 4), kal.evaluatie_deelnemers(ORG, "fin-1"), wd.kal, extra={"retro": "2026-11-06"})
            wd._kalender_nieuw(ev)
            wd._evaluatie("snapshot", "hr", uid=kal.uid("snapshot", "hr", "2026-11-03"), retro="2026-11-06")
            wd.klaar_met({})
            draai(werk)
            return Werkdag(werk).staat

    def test_uitblinker_levert_patroon_oogst(self):
        st = self._scenario("uitblinker")
        patroon = [b for b in st.brein if b["soort"] == "patroon"]
        self.assertEqual(len(patroon), 1)
        self.assertEqual(patroon[0]["over"], "fin-1")
        self.assertFalse(sw.is_dossier(patroon[0]))                     # de werkwijze wordt gedeeld, niet het dossier
        self.assertTrue(any(v["soort"] == "kaart" for v in st.voorstellen.values()))

    def test_aandachtspunt_levert_ontwikkelplan(self):
        st = self._scenario("aandachtspunt")
        e = next(x for x in st.evaluaties if x["soort"] == "evaluatie" and x["agent"] == "fin-1")
        self.assertTrue(e["ontwikkelplan"]["onderdelen"])
        self.assertTrue(e["prestatiedoel"]["doel"] and e["leerdoel"]["doel"] and e["actieplan"])
        self.assertEqual(e["classificatie"], "aandachtspunt")

    def test_dossier_niet_in_prompt_van_collega(self):
        self.inst = INST
        schrijf_dump(self.dump, {"brein": {"bd": {"id": "bd", "soort": "les", "dept": "fin", "agent": "hr-h", "tekst": GEHEIM_DOSSIER,
                                                  "labels": [sw.dossier_label("fin-1")], "ts": 1}},
                                 "taken": {"t2": {"id": "t2", "dept": "fin", "agent": "fin-2", "title": "Werkstijl en bronnen", "status": "volgende", "created": 1,
                                                  "criteria": ["c"], "control": "risk-c2", "afkeuringen": 0},
                                           "t1": {"id": "t1", "dept": "fin", "agent": "fin-1", "title": "Werkstijl en bronnen", "status": "volgende", "created": 2,
                                                  "criteria": ["c"], "control": "risk-c2", "afkeuringen": 0}}})
        werk = self.tmp / "werk"
        Werkdag.start(self.dump, werk)
        wd = Werkdag(werk)
        s2 = wd._nieuwe_stap("uitvoeren", "fin-2", taak="t2", fase="tet", poging=1)
        s1 = wd._nieuwe_stap("uitvoeren", "fin-1", taak="t1", fase="tet", poging=1)
        k = wd._nieuwe_stap("kantine", "fin-1", deelnemers=["fin-1", "fin-2", "mkt-1", "hr-1"], fase="gesprek")
        wd.klaar_met({})
        p2 = pathlib.Path(Werkdag(werk).prompt(s2["id"])["prompt"]).read_text()
        p1 = pathlib.Path(Werkdag(werk).prompt(s1["id"])["prompt"]).read_text()
        pk = pathlib.Path(Werkdag(werk).prompt(k["id"])["prompt"]).read_text()
        self.assertNotIn(GEHEIM_DOSSIER, p2)
        self.assertIn(GEHEIM_DOSSIER, p1)                # de agent ziet zijn eigen dossier wel
        self.assertNotIn(GEHEIM_DOSSIER, pk)             # en de kantine nooit

    def test_control_tet_beoordeelt_blind(self):
        self.inst = INST
        schrijf_dump(self.dump, {"taken": {"t1": {"id": "t1", "dept": "fin", "agent": "fin-1", "title": "Prijsanalyse", "status": "bezig", "created": 1,
                                                  "criteria": ["c"], "control": "risk-c2", "afkeuringen": 0, "bijgewerkt": 10 ** 13,
                                                  "resultaat": "## Resultaat\nPrijs-Tet (fin-1, Finance) adviseert 5% omhoog."}}})
        werk = self.tmp / "werk"
        Werkdag.start(self.dump, werk)
        wd = Werkdag(werk)
        s = wd._nieuwe_stap("uitvoeren", "fin-1", taak="t1", fase="control", poging=1)
        wd.klaar_met({})
        opdracht = pathlib.Path(Werkdag(werk).prompt(s["id"])["prompt"]).read_text().split("======== OPDRACHT ========")[1]
        for verboden in ("Prijs-Tet", "fin-1", "Finance", "Afdelingsdoel"):
            self.assertNotIn(verboden, opdracht)
        self.assertIn("Lengte telt niet mee", opdracht)

    def test_grensovertreding_leidt_tot_incidentevaluatie(self):
        self.inst = INST
        schrijf_dump(self.dump, {"grootboek": {"g1": {"bron": "test", "events": [{"bron": "test", "n": 1, "ts": 10 ** 13, "type": "kantine.lek", "agent": "risk-2",
                                                                                 "data": {"spreker": "fin-1"}}]}}})
        werk = self.tmp / "werk"
        with mock.patch.object(Werkdag, "vandaag", lambda self: dt.date(2026, 11, 2)):
            with mock.patch("tettet.werkdag_hr.nu_ms", lambda: 10 ** 13 + 1000):
                Werkdag.start(self.dump, werk)
                draai(werk)
            st = Werkdag(werk).staat
        inc = [e for e in st.evaluaties if e["soort"] == "incident"]
        self.assertEqual(len(inc), 1)
        self.assertEqual(inc[0]["agent"], "fin-1")
        self.assertTrue(inc[0]["binnen"])
        self.assertTrue(any(b["soort"] == "incident" and b.get("bron") == "incidentevaluatie" for b in st.brein))


class KalenderTest(unittest.TestCase):
    def setUp(self):
        self.k = kal.instellingen(INST)
        self.ev = kal.rooster(ORG, INST, dt.date(2026, 10, 26), dt.date(2026, 11, 30))

    def test_checkins_nooit_op_mt_of_voorbereiding(self):
        mt = INST["overleg"]["mt_dag"]
        jaar = kal.rooster(ORG, INST, dt.date(2026, 1, 1), dt.date(2026, 12, 31))
        for e in jaar:
            if e["soort"] == "checkin":
                d = dt.date.fromisoformat(e["datum"])
                self.assertNotEqual(d.isoweekday(), mt)
                self.assertNotEqual((d + dt.timedelta(days=2)).isoweekday(), mt)

    def test_geldige_ics(self):
        tekst = kal.ics(self.ev, self.k)
        self.assertTrue(tekst.startswith("BEGIN:VCALENDAR\r\n") and tekst.endswith("END:VCALENDAR\r\n"))
        regels = tekst.split("\r\n")[:-1]
        self.assertTrue(all(len(r.encode()) <= 75 for r in regels))
        self.assertEqual(sum(r == "BEGIN:VEVENT" for r in regels), sum(r == "END:VEVENT" for r in regels))
        events = tekst.split("BEGIN:VEVENT")[1:]
        self.assertTrue(events)
        for e in events:
            for veld in ("UID:", "DTSTAMP:", "DTSTART", "SUMMARY:"):
                self.assertIn("\r\n" + veld, "\r\n" + e)
        # alleen soorten die in de agenda horen; geen dagelijkse huddles, geen zelfreflecties
        self.assertNotIn("Zelfreflectie", tekst)
        uids = re.findall(r"^UID:(.+)$", tekst.replace("\r\n ", ""), re.M)
        self.assertEqual(len(uids), len(set(uids)))

    def test_idempotente_uids(self):
        twee = kal.rooster(ORG, INST, dt.date(2026, 10, 26), dt.date(2026, 11, 30))
        self.assertEqual([e["uid"] for e in self.ev], [e["uid"] for e in twee])
        k = kal.MockKalender(INST)
        self.assertEqual(k.synchroniseer(self.ev, "hr-h"), len(self.ev))
        self.assertEqual(k.synchroniseer(twee, "hr-h"), 0)
        self.assertEqual(kal.ics(k.lees(dt.date(2026, 10, 26), dt.date(2026, 11, 30)), self.k), kal.ics(self.ev, self.k))

    def test_verplaatst_en_geannuleerd(self):
        k = kal.MockKalender(INST, events=self.ev)
        e = next(x for x in self.ev if x["soort"] == "evaluatie")
        k.verplaats(e["uid"], "2026-11-10", "raad")
        k.zet({**e}, "hr-h")                                        # het rooster zet hem opnieuw: de agenda blijft leidend
        self.assertEqual(k._haal(e["uid"])["datum"], "2026-11-10")
        k.annuleer(e["uid"], "raad")
        self.assertEqual(k.synchroniseer(kal.rooster(ORG, INST, dt.date(2026, 10, 26), dt.date(2026, 11, 30)), "hr-h"), 0)
        self.assertEqual(k._haal(e["uid"])["status"], "geannuleerd")
        self.assertIn("STATUS:CANCELLED", kal.ics([k._haal(e["uid"])], self.k))
        with self.assertRaises(kal.KalenderFout):
            k.annuleer(e["uid"], "hr-h")                            # alleen de Raad annuleert
        with self.assertRaises(kal.KalenderFout):
            k.zet({**e, "uid": "ander-1", "titel": "Privé"}, "hr-h")   # agents alleen met de eigen prefix

    def test_werkdag_volgt_verplaatst_event_en_plant_geannuleerd_niet_opnieuw(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            dump = tmp / "dump"
            ev = [e for e in self.ev if e["soort"] == "checkin" and e["onderwerp"] == "fin"][:2]
            verplaatst = {**ev[0], "id": ev[0]["uid"].replace("@tettet", ""), "datum": "2026-11-03"}
            geannuleerd = {**ev[1], "id": ev[1]["uid"].replace("@tettet", ""), "status": "geannuleerd"}
            schrijf_dump(dump, {"staat": {"doel": {"naam": "T"}}, "kalender": {verplaatst["id"]: verplaatst, geannuleerd["id"]: geannuleerd}})
            for datum, verwacht in ((dt.date(2026, 11, 2), False), (dt.date(2026, 11, 3), True)):
                werk = tmp / f"w{datum.day}"
                with mock.patch.object(Werkdag, "vandaag", lambda self, d=datum: d):
                    Werkdag.start(dump, werk)
                    wd = Werkdag(werk)
                    wd._agenda_bijwerken()
                    uids = {e["uid"] for e in wd._te_doen()}
                self.assertEqual(verplaatst["uid"] in uids, verwacht)
                self.assertNotIn(geannuleerd["uid"], uids)
                self.assertEqual(sum(1 for e in wd.staat.kalender if e["uid"] == geannuleerd["uid"]), 1)
            self.assertTrue(any(e["type"] == "kalender.geannuleerd" for e in wd.staat.grootboek))
        finally:
            shutil.rmtree(tmp)

    def test_geen_dossierinhoud_in_agenda(self):
        for e in self.ev:
            blok = kal.lees_blok(e["beschrijving"])
            self.assertEqual(set(blok), {"soort", "deelnemers", "voorbereiding", "verslag"})
            self.assertNotRegex(e["beschrijving"], r"ontwikkelplan:|prestatiedoel:|snapshot-waarde|\d\.\d{2}")

    def test_google_adapter_heeft_dezelfde_vorm(self):
        g = kal.maak_kalender({**INST, "hr": {**INST["hr"], "kalender": {**INST["hr"]["kalender"], "bron": "google"}}})
        self.assertIsInstance(g, kal.Kalender)
        with self.assertRaises(NotImplementedError):
            g.lees(dt.date(2026, 11, 1), dt.date(2026, 11, 2))


class GovernanceTest(unittest.TestCase):
    def test_curatie_wijzigt_geen_labels_en_verwijdert_niets(self):
        with self.assertRaises(Geweigerd):
            hr.curatie_velden({"labels": []})
        with self.assertRaises(Geweigerd):
            hr.curatie_velden({"tekst": "nieuw"})
        self.assertEqual(hr.curatie_velden({"vervangen_door": "b1", "herzien_op": "2026-11-02"})["vervangen_door"], "b1")

    def test_curatie_binnen_eigen_toegang(self):
        brein = [{"id": "b1", "soort": "les", "dept": "fin", "tekst": "Altijd de bron van elk getal noemen bij prijzen", "labels": ["boekhouding"]},
                 {"id": "b2", "soort": "les", "dept": "fin", "tekst": "Altijd de bron van elk getal noemen bij prijzen!", "labels": ["boekhouding"]},
                 {"id": "b3", "soort": "les", "dept": "mkt", "tekst": "Doelgroep eerst afbakenen voor elke campagne", "labels": []},
                 {"id": "b4", "soort": "les", "dept": "mkt", "tekst": "Doelgroep eerst afbakenen voor elke campagne.", "labels": []}]
        k = hr.curatie_kandidaten(brein, ORG.effectieve_toegang("hr-h"))
        ids = {i for d in k["dubbel"] for i in d["ids"]}
        self.assertEqual(ids, {"b3", "b4"})
        self.assertEqual(k["verborgen_per_afdeling"], {"fin": 2})

    def test_stijlcontrole(self):
        u = stijl.toets("## Resultaat\nIn dit document wordt de omzet eigenlijk geanalyseerd. De omzet stijgt 12%. Het issue is de marge.")
        soorten = {s["soort"] for s in u["suggesties"]}
        self.assertEqual(soorten, {"lijdend", "opvulling", "geen_bron", "engels", "geen_conclusie_eerst"})
        self.assertEqual(stijl.toets("## Resultaat\nDe marge daalt met 3% (bron: boekhouding). Finance past de prijs aan.")["score"], 100)

    def test_cultuurkloof(self):
        class St:
            taken = {"t1": {"id": "t1", "criteria": ["c"]}, "t2": {"id": "t2"}}
            brein, overleggen, kantine, grootboek, evaluaties, kalender = [], [], [], [], [], []
        k = {x["indicator"]: x for x in hr.cultuurkloof(ORG, St)}
        self.assertEqual(k["taken_met_criteria"]["gedrag"], 0.5)
        self.assertEqual(k["taken_met_criteria"]["kloof"], 0.45)

    def test_mappenstructuur_en_huisstijl(self):
        from tettet.validatie import controleer_mappen
        self.assertEqual(controleer_mappen(), [])
        from tettet import BASIS
        import yaml
        html = (BASIS / "kantoor" / "index.html").read_text(encoding="utf-8")
        hs = yaml.safe_load((BASIS / "kaarten" / "handboek" / "huisstijl.yaml").read_text(encoding="utf-8"))
        for naam, kleur in hs["kleuren"].items():
            self.assertIn(f"--{naam}: {kleur};", html)


if __name__ == "__main__":
    unittest.main()


class KantoorPariteitTest(unittest.TestCase):
    """De pagina maakt dezelfde .ics en kiest dezelfde steekproef als het platform."""

    def js(self, code: str) -> str:
        import shutil as sh
        import subprocess
        node = sh.which("node")
        if not node:
            self.skipTest("node niet beschikbaar")
        from tettet import BASIS
        html = (BASIS / "kantoor" / "index.html").read_text(encoding="utf-8")
        regels = html.splitlines()
        hr_const = next(r for r in regels if r.startswith("const HR = "))
        fn = lambda naam: re.search(rf"^function {naam}\(.*?^}}", html, re.S | re.M).group(0)
        bron = "\n".join([hr_const, next(r for r in regels if r.startswith("function controlegetal(s)")),
                          fn("icsEsc"), fn("icsVouw"), fn("maakIcs"), fn("inSteekproef"), code])
        r = subprocess.run([node, "-e", bron], capture_output=True)   # bytes: \r\n moet blijven staan
        self.assertEqual(r.returncode, 0, r.stderr.decode())
        return r.stdout.decode("utf-8")

    def test_ics_gelijk(self):
        ev = kal.rooster(ORG, INST, dt.date(2026, 11, 1), dt.date(2026, 11, 14))
        ev[0] = {**ev[0], "datum": "2026-11-05"}                 # verplaatst
        ev[1] = {**ev[1], "status": "geannuleerd"}
        uit = self.js(f"process.stdout.write(maakIcs({json.dumps(ev, ensure_ascii=False)}))")
        self.assertEqual(uit, kal.ics(ev, kal.instellingen(INST)))

    def test_steekproef_gelijk(self):
        ids = [f"t{i}" for i in range(400)]
        uit = json.loads(self.js(f"console.log(JSON.stringify({json.dumps(ids)}.filter(inSteekproef)))"))
        self.assertEqual(uit, [i for i in ids if prestatie.in_steekproef(i, INST["hr"]["meting"]["steekproef_raad"])])
        self.assertTrue(uit)
