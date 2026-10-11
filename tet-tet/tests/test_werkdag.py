"""Tests voor de werkdag: een volledige gesimuleerde werkdag op een nep-dump, en pariteit met de pagina."""
import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

from tettet import BASIS
from tettet.kantoordb import KantoorStaat, controlegetal, js_json
from tettet.werkdag import Werkdag


def schrijf_dump(map_, staat: dict):
    for collectie, docs in staat.items():
        (map_ / collectie).mkdir(parents=True, exist_ok=True)
        for doc_id, body in docs.items():
            (map_ / collectie / f"{doc_id}.json").write_text(json.dumps(body, ensure_ascii=False))


def antwoord(stap: dict, prompt: str, streng: bool = False) -> str:
    """Speelt de agent: geeft een antwoord in het gevraagde formaat."""
    if stap["soort"] == "oppertet_plan":
        return json.dumps({"afdelingsdoelen": [{"afdeling": a, "doel": f"Doel {a}", "hoofdlijnen": [f"Hoofdlijn {a}"], "waarom": "-"} for a in stap["afdelingen"][:2]]})
    if stap["soort"] == "hoofdtet_plan":
        tets = re.findall(r"^- ([a-z]+-\d) \(", prompt, re.M)
        return json.dumps({"taken": [{"opdracht": "Werk " + stap["afdeling"], "acceptatiecriteria": ["c"], "toegewezen": tets[0], "budget_eur": 2, "toets": "kwaliteit"}]})
    if stap["soort"] == "uitvoeren" and stap["fase"] == "tet":
        return "## Resultaat\nGedaan.\n## Zelfcheck\n- c: voldaan\n## Zekerheid\nhoog\n## Les\nKlein beginnen."
    if stap["soort"] == "uitvoeren":
        return json.dumps({"oordeel": "afgekeurd" if streng else "goedgekeurd", "score": 4 if streng else 8, "bevindingen": ["Bron ontbreekt."] if streng else []})
    if stap["soort"] == "escalatie":
        return json.dumps({"besluit": "herformuleer", "opdracht": "Scherper werk", "acceptatiecriteria": ["bron per claim"], "toegewezen": "fin-1", "toelichting": "criteria waren vaag"})
    if stap["soort"] == "routine":
        return json.dumps({"bevindingen": ["Alles op koers."], "voorstel": {"titel": f"Voorstel {stap['routine']}", "toelichting": "x", "soort": "werkwijze"}})
    return "Werkdag gedaan. Grootste afhankelijkheid: de Raad."


def draai_werkdag(werk, streng_voor=()):
    batches = []
    for _ in range(80):
        uit = Werkdag(werk).volgende(3)
        batches += uit["batches"]
        if uit["klaar"]:
            break
        for stap in uit["stappen"]:
            while True:
                p = Werkdag(werk).prompt(stap["id"])
                batches += p["batches"]
                prompt = pathlib.Path(p["prompt"]).read_text()
                s = json.loads((werk / "voortgang.json").read_text())["stappen"][stap["id"]]
                pathlib.Path(p["antwoord"]).write_text(antwoord(s, prompt, streng=s.get("taak") in streng_voor and s.get("fase") == "control"))
                r = Werkdag(werk).verwerk(stap["id"])
                batches += r["batches"]
                if r.get("klaar"):
                    break
    batches += Werkdag(werk).einde()["batches"]
    return batches


class WerkdagTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.dump, self.werk = self.tmp / "dump", self.tmp / "werk"
        schrijf_dump(self.dump, {
            "staat": {"doel": {"naam": "Test", "omschrijving": "o", "deadline": "2026-12-31"}, "instellingen": {"modus": "mock"}},
            "taken": {
                "t1": {"id": "t1", "dept": "fin", "agent": "fin-1", "title": "Vastgelopen taak", "status": "bezig", "approval": False, "created": 1, "criteria": ["c"], "control": "risk-c2", "afkeuringen": 0},
                "t2": {"id": "t2", "dept": "risk", "agent": "risk-1", "title": "Risk-taak", "status": "volgende", "approval": False, "created": 2, "criteria": ["c"], "control": "raad", "afkeuringen": 0},
            },
            "patches": {"p1": {"collectie": "taken", "doc": "t2", "velden": {"title": "Risk-taak (gepatcht)"}, "bijgewerkt": 5}},
        })

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_volledige_werkdag(self):
        _, start = Werkdag.start(self.dump, self.werk)
        self.assertEqual(start["hersteld"], 1)
        batches = start["batches"] + draai_werkdag(self.werk, streng_voor=())
        st = Werkdag(self.werk).staat
        v = json.loads((self.werk / "voortgang.json").read_text())
        soorten = [s["soort"] for s in v["stappen"].values()]
        for soort in ("oppertet_plan", "hoofdtet_plan", "uitvoeren", "routine", "dagverslag"):
            self.assertIn(soort, soorten)
        self.assertEqual(st.taken["t1"]["status"], "klaar")
        self.assertTrue(st.taken["t2"]["approval"])                      # risk-werk wacht op de Raad
        self.assertEqual(st.taken["t2"]["title"], "Risk-taak (gepatcht)")  # patch uit de dump toegepast
        self.assertTrue(st.verslagen and st.brein and st.voorstellen)
        # Alle schrijfacties zijn nieuwe documenten of verwijderingen met versie 1: geen versies nodig.
        regels = [r for b in batches for r in b]
        self.assertTrue(all(r["op"] == "set" or (r["op"] == "delete" and r["if_version"] == 1) for r in regels))
        self.assertTrue(all(len(b) <= 50 for b in batches))
        nieuw = [(r["collection"], r["doc_id"]) for r in regels if r["op"] == "set"]
        self.assertEqual(len(nieuw), len(set(nieuw)), "elk document wordt maar één keer aangemaakt")
        bestaande = {("taken", "t1"), ("taken", "t2"), ("staat", "doel")}
        self.assertFalse(bestaande & set(nieuw), "bestaande documenten alleen via patches")

    def test_escalatie_en_herkansing(self):
        Werkdag.start(self.dump, self.werk)
        draai_werkdag(self.werk, streng_voor=("t1",))
        st = Werkdag(self.werk).staat
        t1 = st.taken["t1"]
        self.assertEqual(t1.get("herkansingen"), 1)  # Hoofdtet herformuleerde na escalatie
        self.assertEqual(t1["title"], "Scherper werk")
        self.assertFalse(t1.get("geescaleerd"))
        # Elke afkeuring werd een les of incident; na het besluit van de Hoofdtet is de zekerheid niet meer laag.
        afkeur = [b for b in st.brein if b.get("bron") == "afkeuring" and b.get("taak") == "t1"]
        self.assertTrue(afkeur)
        self.assertTrue(any(b["soort"] == "incident" for b in afkeur))
        self.assertTrue(all(b["zekerheid"] == "middel" and b.get("bevestigd_door") == "fin-h" for b in afkeur))

    def test_stand_per_agent_met_stabiliteit_en_afkeurreden(self):
        Werkdag.start(self.dump, self.werk)
        draai_werkdag(self.werk, streng_voor=("t1",))
        wd = Werkdag(self.werk)
        self.assertEqual(wd.staat.taken["t1"]["afkeurreden"], "Bron ontbreekt.")   # blijft staan na de herkansing
        bericht = wd._routine_bericht("performance")
        self.assertIn("stabiliteitsscore: nog niet gemeten", bericht)              # geen verzonnen getal zolang niet gemeten
        self.assertIn("afgekeurd: 'Scherper werk': Bron ontbreekt.", bericht)
        self.assertIn(", sluit", "\n".join(wd._stand_regels()))

    def test_statustelling_controleert_de_som(self):
        from tettet.werkdag import afkeurreden, stabiliteit_tekst, statustelling
        goed = statustelling([{"status": "klaar"}, {"status": "bezig"}, {"status": "klaar"}])
        self.assertEqual((goed["per_status"], goed["sluit"]), ({"bezig": 1, "klaar": 2}, True))
        fout = statustelling([{"status": "klaar"}, {}])
        self.assertFalse(fout["sluit"])
        self.assertEqual(fout["per_status"]["onbekend"], 1)
        self.assertEqual(afkeurreden({"bevindingen": ["Eerste\nregel", "tweede"]}), "Eerste regel")
        self.assertEqual(afkeurreden({}), "geen reden vastgelegd")
        self.assertEqual(stabiliteit_tekst({"meetwaarden": {"stabiliteitsscore": 0.8}}), "0.8")

    def test_raadsverzoek_met_beslisdatum_en_standaardgedrag(self):
        Werkdag.start(self.dump, self.werk)
        draai_werkdag(self.werk)
        wd = Werkdag(self.werk)
        t2 = wd.staat.taken["t2"]
        self.assertTrue(t2["approval"])
        self.assertEqual(t2["beslis_voor"], "2026-12-30")          # één dag vóór de deadline van de doelstelling
        self.assertIn("al goedgekeurde kaarten", t2["standaardgedrag"])
        self.assertIn("Raad beslist uiterlijk 2026-12-30", wd._routine_bericht("risico"))
        # een lopend verzoek houdt zijn afgesproken datum
        self.assertNotIn("beslis_voor", wd._raadsverzoek(t2, raadsvraag="x"))

    def test_beslisregel_en_verlopen(self):
        from tettet.werkdag import beslisregel, verlopen_raadsverzoeken
        self.assertEqual(beslisregel("2026-10-20", {"marge_dagen": 2}, "2026-10-11")["beslis_voor"], "2026-10-18")
        self.assertEqual(beslisregel("2026-10-11", {}, "2026-10-11")["beslis_voor"], "2026-10-11")   # nooit vóór vandaag
        self.assertEqual(beslisregel(None, {"zonder_deadline_dagen": 3}, "2026-10-11")["beslis_voor"], "2026-10-14")
        self.assertEqual(beslisregel("onzin", {}, "2026-10-11")["beslis_voor"], "2026-10-14")
        taken = [{"approval": True, "status": "bezig", "beslis_voor": "2026-10-10"}, {"approval": True, "status": "bezig", "beslis_voor": "2026-10-12"},
                 {"approval": False, "beslis_voor": "2026-10-01"}]
        self.assertEqual(len(verlopen_raadsverzoeken(taken, "2026-10-11")), 1)

    def test_niet_meetbaar_vraagt_de_raad(self):
        Werkdag.start(self.dump, self.werk)
        wd = Werkdag(self.werk)
        stap = wd.volgende(3)["stappen"][0]
        self.assertEqual(stap["soort"], "oppertet_plan")
        p = Werkdag(self.werk).prompt(stap["id"])
        self.assertIn("meetbaar", pathlib.Path(p["prompt"]).read_text())
        pathlib.Path(p["antwoord"]).write_text(json.dumps({"meetbaar": False, "ontbreekt": ["kpi"], "vraag_aan_raad": "Welke KPI?", "afdelingsdoelen": []}))
        r = Werkdag(self.werk).verwerk(stap["id"])
        self.assertEqual(r["uitkomst"], "verduidelijking")
        st = Werkdag(self.werk).staat
        self.assertEqual(st.doel["verduidelijking"]["vraag"], "Welke KPI?")
        patches = [json.loads(pathlib.Path(x["file_path"]).read_text()) for b in r["batches"] for x in b if x["collection"] == "patches"]
        self.assertTrue(any(x["collectie"] == "staat" and x["velden"].get("verduidelijking") for x in patches))
        # een nieuwe werkdag zet de doelstelling niet opnieuw om zolang de vraag openstaat
        schrijf_dump(self.dump, {"staat": {"doel": {**st.doel}}})
        Werkdag.start(self.dump, self.werk)
        soorten = [s["soort"] for s in Werkdag(self.werk).volgende(3)["stappen"]]
        self.assertNotIn("oppertet_plan", soorten)

    def test_brein_patch_bij_dubbele_les(self):
        Werkdag.start(self.dump, self.werk)
        wd = Werkdag(self.werk)
        t = wd.staat.taken["t1"]
        t["resultaat"] = "## Les\nKlein beginnen met de criteria."
        wd._leer(t)
        wd._brein_les({"id": "bx", "soort": "les", "dept": "mkt", "agent": "mkt-1", "taak": "t9", "tekst": "Klein beginnen met de criteria!", "bevestigd": 1, "ts": 1})
        self.assertEqual(len(wd.staat.brein), 1)
        self.assertEqual(wd.staat.brein[0]["bevestigd"], 2)
        self.assertEqual(wd.staat.brein[0]["ook"], ["mkt"])
        uit = wd.klaar_met({})
        regels = [r for b in uit["batches"] for r in b]
        patch = [json.loads(pathlib.Path(r["file_path"]).read_text()) for r in regels if r["collection"] == "patches"]
        self.assertTrue(any(p["collectie"] == "brein" and p["velden"]["bevestigd"] == 2 for p in patch))

    def test_dump_met_patches_laden(self):
        st = KantoorStaat.uit_dump(self.dump)
        self.assertEqual(st.taken["t2"]["title"], "Risk-taak (gepatcht)")


class GrootboekPariteitTest(unittest.TestCase):
    def test_controlegetal_gelijk_aan_pagina(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node niet beschikbaar")
        html = (BASIS / "kantoor" / "index.html").read_text(encoding="utf-8")
        fn = next(r for r in html.splitlines() if r.startswith("function controlegetal(s)"))
        e = {"bron": "werkdag-1", "n": 1, "ts": 1791518245999, "type": "taak.opgeleverd", "agent": "rnd-2", "taak": "t1",
             "data": {"tekst": "Eén € en 中文, \"quotes\"\nregel", "score": 8, "lijst": [True, None]}, "modus": "werkdag"}
        verwacht = controlegetal("abc" + js_json(e))
        js = fn + f"\nconsole.log(controlegetal('abc' + JSON.stringify({js_json(e)})));"
        r = subprocess.run([node, "-e", js], capture_output=True, text=True)
        uit = r.stdout.strip() or r.stderr
        self.assertEqual(uit, verwacht)


if __name__ == "__main__":
    unittest.main()
