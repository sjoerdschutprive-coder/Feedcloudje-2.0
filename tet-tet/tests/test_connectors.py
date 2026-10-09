"""Tests voor connectors: register, toewijzing via de cultuurkaart van de afdeling en uitzonderingen op de profielkaart."""
import pathlib
import re
import shutil
import tempfile
import unittest

from tettet import BASIS
from tettet.kaarten import KaartFout, Organisatie
from tettet.validatie import valideer

ORG = Organisatie()


def kopie(aanpassen) -> pathlib.Path:
    """Kopie van de kaarten waarin `aanpassen(map)` iets wijzigt."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    shutil.copytree(BASIS / "kaarten", tmp / "kaarten")
    aanpassen(tmp / "kaarten")
    return tmp


def extra(map_, agent: str, regel: str):
    p = map_ / "agents" / f"{agent}.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("  extra_connectors: []", "  extra_connectors:\n" + regel), encoding="utf-8")


class RegisterTest(unittest.TestCase):
    def test_alleen_verbonden_connectors(self):
        verbonden = {c for c, x in ORG.connectors.items() if x["verbonden"]}
        self.assertEqual(verbonden, {"gdrive", "gcal", "gmail", "firecrawl"})
        for a in ORG.agents:
            bronnen = ORG.effectieve_toegang(a).bronnen
            self.assertFalse({c for c in bronnen if c in ORG.connectors} - verbonden, a)
            for oud in ("exact", "hubspot", "slack", "notion", "canva", "github", "klantsysteem", "reviews"):
                self.assertNotIn(oud, bronnen, a)

    def test_connectors_komen_van_de_cultuurkaart(self):
        for d, kaart in ORG.afdelingen.items():
            for a in ORG.team(d):
                t = ORG.effectieve_toegang(a["id"]).bronnen
                for c in ORG.afdelingsconnectors(d):
                    if not any(i.startswith(c + ":") for i in a["mandaat"]["inperkingen"]):
                        self.assertIn(c, t, (a["id"], c))
        self.assertTrue(all("connectors" not in t for t in ORG.toegang.values()))
        self.assertEqual(ORG.effectieve_toegang("mkt-1").bronnen.get("firecrawl"), "r")
        self.assertNotIn("gmail", ORG.effectieve_toegang("mkt-1").bronnen)

    def test_niet_verbonden_telt_niet(self):
        def zet(m):
            p = m / "afdelingen" / "mkt.yaml"
            p.write_text(p.read_text(encoding="utf-8").replace("connectors:\n", "connectors:\n  omniroute: r\n"), encoding="utf-8")
        tmp = kopie(zet)
        try:
            org = Organisatie(tmp / "kaarten")
            self.assertNotIn("omniroute", org.effectieve_toegang("mkt-1").bronnen)
        finally:
            shutil.rmtree(tmp)

    def test_onbekende_connector_is_fout(self):
        def zet(m):
            p = m / "afdelingen" / "mkt.yaml"
            p.write_text(p.read_text(encoding="utf-8").replace("connectors:\n", "connectors:\n  slack: rw\n"), encoding="utf-8")
        tmp = kopie(zet)
        try:
            _, fouten = valideer(tmp / "kaarten")
            self.assertTrue(any("slack staat niet in het connectorregister" in f for f in fouten), fouten)
        finally:
            shutil.rmtree(tmp)


class ExtraConnectorTest(unittest.TestCase):
    def test_raad_geeft_een_tet_gmail_van_een_andere_afdeling(self):
        tmp = kopie(lambda m: extra(m, "mkt-1", "    - {connector: gmail, recht: r, reden: 'leest klantmails voor de doelgroepanalyse', goedgekeurd_door: raad}\n"))
        try:
            org = Organisatie(tmp / "kaarten")
            self.assertEqual(org.effectieve_toegang("mkt-1").bronnen["gmail"], "r")
            self.assertNotIn("gmail", org.effectieve_toegang("mkt-2").bronnen)     # alleen voor deze agent
            self.assertIn("gmail:", "\n".join(org.effectieve_toegang("mkt-1").regels))
        finally:
            shutil.rmtree(tmp)

    def test_grenzen_aan_extra_connectors(self):
        gevallen = {
            "schrijfrecht dat geen afdeling heeft": ("mkt-1", "    - {connector: gmail, recht: rw, reden: 'versturen', goedgekeurd_door: raad}\n", "met schrijfrecht"),
            "connector van de eigen afdeling": ("mkt-1", "    - {connector: gdrive, recht: rw, reden: 'dubbel', goedgekeurd_door: raad}\n", "heeft de afdeling al"),
            "zonder akkoord van de Raad": ("mkt-1", "    - {connector: gmail, recht: r, reden: 'zomaar', goedgekeurd_door: mkt-h}\n", "schema"),
            "niet in het register": ("mkt-1", "    - {connector: slack, recht: r, reden: 'chat', goedgekeurd_door: raad}\n", "niet in het connectorregister"),
            "assistent": ("oppertet-a", "    - {connector: gmail, recht: r, reden: 'mail', goedgekeurd_door: raad}\n", "geen extra connectors"),
        }
        for naam, (agent, regel, verwacht) in gevallen.items():
            tmp = kopie(lambda m: extra(m, agent, regel))
            try:
                _, fouten = valideer(tmp / "kaarten")
                self.assertTrue(any(verwacht in f for f in fouten), (naam, fouten))
                with self.assertRaises(KaartFout):
                    Organisatie(tmp / "kaarten")
            finally:
                shutil.rmtree(tmp)


class WerkdagPromptTest(unittest.TestCase):
    def test_prompt_noemt_alleen_eigen_connectors(self):
        from tettet.werkdag import Werkdag
        wd = Werkdag.__new__(Werkdag)
        wd.org = ORG
        hr = "\n".join(wd._connector_regels("hr-h"))
        self.assertIn("mcp__Gmail__", hr)
        self.assertIn("alleen lezen", hr)
        self.assertNotIn("mcp__Firecrawl__", hr)
        self.assertIn("geen tools waarvan de naam met mcp__ begint", "\n".join(wd._connector_regels("oppertet")))
        self.assertTrue(re.search(r"Google Drive.*lezen en schrijven", "\n".join(wd._connector_regels("fin-1"))))


if __name__ == "__main__":
    unittest.main()
