"""Zet de kaarten en de samengestelde agentprompts in het Tet Tet-kantoor (kantoor/index.html).

Alles tussen de markeringen @@KAARTEN:BEGIN en @@KAARTEN:END wordt opnieuw gegenereerd.
Draai dit na elke kaartwijziging, en publiceer daarna het kantoor opnieuw.

Gebruik:  python tet-tet/scripts/bouw_kantoor.py
"""
import json
import pathlib
import re
import sys

BASIS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASIS))
import yaml  # noqa: E402

from tettet import hr  # noqa: E402
from tettet import kalender as kal  # noqa: E402
from tettet import keten  # noqa: E402
from tettet import prestatie  # noqa: E402
from tettet import samenwerking as sw  # noqa: E402
from tettet.kaarten import Organisatie  # noqa: E402
from tettet.validatie import controleer_mappen  # noqa: E402

J = lambda o: json.dumps(o, ensure_ascii=False)
VOLGORDE = ["oppertet", "ops-h", "ops-1", "ops-2", "ops-3", "fin-h", "fin-1", "fin-2", "fin-3", "mkt-h", "mkt-1", "mkt-2", "mkt-3",
            "rnd-h", "rnd-1", "rnd-2", "rnd-3", "hr-h", "hr-1", "hr-2", "hr-3", "risk-h", "risk-1", "risk-2", "risk-c1", "risk-c2",
            "prod-h", "prod-1", "prod-2", "prod-3"]


def principes(kaart):
    return [f'{p["principe"]}: {p["toepassing"].strip()}' for p in kaart.get("edge_principes", [])]


def blok(org: Organisatie) -> str:
    o = org.organisatie
    cultuur_org = {"waarden": [w["naam"] for w in o["kernwaarden"]],
                   "werkwijze": o["toon"]["regels"] + ["Leg elke beslissing met reden en eigenaar vast in het Brein."],
                   "principes": principes(o), "rode_lijnen": o["rode_lijnen"]}
    afd = {d: {"missie": k["missie"], "cultuur": {"waarden": k["waarden"], "werkwijze": k["werkwijze"], "principes": principes(k)}}
           for d, k in org.afdelingen.items()}
    kpis = {d: [x[:1].upper() + x[1:] for x in k.get("kpis", [])] for d, k in org.afdelingen.items()}
    ids = [i for i in VOLGORDE if i in org.agents] + sorted(set(org.agents) - set(VOLGORDE))
    agents = []
    for i in ids:
        a, p = org.agents[i], org.agents[i]["persoonlijkheid"]
        item = {"id": i, "naam": a["naam"], "rol": a["rol"], "dept": None if a["afdeling"] == "centraal" else a["afdeling"],
                "specialisme": a["specialisme"], "missie": a["missie"], "expertise": a["expertise"],
                "kenmerken": [p["stijl"], "Sterk in " + p["sterk_in"]] + ["Valkuil: " + v for v in p["valkuilen"]],
                "versie": a["versie"], "inzet": a.get("inzet", "actief"), "stijl": p["stijl"], "sterk_in": p["sterk_in"],
                # Effectieve toegang (zonder publieke bronnen): het deelfilter in de kantine rekent hiermee.
                "toegang": sorted(b for b in org.effectieve_toegang(i).bronnen if b not in sw.PUBLIEK)}
        if a["mandaat"]["inperkingen"]:
            item["inperking"] = a["mandaat"]["inperkingen"]
        agents.append(item)
    prompts = {i: org.systeemprompt(i) for i in ids}
    protocols = {"oppertet": keten.PROTOCOL_OPPERTET, "hoofdtet": keten.PROTOCOL_HOOFDTET, "tet": keten.PROTOCOL_TET,
                 "controltet": keten.PROTOCOL_CONTROLTET, "voorstellen": keten.PROTOCOL_VOORSTELLEN,
                 "kantine": sw.PROTOCOL_KANTINE, "toezicht": sw.PROTOCOL_TOEZICHT}
    inst = keten.laad_instellingen()
    samen = {"kantine": inst.get("kantine", {}), "overleg": {"mt_dag": (inst.get("overleg") or {}).get("mt_dag", 5)},
             "publiek": sorted(sw.PUBLIEK), "toezicht": sw.TOEZICHT}
    hb = {k["onderdeel"]: k for k in org.kaarten.values() if k["type"] == "handboek"}
    k = kal.instellingen(inst)
    hr_data = {
        "criteria": [{"dimensie": d, "id": c, "label": l, "uitleg": u} for d, c, l, u in prestatie.CRITERIA],
        "toekomstvragen": hr.TOEKOMSTVRAGEN,
        "meting": prestatie.standaard_instellingen(inst),
        "kalender": {"prefix": k["prefix"], "tijdzone": k["tijdzone"], "kalender_id": k["kalender_id"], "bron": k["bron"],
                     "soorten_in_agenda": sorted(k["soorten_in_agenda"]), "begintijd": k["begintijd"], "duur": k["duur"],
                     "namen": kal.SOORT_NAAM, "omschrijving": kal.OMSCHRIJVING},
        "handboek": {o: {"versie": x["versie"], "status": x["status"], "documentsoort": x["documentsoort"]} for o, x in sorted(hb.items())},
        "schrijfstijl": hb.get("schrijfstijl", {}).get("regels", {}),
        "huisstijl": {"afdelingen": hb.get("huisstijl", {}).get("afdelingen", {})},
        "mappen": controleer_mappen(),
        "principes": [{"principe": p_["principe"], "indicator": p_.get("indicator"), "norm": p_.get("norm")} for p_ in org.organisatie.get("edge_principes", [])],
        "dossier": org.beleid.get("hr_dossier", {}),
        "hr_tets": {"prestatie": kal.beoordelaar_hr(org, "prestatie"), "governance": kal.beoordelaar_hr(org, "governance"),
                    "personeel": kal.beoordelaar_hr(org, "personeel")},
    }
    regels = [
        "/* @@KAARTEN:BEGIN – gegenereerd door scripts/bouw_kantoor.py uit tet-tet/kaarten/. Niet met de hand wijzigen. */",
        f"const MAX_AFKEURINGEN = {keten.laad_instellingen()['taken']['max_afkeuringen']};",
        f"const BREIN_OVERLAP = {float(keten.laad_instellingen().get('brein', {}).get('overlap_drempel', 0.6))};",
        f"const CULTUUR_ORG = {J(cultuur_org)};",
        f"const DEPT_KAARTEN = {J(afd)};",
        f"const AFDELING_KAART_KPIS = {J(kpis)};",
        "const AGENTS = [\n" + ",\n".join("  " + J(a) for a in agents) + "\n];",
        f"const AGENT_PROMPTS = {J(prompts)};",
        f"const PROTOCOLS = {J(protocols)};",
        f"const SAMEN = {J(samen)};",
        f"const HR = {J(hr_data)};",
        "/* @@KAARTEN:END */",
    ]
    return "\n".join(regels)


