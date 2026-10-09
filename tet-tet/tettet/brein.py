"""Het Brein: gedeeld geheugen met lessen, besluiten en notities.

Na elke afgeronde taak schrijft de agent één les (cultuurprincipe 'Leren na elke taak').
Na een afkeuring of escalatie volgt automatisch een les of incident met de bevindingen van de Control Tet
('bijna-fouten tellen mee'); die heeft zekerheid laag zolang de Hoofdtet de afkeuring niet heeft bevestigd.
Voor de start van een taak leest een agent de lessen van zijn afdeling en de organisatie.

Lessen worden niet dubbel opgeslagen: lijkt een nieuwe les op een bestaande (woordoverlap, Jaccard),
dan telt het veld `bevestigd` van de bestaande les op en wordt de nieuwe tekst als variant bewaard.
De selectie kiest op afdeling, dan op `bevestigd`, dan op recentheid.

Collectief Brein (zie tettet/samenwerking.py): items dragen `labels` (de bronnen waarop ze steunen). Wie die bronnen
niet mag zien, krijgt het item niet; lessen worden alleen samengevoegd met lessen op dezelfde bronnen.
Naast lessen bevat het Brein vragen (vraagbaak) en signalen voor andere afdelingen.
"""
from __future__ import annotations

import json
import pathlib
import re
import time

SOORTEN = {"les", "besluit", "notitie", "incident", "vraag", "signaal", "patroon"}
LES_SOORTEN = ("les", "incident")
DREMPEL = 0.6          # standaard; de waarde in config/instellingen.yaml (brein.overlap_drempel) gaat voor
MAX_VARIANTEN = 10


def woorden(tekst: str) -> set[str]:
    return set(re.findall(r"\w{3,}", str(tekst or "").lower()))


def overlap(a: str, b: str) -> float:
    """Jaccard-overlap van de woorden (3+ tekens) van twee teksten."""
    wa, wb = woorden(a), woorden(b)
    return len(wa & wb) / len(wa | wb) if wa | wb else 0.0


def zoek_dubbel(items: list[dict], tekst: str, soort: str, drempel: float = DREMPEL) -> dict | None:
    """De bestaande les van dezelfde soort met de grootste overlap boven de drempel, of None."""
    beste, score = None, drempel
    for i in items:
        if (i.get("soort") or "les") != soort:
            continue
        o = overlap(i.get("tekst", ""), tekst)
        if o >= score:
            beste, score = i, o
    return beste


def bevestig(item: dict, tekst: str, afdeling: str | None, afdeling_veld: str = "afdeling") -> dict:
    """Telt een dubbele les bij de bestaande op; de originele tekst blijft bewaard als variant (terug te draaien)."""
    item["bevestigd"] = int(item.get("bevestigd") or 1) + 1
    item["varianten"] = (list(item.get("varianten") or []) + [tekst.strip()[:500]])[-MAX_VARIANTEN:]
    if afdeling and afdeling != item.get(afdeling_veld) and afdeling not in (item.get("ook") or []):
        item["ook"] = list(item.get("ook") or []) + [afdeling]
    return item


def hoort_bij(item: dict, afdeling: str, afdeling_veld: str = "afdeling") -> bool:
    return item.get(afdeling_veld) == afdeling or afdeling in (item.get("ook") or [])


def rangorde(items: list[dict]) -> list[dict]:
    """Eerst vaker bevestigd, daarna recenter (lijst staat in volgorde van schrijven)."""
    genummerd = list(enumerate(items))
    genummerd.sort(key=lambda x: (int(x[1].get("bevestigd") or 1), x[1].get("ts") or 0, x[0]), reverse=True)
    return [i for _, i in genummerd]


def als_regel(item: dict) -> str:
    extra = []
    if int(item.get("bevestigd") or 1) > 1:
        extra.append(f"{item['bevestigd']}x bevestigd")
    if item.get("zekerheid") == "laag":
        extra.append("zekerheid laag")
    return item.get("tekst", "") + (f" ({', '.join(extra)})" if extra else "")


class Brein:
    def __init__(self, pad: pathlib.Path | None = None, drempel: float = DREMPEL):
        self.pad = pad
        self.drempel = drempel
        self.items: list[dict] = []
        if pad and pad.exists():
            self.items = json.loads(pad.read_text(encoding="utf-8"))

    def schrijf(self, soort: str, agent: str, afdeling: str, tekst: str, *, taak: str | None = None,
                bron: str | None = None, zekerheid: str | None = None, labels: list[str] | None = None, **extra) -> dict:
        if soort not in SOORTEN:
            raise ValueError(f"Onbekende soort: {soort}")
        if soort in LES_SOORTEN:
            zelfde = [i for i in self.items if sorted(i.get("labels") or []) == sorted(labels or [])]
            dubbel = zoek_dubbel(zelfde, tekst, soort, self.drempel)
            if dubbel:
                bevestig(dubbel, tekst, afdeling)
                self._bewaar()
                return dubbel
        item = {"id": f"b{len(self.items) + 1}", "soort": soort, "agent": agent, "afdeling": afdeling,
                "tekst": tekst.strip(), "taak": taak, "bron": bron, "zekerheid": zekerheid, "labels": sorted(labels or []), "bevestigd": 1, **extra,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        self.items.append(item)
        self._bewaar()
        return item

    def lessen_voor(self, afdeling: str, max_aantal: int = 5, toegang=None) -> list[dict]:
        """Lessen (en incidenten) van de eigen afdeling, aangevuld met lessen van de organisatie.

        Met `toegang` (effectieve toegang van de lezer) alleen lessen die hij mag zien.
        Binnen elke groep: eerst vaker bevestigd, daarna recenter."""
        from .samenwerking import zichtbaar
        lessen = [i for i in self.items if i["soort"] in LES_SOORTEN and (toegang is None or zichtbaar(i, toegang))]
        eigen = [i for i in lessen if hoort_bij(i, afdeling)]
        rest = [i for i in lessen if i["afdeling"] in ("centraal", "risk") and i not in eigen]
        return (rangorde(eigen) + rangorde(rest))[:max_aantal]

    def _bewaar(self):
        if self.pad:
            self.pad.parent.mkdir(parents=True, exist_ok=True)
            self.pad.write_text(json.dumps(self.items, ensure_ascii=False, indent=1), encoding="utf-8")
