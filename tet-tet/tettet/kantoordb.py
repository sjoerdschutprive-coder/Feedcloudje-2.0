"""De gedeelde opslag van het live kantoor, zoals Claude Code die ziet en beschrijft.

Lezen: een dump van de collecties (ArtifactData `list` met `out_dir`) wordt een `KantoorStaat`,
met de patches al toegepast.

Schrijven zonder versienummers: de werkdag maakt alleen NIEUWE documenten aan:
- nieuwe taken, lessen, voorstellen, verslagen, activiteit en grootboekblokken;
- wijzigingen aan bestaande documenten als `patches/<bron>-pNNNN` ({collectie, doc, velden, bijgewerkt}).
De pagina verwerkt patches en ruimt ze op; `KantoorStaat` past ze bij het laden ook zelf toe.
Het grootboek gebruikt dezelfde controleketen als de pagina (FNV-1a over UTF-16, per bron).
"""
from __future__ import annotations

import json
import pathlib
import time

COLLECTIES = ["staat", "afdelingsdoelen", "taken", "berichten", "brein", "voorstellen", "grootboek", "activiteit", "patches", "verslagen"]


def nu_ms() -> int:
    return int(time.time() * 1000)


def controlegetal(s: str) -> str:
    """Zelfde als `controlegetal` in kantoor/index.html (JavaScript werkt met UTF-16 code units)."""
    h = 2166136261
    data = s.encode("utf-16-le")
    for i in range(0, len(data), 2):
        h ^= data[i] | (data[i + 1] << 8)
        h = (h * 16777619) & 0xFFFFFFFF
    return format(h, "08x")


def js_json(o) -> str:
    """JSON zoals JSON.stringify het schrijft (geen spaties, unicode niet ge-escaped, sleutelvolgorde behouden)."""
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


class KantoorStaat:
    def __init__(self):
        self.doel = {"naam": "", "omschrijving": "", "deadline": ""}
        self.instellingen = {"modus": "mock"}
        self.connectors: dict = {}
        self.afdelingsdoelen: dict[str, dict] = {}
        self.taken: dict[str, dict] = {}
        self.brein: list[dict] = []
        self.voorstellen: dict[str, dict] = {}
        self.verslagen: list[dict] = []
        self.activiteit: list[dict] = []
        self.grootboek: list[dict] = []
        self.patches: list[dict] = []

    # ---------- laden ----------
    @classmethod
    def uit_dump(cls, map_dump: pathlib.Path) -> "KantoorStaat":
        st = cls()
        lees = lambda c: {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((map_dump / c).glob("*.json"))} if (map_dump / c).exists() else {}
        staat = lees("staat")
        st.doel = staat.get("doel", st.doel)
        st.instellingen = staat.get("instellingen", st.instellingen)
        st.connectors = staat.get("connectors", {})
        st.afdelingsdoelen = {k: {**v, "id": k} for k, v in lees("afdelingsdoelen").items()}
        st.taken = {k: {**v, "id": v.get("id", k)} for k, v in lees("taken").items()}
        st.brein = sorted(lees("brein").values(), key=lambda b: b.get("ts", 0))
        st.voorstellen = {k: {**v, "id": v.get("id", k)} for k, v in lees("voorstellen").items()}
        st.verslagen = sorted(lees("verslagen").values(), key=lambda v: v.get("ts", 0))
        st.activiteit = sorted(({**v, "id": v.get("id", k)} for k, v in lees("activiteit").items()), key=lambda a: a.get("ts", 0))
        events = {}
        for blok in lees("grootboek").values():
            for e in blok.get("events", []):
                events[(e.get("bron", "blok"), e.get("n"))] = e
        st.grootboek = sorted(events.values(), key=lambda e: (e.get("ts", 0), e.get("n", 0)))
        st.patches = sorted(({**v, "id": k} for k, v in lees("patches").items()), key=lambda p: p.get("bijgewerkt", 0))
        for p in st.patches:
            st.pas_patch_toe(p)
        return st

    def pas_patch_toe(self, p: dict) -> None:
        c, doc, velden = p.get("collectie"), p.get("doc"), p.get("velden", {})
        doel = None
        if c == "taken":
            doel = self.taken.get(doc)
        elif c == "afdelingsdoelen":
            doel = self.afdelingsdoelen.setdefault(doc, {"id": doc, "doel": "", "deadline": "", "hoofdlijnen": []})
        elif c == "voorstellen":
            doel = self.voorstellen.get(doc)
        elif c == "staat" and doc == "doel":
            doel = self.doel
        if doel is not None and p.get("bijgewerkt", 0) >= doel.get("bijgewerkt", 0):
            doel.update(velden)
            doel["bijgewerkt"] = p.get("bijgewerkt", 0)

    # ---------- bewaren tussen stappen van één werkdag ----------
    def naar_json(self) -> dict:
        return {k: v for k, v in vars(self).items()}

    @classmethod
    def uit_json(cls, d: dict) -> "KantoorStaat":
        st = cls()
        for k, v in d.items():
            setattr(st, k, v)
        return st

    # ---------- handig ----------
    def open_hoofdlijnen(self, afdeling: str) -> list[int]:
        hl = self.afdelingsdoelen.get(afdeling, {}).get("hoofdlijnen", [])
        bezet = {t.get("hl") for t in self.taken.values() if t.get("dept") == afdeling}
        return [i for i in range(len(hl)) if i not in bezet]


