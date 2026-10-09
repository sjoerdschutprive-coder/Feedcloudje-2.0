"""Tests voor samenwerking: collectief Brein, deelfilter en toezicht, kantine en de overlegcyclus (mockmodus, zonder API)."""
import datetime as dt
import json
import pathlib
import re
import shutil
import tempfile
import unittest
from unittest import mock

from tettet import samenwerking as sw
from tettet.kaarten import Organisatie
from tettet.werkdag import Werkdag

ORG = Organisatie()
GEHEIM = "Marge per klant 31,4 procent"


def schrijf_dump(map_, staat: dict):
    for collectie, docs in staat.items():
        (map_ / collectie).mkdir(parents=True, exist_ok=True)
        for doc_id, body in docs.items():
            (map_ / collectie / f"{doc_id}.json").write_text(json.dumps(body, ensure_ascii=False))


def pas_batches_toe(dump: pathlib.Path, batches):
    """Doet wat de ArtifactData-tool doet: elke regel zetten of verwijderen in de opslag (hier: de dumpmap)."""
    for b in batches:
        for r in b:
            pad = dump / r["collection"] / f"{r['doc_id']}.json"
            if r["op"] == "set":
                pad.parent.mkdir(parents=True, exist_ok=True)
                pad.write_text(pathlib.Path(r["file_path"]).read_text(encoding="utf-8"), encoding="utf-8")
            else:
                pad.unlink(missing_ok=True)


def antwoord(stap: dict, prompt: str, lek: bool = False) -> str:
    """Speelt de agents, ook in de nieuwe overleg- en kantinebeurten."""
    s = stap["soort"]
    if s == "oppertet_plan":
        return json.dumps({"afdelingsdoelen": [{"afdeling": a, "doel": f"Doel {a}", "hoofdlijnen": [f"Hoofdlijn {a}"], "waarom": "-"} for a in stap["afdelingen"][:3]]})
    if s == "hoofdtet_plan":
        tets = re.findall(r"^- ([a-z]+-\d) \(", prompt, re.M)
        return json.dumps({"taken": [{"opdracht": "Werk " + stap["afdeling"], "acceptatiecriteria": ["c"], "toegewezen": tets[0], "budget_eur": 2, "toets": "kwaliteit"}]})
    if s == "uitvoeren" and stap["fase"] == "tet":
        extra = ""
        if "fin" in prompt and "Taakcontract" in prompt and "Werk fin" in prompt:
            extra = "\n## Bronnen\nboekhouding\n## Vragen aan het Brein\n- [aan: mkt] Welke doelgroep is het meest prijsgevoelig?\n## Signalen\n- [voor: mkt] Prijsverhoging raakt de positionering."
        vraag = re.search(r"^- \[(b[\w-]+)\] Welke doelgroep", prompt, re.M)
        if vraag:
            extra += f"\n## Antwoorden\n- [{vraag.group(1)}] Studenten, volgens de reviewanalyse."
        return "## Resultaat\nGedaan.\n## Zelfcheck\n- c: voldaan\n## Zekerheid\nhoog\n## Les\nKlein beginnen." + extra
    if s == "uitvoeren":
        return json.dumps({"oordeel": "goedgekeurd", "score": 8, "bevindingen": []})
    if s == "huddle":
        ids = re.findall(r"^- ([a-z]+-[a-z0-9]+) \(", prompt, re.M)
        return json.dumps({"beurten": [{"agent": i, "prioriteit": "taak afmaken", "knelpunt": None, "nodig_van": None} for i in ids],
                           "besluiten": [{"wat": "Eerst de open taak afronden", "eigenaar": ids[0]}], "vragen_brein": []})
    if s == "kantine" and stap.get("fase") == "toezicht":
        return json.dumps({"oordelen": [], "ingreep": "Even stoppen: dat is niet voor iedereen aan tafel."})
    if s == "kantine":
        beurten = [{"agent": a, "tekst": f"Hoi, {a} hier. Lekker weertje.", "verwijst_naar": []} for a in stap["deelnemers"]]
        if lek:
            fin_taak = re.search(r"^- (fin-[a-z0-9]+): \[([\w-]+)\].*NIET deelbaar", prompt, re.M)
            if fin_taak:
                beurten.append({"agent": fin_taak.group(1), "tekst": GEHEIM, "verwijst_naar": [fin_taak.group(2)]})
        return json.dumps({"beurten": beurten, "uitkomsten": [{"soort": "vraag", "door": stap["deelnemers"][0], "aan": "hr", "tekst": "Wie organiseert de vrijdagborrel?"}]})
    if s == "voorbereiding":
        return json.dumps({"voortgang": "op schema", "risico": "deadline", "kans": "hergebruik", "alleen_ik_weet": [f"Detail van {stap['agent']}"]})
    if s == "afdelingsoverleg":
        return json.dumps({"beurten": [], "memo": {"samenvatting": "Op schema.", "besluitvragen": [f"Prioriteit voor {stap['afdeling']}?"],
                                                   "alleen_wij_weten": ["x"], "risicos": []}, "besluiten": []})
    if s == "bilateraal":
        return json.dumps({"afspraken": [{"wat": "Wekelijks prijs en positionering afstemmen", "eigenaar": stap["agent"]}], "conflicten": []})
    if s == "vooraf_lezen":
        memo = re.findall(r"^## Memo (.+)$", prompt, re.M)
        return json.dumps({"vragen": [{"memo": "fin", "vraag": "Welke aanname weegt het zwaarst?"}] if memo else []})
    if s == "mt_oordeel":
        nrs = [int(n) for n in re.findall(r"^(\d+)\. \(", prompt, re.M)]
        return json.dumps({"oordelen": [{"nr": n, "oordeel": "Eerst Finance", "onderbouwing": "-", "zekerheid": "middel"} for n in nrs]})
    if s == "mt":
        return json.dumps({"samenvatting": "Besloten.", "besluiten": [{"nr": 1, "besluit": "Finance gaat voor", "eigenaar": "fin-h", "reden": "afhankelijkheid", "deadline": None}],
                           "vragen_aan_raad": []})
    if s == "retro":
        return json.dumps({"bevindingen": ["Kantine werkt"], "voorstel": {"titel": "Huddles korter", "toelichting": "x", "soort": "werkwijze"}})
    if s == "routine":
        return json.dumps({"bevindingen": ["ok"], "voorstel": None})
    return "Werkdag gedaan."


