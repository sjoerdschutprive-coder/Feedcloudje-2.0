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
