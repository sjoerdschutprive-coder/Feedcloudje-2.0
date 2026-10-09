"""Tests voor Tet Tet. Draaien zonder API-sleutel (mockmodus).

  cd tet-tet && python -m unittest -v      (of: python -m pytest)
"""
import json
import pathlib
import shutil
import tempfile
import unittest

from tettet import BASIS
from tettet.beleid import Beleidsmotor, Geweigerd
from tettet.grootboek import Grootboek
from tettet.kaarten import KaartFout, Organisatie
from tettet.keten import Doelstelling, Kantoor
from tettet.runtime import MockClient, lees_json
from tettet.taken import OngeldigeOvergang, Taak, Takenmarkt

ORG = Organisatie()


class KaartenTest(unittest.TestCase):
    def test_alle_agents_geladen(self):
        self.assertEqual(len(ORG.agents), 31)   # 30 + de Assistent-Oppertet (gepland)
        self.assertEqual(len(ORG.actieve_agents()), 31)   # alle agents ingezet door de Raad (9 oktober 2026)
        self.assertEqual(len(ORG.afdelingen), 7)

    def test_afdelingsomvang(self):
        """Norm: 1 Hoofdtet + 3 Tets per afdeling (Risk & Safety heeft daarnaast twee Control Tets)."""
        for d in ORG.afdelingen:
            tets = [a for a in ORG.team(d, ook_gepland=True) if a["rol"] == "tet"]
            self.assertEqual(len(tets), 2 if d == "risk" else 3, d)
            self.assertEqual(sum(1 for a in ORG.team(d, ook_gepland=True) if a["rol"] == "hoofdtet"), 1, d)
        self.assertIn("ops-3", [a["id"] for a in ORG.tets("ops")])   # ingezet: hoort nu bij het team
        self.assertIn("risk-2", [a["id"] for a in ORG.tets("risk")])

    def test_instructies_in_vaste_volgorde(self):
        p = ORG.systeemprompt("fin-1")
        koppen = ["## 1. Harde grenzen", "## 2. Cultuur van Tet Tet", "## 3. Cultuur van Finance", "## 4. Jouw profiel", "## 5. Wat je mag"]
        posities = [p.index(k) for k in koppen]
        self.assertEqual(posities, sorted(posities))

    def test_werkstijl_letterlijk_in_prompt(self):
        a = ORG.agent("risk-c1")
        p = ORG.systeemprompt("risk-c1")
        for tekst in a["werkstijl"].values():
            self.assertIn(tekst, p)

    def test_oppertet_heeft_geen_afdelingslaag(self):
        self.assertNotIn("## 3. Cultuur van", ORG.systeemprompt("oppertet"))

    def test_kaartversies_voor_grootboek(self):
        v = ORG.kaartversies("fin-1")
        for k in ("cultuur-tet-tet", "cultuur-fin", "fin-1", "rol-tet", "toegang-fin", "beleid-tet-tet"):
            self.assertIn(k, v)

    def test_ongeldige_kaart_weigert_start(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            shutil.copytree(BASIS / "kaarten", tmp / "kaarten")
            pad = tmp / "kaarten/afdelingen/ops.yaml"
            pad.write_text(pad.read_text().replace("accent_op: [waarde-creeren", "accent_op: [snelheid"))
            with self.assertRaises(KaartFout):
                Organisatie(tmp / "kaarten")
        finally:
            shutil.rmtree(tmp)

    def test_nieuwe_kaart_zonder_codewijziging(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            shutil.copytree(BASIS / "kaarten", tmp / "kaarten")
            bron = (tmp / "kaarten/agents/fin-2.yaml").read_text()
            nieuw = bron.replace("id: fin-2", "id: fin-3").replace("naam: Kosten-Tet", "naam: Subsidie-Tet")
            nieuw = nieuw.replace("kenmerken: {}", "kenmerken:\n  favoriete_bron: rijksoverheid")
            (tmp / "kaarten/agents/fin-3.yaml").write_text(nieuw)
            org = Organisatie(tmp / "kaarten")
            self.assertIn("fin-3", org.agents)
            self.assertEqual(org.agent("fin-3")["kenmerken"]["favoriete_bron"], "rijksoverheid")
        finally:
            shutil.rmtree(tmp)


class ToegangTest(unittest.TestCase):
    def test_profiel_perkt_in(self):
        self.assertEqual(ORG.effectieve_toegang("hr-h").bronnen["gmail"], "r")
        self.assertNotIn("gmail", ORG.effectieve_toegang("hr-1").bronnen)    # profielkaart perkt in
        self.assertEqual(ORG.effectieve_toegang("ops-2").bronnen["orderbeheer"], "r")

    def test_control_tet_alleen_lezen(self):
        self.assertTrue(all(v == "r" for v in ORG.effectieve_toegang("risk-c1").bronnen.values()))

    def test_geen_tools_van_andere_afdeling(self):
        gb = Grootboek()
        motor = Beleidsmotor(ORG, gb)
        with self.assertRaises(Geweigerd):
            motor.gebruik_bron("mkt-1", "rekenmodellen", "r")  # rekenmodel is van Finance
        motor.gebruik_bron("fin-1", "rekenmodellen", "rw")
        self.assertEqual(len(gb.zoek(type="beleid.overtreding")), 1)

    def test_rolkaart_en_harde_grenzen(self):
        motor = Beleidsmotor(ORG, Grootboek())
        self.assertTrue(motor.toets_handeling("fin-1", "taak.uitvoeren").toegestaan)
        self.assertEqual(motor.toets_handeling("fin-1", "taken.toewijzen").uitkomst, "geweigerd")
        self.assertEqual(motor.toets_handeling("oppertet", "extern.communiceren").uitkomst, "goedkeuring_nodig")
        self.assertEqual(motor.toets_handeling("oppertet", "betaling.uitvoeren").uitkomst, "geweigerd")
        self.assertEqual(len(motor.inbox), 1)


class GrootboekTest(unittest.TestCase):
    def test_hashketen_detecteert_wijziging(self):
        gb = Grootboek()
        for i in range(3):
            gb.schrijf("test", "fin-1", {"i": i}, kosten_eur=0.1)
        self.assertEqual(gb.controleer(), [])
        self.assertAlmostEqual(gb.kosten(), 0.3)
        gb.events[1]["data"]["i"] = 99
        self.assertTrue(gb.controleer())

    def test_opslag_op_schijf(self):
        tmp = pathlib.Path(tempfile.mkdtemp()) / "gb.jsonl"
        try:
            Grootboek(tmp).schrijf("test", "raad", {"a": 1})
            gb = Grootboek(tmp)
            gb.schrijf("test", "raad", {"a": 2})
            self.assertEqual(len(gb.events), 2)
            self.assertEqual(gb.controleer(), [])
        finally:
            shutil.rmtree(tmp.parent)


class TakenTest(unittest.TestCase):
    def taak(self):
        return Taak(id="T1", doel_id="D1", opdracht="x", acceptatiecriteria=["y"], eigenaar="fin", budget_eur=1)

    def test_levenscyclus_en_escalatie(self):
        markt = Takenmarkt(Grootboek(), max_afkeuringen=2)
        t = markt.publiceer(self.taak(), "fin-h")
        markt.claim(t, "fin-1"); markt.start(t, "fin-1"); markt.lever_op(t, "fin-1", "r1")
        self.assertEqual(markt.beoordeel(t, "risk-c1", False, ["b"]), "in_uitvoering")
        markt.lever_op(t, "fin-1", "r2")
        self.assertEqual(markt.beoordeel(t, "risk-c1", False, ["b"]), "geëscaleerd")

    def test_ongeldige_overgang(self):
        markt = Takenmarkt(Grootboek())
        t = markt.publiceer(self.taak(), "fin-h")
        with self.assertRaises(OngeldigeOvergang):
            markt.lever_op(t, "fin-1", "te vroeg")


class KetenTest(unittest.TestCase):
    def test_volledige_keten(self):
        k = Kantoor(mock=True)
        verslag = k.draai(Doelstelling("Testdoel", "omschrijving", "2026-12-31"), ["fin"])
        taken = list(k.markt.taken.values())
        self.assertTrue(taken)
        self.assertTrue(all(t.status == "afgerond" for t in taken))
        self.assertTrue(all(t.control_tet in {"risk-c1", "risk-c2"} for t in taken))
        self.assertEqual(k.gb.controleer(), [])
        self.assertEqual(len(k.gb.zoek(type="beleid.overtreding")), 0)
        # Elke taak leverde een les; lessen die op elkaar lijken zijn samengevoegd (teller 'bevestigd').
        self.assertEqual(sum(i.get("bevestigd", 1) for i in k.brein.items if i["soort"] == "les"), len(taken))
        self.assertIn("Grootboek intact: ja", verslag)
        aanroep = k.gb.zoek(type="model.aanroep", agent="fin-1")[0]
        self.assertIn("cultuur-fin", aanroep["kaartversies"])

    def test_afkeuring_bevindingen_en_escalatie(self):
        client = MockClient(afkeuren={"*": 99})
        k = Kantoor(client=client)
        k.draai(Doelstelling("Streng"), ["mkt"])
        taken = list(k.markt.taken.values())
        self.assertTrue(all(t.status == "geëscaleerd" for t in taken))
        self.assertTrue(k.gb.zoek(type="escalatie"))
        # De tweede poging van de Tet kreeg de bevindingen van de Control Tet mee.
        tet_berichten = [b for rol, b in client.aanroepen if rol == "tet"]
        self.assertIn("Bevindingen van de vorige beoordeling", tet_berichten[1])

    def test_een_keer_afgekeurd_dan_goed(self):
        k = Kantoor(client=MockClient(afkeuren={"*": 1}))
        k.draai(Doelstelling("Eén ronde"), ["fin"])
        statussen = [t.status for t in k.markt.taken.values()]
        self.assertEqual(statussen[0], "afgerond")
        self.assertEqual(list(k.markt.taken.values())[0].afkeuringen, 1)

    def test_risk_niet_door_eigen_control_tet(self):
        k = Kantoor(mock=True)
        k.draai(Doelstelling("Risico's"), ["risk"])
        self.assertTrue(all(t.control_tet == "raad" for t in k.markt.taken.values()))
        self.assertTrue(k.beleid.inbox)

    def test_lessen_gaan_naar_volgende_taak(self):
        client = MockClient()
        k = Kantoor(client=client)
        k.draai(Doelstelling("Leren"), ["fin"])
        tweede_taak = [b for rol, b in client.aanroepen if rol == "tet"][1]
        self.assertIn("Lessen uit het Brein", tweede_taak)

    def test_afkeuring_wordt_les_en_escalatie_incident(self):
        k = Kantoor(client=MockClient(afkeuren={"*": 99}))
        k.draai(Doelstelling("Streng"), ["mkt"])
        afkeur = [i for i in k.brein.items if i.get("bron") == "afkeuring"]
        self.assertTrue(any(i["soort"] == "les" for i in afkeur))
        self.assertTrue(any(i["soort"] == "incident" for i in afkeur))
        self.assertTrue(all(i["zekerheid"] == "laag" and i["afdeling"] == "mkt" for i in afkeur))
        self.assertIn("Onderbouwing ontbreekt", afkeur[0]["tekst"])
        # en komt in de lessen-selectie van de eigen afdeling
        self.assertTrue(any(i.get("bron") == "afkeuring" for i in k.brein.lessen_voor("mkt")))

    def test_niet_meetbare_doelstelling_geeft_een_vraag(self):
        class Vaag(MockClient):
            def _oppertet(self, b):
                return json.dumps({"meetbaar": False, "ontbreekt": ["klant", "kpi", "onzin"], "vraag_aan_raad": "Voor welke klant, en welke KPI?",
                                   "afdelingsdoelen": [{"afdeling": "fin", "doel": "Kosten per taak meten", "hoofdlijnen": ["Kostenmeting"]}]})
        k = Kantoor(client=Vaag())
        k.stel_doelstelling_in(Doelstelling("The beginning"))
        doelen = k.plan_oppertet(["fin", "mkt"])
        self.assertEqual([d.afdeling for d in doelen], ["fin"])
        self.assertEqual(k.verduidelijking["ontbreekt"], ["klant", "kpi"])
        self.assertTrue(k.gb.zoek(type="doelstelling.verduidelijking_gevraagd"))

    def test_meetbare_doelstelling_geen_vraag(self):
        k = Kantoor(mock=True)
        k.stel_doelstelling_in(Doelstelling("Doel"))
        k.plan_oppertet(["fin"])
        self.assertIsNone(k.verduidelijking)

    def test_geen_doelstelling_geen_plan(self):
        with self.assertRaises(RuntimeError):
            Kantoor(mock=True).plan_oppertet()


class BreinTest(unittest.TestCase):
    def test_dubbele_les_wordt_bevestigd_met_variant(self):
        from tettet.brein import Brein
        b = Brein()
        b.schrijf("les", "fin-1", "fin", "De doelstelling is niet meetbaar, eerst terugleggen bij de opdrachtgever.")
        b.schrijf("les", "mkt-1", "mkt", "De doelstelling is niet meetbaar: eerst terugleggen bij de opdrachtgever!")
        b.schrijf("les", "fin-2", "fin", "Bronnen per kernclaim noteren voordat je rekent.")
        self.assertEqual(len(b.items), 2)
        eerste = b.items[0]
        self.assertEqual(eerste["bevestigd"], 2)
        self.assertEqual(eerste["ook"], ["mkt"])
        self.assertIn("opdrachtgever!", eerste["varianten"][0])   # origineel bewaard, terug te draaien
        # mkt ziet de samengevoegde les ook; vaker bevestigd gaat voor recenter
        self.assertEqual(b.lessen_voor("mkt")[0]["id"], eerste["id"])
        self.assertEqual(b.lessen_voor("fin")[0]["id"], eerste["id"])

    def test_verschillende_lessen_blijven_apart(self):
        from tettet.brein import overlap
        self.assertLess(overlap("Klein beginnen met één afdeling.", "Bronnen per kernclaim noteren."), 0.6)
        self.assertEqual(overlap("a b", ""), 0.0)


class AnthropicClientTest(unittest.TestCase):
    """Controleert de vorm van de API-aanroep met een nep-SDK (geen netwerk, geen sleutel nodig)."""

    def test_aanroep_vorm(self):
        import os
        import sys
        import types
        gezien = {}

        class Berichten:
            def create(self, **kw):
                gezien.update(kw)
                blok = types.SimpleNamespace(type="text", text='{"oordeel": "goedgekeurd", "score": 9, "bevindingen": []}')
                return types.SimpleNamespace(content=[blok], usage=types.SimpleNamespace(input_tokens=100, output_tokens=20))

        nep = types.ModuleType("anthropic")
        nep.Anthropic = lambda: types.SimpleNamespace(messages=Berichten())
        oud_mod, oud_key = sys.modules.get("anthropic"), os.environ.get("ANTHROPIC_API_KEY")
        sys.modules["anthropic"], os.environ["ANTHROPIC_API_KEY"] = nep, "test"
        try:
            from tettet.runtime import AnthropicClient
            a = AnthropicClient("claude-sonnet-5-5", 1000).genereer("controltet", "systeem", "bericht")
            self.assertEqual(a.tokens_in, 100)
            self.assertEqual(gezien["model"], "claude-sonnet-5-5")
            self.assertEqual(gezien["system"][0]["cache_control"], {"type": "ephemeral"})
            self.assertEqual(gezien["messages"], [{"role": "user", "content": "bericht"}])
        finally:
            if oud_mod is None:
                sys.modules.pop("anthropic", None)
            else:
                sys.modules["anthropic"] = oud_mod
            if oud_key is None:
                os.environ.pop("ANTHROPIC_API_KEY", None)
            else:
                os.environ["ANTHROPIC_API_KEY"] = oud_key


class HulpTest(unittest.TestCase):
    def test_json_uit_codeblok(self):
        self.assertEqual(lees_json('Hier:\n```json\n{"a": 1}\n```'), {"a": 1})
        with self.assertRaises(ValueError):
            lees_json("geen json")
        json.dumps(ORG.effectieve_toegang("fin-1").bronnen)


if __name__ == "__main__":
    unittest.main()