class Schrijver:
    """Verzamelt schrijfacties als losse JSON-bestanden en levert ze als ArtifactData-batch.

    Houdt de staat van de eigen grootboekketen bij in de werkmap, zodat elke stap van één werkdag
    dezelfde bron en een doorlopende keten gebruikt.
    """

    def __init__(self, werk: pathlib.Path, staat: KantoorStaat, bron: str | None = None):
        self.werk, self.staat = werk, staat
        self.pad_meta = werk / "schrijver.json"
        meta = json.loads(self.pad_meta.read_text()) if self.pad_meta.exists() else {}
        self.bron = meta.get("bron") or bron or "werkdag-" + time.strftime("%Y%m%d%H%M")
        self.n, self.vorige = meta.get("n", 0), meta.get("vorige", "")
        self.teller = meta.get("teller", 0)
        self.blok = meta.get("blok", 0)
        self.wachtend_events: list[dict] = meta.get("wachtend_events", [])
        self.docs: list[tuple[str, str, dict]] = []   # (collectie, id, body)
        self.weg: list[tuple[str, str]] = []

    def _id(self, soort: str) -> str:
        self.teller += 1
        return f"{self.bron}-{soort}{self.teller:04d}"

    def nieuw(self, collectie: str, doc_id: str, body: dict) -> None:
        self.docs.append((collectie, doc_id, body))

    def patch(self, collectie: str, doc: str, velden: dict) -> None:
        t = nu_ms()
        self.nieuw("patches", self._id("p"), {"collectie": collectie, "doc": doc, "velden": velden, "bijgewerkt": t, "bron": self.bron})
        st = self.staat
        doel = {"taken": st.taken.get(doc), "voorstellen": st.voorstellen.get(doc),
                "afdelingsdoelen": st.afdelingsdoelen.setdefault(doc, {"id": doc, "doel": "", "deadline": "", "hoofdlijnen": []}) if collectie == "afdelingsdoelen" else None,
                "staat": st.doel if doc == "doel" else None}.get(collectie)
        if doel is not None:
            doel.update(velden)
            doel["bijgewerkt"] = t

    def activiteit(self, agent: str, status: str, tekst: str, taak: str | None = None) -> None:
        a = {"id": self._id("a"), "agent": agent, "status": status, "tekst": str(tekst)[:160], "taak": taak, "ts": nu_ms(), "bron": self.bron}
        self.nieuw("activiteit", a["id"], a)
        self.staat.activiteit.append(a)

    def event(self, type_: str, agent: str, data: dict | None = None, taak: str | None = None) -> None:
        self.n += 1
        e = {"bron": self.bron, "n": self.n, "ts": nu_ms(), "type": type_, "agent": agent, "taak": taak, "data": data or {}, "modus": "werkdag"}
        e["h"] = controlegetal(self.vorige + js_json(e))
        self.vorige = e["h"]
        self.wachtend_events.append(e)
        self.staat.grootboek.append(e)

    def verwijder(self, collectie: str, doc_id: str) -> None:
        self.weg.append((collectie, doc_id))

    def schrijf(self, grootboek_nu: bool = False) -> list[dict]:
        """Zet alles klaar als bestanden en geeft de batch-regels terug (max. 50 per batch)."""
        if self.wachtend_events and (grootboek_nu or len(self.wachtend_events) >= 25):
            self.blok += 1
            self.nieuw("grootboek", f"{self.bron}-{self.blok:04d}", {"bron": self.bron, "events": self.wachtend_events})
            self.wachtend_events = []
        map_docs = self.werk / "docs"
        map_docs.mkdir(parents=True, exist_ok=True)
        regels = []
        for collectie, doc_id, body in self.docs:
            pad = map_docs / f"{collectie}--{doc_id}.json"
            pad.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
            regels.append({"op": "set", "collection": collectie, "doc_id": doc_id, "file_path": str(pad)})
        for collectie, doc_id in self.weg:
            regels.append({"op": "delete", "collection": collectie, "doc_id": doc_id, "if_version": 1})
        self.docs, self.weg = [], []
        self.pad_meta.write_text(json.dumps({"bron": self.bron, "n": self.n, "vorige": self.vorige, "teller": self.teller,
                                             "blok": self.blok, "wachtend_events": self.wachtend_events}, ensure_ascii=False))
        return regels


def in_batches(regels: list[dict], grootte: int = 50) -> list[list[dict]]:
    return [regels[i:i + grootte] for i in range(0, len(regels), grootte)]
