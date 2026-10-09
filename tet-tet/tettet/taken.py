"""Taakcontract en takenmarkt.

Levenscyclus: gepubliceerd -> geclaimd -> in_uitvoering -> ter_evaluatie -> afgerond,
of bij afkeuring terug naar in_uitvoering. Na `max_afkeuringen` escaleert de taak naar de Hoofdtet.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .grootboek import Grootboek

OVERGANGEN = {
    "gepubliceerd": {"geclaimd"},
    "geclaimd": {"in_uitvoering"},
    "in_uitvoering": {"ter_evaluatie", "geëscaleerd"},
    "ter_evaluatie": {"afgerond", "in_uitvoering", "geëscaleerd"},
    "geëscaleerd": {"gepubliceerd"},
    "afgerond": set(),
}


@dataclass
class Taak:
    id: str
    doel_id: str
    opdracht: str
    acceptatiecriteria: list[str]
    eigenaar: str            # afdeling die verantwoordelijk is
    budget_eur: float
    deadline: str | None = None
    toegewezen: str | None = None   # agent-id van de Tet
    control_tet: str | None = None  # agent-id van de beoordelaar, of 'raad'
    status: str = "gepubliceerd"
    afkeuringen: int = 0
    resultaat: str | None = None
    bevindingen: list[str] = field(default_factory=list)

    def contract(self) -> str:
        """Laag 6 van de instructies: het taakcontract als bericht aan de agent."""
        regels = [f"# Taakcontract {self.id}", f"Opdracht: {self.opdracht}", "Acceptatiecriteria:",
                  *[f"- {c}" for c in self.acceptatiecriteria],
                  f"Budget: {self.budget_eur:.2f} euro", f"Deadline: {self.deadline or 'geen'}",
                  f"Wordt beoordeeld door: {self.control_tet or 'nog niet bepaald'}"]
        return "\n".join(regels)


class OngeldigeOvergang(Exception):
    pass


class Takenmarkt:
    def __init__(self, grootboek: Grootboek, max_afkeuringen: int = 2):
        self.gb = grootboek
        self.max_afkeuringen = max_afkeuringen
        self.taken: dict[str, Taak] = {}

    def publiceer(self, taak: Taak, door: str) -> Taak:
        self.taken[taak.id] = taak
        self.gb.schrijf("taak.gepubliceerd", door, asdict(taak), taak=taak.id)
        return taak

    def _naar(self, taak: Taak, status: str, door: str, data: dict | None = None):
        if status not in OVERGANGEN[taak.status]:
            raise OngeldigeOvergang(f"{taak.id}: {taak.status} -> {status} kan niet")
        oud, taak.status = taak.status, status
        self.gb.schrijf(f"taak.{status}", door, {"van": oud, **(data or {})}, taak=taak.id)

    def claim(self, taak: Taak, agent_id: str):
        taak.toegewezen = agent_id
        self._naar(taak, "geclaimd", agent_id)

    def start(self, taak: Taak, agent_id: str):
        self._naar(taak, "in_uitvoering", agent_id)

    def lever_op(self, taak: Taak, agent_id: str, resultaat: str):
        taak.resultaat = resultaat
        self._naar(taak, "ter_evaluatie", agent_id, {"lengte": len(resultaat)})

    def beoordeel(self, taak: Taak, beoordelaar: str, goedgekeurd: bool, bevindingen: list[str], score=None) -> str:
        """Geeft de nieuwe status terug: afgerond, in_uitvoering (opnieuw) of geëscaleerd."""
        taak.bevindingen = bevindingen
        data = {"goedgekeurd": goedgekeurd, "bevindingen": bevindingen, "score": score}
        self.gb.schrijf("taak.beoordeeld", beoordelaar, data, taak=taak.id)
        if goedgekeurd:
            self._naar(taak, "afgerond", beoordelaar)
        else:
            taak.afkeuringen += 1
            if taak.afkeuringen >= self.max_afkeuringen:
                self._naar(taak, "geëscaleerd", beoordelaar, {"afkeuringen": taak.afkeuringen})
            else:
                self._naar(taak, "in_uitvoering", beoordelaar, {"afkeuringen": taak.afkeuringen})
        return taak.status

    def per_status(self) -> dict[str, int]:
        uit: dict[str, int] = {}
        for t in self.taken.values():
            uit[t.status] = uit.get(t.status, 0) + 1
        return uit
