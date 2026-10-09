"""Het Brein: gedeeld geheugen met lessen, besluiten en notities.

Na elke afgeronde taak schrijft de agent één les (cultuurprincipe 'Leren na elke taak').
Voor de start van een taak leest een agent de lessen van zijn afdeling en de organisatie.
"""
from __future__ import annotations

import json
import pathlib
import time

SOORTEN = {"les", "besluit", "notitie"}


class Brein:
    def __init__(self, pad: pathlib.Path | None = None):
        self.pad = pad
        self.items: list[dict] = []
        if pad and pad.exists():
            self.items = json.loads(pad.read_text(encoding="utf-8"))

    def schrijf(self, soort: str, agent: str, afdeling: str, tekst: str, *, taak: str | None = None,
                bron: str | None = None, zekerheid: str | None = None) -> dict:
        if soort not in SOORTEN:
            raise ValueError(f"Onbekende soort: {soort}")
        item = {"id": f"b{len(self.items) + 1}", "soort": soort, "agent": agent, "afdeling": afdeling,
                "tekst": tekst.strip(), "taak": taak, "bron": bron, "zekerheid": zekerheid,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        self.items.append(item)
        self._bewaar()
        return item

    def lessen_voor(self, afdeling: str, max_aantal: int = 5) -> list[dict]:
        """Recentste lessen van de eigen afdeling, aangevuld met lessen van de organisatie."""
        eigen = [i for i in self.items if i["soort"] == "les" and i["afdeling"] == afdeling]
        rest = [i for i in self.items if i["soort"] == "les" and i["afdeling"] in ("centraal", "risk") and i not in eigen]
        return (eigen[::-1] + rest[::-1])[:max_aantal]

    def _bewaar(self):
        if self.pad:
            self.pad.parent.mkdir(parents=True, exist_ok=True)
            self.pad.write_text(json.dumps(self.items, ensure_ascii=False, indent=1), encoding="utf-8")
