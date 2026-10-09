"""Kaartenlader: laadt de kaarten, stelt per agent de instructies samen en berekent de effectieve toegang.

Volgorde van de instructies (whitepaper, sectie Cultuur- en profielkaarten):
harde grenzen -> cultuur organisatie -> cultuur afdeling -> profielkaart -> rol en toegang -> taakcontract.
Bij waarden wint het hogere niveau, bij werkwijze het lagere. Toegang is de doorsnede van alle lagen.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field

import yaml

from . import BASIS
from .validatie import valideer


class KaartFout(Exception):
    """De kaarten zijn ongeldig; het platform start niet met ongeldige kaarten."""


RECHT = {"r": "alleen lezen", "rw": "lezen en schrijven"}


@dataclass
class Toegang:
    """Effectieve toegang van één agent. `bronnen` = naam -> 'r' of 'rw'."""
    bronnen: dict[str, str]
    regels: list[str] = field(default_factory=list)  # inperkingen die geen bron raken, als tekstregel
    agent: str | None = None
    dossiers: frozenset = frozenset()                  # agents van wie deze agent het HR-dossier mag zien

    def mag_dossier(self, agent_id: str) -> bool:
        return agent_id in self.dossiers

    def mag(self, bron: str, modus: str = "r") -> bool:
        recht = self.bronnen.get(bron)
        return recht == "rw" if modus == "rw" else recht in ("r", "rw")


class Organisatie:
    """Alle kaarten van Tet Tet, gevalideerd en doorzoekbaar."""

    def __init__(self, map_kaarten: pathlib.Path | None = None, map_config: pathlib.Path | None = None):
        self.map_kaarten = map_kaarten or BASIS / "kaarten"
        kaarten, fouten = valideer(self.map_kaarten)
        if fouten:
            raise KaartFout("Ongeldige kaarten:\n" + "\n".join(fouten))
        self.kaarten = kaarten
        per = lambda t: {k: v for k, v in kaarten.items() if v["type"] == t}
        self.organisatie = next(iter(per("cultuurkaart_organisatie").values()))
        self.afdelingen = {v["afdeling"]: v for v in per("cultuurkaart_afdeling").values()}
        self.agents = per("profielkaart")
        self.rollen = per("rolkaart")
        self.toegang = per("toegangskaart_afdeling")
        self.beleid = yaml.safe_load(((map_config or BASIS / "config") / "beleid.yaml").read_text(encoding="utf-8"))

    # ---------- opzoeken ----------
    def agent(self, agent_id: str) -> dict:
        if agent_id not in self.agents:
            raise KeyError(f"Onbekende agent: {agent_id}")
        return self.agents[agent_id]

    @staticmethod
    def ingezet(a: dict) -> bool:
        """Een agent met `inzet: gepland` heeft een kaart maar werkt nog niet mee (de Raad activeert hem na een meting)."""
        return a.get("inzet", "actief") == "actief"

    def actieve_agents(self) -> list[dict]:
        return [a for a in self.agents.values() if self.ingezet(a)]

    def team(self, afdeling: str, ook_gepland: bool = False) -> list[dict]:
        return [a for a in self.agents.values() if a["afdeling"] == afdeling and (ook_gepland or self.ingezet(a))]

    def hoofdtet(self, afdeling: str) -> dict:
        return next(a for a in self.team(afdeling) if a["rol"] == "hoofdtet")

    def tets(self, afdeling: str) -> list[dict]:
        return [a for a in self.team(afdeling) if a["rol"] == "tet"]

    def control_tets(self) -> list[dict]:
        return [a for a in self.actieve_agents() if a["rol"] == "controltet"]

    def kaartversies(self, agent_id: str) -> dict[str, str]:
        """Alle kaarten (met versie) die het gedrag van deze agent bepalen; gaat mee in elk grootboek-event."""
        a = self.agent(agent_id)
        ids = [*a["erft_van"], a["id"], a["rolkaart"], a["mandaat"]["toegangskaart"]]
        versies = {i: self.kaarten[i]["versie"] for i in ids if i in self.kaarten}
        versies[self.beleid["id"]] = self.beleid["versie"]
        return versies

    # ---------- toegang ----------
    def effectieve_toegang(self, agent_id: str) -> Toegang:
        """Doorsnede van toegangskaart en profielmandaat. Het mandaat kan alleen inperken."""
        a = self.agent(agent_id)
        tk = self.toegang[a["mandaat"]["toegangskaart"]]
        bronnen = {**tk.get("intern", {}), **tk.get("connectors", {})}
        regels = []
        for inperking in a["mandaat"]["inperkingen"]:
            m = re.match(r"^([a-z_]+):\s*(.+)$", inperking)
            if not m or m.group(1) not in bronnen:
                regels.append(inperking)
                continue
            bron, wat = m.group(1), m.group(2).lower()
            if "geen toegang" in wat:
                bronnen.pop(bron)
            elif "alleen lezen" in wat or "geen schrijfrecht" in wat:
                bronnen[bron] = "r"
            else:
                regels.append(inperking)
        if self.rollen[a["rolkaart"]].get("toegangsmodus") == "alleen_lezen":
            bronnen = {b: "r" for b in bronnen}
        # Spelregels van de afdeling alleen tonen voor bronnen die de agent echt heeft.
        spel = [r for r in tk.get("spelregels", []) if (m := re.match(r"^([a-z_]+):", r)) is None or m.group(1) in bronnen]
        return Toegang(bronnen=bronnen, regels=regels + spel, agent=agent_id, dossiers=frozenset(self.dossier_inzage(agent_id)))

    def dossier_inzage(self, kijker: str) -> list[str]:
        """Van welke agents `kijker` het HR-dossier mag zien (config/beleid.yaml, `hr_dossier`)."""
        regel = self.beleid.get("hr_dossier") or {"eigen": True}
        k = self.agent(kijker)
        if k["afdeling"] in (regel.get("afdelingen") or []) or k["rol"] in (regel.get("rollen") or []):
            return sorted(self.agents)
        uit = [kijker] if regel.get("eigen", True) else []
        if regel.get("leidinggevende", True):
            uit += [a["id"] for a in self.agents.values() if a["rapporteert_aan"] == kijker]
        return sorted(set(uit))

    def mag_handeling(self, agent_id: str, handeling: str) -> bool:
        """Of de rol van deze agent een handeling mag (rolkaart: 'mag' en niet in 'mag_niet')."""
        rol = self.rollen[self.agent(agent_id)["rolkaart"]]
        return handeling in rol["mag"] and handeling not in rol["mag_niet"]

    # ---------- instructies ----------
    def systeemprompt(self, agent_id: str) -> str:
        """Laag 1 t/m 5 als één systeemprompt. Het taakcontract komt los in het bericht (laag 6)."""
        a = self.agent(agent_id)
        org, b = self.organisatie, self.beleid
        afd = self.afdelingen.get(a["afdeling"])
        rol = self.rollen[a["rolkaart"]]
        t = self.effectieve_toegang(agent_id)
        L = lijst
        delen = [
            f"# Instructies voor {a['naam']}",
            "Je bent een agent in Tet Tet, een organisatie van AI-agents die centraal wordt aangestuurd door de Oppertet "
            "en uiteindelijk door de Raad (de mens). De lagen hieronder gelden in deze volgorde. Bij waarden wint een "
            "hogere laag, bij werkwijze een lagere. Harde grenzen gaan altijd voor.",
            "## 1. Harde grenzen", L(b["harde_grenzen"]),
            "## 2. Cultuur van Tet Tet",
            f"Missie: {org['missie'].strip()}",
            "Kernwaarden:\n" + "\n".join(
                f"- **{w['naam']}**: {w['betekenis']} Wel: {', '.join(w.get('we_doen', []))}. Niet: {', '.join(w.get('we_doen_niet', []))}."
                for w in org["kernwaarden"]),
            "Principes:\n" + L(f"{p['principe']}: {p['toepassing'].strip()}" for p in org.get("edge_principes", [])),
            "Toon: " + f"{org['toon']['register']}, in het {'Nederlands' if org['toon']['taal'] == 'nl' else org['toon']['taal']}.",
            L(org["toon"].get("regels", [])),
            "Beslisprincipes:\n" + L(org["beslisprincipes"]),
            "Rode lijnen:\n" + L(org["rode_lijnen"]),
        ]
        if afd:
            delen += [
                f"## 3. Cultuur van {afd['naam']}",
                f"Missie: {afd['missie']}",
                "Verantwoordelijk voor:\n" + L(afd.get("verantwoordelijk_voor", [])),
                "Waarden:\n" + L(afd["waarden"]),
                "Werkwijze:\n" + L(afd["werkwijze"]),
                "Principes:\n" + L(f"{p['principe']}: {p['toepassing'].strip()}" for p in afd.get("edge_principes", [])),
                f"Kwaliteitsnorm: {afd.get('kwaliteitsnorm', '')}",
            ]
        p = a["persoonlijkheid"]
        delen += [
            "## 4. Jouw profiel",
            f"Je bent {a['naam']} (rol: {rol['naam']}, id: {a['id']}). Je rapporteert aan {self._naam(a['rapporteert_aan'])}.",
            f"Specialisme: {a['specialisme']}. Missie: {a['missie']}",
            "Verantwoordelijkheden:\n" + L(a["verantwoordelijkheden"]),
            "Expertise: " + ", ".join(a["expertise"]) + ".",
            f"Stijl: {p['stijl']}. Sterk in: {p['sterk_in']}. Let op je valkuilen: {'; '.join(p['valkuilen'])}.",
            f"Toon: {a['toon'].strip().rstrip('.')}.",
            "Werkstijl:\n" + L(f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in a["werkstijl"].items()),
        ]
        # Vrije kenmerken (uitbreidbaar zonder schema- of codewijziging) gaan als eigen kopjes mee.
        for sleutel, waarde in (a.get("kenmerken") or {}).items():
            kop = sleutel.replace("_", " ").capitalize()
            if isinstance(waarde, list):
                delen.append(f"{kop}:\n" + L(waarde))
            elif isinstance(waarde, dict):
                delen.append(f"{kop}:\n" + L(f"{k}: {v}" for k, v in waarde.items()))
            else:
                delen.append(f"{kop}: {waarde}")
        opdracht = a.get("opdracht") or {}
        if opdracht.get("doelstelling"):
            delen.append("Huidige opdracht:\n" + L([f"Doelstelling: {opdracht['doelstelling']}",
                                                    *[f"Deliverable: {d}" for d in opdracht.get("deliverables", [])],
                                                    f"Deadline: {opdracht.get('deadline') or 'geen'}"]))
        delen += [
            "## 5. Wat je mag",
            f"Bereik: {rol['bereik'].replace('_', ' ')}. Autonomieniveau: {a['autonomieniveau']}.",
            "Handelingen die je mag:\n" + L(rol["mag"]),
            "Handelingen die je niet mag:\n" + L(rol["mag_niet"]),
            "Toegang:\n" + (L(f"{bron}: {RECHT[r]}" for bron, r in sorted(t.bronnen.items())) or "- geen"),
        ]
        if t.regels:
            delen.append("Extra regels bij je toegang:\n" + L(t.regels))
        delen.append("Wat niet in je toegang staat, mag je niet. Twijfel je over je mandaat: escaleer, gok niet.")
        return "\n\n".join(d for d in delen if d)

    def _naam(self, agent_id: str) -> str:
        return "de Raad" if agent_id == "raad" else self.agents[agent_id]["naam"] if agent_id in self.agents else agent_id


def lijst(items) -> str:
    return "\n".join(f"- {i}" for i in items)
