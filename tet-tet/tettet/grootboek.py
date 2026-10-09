"""Grootboek: onveranderlijk logboek van alle events, besluiten en kosten.

Elk event bevat de hash van het vorige event. Wie een regel achteraf wijzigt of verwijdert,
breekt de keten; `controleer()` vindt dat.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time


def _hash(event: dict) -> str:
    body = {k: v for k, v in event.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Grootboek:
    def __init__(self, pad: pathlib.Path | None = None):
        """Zonder pad blijft het grootboek in het geheugen (tests en demo's)."""
        self.pad = pad
        self.events: list[dict] = []
        if pad and pad.exists():
            self.events = [json.loads(r) for r in pad.read_text(encoding="utf-8").splitlines() if r.strip()]

    def schrijf(self, type: str, agent: str, data: dict | None = None, *, taak: str | None = None,
                kaartversies: dict | None = None, kosten_eur: float = 0.0) -> dict:
        event = {
            "seq": len(self.events) + 1,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "type": type,
            "agent": agent,
            "taak": taak,
            "data": data or {},
            "kaartversies": kaartversies or {},
            "kosten_eur": round(kosten_eur, 6),
            "vorige_hash": self.events[-1]["hash"] if self.events else None,
        }
        event["hash"] = _hash(event)
        self.events.append(event)
        if self.pad:
            self.pad.parent.mkdir(parents=True, exist_ok=True)
            with self.pad.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def controleer(self) -> list[str]:
        """Lege lijst = de keten is intact."""
        fouten, vorige = [], None
        for e in self.events:
            if e.get("vorige_hash") != vorige:
                fouten.append(f"event {e.get('seq')}: verwijzing naar vorig event klopt niet")
            if _hash(e) != e.get("hash"):
                fouten.append(f"event {e.get('seq')}: inhoud is gewijzigd")
            vorige = e.get("hash")
        return fouten

    def zoek(self, *, type: str | None = None, agent: str | None = None, taak: str | None = None) -> list[dict]:
        return [e for e in self.events
                if (type is None or e["type"] == type) and (agent is None or e["agent"] == agent)
                and (taak is None or e["taak"] == taak)]

    def kosten(self, *, agent: str | None = None, taak: str | None = None) -> float:
        return round(sum(e["kosten_eur"] for e in self.zoek(agent=agent, taak=taak)), 6)
