"""Beleidsmotor, tool-gateway en budgetbewaking.

Elke handeling en elk gebruik van een bron gaat langs de beleidsmotor:
verboden -> geweigerd; vraagt akkoord -> goedkeuringsinbox; anders rolkaart en effectieve toegang.
"""
from __future__ import annotations

from dataclasses import dataclass

from .grootboek import Grootboek
from .kaarten import Organisatie


class Geweigerd(Exception):
    """De handeling valt buiten rol, toegang of beleid."""


class BudgetOverschreden(Exception):
    """Een taak of agent gaat over het toegewezen budget; de uitvoering stopt."""


@dataclass
class Besluit:
    uitkomst: str  # toegestaan | geweigerd | goedkeuring_nodig
    reden: str

    @property
    def toegestaan(self) -> bool:
        return self.uitkomst == "toegestaan"


class Beleidsmotor:
    def __init__(self, org: Organisatie, grootboek: Grootboek):
        self.org, self.gb = org, grootboek
        self.inbox: list[dict] = []  # goedkeuringsinbox van de Raad

    def toets_handeling(self, agent_id: str, handeling: str, context: str = "") -> Besluit:
        b = self.org.beleid
        if handeling in b.get("verboden", []):
            besluit = Besluit("geweigerd", "verboden volgens de harde grenzen")
        elif handeling in b.get("goedkeuring_raad", []):
            besluit = Besluit("goedkeuring_nodig", "vraagt altijd akkoord van de Raad")
            self.inbox.append({"agent": agent_id, "handeling": handeling, "context": context, "status": "open"})
        elif self.org.mag_handeling(agent_id, handeling):
            besluit = Besluit("toegestaan", "binnen rolkaart")
        else:
            besluit = Besluit("geweigerd", "niet toegestaan door de rolkaart")
        self._log(agent_id, "handeling", handeling, besluit, context)
        return besluit

    def gebruik_bron(self, agent_id: str, bron: str, modus: str = "r", context: str = "") -> None:
        """Tool-gateway: elke aanroep van een tool of databron gaat hierlangs. Gooit Geweigerd bij geen toegang."""
        t = self.org.effectieve_toegang(agent_id)
        ok = t.mag(bron, modus)
        besluit = Besluit("toegestaan" if ok else "geweigerd",
                          "binnen effectieve toegang" if ok else f"geen {'schrijf' if modus == 'rw' else 'lees'}recht op {bron}")
        self._log(agent_id, "bron", f"{bron}:{modus}", besluit, context)
        if not ok:
            raise Geweigerd(f"{agent_id}: {besluit.reden}")

    def eis(self, agent_id: str, handeling: str, context: str = "") -> None:
        besluit = self.toets_handeling(agent_id, handeling, context)
        if not besluit.toegestaan:
            raise Geweigerd(f"{agent_id} mag '{handeling}' niet: {besluit.reden}")

    def _log(self, agent_id, soort, wat, besluit: Besluit, context):
        type_ = "beleid.overtreding" if besluit.uitkomst == "geweigerd" else (
            "beleid.goedkeuring_gevraagd" if besluit.uitkomst == "goedkeuring_nodig" else "beleid.toegestaan")
        self.gb.schrijf(type_, agent_id, {"soort": soort, "wat": wat, "reden": besluit.reden, "context": context},
                        kaartversies=self.org.kaartversies(agent_id))


class Budget:
    """Houdt kosten per taak bij en stopt bij overschrijding van het taakbudget."""

    def __init__(self, grootboek: Grootboek):
        self.gb = grootboek

    def controleer(self, taak_id: str, budget_eur: float) -> None:
        """Na elke modelaanroep: stop de taak als de geboekte kosten boven het budget komen."""
        besteed = self.gb.kosten(taak=taak_id)
        if besteed > budget_eur:
            raise BudgetOverschreden(f"taak {taak_id}: {besteed:.4f} van {budget_eur:.2f} euro besteed")

    def resterend(self, taak_id: str, budget_eur: float) -> float:
        return round(budget_eur - self.gb.kosten(taak=taak_id), 6)
