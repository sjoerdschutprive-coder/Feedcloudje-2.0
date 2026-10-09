"""Agent-runtime: modelclients (mock en Anthropic) en de Agent die instructies, kosten en grootboek koppelt."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import yaml

from . import BASIS
from .grootboek import Grootboek
from .kaarten import Organisatie


def laad_instellingen(pad=None) -> dict:
    return yaml.safe_load(((pad or BASIS / "config" / "instellingen.yaml")).read_text(encoding="utf-8"))


@dataclass
class Antwoord:
    tekst: str
    tokens_in: int
    tokens_uit: int


class AnthropicClient:
    """Echte agents via de Anthropic API. De SDK wordt pas geladen als deze client gebruikt wordt."""

    def __init__(self, model: str, max_tokens: int):
        try:
            import anthropic  # noqa: PLC0415
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("Installeer de SDK: pip install anthropic") from e
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("Zet ANTHROPIC_API_KEY in de omgeving, of draai met --mock.")
        self.client = anthropic.Anthropic()
        self.model, self.max_tokens = model, max_tokens

    def genereer(self, rol: str, systeem: str, bericht: str) -> Antwoord:
        r = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens,
            # De systeemprompt (kaarten) is per agent stabiel; caching scheelt kosten bij herhaalde taken.
            system=[{"type": "text", "text": systeem, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": bericht}],
        )
        tekst = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        return Antwoord(tekst, r.usage.input_tokens, r.usage.output_tokens)


class MockClient:
    """Deterministische agents zonder API-aanroepen, voor tests en demo's.

    `afkeuren`: hoe vaak een Control Tet een taak eerst afkeurt (taak-id -> aantal, of '*' voor alle taken).
    """

    def __init__(self, afkeuren: dict[str, int] | None = None):
        self.afkeuren = dict(afkeuren or {})
        self.aanroepen: list[tuple[str, str]] = []

    def genereer(self, rol: str, systeem: str, bericht: str) -> Antwoord:
        self.aanroepen.append((rol, bericht))
        tekst = getattr(self, f"_{rol}")(bericht)
        return Antwoord(tekst, max(1, (len(systeem) + len(bericht)) // 4), max(1, len(tekst) // 4))

    def _oppertet(self, b: str) -> str:
        naam = _veld(b, "Naam") or "de doelstelling"
        afd = re.findall(r"^- ([a-z]+) \((.+?)\):", b, re.M)
        return json.dumps({"afdelingsdoelen": [
            {"afdeling": a, "doel": f"Bijdrage van {n} aan: {naam}",
             "hoofdlijnen": [f"Analyse {n}", f"Advies {n}"], "waarom": f"{n} levert de eigen expertise."} for a, n in afd]},
            ensure_ascii=False)

    def _hoofdtet(self, b: str) -> str:
        tets = re.findall(r"^- ([a-z]+-\d) \(", b, re.M)
        hl = re.findall(r"^- Hoofdlijn: (.+)$", b, re.M)
        return json.dumps({"taken": [
            {"opdracht": h, "acceptatiecriteria": [f"{h} beantwoordt de doelstelling", "Aannames en bronnen benoemd"],
             "toegewezen": tets[i % len(tets)] if tets else None, "budget_eur": 2.0, "toets": "kwaliteit"}
            for i, h in enumerate(hl)]}, ensure_ascii=False)

    def _tet(self, b: str) -> str:
        opdracht = _veld(b, "Opdracht") or "de taak"
        criteria = re.findall(r"^- (.+)$", b.split("Acceptatiecriteria:")[1].split("Budget:")[0], re.M) if "Acceptatiecriteria:" in b else []
        return "\n".join([
            "## Resultaat", f"Uitwerking van '{opdracht}' (mockmodus, geen echte analyse).",
            "## Zelfcheck", *[f"- {c}: voldaan" for c in criteria],
            "## Zekerheid", "middel", "## Les", f"Bij '{opdracht}' eerst de acceptatiecriteria naast elkaar leggen."])

    def _controltet(self, b: str) -> str:
        taak = (re.search(r"# Taakcontract (\S+)", b) or [None, ""])[1]
        sleutel = taak if taak in self.afkeuren else "*" if "*" in self.afkeuren else None
        if sleutel and self.afkeuren[sleutel] > 0:
            self.afkeuren[sleutel] -= 1
            return json.dumps({"oordeel": "afgekeurd", "score": 5,
                               "bevindingen": ["Onderbouwing ontbreekt bij de kernclaim: voeg bron of berekening toe."]})
        return json.dumps({"oordeel": "goedgekeurd", "score": 8, "bevindingen": []})


def _veld(tekst: str, naam: str) -> str | None:
    m = re.search(rf"^{naam}: (.+)$", tekst, re.M)
    return m.group(1).strip() if m else None


def lees_json(tekst: str) -> dict:
    """Haalt het eerste JSON-object uit een modelantwoord (ook als het in een codeblok staat)."""
    m = re.search(r"\{.*\}", tekst, re.S)
    if not m:
        raise ValueError("Geen JSON in het antwoord")
    return json.loads(m.group(0))


def maak_client(instellingen: dict, mock: bool | None = None, **mock_opties):
    m = instellingen["model"]
    if mock or (mock is None and m["aanbieder"] == "mock"):
        return MockClient(**mock_opties)
    return AnthropicClient(m["naam"], m["max_tokens"])


class Agent:
    """Eén agent: systeemprompt uit de kaarten, aanroep via de client, kosten en kaartversies in het grootboek."""

    def __init__(self, org: Organisatie, agent_id: str, client, grootboek: Grootboek, instellingen: dict):
        self.org, self.id, self.client, self.gb, self.inst = org, agent_id, client, grootboek, instellingen
        self.kaart = org.agent(agent_id)
        self.systeem = org.systeemprompt(agent_id)

    def vraag(self, bericht: str, *, taak: str | None = None, doel: str = "") -> str:
        a = self.client.genereer(self.kaart["rol"], self.systeem, bericht)
        m = self.inst["model"]
        kosten = a.tokens_in / 1e6 * m["prijs_per_mtok_in_eur"] + a.tokens_uit / 1e6 * m["prijs_per_mtok_uit_eur"]
        self.gb.schrijf("model.aanroep", self.id, {"doel": doel, "tokens_in": a.tokens_in, "tokens_uit": a.tokens_uit},
                        taak=taak, kaartversies=self.org.kaartversies(self.id), kosten_eur=kosten)
        return a.tekst
