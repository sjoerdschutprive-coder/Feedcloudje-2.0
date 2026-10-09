"""Validatie van alle Tet Tet-kaarten: schema, verwijzingen, overerving en mandaat."""
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
                if re.fullmatch(r"[a-z]+-(h|\d|c\d)", str(ref)) and ref not in agents:
                    fouten.append(f"{k['id']}: samenwerking.{veld} verwijst naar onbekende agent {ref}")

    return kaarten, fouten