def huisstijl() -> str:
    """De tokens uit het handboek (huisstijl.yaml) als CSS-variabelen. Het handboek is leidend."""
    hs = yaml.safe_load((BASIS / "kaarten" / "handboek" / "huisstijl.yaml").read_text(encoding="utf-8"))
    regels = [f"    --{n}: {v};" for n, v in hs["kleuren"].items()]
    regels += [f"    --{n}: {v};" for n, v in hs.get("vormen", {}).items()]
    regels += [f"    --{n}: {v};" for n, v in hs["typografie"].items() if n.startswith("font")]
    return "    /* @@HUISSTIJL:BEGIN – uit kaarten/handboek/huisstijl.yaml (scripts/bouw_kantoor.py) */\n" + "\n".join(regels) + "\n    /* @@HUISSTIJL:END */\n"


def main():
    pad = BASIS / "kantoor" / "index.html"
    html = pad.read_text(encoding="utf-8")
    stijl = re.compile(r"    /\* @@HUISSTIJL:BEGIN.*?@@HUISSTIJL:END \*/\n", re.S)
    if not stijl.search(html):
        sys.exit("Markeringen @@HUISSTIJL niet gevonden in kantoor/index.html")
    html = stijl.sub(lambda m: huisstijl(), html)
    nieuw = blok(Organisatie())
    patroon = re.compile(r"/\* @@KAARTEN:BEGIN.*?@@KAARTEN:END \*/", re.S)
    if not patroon.search(html):
        sys.exit("Markeringen @@KAARTEN niet gevonden in kantoor/index.html")
    html = patroon.sub(lambda m: nieuw, html)
    pad.write_text(html, encoding="utf-8")
    print(f"kantoor/index.html bijgewerkt ({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()
