"""Stijlcontrole: toetst een tekst aan het handboek (schrijfstijl.yaml en woordenlijst.yaml).

Deterministisch en signalerend, nooit blokkerend. Uitvoer: een score (0–100) en concrete suggesties per zin.
De Governance-Tet beheert de norm; de Eindredactie-Tet gebruikt de controle bij het toepassen van de stijl.
De score telt mee als dimensie 'stijl' in het prestatieprofiel (tettet/prestatie.py).
"""
from __future__ import annotations

import functools
import pathlib
import re

import yaml

from . import BASIS


@functools.lru_cache(maxsize=4)
def laad_norm(map_kaarten: str | None = None) -> dict:
    """Schrijfstijl en woordenlijst uit het handboek, samengevoegd."""
    hb = pathlib.Path(map_kaarten or BASIS / "kaarten") / "handboek"
    stijl = yaml.safe_load((hb / "schrijfstijl.yaml").read_text(encoding="utf-8"))
    woorden = yaml.safe_load((hb / "woordenlijst.yaml").read_text(encoding="utf-8"))
    return {"stijl": stijl, "woorden": woorden}


def kern(tekst: str) -> str:
    """Het blok '## Resultaat' als dat er is (het eindproduct zelf), anders de hele tekst."""
    m = re.search(r"^## Resultaat\s*\n(.+?)(?:\n## |\Z)", tekst or "", re.S | re.M)
    return m.group(1) if m else (tekst or "")


def zinnen(tekst: str) -> list[str]:
    regels = []
    for r in tekst.splitlines():
        r = re.sub(r"^\s*(#+|[-*•]|\d+[.)])\s*", "", r).strip()
        if r:
            regels.append(r)
    uit = []
    for r in regels:
        uit += [z.strip() for z in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý0-9€\"'(])", r) if z.strip()]
    return uit


def _bevat(zin: str, woord: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(woord.lower())}(?![\w-])", zin.lower()) is not None


def toets(tekst: str, norm: dict | None = None) -> dict:
    """Score 0–100 en suggesties per zin. Lege tekst: score None."""
    norm = norm or laad_norm()
    s, w = norm["stijl"], norm["woorden"]
    regels, weging = s["regels"], s.get("weging", {})
    heel = tekst or ""
    zz = zinnen(kern(heel))
    if not zz:
        return {"score": None, "zinnen": 0, "suggesties": []}
    heeft_bronnenblok = re.search(r"^## Bronnen", heel, re.M) is not None
    lijdend_hulp = s.get("lijdende_vorm", {}).get("hulpwerkwoorden", [])
    deelwoord = re.compile(s.get("lijdende_vorm", {}).get("deelwoord", r"\bge\w+[dt]\b"))
    bronpatronen = [re.compile(p, re.I) for p in s.get("bronpatronen", [])]
    engels = {k: v for k, v in (w.get("engels") or {}).items() if k not in set(w.get("engels_toegestaan") or [])}
    vervang = {**(w.get("nooit") or {}), **(w.get("voorkeur") or {})}
    sugg, straf = [], 0
    def plus(i, zin, soort, tekst_):
        nonlocal straf
        straf += int(weging.get(soort, 2))
        sugg.append({"zin": i, "tekst": zin[:140], "soort": soort, "suggestie": tekst_})
    for i, z in enumerate(zz, 1):
        n = len(re.findall(r"\w+", z))
        if n > regels["max_zinslengte"]:
            plus(i, z, "te_lang", f"Zin van {n} woorden; maak er twee zinnen van (max. {regels['max_zinslengte']}).")
        if regels.get("actief_schrijven", True) and any(_bevat(z, h) for h in lijdend_hulp) and deelwoord.search(z.lower()):
            plus(i, z, "lijdend", "Lijdende vorm: zeg wie het doet.")
        for o in w.get("opvulling") or []:
            if _bevat(z, o):
                plus(i, z, "opvulling", f"Schrap '{o}'.")
        for e, nl in engels.items():
            if _bevat(z, e):
                plus(i, z, "engels", f"Gebruik '{nl}' in plaats van '{e}'.")
        for oud, nieuw in vervang.items():
            if _bevat(z, oud):
                plus(i, z, "opvulling", f"Schrijf '{nieuw}' in plaats van '{oud}'.")
        if regels.get("bron_bij_getal", True) and not heeft_bronnenblok and re.search(r"\d", z) \
                and not any(p.search(z) for p in bronpatronen):
            plus(i, z, "geen_bron", "Getal zonder bron: noem de bron of zet hem onder '## Bronnen'.")
    if regels.get("conclusie_eerst", True):
        eerste = zz[0].lower()
        if any(eerste.startswith(a) for a in s.get("aanloop_openingen") or []):
            plus(1, zz[0], "geen_conclusie_eerst", "Begin met de conclusie, niet met een aanloop.")
    score = max(0, round(100 * (1 - straf / (10 * len(zz)))))
    return {"score": score, "zinnen": len(zz), "suggesties": sugg}