def draai(werk, lek=False):
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
                pathlib.Path(p["antwoord"]).write_text(antwoord(s, prompt, lek))
                r = Werkdag(werk).verwerk(stap["id"])
                batches += r["batches"]
                if r.get("klaar"):
                    break
    batches += Werkdag(werk).einde()["batches"]
    return batches


class DeelfilterTest(unittest.TestCase):
    def test_label_buiten_toegang_wordt_geblokkeerd(self):
        index = {"t1": {"id": "t1", "labels": ["boekhouding"]}, "b1": {"id": "b1", "labels": []}}
        beurten = [{"agent": "fin-1", "tekst": "Mijn taak loopt", "verwijst_naar": ["t1"]},
                   {"agent": "fin-1", "tekst": "Mooie les in het Brein", "verwijst_naar": ["b1"]},
                   {"agent": "fin-1", "tekst": "In de boekhouding zag ik iets geks", "verwijst_naar": []}]
        uit = sw.deelfilter(beurten, ["fin-1", "mkt-1", "rnd-1"], ORG, index)
        self.assertEqual([b["filter"] for b in uit], ["geblokkeerd", "ok", "twijfel"])
        self.assertIn("boekhouding", uit[0]["reden"])

    def test_toezicht_ziet_alles_en_finance_onderling_mag(self):
        item = {"labels": ["boekhouding"]}
        self.assertTrue(sw.zichtbaar(item, ORG.effectieve_toegang("risk-2")))
        self.assertTrue(sw.zichtbaar(item, ORG.effectieve_toegang("fin-2")))
        self.assertFalse(sw.zichtbaar(item, ORG.effectieve_toegang("mkt-1")))

    def test_labels_alleen_uit_eigen_toegang(self):
        t = ORG.effectieve_toegang("fin-1")
        self.assertEqual(sw.labels_uit("## Resultaat\nx\n## Bronnen\nboekhouding, web, canva\n## Les\ny", t), ["boekhouding"])


class BreinTest(unittest.TestCase):
    def test_wie_weet_wat(self):
        wie = sw.wie_weet_wat(ORG, "prijsstrategie en elasticiteit van de omzet", zelf="mkt-1")
        self.assertEqual(wie[0]["agent"], "fin-1")
        self.assertTrue(all(ORG.ingezet(ORG.agent(w["agent"])) for w in wie))

    def test_blokken(self):
        b = sw.blokken_uit("## Vragen aan het Brein\n- [aan: mkt] Vraag?\n## Signalen\n- [voor: mkt, prod] Let op\n## Antwoorden\n- [b12] Ja")
        self.assertEqual(b["vragen"][0]["aan"], "mkt")
        self.assertEqual(b["signalen"][0]["voor"], ["mkt", "prod"])
        self.assertEqual(b["antwoorden"][0]["vraag"], "b12")

    def test_kantinetafel_gemengd(self):
        tafel = sw.tafel(ORG, [], sleutel="x", grootte=6, min_afdelingen=3)
        self.assertEqual(len(tafel), 6)
        self.assertGreaterEqual(len({ORG.agent(a)["afdeling"] for a in tafel}), 3)
        # roulatie: wie net aan tafel zat, schuift de volgende keer door
        tweede = sw.tafel(ORG, [{"deelnemers": tafel}], sleutel="y", grootte=6)
        self.assertFalse(set(tafel) & set(tweede))

    def test_overlegcyclus(self):
        wo, vr = dt.date(2026, 11, 4), dt.date(2026, 11, 6)
        self.assertEqual(sw.overleg_cyclus(wo, 5), ("2026-11-06", 2))
        self.assertEqual(sw.fasen_open(wo, 5, set()), ["voorbereiding", "afdelingsoverleg"])
        self.assertEqual(sw.fasen_open(vr, 5, {"voorbereiding"}), ["afdelingsoverleg", "bilateraal", "vooraf_lezen", "mt_oordeel", "mt"])
        self.assertTrue(sw.retro_nodig("2026-11-06"))
        self.assertFalse(sw.retro_nodig("2026-11-13"))


