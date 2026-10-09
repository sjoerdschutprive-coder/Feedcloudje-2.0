"""Validatie van alle Tet Tet-kaarten: schema, verwijzingen, overerving en mandaat."""
import fnmatch
import json
import pathlib
import re

import yaml
from jsonschema import Draft202012Validator

KAARTEN = pathlib.Path(__file__).resolve().parent.parent / "kaarten"


def laad(pad):
    data = yaml.safe_load(pad.read_text(encoding="utf-8"))
    return json.loads(json.dumps(data, default=str))  # datums als tekst


def valideer(map_kaarten=KAARTEN):
    """Geeft (kaarten per id, lijst met fouten) terug."""
    schema = json.loads((map_kaarten / "schema" / "kaarten.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    kaarten, fouten = {}, []

    for pad in sorted(map_kaarten.rglob("*.yaml")):
        kaart = laad(pad)
        naam = pad.relative_to(map_kaarten)
        for err in validator.iter_errors(kaart):
            fouten.append(f"{naam}: schema: {err.message[:160]}")
        if kaart["id"] in kaarten:
            fouten.append(f"{naam}: dubbel id {kaart['id']}")
        kaarten[kaart["id"]] = kaart

    per_type = lambda t: {k: v for k, v in kaarten.items() if v["type"] == t}
    org = per_type("cultuurkaart_organisatie")
    afd = per_type("cultuurkaart_afdeling")
    agents = per_type("profielkaart")
    rollen = per_type("rolkaart")
    toegang = per_type("toegangskaart_afdeling")
    waarde_ids = {w["id"] for o in org.values() for w in o["kernwaarden"]}

    for k in afd.values():
        if k["erft_van"] not in org:
            fouten.append(f"{k['id']}: erft_van {k['erft_van']} bestaat niet")
        for a in k.get("accent_op", []):
            if a not in waarde_ids:
                fouten.append(f"{k['id']}: accent_op '{a}' is geen kernwaarde van de organisatie")

    for k in agents.values():
        for e in k["erft_van"]:
            if e not in org and e not in afd:
                fouten.append(f"{k['id']}: erft_van {e} bestaat niet")
        if k["afdeling"] != "centraal" and f"cultuur-{k['afdeling']}" not in k["erft_van"]:
            fouten.append(f"{k['id']}: erft niet van de cultuurkaart van de eigen afdeling")
        if k["rapporteert_aan"] != "raad" and k["rapporteert_aan"] not in agents:
            fouten.append(f"{k['id']}: rapporteert_aan {k['rapporteert_aan']} bestaat niet")
        rol = rollen.get(k["rolkaart"])
        if not rol:
            fouten.append(f"{k['id']}: rolkaart {k['rolkaart']} bestaat niet")
        elif k["autonomieniveau"] > rol["max_autonomieniveau"]:
            fouten.append(f"{k['id']}: autonomieniveau hoger dan de rol toestaat")
        tk = k["mandaat"]["toegangskaart"]
        if tk not in toegang:
            fouten.append(f"{k['id']}: toegangskaart {tk} bestaat niet")
        elif toegang[tk]["afdeling"] != k["afdeling"]:
            fouten.append(f"{k['id']}: toegangskaart {tk} hoort bij een andere afdeling")
        else:
            # Inperkingen in de vorm 'bron: ...' mogen alleen rechten raken die de afdeling heeft.
            beschikbaar = set(toegang[tk]["connectors"]) | set(toegang[tk]["intern"])
            for inp in k["mandaat"]["inperkingen"]:
                m = re.match(r"^([a-z_]+):", inp)
                if m and m.group(1) not in beschikbaar:
                    fouten.append(f"{k['id']}: inperking '{inp}' gaat over iets wat de afdeling niet heeft")
        for veld, waarde in k.get("samenwerking", {}).items():
            for ref in waarde if isinstance(waarde, list) else [waarde]:
                if re.fullmatch(r"[a-z]+-(h|a|\d|c\d)", str(ref)) and ref not in agents:
                    fouten.append(f"{k['id']}: samenwerking.{veld} verwijst naar onbekende agent {ref}")

    for k in per_type("ijkset").values():
        if k["rol"] not in rollen:
            fouten.append(f"{k['id']}: rol {k['rol']} bestaat niet")
        ids = [x["id"] for x in k["taken"]]
        if len(ids) != len(set(ids)):
            fouten.append(f"{k['id']}: dubbele taak-id in de ijkset")
    onderdelen = sorted(k["onderdeel"] for k in per_type("handboek").values())
    if onderdelen and len(onderdelen) != len(set(onderdelen)):
        fouten.append("handboek: een onderdeel staat er meer dan eens in")

    fouten += valideer_lijn(agents, rollen, toegang)
    return kaarten, fouten


def _niveau(agents, rollen, agent_id):
    if agent_id == "raad":
        return 0
    rol = rollen.get(agents[agent_id]["rolkaart"]) if agent_id in agents else None
    return rol.get("niveau") if rol else None


def valideer_lijn(agents, rollen, toegang):
    """Hiërarchie: rangorde, geen cirkels, en de regels voor een assistent onder de top van de lijn.

    - Wie aan iemand rapporteert, staat lager in de lijn (hoger niveaugetal) dan die ander.
    - De rapportagelijn eindigt bij de Raad (geen cirkels).
    - Handelingen die een rolkaart 'voorbehouden' noemt, mag geen rol lager in de lijn hebben.
    - Hoogstens één assistent_oppertet; hij rapporteert aan een oppertet, en zijn toegang is een deelverzameling
      van die van de oppertet (zelfde of smallere toegangskaart, rechten nooit ruimer).
    """
    fouten = []
    for k in agents.values():
        mijn, baas = _niveau(agents, rollen, k["id"]), _niveau(agents, rollen, k["rapporteert_aan"])
        if mijn is not None and baas is not None and baas >= mijn:
            fouten.append(f"{k['id']}: rapporteert aan {k['rapporteert_aan']}, die niet hoger in de lijn staat")
        gezien, cur = set(), k["id"]
        while cur != "raad" and cur in agents:
            if cur in gezien:
                fouten.append(f"{k['id']}: cirkel in de rapportagelijn")
                break
            gezien.add(cur)
            cur = agents[cur]["rapporteert_aan"]
    for r in rollen.values():
        for ander in rollen.values():
            if ander.get("niveau", 0) > r.get("niveau", 0):
                for h in sorted(set(r.get("voorbehouden") or []) & set(ander["mag"])):
                    fouten.append(f"{ander['id']}: mag '{h}', maar dat is voorbehouden aan {r['naam']}")
    assistenten = [k for k in agents.values() if k["rol"] == "assistent_oppertet"]
    if len(assistenten) > 1:
        fouten.append("meer dan één assistent_oppertet: " + ", ".join(k["id"] for k in assistenten))
    for k in assistenten:
        baas = agents.get(k["rapporteert_aan"])
        if not baas or baas["rol"] != "oppertet":
            fouten.append(f"{k['id']}: een assistent_oppertet rapporteert aan de oppertet")
            continue
        eigen, top = toegang.get(k["mandaat"]["toegangskaart"]), toegang.get(baas["mandaat"]["toegangskaart"])
        if eigen and top:
            ruim = {**top.get("intern", {}), **top.get("connectors", {})}
            for bron, recht in {**eigen.get("intern", {}), **eigen.get("connectors", {})}.items():
                if bron not in ruim or (recht == "rw" and ruim[bron] != "rw"):
                    fouten.append(f"{k['id']}: toegang tot {bron} ({recht}) gaat verder dan die van {baas['id']}")
    return fouten



def controleer_mappen(map_kaarten=KAARTEN, basis: pathlib.Path | None = None) -> list[str]:
    """Waarschuwingen (geen fouten) voor bestanden op een plek die niet in het handboek (mappenstructuur) staat."""
    basis = basis or map_kaarten.parent
    pad = map_kaarten / "handboek" / "mappenstructuur.yaml"
    if not pad.exists():
        return []
    ms = laad(pad)
    mappen = {m["pad"].strip("/"): m["patronen"] for m in ms["mappen"]}
    negeren = ms.get("negeren", [])
    uit = []
    for f in sorted(basis.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(basis)
        if any(fnmatch.fnmatch(deel, n) for deel in rel.parts for n in negeren):
            continue
        map_ = str(rel.parent).replace("\\", "/")
        patronen = mappen.get(map_)
        if patronen is None:
            uit.append(f"{rel}: map '{map_}' staat niet in het handboek (mappenstructuur)")
        elif not any(fnmatch.fnmatch(rel.name, p) for p in patronen):
            uit.append(f"{rel}: bestandssoort hoort niet in '{map_}' volgens het handboek")
    return uit