class WeekTest(unittest.TestCase):
    """Een volledige week in mockmodus: huddles, kantine, voorbereiding, memo's, MT en retro; plus toezicht op een lek."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.dump = self.tmp / "dump"
        schrijf_dump(self.dump, {"staat": {"doel": {"naam": "Test", "omschrijving": "o", "deadline": "2026-12-31"}, "instellingen": {"modus": "mock"}}})

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def dag(self, datum: dt.date, lek=False):
        werk = self.tmp / f"werk-{datum.isoformat()}"
        with mock.patch.object(Werkdag, "vandaag", lambda self: datum):
            _, start = Werkdag.start(self.dump, werk)
            batches = start["batches"] + draai(werk, lek)
        pas_batches_toe(self.dump, batches)
        return Werkdag(werk).staat, batches

    def test_week(self):
        for d in range(2, 7):   # maandag 2 t/m vrijdag 6 november 2026; MT op vrijdag, eerste van de maand → retro
            st, batches = self.dag(dt.date(2026, 11, d), lek=(d == 3))
        soorten = [o["soort"] for o in st.overleggen]
        for s in ("huddle", "voorbereiding", "afdelingsoverleg", "vooraf_lezen", "mt_oordeel", "mt", "retro"):
            self.assertIn(s, soorten, s)
        self.assertGreaterEqual(sum(1 for o in st.overleggen if o["soort"] == "huddle"), 5)
        fasen = {o["fase"] for o in st.overleggen if o["soort"] == "fase" and o["cyclus"] == "2026-11-06"}
        self.assertTrue({"voorbereiding", "afdelingsoverleg", "bilateraal", "vooraf_lezen", "mt_oordeel", "mt", "retro"} <= fasen)
        mt = next(o for o in st.overleggen if o["soort"] == "mt")
        self.assertEqual(mt["besluiten"][0]["eigenaar"], "fin-h")
        self.assertTrue(any(b["soort"] == "besluit" and "MT 2026-11-06" in b["tekst"] for b in st.brein))
        self.assertEqual(len(st.kantine), 5)
        # voorbereiding: ieder zelfstandig; de prompts van de voorbereiding bevatten niets van anderen
        voor = [o for o in st.overleggen if o["soort"] == "voorbereiding"]
        self.assertEqual(len({o["agent"] for o in voor}), len(voor))

        # Collectief Brein: de vraag van Finance aan Marketing is beantwoord, het signaal staat bij Marketing.
        vraag = next(b for b in st.brein if b["soort"] == "vraag" and b.get("aan") == "mkt")
        self.assertEqual(vraag["labels"], ["boekhouding"])
        sig = next(b for b in st.brein if b["soort"] == "signaal")
        self.assertIn("mkt", sig["ook"])

        # Toezicht: op dinsdag noemde een Finance-agent werk op de boekhouding aan een gemengde tafel.
        lek = [k for k in st.kantine if k["geblokkeerd"]]
        alle_tekst = json.dumps([st.kantine, st.grootboek, st.brein, st.overleggen], ensure_ascii=False)
        if lek:   # alleen als een Finance-agent met een taak die dag aan tafel zat
            k = lek[0]
            self.assertTrue(any(b.get("tekst") == "[niet gedeeld]" for b in k["beurten"]))
            self.assertTrue(any(b.get("ingreep") and b["agent"] == "risk-2" for b in k["beurten"]))
            self.assertTrue(any(e["type"] == "kantine.lek_voorkomen" for e in st.grootboek))
            self.assertTrue(any(b.get("bron") == "kantine" and b["agent"] == "risk-2" for b in st.brein))
            later = [x for x in st.kantine if x["ts"] > k["ts"] and set(x["deelnemers"]) & set(k["deelnemers"])]
            if later:
                self.assertTrue(later[0]["streng"])
        self.assertNotIn(GEHEIM, alle_tekst, "de inhoud van een tegengehouden beurt komt nergens terecht")

    def test_lek_wordt_tegengehouden(self):
        """Gericht scenario: een Finance-taak op de boekhouding, een gemengde tafel met Finance, en een verwijzing ernaar."""
        schrijf_dump(self.dump, {"taken": {"tf": {"id": "tf", "dept": "fin", "agent": "fin-1", "title": "Margeanalyse", "status": "bezig",
                                                  "labels": ["boekhouding"], "created": 1, "control": "risk-c2", "afkeuringen": 0, "bijgewerkt": 10 ** 13}},
                                 "kantine": {f"k{i}": {"id": f"k{i}", "ts": i, "deelnemers": [a["id"] for a in ORG.actieve_agents() if a["id"] not in ("fin-1", "mkt-1", "rnd-1", "risk-2")][:6]}
                                             for i in range(3)}})
        werk = self.tmp / "werk"
        with mock.patch.object(Werkdag, "vandaag", lambda self: dt.date(2026, 11, 2)):
            Werkdag.start(self.dump, werk)
            wd = Werkdag(werk)
            stap = wd._nieuwe_stap("kantine", "fin-1", deelnemers=["fin-1", "mkt-1", "rnd-1", "hr-1"], fase="gesprek")
            wd.klaar_met({})
            p = Werkdag(werk).prompt(stap["id"])
            prompt = pathlib.Path(p["prompt"]).read_text()
            self.assertIn("[tf] Margeanalyse", prompt)
            self.assertIn("NIET deelbaar", prompt)
            pathlib.Path(p["antwoord"]).write_text(antwoord({**stap}, prompt, lek=True))
            r = Werkdag(werk).verwerk(stap["id"])
            self.assertFalse(r["klaar"])                        # eerst toezicht, dan pas zichtbaar
            p = Werkdag(werk).prompt(stap["id"])
            self.assertEqual(p["agent"], "risk-2")
            tp = pathlib.Path(p["prompt"]).read_text()
            self.assertIn("filter: geblokkeerd", tp)
            pathlib.Path(p["antwoord"]).write_text(json.dumps({"oordelen": [], "ingreep": "Even stoppen: dit hoort niet aan deze tafel."}))
            r = Werkdag(werk).verwerk(stap["id"])
            self.assertEqual(r["geblokkeerd"], 1)
            st = Werkdag(werk).staat
        k = st.kantine[-1]
        self.assertEqual(k["beurten"][-2]["tekst"], "[niet gedeeld]")
        self.assertEqual(k["beurten"][-1]["agent"], "risk-2")
        self.assertNotIn(GEHEIM, json.dumps([st.kantine, st.grootboek, st.brein], ensure_ascii=False))
        self.assertFalse(any(b["soort"] == "vraag" and b["agent"] == "fin-1" for b in st.brein))   # uitkomsten van de spreker vervallen

    def test_brein_zichtbaarheid_in_prompts(self):
        """Een les op de boekhouding komt in de prompt van Finance, niet in die van Marketing."""
        schrijf_dump(self.dump, {"brein": {"bx": {"id": "bx", "soort": "les", "dept": "mkt", "ook": ["fin"], "agent": "fin-2", "tekst": "Geheime les over kostprijzen",
                                                  "labels": ["boekhouding"], "ts": 1}},
                                 "taken": {"tm": {"id": "tm", "dept": "mkt", "agent": "mkt-1", "title": "Doelgroepen en prijsstrategie", "status": "volgende", "created": 1, "criteria": ["c"],
                                                  "control": "risk-c1", "afkeuringen": 0},
                                           "tf": {"id": "tf", "dept": "fin", "agent": "fin-1", "title": "Kostprijzen", "status": "volgende", "created": 2, "criteria": ["c"],
                                                  "control": "risk-c2", "afkeuringen": 0}}})
        werk = self.tmp / "werk"
        Werkdag.start(self.dump, werk)
        wd = Werkdag(werk)
        m = wd._nieuwe_stap("uitvoeren", "mkt-1", taak="tm", fase="tet", poging=1)
        f = wd._nieuwe_stap("uitvoeren", "fin-1", taak="tf", fase="tet", poging=1)
        wd.klaar_met({})
        pm = pathlib.Path(Werkdag(werk).prompt(m["id"])["prompt"]).read_text()
        pf = pathlib.Path(Werkdag(werk).prompt(f["id"])["prompt"]).read_text()
        self.assertNotIn("Geheime les", pm)
        self.assertIn("Geheime les", pf)
        self.assertIn("# Wie weet wat", pm)


if __name__ == "__main__":
    unittest.main()
