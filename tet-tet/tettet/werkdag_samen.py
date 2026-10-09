"""Samenwerkingsstappen van de werkdag: huddle, kantine (met toezicht) en de overlegcyclus naar het MT.

Wordt door `Werkdag` gebruikt (mixin). Alles wat hier gebeurt, komt in de collecties `overleggen` en `kantine`
(alleen-toevoegen) en in het Brein; de deelnemers lopen in het kantoor naar de overleghoek, de kantine of de vergaderzaal
(veld `plek` in `activiteit`).

Volgorde in een werkdagrun: planstappen → taken → huddles → kantine → overlegcyclus → vaste rondes → dagverslag.
"""
from __future__ import annotations

import datetime as dt

from . import samenwerking as sw
from .brein import als_regel, rangorde
from .kantoordb import nu_ms
from .runtime import lees_json

PARALLEL = {"uitvoeren", "huddle", "voorbereiding", "afdelingsoverleg", "vooraf_lezen", "mt_oordeel"}
SAMEN = {"huddle", "kantine", "voorbereiding", "afdelingsoverleg", "bilateraal", "vooraf_lezen", "mt_oordeel", "mt", "retro"}
ZAAL = "vergaderzaal"
kort = lambda s, n=70: (s := str(s or "")) if len(s) <= n else s[: n - 1] + "…"


def hoek(afdeling: str) -> str:
    return f"overleghoek-{afdeling}"


class SamenwerkingStappen:
    """Mixin voor `Werkdag`. Verwacht: self.org, self.staat, self.s, self.v, self._nieuwe_stap, self._gedaan, self.log."""

    # ---------- instellingen ----------
    def _samen_instellingen(self, inst: dict):
        o, k = inst.get("overleg") or {}, inst.get("kantine") or {}
        self.o_aan, self.o_huddle = bool(o.get("aan", True)), bool(o.get("huddle", True))
        self.o_mt_dag, self.o_max = int(o.get("mt_dag", 5)), int(o.get("max_stappen_per_run", 30))
        self.k_aan, self.k_tafel = bool(k.get("aan", True)), int(k.get("tafel", 6))
        self.k_min_afd, self.k_min, self.k_max = int(k.get("min_afdelingen", 3)), int(k.get("min_beurten", 4)), int(k.get("max_beurten", 8))

    def vandaag(self) -> dt.date:
        return dt.date.today()

    # ---------- hulpjes ----------
    def _naam(self, a: str) -> str:
        return "de Raad" if a == "raad" else self.org.agent(a)["naam"] if a in self.org.agents else str(a)

    def _afd_naam(self, d: str) -> str:
        return self.org.afdelingen[d]["naam"] if d in self.org.afdelingen else str(d)

    def _toegang(self, a: str):
        return self.org.effectieve_toegang(a)

    def _toezichthouder(self) -> str:
        for kandidaat in ("risk-2", "risk-1", "risk-h"):
            if kandidaat in self.org.agents and self.org.ingezet(self.org.agent(kandidaat)):
                return kandidaat
        return "risk-h"

    def _overleg(self, body: dict) -> dict:
        body = {"id": f"{self.s.bron}-o{len(self.staat.overleggen) + 1:03d}-{body['soort']}", "ts": nu_ms(), "bron": self.s.bron, **body}
        self.staat.overleggen.append(body)
        self.s.nieuw("overleggen", body["id"], body)
        return body

    def _brein_nieuw(self, soort: str, agent: str, dept: str, tekst: str, **extra) -> dict:
        item = {"id": f"b{nu_ms()}-{len(self.staat.brein)}", "soort": soort, "dept": dept, "agent": agent, "taak": extra.pop("taak", None),
                "tekst": str(tekst).strip()[:500], "labels": extra.pop("labels", []), "bevestigd": 1, "ts": nu_ms(), **extra}
        self.staat.brein.append(item)
        self.s.nieuw("brein", item["id"], item)
        self.s.event("brein." + soort, agent, {"id": item["id"]}, item["taak"])
        return item

    def _samen_stappen_deze_run(self) -> int:
        return sum(1 for s in self.v["stappen"].values() if s["soort"] in SAMEN)

    def _plek(self, stap: dict) -> str | None:
        soort = stap["soort"]
        if soort == "kantine":
            return "kantine"
        if soort in ("huddle", "afdelingsoverleg"):
            return hoek(stap["afdeling"])
        if soort in ("bilateraal", "mt", "retro"):
            return ZAAL
        return None

    def _deelnemers(self, stap: dict) -> list[str]:
        soort = stap["soort"]
        if soort == "kantine":
            return stap["deelnemers"] + ([self._toezichthouder()] if stap.get("fase") == "toezicht" else [])
        if soort in ("huddle", "afdelingsoverleg"):
            return [a["id"] for a in self.org.team(stap["afdeling"])]
        if soort == "bilateraal":
            return [self.org.hoofdtet(d)["id"] for d in stap["paar"]]
        if soort in ("mt", "retro"):
            return ["oppertet", *[self.org.hoofdtet(d)["id"] for d in self.org.afdelingen]]
        return [stap["agent"]]

    def _samen_bij_prompt(self, stap: dict, agent: str, label: str):
        """Iedereen die meedoet loopt naar de plek van het overleg."""
        plek = self._plek(stap)
        if not plek:
            return
        for d in self._deelnemers(stap):
            if d != agent:
                self.s.activiteit(d, "bezig", {"kantine": "pauze in de kantine"}.get(stap["soort"], "in overleg: " + label), None, plek)

    def _samen_klaar(self, stap: dict, tekst: str):
        for d in self._deelnemers(stap):
            self.s.activiteit(d, "klaar", tekst, None, None)

    # ---------- bepalen ----------
    def _bepaal_samen(self, aantal: int, lopend: list[dict]) -> list[dict]:
        soorten = {s["soort"] for s in lopend}
        # Huddles: dagelijks per afdeling met werk, parallel, vlak vóór de pauze.
        if self.o_aan and self.o_huddle and soorten <= {"huddle"}:
            open_ = [d for d in self._huddle_afdelingen() if not self._gedaan("huddle", afdeling=d) and not self._huddle_vandaag(d)]
            nieuw = [self._nieuwe_stap("huddle", self._voorzitter(d), afdeling=d) for d in open_[:max(0, aantal - len(lopend))]]
            if nieuw or lopend:
                return nieuw
        if lopend:
            pass
        # Kantine: één gemengde tafel per run.
        elif self.k_aan and not self._gedaan("kantine") and len(self.org.actieve_agents()) >= 4:
            bezet = {self.staat.taken[s["taak"]]["agent"] for s in lopend if s.get("taak") in self.staat.taken}
            tafel = sw.tafel(self.org, self.staat.kantine[-20:], sleutel=self.s.bron, grootte=self.k_tafel,
                             min_afdelingen=self.k_min_afd, bezet=bezet | {self._toezichthouder()})
            if len(tafel) >= 3:
                return [self._nieuwe_stap("kantine", tafel[0], deelnemers=tafel, fase="gesprek")]
        if self.o_aan:
            return self._bepaal_overleg(aantal, lopend)
        return []

    def _huddle_afdelingen(self) -> list[str]:
        st = self.staat
        return [d for d in self.org.afdelingen if len(self.org.team(d)) > 1 and (st.afdelingsdoelen.get(d, {}).get("doel")
                or any(t.get("dept") == d and t.get("status") in ("volgende", "bezig") for t in st.taken.values()))]

    def _huddle_vandaag(self, d: str) -> bool:
        return any(o.get("soort") == "huddle" and o.get("dept") == d and o.get("datum") == self.vandaag().isoformat() for o in self.staat.overleggen)

    def _voorzitter(self, d: str) -> str:
        team = sorted(a["id"] for a in self.org.team(d))
        return team[self.vandaag().toordinal() % len(team)]  # roulerend voorzitterschap

    def _memos(self, cyclus: str) -> dict[str, dict]:
        return {o["dept"]: o for o in self.staat.overleggen if o.get("soort") == "afdelingsoverleg" and o.get("cyclus") == cyclus and o.get("memo")}

    def _agenda(self, cyclus: str) -> list[dict]:
        uit = []
        for d in self.org.afdelingen:
            m = self._memos(cyclus).get(d)
            for v in (m or {}).get("memo", {}).get("besluitvragen", [])[:2]:
                uit.append({"nr": len(uit) + 1, "dept": d, "vraag": str(v)[:300]})
        return uit[:8]

    def _eenheden(self, fase: str, cyclus: str, afd: list[str]) -> list[dict]:
        org = self.org
        memos = self._memos(cyclus)
        if fase == "voorbereiding":
            return [{"key": a["id"], "agent": a["id"], "extra": {"afdeling": d}} for d in afd for a in org.team(d)]
        if fase == "afdelingsoverleg":
            return [{"key": d, "agent": org.hoofdtet(d)["id"], "extra": {"afdeling": d}} for d in afd]
        if fase == "bilateraal":
            paren = sw.bilaterale_paren(org, list(memos), list(self.staat.taken.values()))
            return [{"key": f"{a}+{b}", "agent": org.hoofdtet(a)["id"], "extra": {"paar": [a, b]}} for a, b in paren]
        if fase == "vooraf_lezen":
            return [{"key": d, "agent": org.hoofdtet(d)["id"], "extra": {"afdeling": d}} for d in memos] + \
                   ([{"key": "oppertet", "agent": "oppertet", "extra": {}}] if memos else [])
        if fase == "mt_oordeel":
            return [{"key": d, "agent": org.hoofdtet(d)["id"], "extra": {"afdeling": d}} for d in memos] if self._agenda(cyclus) else []
        if fase == "mt":
            return [{"key": "mt", "agent": "oppertet", "extra": {}}] if memos else []
        return []

    def _fase_klaar(self, cyclus: str, fase: str):
        self._overleg({"soort": "fase", "cyclus": cyclus, "fase": fase})

    def _bepaal_overleg(self, aantal: int, lopend: list[dict]) -> list[dict]:
        vandaag = self.vandaag()
        cyclus, dagen = sw.overleg_cyclus(vandaag, self.o_mt_dag)
        afd = [a for a in self.org.afdelingen if self.staat.afdelingsdoelen.get(a, {}).get("doel")]
        if not afd:
            return []
        gedaan = {o["fase"] for o in self.staat.overleggen if o.get("soort") == "fase" and o.get("cyclus") == cyclus}
        for fase in sw.fasen_open(vandaag, self.o_mt_dag, gedaan):
            klaar = {o.get("eenheid") for o in self.staat.overleggen if o.get("soort") == fase and o.get("cyclus") == cyclus}
            uitgegeven = {s.get("eenheid") for s in self.v["stappen"].values() if s["soort"] == fase and s.get("cyclus") == cyclus}
            rest = [e for e in self._eenheden(fase, cyclus, afd) if e["key"] not in klaar and e["key"] not in uitgegeven]
            eigen_lopend = [s for s in lopend if s["soort"] == fase]
            if lopend and not eigen_lopend:
                return []
            if rest:
                if self._samen_stappen_deze_run() >= self.o_max:
                    return []
                ruimte = max(0, aantal - len(lopend)) if fase in PARALLEL else (0 if lopend else 1)
                ruimte = min(ruimte, self.o_max - self._samen_stappen_deze_run())
                return [self._nieuwe_stap(fase, e["agent"], cyclus=cyclus, eenheid=e["key"], **e["extra"]) for e in rest[:ruimte]]
            if eigen_lopend:
                return []
            self._fase_klaar(cyclus, fase)   # alle eenheden gedaan (of mislukt in deze run): door naar de volgende fase
            gedaan.add(fase)
        if dagen == 0 and "mt" in gedaan and sw.retro_nodig(cyclus) and "retro" not in gedaan and not lopend and not self._gedaan("retro"):
            return [self._nieuwe_stap("retro", "oppertet", cyclus=cyclus, eenheid="retro")]
        return []

    # ---------- prompts ----------
    def _omschrijf_samen(self, s: dict) -> str | None:
        naam = self._naam(s["agent"])
        return {"huddle": f"huddle {self._afd_naam(s.get('afdeling'))}", "kantine": "pauze in de kantine",
                "voorbereiding": f"{naam} bereidt het MT voor", "afdelingsoverleg": f"afdelingsoverleg {self._afd_naam(s.get('afdeling'))}",
                "bilateraal": "bilaterale afstemming " + " en ".join(self._afd_naam(x) for x in s.get("paar", [])),
                "vooraf_lezen": f"{naam} leest de memo's", "mt_oordeel": f"{naam} vormt een eigen oordeel", "mt": "MT-overleg",
                "retro": "retrospectief"}.get(s["soort"])

    def _brein_context(self, agent: str, onderwerp: str) -> list[str]:
        """Wat een agent uit het collectieve Brein meekrijgt: wie weet wat, wie werkt waaraan, open vragen, signalen."""
        st, org = self.staat, self.org
        t = self._toegang(agent)
        afd = org.agent(agent)["afdeling"]
        delen = []
        wie = sw.wie_weet_wat(org, onderwerp, zelf=agent, brein=st.brein, taken=list(st.taken.values()))
        if wie:
            delen.append("# Wie weet wat (vraag het hen via de vraagbaak of een directe lijn)\n" + "\n".join(
                f"- {w['naam']} ({self._afd_naam(w['afdeling'])}): {w['reden']}" for w in wie))
        werk = sw.wie_werkt_waaraan(org, list(st.taken.values()), agent)
        if werk:
            delen.append("# Wie werkt waaraan (voorkom dubbel werk)\n" + "\n".join(f"- {r}" for r in werk))
        vragen = sw.open_vragen(org, st.brein, agent)
        if vragen:
            delen.append("# Open vragen in het Brein die bij jou passen (beantwoord ze onder '## Antwoorden' als je het weet)\n" + "\n".join(
                f"- [{v['id']}] {v['tekst']} (van {self._naam(v.get('agent'))})" for v in vragen))
        signalen = [b for b in st.brein if b.get("soort") == "signaal" and afd in (b.get("ook") or []) and sw.zichtbaar(b, t)][-3:]
        if signalen:
            delen.append("# Signalen van andere afdelingen\n" + "\n".join(f"- {b['tekst']} (van {self._naam(b.get('agent'))})" for b in signalen))
        return delen

    def _zichtbare_lessen(self, agent: str, dept: str, behalve_taak: str | None = None, n: int = 5) -> list[str]:
        t = self._toegang(agent)
        from .brein import hoort_bij
        items = [b for b in self.staat.brein if (b.get("soort") or "les") in ("les", "incident", "besluit") and hoort_bij(b, dept, "dept")
                 and b.get("taak") != behalve_taak and sw.zichtbaar(b, t)]
        return [als_regel(b) for b in rangorde(items)[:n]]

    def _bericht_samen(self, stap: dict) -> tuple[str, str]:
        return getattr(self, "_bericht_" + stap["soort"])(stap)

    def _team_bord(self, d: str) -> list[str]:
        regels = []
        for a in self.org.team(d):
            mijn = [t for t in self.staat.taken.values() if t.get("agent") == a["id"] and t.get("status") in ("volgende", "bezig")]
            regels.append(f"- {a['id']} ({a['naam']}): " + ("; ".join(f"{t['status']}: {kort(t.get('title'), 60)}" for t in mijn) or "geen open taken"))
        return regels

    def _bericht_huddle(self, stap):
        d = stap["afdeling"]
        ad = self.staat.afdelingsdoelen.get(d, {})
        vragen = [b for b in self.staat.brein if b.get("soort") == "vraag" and b.get("status", "open") == "open" and b.get("aan") == d]
        return "\n\n".join([
            f"# Huddle {self._afd_naam(d)} – {self.vandaag().strftime('%d-%m')}",
            f"Afdelingsdoel: {ad.get('doel') or '-'}",
            "# Het bord (wie heeft wat open)\n" + "\n".join(self._team_bord(d)),
            "# Open vragen aan de afdeling\n" + ("\n".join(f"- [{v['id']}] {v['tekst']}" for v in vragen) or "- geen"),
            f"Jij bent vandaag voorzitter ({self._naam(stap['agent'])}); de voorzitter rouleert.",
            "# Opdracht\n" + sw.PROTOCOL_HUDDLE]), f"zit de huddle van {self._afd_naam(d)} voor"

    def _kantine_kennis(self, deelnemers: list[str]) -> tuple[list[str], list[str]]:
        tg = sw.toegangen(self.org, deelnemers)
        werk = []
        for a in deelnemers:
            mijn = [t for t in self.staat.taken.values() if t.get("agent") == a][-3:]
            for t in mijn:
                deelbaar = all(sw.zichtbaar(t, x) for x in tg.values())
                werk.append(f"- {a}: [{t['id']}] {kort(t.get('title'), 80)} ({t.get('status')}) – "
                            + ("deelbaar aan deze tafel" if deelbaar else "NIET deelbaar aan deze tafel: alleen in algemene termen, zonder inhoud"))
        brein = [f"- [{b['id']}] {kort(b.get('tekst'), 140)}" for b in sw.deelbaar(self.staat.brein, tg)[-6:]]
        return werk, brein

    def _streng(self, deelnemers: list[str]) -> bool:
        """Cascadebewaking: na een tegengehouden beurt zijn de volgende kantinemomenten van dezelfde deelnemers strenger."""
        recent = self.staat.kantine[-3:]
        return any(k.get("geblokkeerd") and set(k.get("deelnemers") or []) & set(deelnemers) for k in recent)

    def _bericht_kantine(self, stap):
        org, d = self.org, stap["deelnemers"]
        if stap.get("fase") == "toezicht":
            tg = sw.toegangen(org, d)
            regels = ["# Aan tafel en wat ieder mag zien",
                      *[f"- {a} ({self._naam(a)}, {self._afd_naam(org.agent(a)['afdeling'])}): " + ", ".join(sorted(b for b in tg[a].bronnen if b not in sw.PUBLIEK)) for a in d],
                      "", "# Beurten (nog niet gedeeld)",
                      *[f"{i}. {self._naam(b['agent'])}: {b.get('tekst', '')} | filter: {b['filter']}{' – ' + b['reden'] if b.get('reden') else ''}"
                        for i, b in enumerate(stap.get("beurten", []), 1)]]
            if stap.get("streng"):
                regels.append("\nLet op: aan deze tafel is kort geleden iets tegengehouden. Toets strenger: bij twijfel blokkeren.")
            return "\n".join(regels + ["", "# Opdracht", sw.PROTOCOL_TOEZICHT]), "houdt toezicht in de kantine"
        werk, brein = self._kantine_kennis(d)
        stap["streng"] = self._streng(d)
        return "\n".join([
            "# Aan tafel",
            *[f"- {a}: {org.agent(a)['naam']} ({self._afd_naam(org.agent(a)['afdeling'])}). Stijl: {org.agent(a)['persoonlijkheid']['stijl']}. "
              f"Sterk in {org.agent(a)['persoonlijkheid']['sterk_in']}. Vak: {org.agent(a)['specialisme']}." for a in d],
            "", "# Waar iedereen mee bezig is", *(werk or ["- niets bijzonders"]),
            "", "# Uit het Brein (deelbaar aan deze tafel)", *(brein or ["- nog niets"]),
            "", f"Lengte: {self.k_min} tot {self.k_max} beurten.", "", "# Opdracht", sw.PROTOCOL_KANTINE]), "pauze in de kantine"

    def _bericht_voorbereiding(self, stap):
        a, d = stap["agent"], stap["afdeling"]
        mijn = [t for t in self.staat.taken.values() if t.get("agent") == a][-6:]
        lessen = self._zichtbare_lessen(a, d)
        return "\n\n".join([f"# Voorbereiding MT ({stap['cyclus']})", f"Afdelingsdoel: {self.staat.afdelingsdoelen.get(d, {}).get('doel') or '-'}",
                            "# Jouw taken\n" + ("\n".join(f"- {t.get('status')}: {kort(t.get('title'), 90)}" for t in mijn) or "- geen"),
                            "# Lessen uit het Brein\n" + ("\n".join(f"- {x}" for x in lessen) or "- geen"),
                            "# Opdracht\n" + sw.PROTOCOL_VOORBEREIDING]), "bereidt het MT voor"

    def _kpis(self, d: str) -> list[str]:
        taken = [t for t in self.staat.taken.values() if t.get("dept") == d]
        klaar = [t for t in taken if t.get("status") == "klaar"]
        eerste = [t for t in klaar if not t.get("afkeuringen") and not t.get("herkansingen")]
        return [f"Taken: {len(taken)} totaal, {len(klaar)} klaar, {sum(1 for t in taken if t.get('status') in ('volgende', 'bezig'))} open",
                f"Eerste keer goed: {round(len(eerste) / len(klaar) * 100) if klaar else '–'}%",
                f"Afkeuringen: {sum(t.get('afkeuringen', 0) for t in taken)}, wacht op de Raad: {sum(1 for t in taken if t.get('approval'))}"]

    def _bericht_afdelingsoverleg(self, stap):
        d, c = stap["afdeling"], stap["cyclus"]
        voor = [o for o in self.staat.overleggen if o.get("soort") == "voorbereiding" and o.get("cyclus") == c and o.get("dept") == d]
        regels = [f"- {self._naam(o['agent'])}: voortgang: {o['inhoud'].get('voortgang')}; risico: {o['inhoud'].get('risico')}; kans: {o['inhoud'].get('kans')}; "
                  f"alleen ik weet: {'; '.join(o['inhoud'].get('alleen_ik_weet') or []) or '-'}" for o in voor]
        return "\n\n".join([f"# Afdelingsoverleg {self._afd_naam(d)} ({c})", f"Afdelingsdoel: {self.staat.afdelingsdoelen.get(d, {}).get('doel') or '-'}",
                            "# Voorbereidingen (zelfstandig geschreven)\n" + ("\n".join(regels) or "- geen ingeleverd"),
                            "# Cijfers uit het grootboek\n" + "\n".join(f"- {k}" for k in self._kpis(d)),
                            "# Opdracht\n" + sw.PROTOCOL_AFDELINGSOVERLEG]), f"leidt het afdelingsoverleg van {self._afd_naam(d)}"

    def _memo_tekst(self, m: dict) -> str:
        memo = m.get("memo", {})
        return "\n".join([f"## Memo {self._afd_naam(m['dept'])}", memo.get("samenvatting", ""),
                          "Besluitvragen: " + ("; ".join(memo.get("besluitvragen") or []) or "-"),
                          "Alleen wij weten: " + ("; ".join(memo.get("alleen_wij_weten") or []) or "-"),
                          "Risico's: " + ("; ".join(memo.get("risicos") or []) or "-"), *[f"KPI: {k}" for k in m.get("kpis", [])]])

    def _bericht_bilateraal(self, stap):
        memos = self._memos(stap["cyclus"])
        return "\n\n".join([f"# Bilaterale afstemming {' en '.join(self._afd_naam(x) for x in stap['paar'])}",
                            *[self._memo_tekst(memos[x]) for x in stap["paar"] if x in memos],
                            f"Je spreekt met {self._naam(self.org.hoofdtet(stap['paar'][1])['id'])}.",
                            "# Opdracht\n" + sw.PROTOCOL_BILATERAAL]), "stemt bilateraal af"

    def _bilaterale_tekst(self, cyclus: str) -> list[str]:
        return [f"- {' + '.join(self._afd_naam(x) for x in o['paar'])}: " + "; ".join(a.get("wat", "") for a in o.get("afspraken") or []) +
                (f" | conflict: {'; '.join(o.get('conflicten'))}" if o.get("conflicten") else "")
                for o in self.staat.overleggen if o.get("soort") == "bilateraal" and o.get("cyclus") == cyclus]

    def _bericht_vooraf_lezen(self, stap):
        c = stap["cyclus"]
        return "\n\n".join([f"# Memo's voor het MT ({c})", *[self._memo_tekst(m) for m in self._memos(c).values()],
                            "# Bilaterale afspraken\n" + ("\n".join(self._bilaterale_tekst(c)) or "- geen"),
                            "# Opdracht\n" + sw.PROTOCOL_VOORAF_LEZEN]), "leest de memo's voor het MT"

    def _bericht_mt_oordeel(self, stap):
        c = stap["cyclus"]
        return "\n\n".join([f"# Agenda MT ({c})", *[f"{x['nr']}. ({self._afd_naam(x['dept'])}) {x['vraag']}" for x in self._agenda(c)],
                            *[self._memo_tekst(m) for m in self._memos(c).values()],
                            "# Opdracht\n" + sw.PROTOCOL_MT_OORDEEL]), "vormt een eigen oordeel voor het MT"

    def _bericht_mt(self, stap):
        c = stap["cyclus"]
        oordelen = [o for o in self.staat.overleggen if o.get("soort") == "mt_oordeel" and o.get("cyclus") == c]
        vragen = [v for o in self.staat.overleggen if o.get("soort") == "vooraf_lezen" and o.get("cyclus") == c for v in o.get("vragen") or []]
        regels = [f"# MT-overleg ({c})", "# Agenda"]
        for x in self._agenda(c):
            regels.append(f"{x['nr']}. ({self._afd_naam(x['dept'])}) {x['vraag']}")
            for o in oordelen:
                for oo in o.get("oordelen") or []:
                    if oo.get("nr") == x["nr"]:
                        regels.append(f"   - {self._naam(o['agent'])}: {oo.get('oordeel')} ({oo.get('zekerheid', '?')}) – {oo.get('onderbouwing', '')}")
        regels += ["", "# Vragen op de memo's", *([f"- {self._afd_naam(v.get('memo'))}: {v.get('vraag')}" for v in vragen] or ["- geen"]),
                   "", "# Bilaterale afspraken", *(self._bilaterale_tekst(c) or ["- geen"]),
                   "", *[self._memo_tekst(m) for m in self._memos(c).values()], "", "# Opdracht", sw.PROTOCOL_MT]
        return "\n".join(regels), "zit het MT-overleg voor"

    def _bericht_retro(self, stap):
        c = sw.cultuur(self.org, self.staat.kantine, self.staat.overleggen, self.staat.grootboek)
        incidenten = [b for b in self.staat.brein if b.get("soort") == "incident" or b.get("bron") in ("afkeuring", "kantine")][-8:]
        return "\n\n".join(["# Retrospectief", "# Cultuur en samenwerking\n" + "\n".join(f"- {k}: {v if v is not None else '–'}" for k, v in c.items()),
                            "# Incidenten en bijna-fouten\n" + ("\n".join(f"- {b['tekst']}" for b in incidenten) or "- geen"),
                            "# Opdracht\n" + sw.PROTOCOL_RETRO]), "leidt het retrospectief"

    # ---------- verwerken ----------
    def _verwerk_huddle(self, stap, tekst):
        o = lees_json(tekst)
        d = stap["afdeling"]
        team = {a["id"] for a in self.org.team(d)}
        beurten = [{"agent": b["agent"], "tekst": "; ".join(x for x in [f"prioriteit: {b.get('prioriteit')}" if b.get("prioriteit") else "",
                                                                         f"knelpunt: {b['knelpunt']}" if b.get("knelpunt") else "",
                                                                         f"nodig van: {self._naam(b['nodig_van'])}" if b.get("nodig_van") else ""] if x)}
                   for b in o.get("beurten") or [] if b.get("agent") in team]
        besluiten = [{"wat": str(b.get("wat", ""))[:200], "eigenaar": b.get("eigenaar") if b.get("eigenaar") in team else stap["agent"]}
                     for b in (o.get("besluiten") or [])[:4] if b.get("wat")]
        self._overleg({"soort": "huddle", "dept": d, "datum": self.vandaag().isoformat(), "voorzitter": stap["agent"],
                       "deelnemers": sorted(team), "beurten": beurten, "besluiten": besluiten})
        for b in besluiten:
            self._brein_nieuw("besluit", b["eigenaar"], d, f"Huddle {self._afd_naam(d)}: {b['wat']} (eigenaar {self._naam(b['eigenaar'])})")
        for v in (o.get("vragen_brein") or [])[:2]:
            if v.get("tekst"):
                self._brein_nieuw("vraag", stap["agent"], d, v["tekst"], aan=v.get("aan"), status="open")
        stap["status"] = "klaar"
        self._samen_klaar(stap, "huddle klaar")
        self.log(f"Huddle {self._afd_naam(d)}: {len(beurten)} beurten, {len(besluiten)} besluiten.")
        return {"uitkomst": "klaar", "klaar": True}

    def _verwerk_kantine(self, stap, tekst):
        o = lees_json(tekst)
        if stap.get("fase") == "toezicht":
            oordelen = {int(x.get("nr", 0)): x for x in o.get("oordelen") or [] if str(x.get("nr", "")).isdigit()}
            return self._kantine_publiceer(stap, oordelen, o.get("ingreep"))
        d = stap["deelnemers"]
        beurten = [{"agent": b["agent"], "tekst": str(b.get("tekst", ""))[:400], "verwijst_naar": [str(x) for x in b.get("verwijst_naar") or []][:3]}
                   for b in o.get("beurten") or [] if b.get("agent") in d and b.get("tekst")][: self.k_max]
        if not beurten:
            raise ValueError("geen beurten")
        stap["beurten"] = sw.deelfilter(beurten, d, self.org, sw.kennis_index(self.staat.brein, list(self.staat.taken.values())))
        stap["uitkomsten"] = [u for u in (o.get("uitkomsten") or [])[:3] if isinstance(u, dict) and u.get("tekst")]
        stap["fase"] = "toezicht"
        return {"uitkomst": "toezicht", "klaar": False, "volgende": "prompt"}

    def _kantine_zonder_toezicht(self, stap, reden):
        """Toezicht mislukt: alleen wat het deelfilter 'ok' vond, wordt gedeeld (twijfel gaat niet door)."""
        self.log(f"Toezicht in de kantine niet gelukt ({reden}); alleen beurten die het filter goedkeurde zijn gedeeld.")
        return self.klaar_met({"stap": stap["id"], **self._kantine_publiceer(stap, {}, None, zonder_toezicht=True)})

    def _kantine_publiceer(self, stap, oordelen: dict, ingreep, zonder_toezicht: bool = False):
        toez = self._toezichthouder()
        streng = stap.get("streng") or zonder_toezicht
        uit, lekken, geblokt_sprekers = [], [], set()
        for i, b in enumerate(stap.get("beurten", []), 1):
            oord = (oordelen.get(i) or {}).get("oordeel")
            blok = b["filter"] == "geblokkeerd" or oord == "blokkeer" or (b["filter"] == "twijfel" and (streng and oord != "ok"))
            if blok:
                reden = b.get("reden") or (oordelen.get(i) or {}).get("reden") or "informatie die niet iedereen aan tafel mag zien"
                uit.append({"agent": b["agent"], "tekst": "[niet gedeeld]", "geblokkeerd": True, "reden": str(reden)[:200]})
                lekken.append({"spreker": b["agent"], "reden": str(reden)[:200], "hoorders": [x for x in stap["deelnemers"] if x != b["agent"]]})
                geblokt_sprekers.add(b["agent"])
                if len(lekken) == 1:
                    uit.append({"agent": toez, "tekst": str(ingreep or "Even stoppen: dat werk is niet voor iedereen aan deze tafel. Op hoofdlijnen mag het wel.")[:300],
                                "ingreep": True})
            else:
                uit.append({"agent": b["agent"], "tekst": b["tekst"], "verwijst_naar": b.get("verwijst_naar") or []})
        uitkomsten = [u for u in stap.get("uitkomsten", []) if u.get("door") in stap["deelnemers"] and u.get("door") not in geblokt_sprekers]
        doc = {"soort": "kantine", "deelnemers": stap["deelnemers"], "beurten": uit, "uitkomsten": uitkomsten, "toezicht": toez,
               "geblokkeerd": len(lekken), "streng": bool(stap.get("streng")), "zonder_toezicht": zonder_toezicht}
        doc = {"id": f"{self.s.bron}-k{len(self.staat.kantine) + 1:02d}", "ts": nu_ms(), "bron": self.s.bron, **doc}
        self.staat.kantine.append(doc)
        self.s.nieuw("kantine", doc["id"], doc)
        self.s.event("kantine.gesprek", stap["deelnemers"][0], {"deelnemers": stap["deelnemers"], "beurten": len(uit), "geblokkeerd": len(lekken)})
        for lek in lekken:  # zonder inhoud: wie, aan wie, waarom
            self.s.event("kantine.lek_voorkomen", toez, lek)
        if lekken:
            self._brein_nieuw("les", toez, "risk", f"Kantine: {len(lekken)} beurt(en) tegengehouden vóór ze gedeeld werden ({lekken[0]['reden']}). "
                              "Systeem: werk dat niet voor iedereen aan tafel is, noem je alleen op hoofdlijnen.", bron="kantine", zekerheid="middel")
        for u in uitkomsten:
            door = u["door"]
            dept = self.org.agent(door)["afdeling"]
            if u.get("soort") == "vraag":
                self._brein_nieuw("vraag", door, dept, u["tekst"], aan=u.get("aan"), status="open", bron="kantine")
            elif u.get("soort") == "signaal":
                self._brein_nieuw("signaal", door, dept, u["tekst"], ook=[u["aan"]] if u.get("aan") in self.org.afdelingen else [], bron="kantine")
            elif u.get("soort") == "lijn":
                self._brein_nieuw("notitie", door, dept, "Idee voor een directe lijn: " + u["tekst"], bron="kantine")
        stap["status"] = "klaar"
        self._samen_klaar(stap, "terug van de pauze")
        self.log(f"Kantine: {len(stap['deelnemers'])} agents aan tafel, {len(uit)} beurten" + (f", {len(lekken)} tegengehouden door {self._naam(toez)}" if lekken else "") + ".")
        return {"uitkomst": "klaar", "geblokkeerd": len(lekken), "klaar": True}

    def _verwerk_voorbereiding(self, stap, tekst):
        o = lees_json(tekst)
        inhoud = {k: (str(o.get(k) or "")[:400]) for k in ("voortgang", "risico", "kans")}
        inhoud["alleen_ik_weet"] = [str(x)[:300] for x in (o.get("alleen_ik_weet") or [])[:3]]
        self._overleg({"soort": "voorbereiding", "cyclus": stap["cyclus"], "eenheid": stap["eenheid"], "dept": stap["afdeling"], "agent": stap["agent"], "inhoud": inhoud})
        stap["status"] = "klaar"
        self.s.activiteit(stap["agent"], "klaar", "voorbereiding MT ingeleverd")
        return {"uitkomst": "klaar", "klaar": True}

    def _verwerk_afdelingsoverleg(self, stap, tekst):
        o = lees_json(tekst)
        d = stap["afdeling"]
        team = {a["id"] for a in self.org.team(d)}
        m = o.get("memo") or {}
        memo = {"samenvatting": str(m.get("samenvatting", ""))[:1200], **{k: [str(x)[:300] for x in (m.get(k) or [])[:4]] for k in ("besluitvragen", "alleen_wij_weten", "risicos")}}
        besluiten = [{"wat": str(b.get("wat", ""))[:200], "eigenaar": b.get("eigenaar") if b.get("eigenaar") in team else stap["agent"]} for b in (o.get("besluiten") or [])[:4] if b.get("wat")]
        self._overleg({"soort": "afdelingsoverleg", "cyclus": stap["cyclus"], "eenheid": d, "dept": d, "voorzitter": stap["agent"], "deelnemers": sorted(team),
                       "beurten": [{"agent": b["agent"], "tekst": str(b.get("inbreng", ""))[:300]} for b in o.get("beurten") or [] if b.get("agent") in team],
                       "memo": memo, "kpis": self._kpis(d), "besluiten": besluiten})
        for b in besluiten:
            self._brein_nieuw("besluit", b["eigenaar"], d, f"Afdelingsoverleg {self._afd_naam(d)}: {b['wat']} (eigenaar {self._naam(b['eigenaar'])})")
        stap["status"] = "klaar"
        self._samen_klaar(stap, "afdelingsoverleg klaar, memo staat")
        self.log(f"Afdelingsoverleg {self._afd_naam(d)}: memo met {len(memo['besluitvragen'])} besluitvragen.")
        return {"uitkomst": "klaar", "klaar": True}

    def _verwerk_bilateraal(self, stap, tekst):
        o = lees_json(tekst)
        hoofden = {self.org.hoofdtet(x)["id"] for x in stap["paar"]}
        afspraken = [{"wat": str(a.get("wat", ""))[:200], "eigenaar": a.get("eigenaar") if a.get("eigenaar") in hoofden else stap["agent"]} for a in (o.get("afspraken") or [])[:4] if a.get("wat")]
        self._overleg({"soort": "bilateraal", "cyclus": stap["cyclus"], "eenheid": stap["eenheid"], "paar": stap["paar"], "deelnemers": sorted(hoofden),
                       "afspraken": afspraken, "conflicten": [str(c)[:200] for c in (o.get("conflicten") or [])[:3]]})
        stap["status"] = "klaar"
        self._samen_klaar(stap, "bilaterale afstemming klaar")
        return {"uitkomst": "klaar", "klaar": True}

    def _verwerk_vooraf_lezen(self, stap, tekst):
        o = lees_json(tekst)
        memos = self._memos(stap["cyclus"])
        per: dict[str, int] = {}
        vragen = []
        for v in o.get("vragen") or []:
            if v.get("memo") in memos and per.get(v["memo"], 0) < 2 and v.get("vraag"):
                per[v["memo"]] = per.get(v["memo"], 0) + 1
                vragen.append({"memo": v["memo"], "vraag": str(v["vraag"])[:300], "door": stap["agent"]})
        self._overleg({"soort": "vooraf_lezen", "cyclus": stap["cyclus"], "eenheid": stap["eenheid"], "agent": stap["agent"], "vragen": vragen})
        stap["status"] = "klaar"
        self.s.activiteit(stap["agent"], "klaar", f"memo's gelezen, {len(vragen)} vragen")
        return {"uitkomst": "klaar", "klaar": True}

    def _verwerk_mt_oordeel(self, stap, tekst):
        o = lees_json(tekst)
        nrs = {x["nr"] for x in self._agenda(stap["cyclus"])}
        oordelen = [{"nr": int(x["nr"]), "oordeel": str(x.get("oordeel", ""))[:300], "onderbouwing": str(x.get("onderbouwing", ""))[:300],
                     "zekerheid": x.get("zekerheid") if x.get("zekerheid") in ("hoog", "middel", "laag") else "middel"}
                    for x in o.get("oordelen") or [] if str(x.get("nr", "")).isdigit() and int(x["nr"]) in nrs]
        self._overleg({"soort": "mt_oordeel", "cyclus": stap["cyclus"], "eenheid": stap["eenheid"], "agent": stap["agent"], "oordelen": oordelen})
        stap["status"] = "klaar"
        self.s.activiteit(stap["agent"], "klaar", "eigen oordeel voor het MT klaar")
        return {"uitkomst": "klaar", "klaar": True}

    def _verwerk_mt(self, stap, tekst):
        o = lees_json(tekst)
        c = stap["cyclus"]
        agenda = self._agenda(c)
        deelnemers = self._deelnemers(stap)
        besluiten = []
        for b in (o.get("besluiten") or [])[:8]:
            if not b.get("besluit"):
                continue
            eig = b.get("eigenaar") if b.get("eigenaar") in self.org.agents else "oppertet"
            besluiten.append({"nr": b.get("nr"), "besluit": str(b["besluit"])[:300], "eigenaar": eig, "reden": str(b.get("reden", ""))[:300],
                              "deadline": b.get("deadline") if b.get("deadline") not in ("null", None, "") else None})
        oordelen = [o2 for o2 in self.staat.overleggen if o2.get("soort") == "mt_oordeel" and o2.get("cyclus") == c]
        beurten = [{"agent": x["agent"], "tekst": "; ".join(f"{oo['nr']}: {oo['oordeel']}" for oo in x.get("oordelen") or [])} for x in oordelen]
        vragen_raad = [str(v)[:300] for v in (o.get("vragen_aan_raad") or [])[:3]]
        self._overleg({"soort": "mt", "cyclus": c, "eenheid": "mt", "deelnemers": deelnemers, "agenda": agenda, "beurten": beurten,
                       "samenvatting": str(o.get("samenvatting", ""))[:1200], "besluiten": besluiten, "vragen_aan_raad": vragen_raad})
        for b in besluiten:
            self._brein_nieuw("besluit", b["eigenaar"], self.org.agent(b["eigenaar"])["afdeling"] if b["eigenaar"] in self.org.agents else "centraal",
                              f"MT {c}: {b['besluit']} (eigenaar {self._naam(b['eigenaar'])}; reden: {b['reden']})")
            self.s.event("mt.besluit", "oppertet", {"besluit": b["besluit"], "eigenaar": b["eigenaar"]})
        stap["status"] = "klaar"
        self._samen_klaar(stap, "MT-overleg klaar")
        self.log(f"MT-overleg: {len(besluiten)} besluiten" + (f"; vragen aan de Raad: {' | '.join(vragen_raad)}" if vragen_raad else "") + ".")
        return {"uitkomst": "klaar", "besluiten": len(besluiten), "klaar": True}

    def _verwerk_retro(self, stap, tekst):
        o = lees_json(tekst)
        bevindingen = [str(b)[:300] for b in (o.get("bevindingen") or [])[:3]]
        v = o.get("voorstel") or {}
        self._overleg({"soort": "retro", "cyclus": stap["cyclus"], "eenheid": "retro", "deelnemers": self._deelnemers(stap), "bevindingen": bevindingen,
                       "cultuur": sw.cultuur(self.org, self.staat.kantine, self.staat.overleggen, self.staat.grootboek)})
        for b in bevindingen:
            self._brein_nieuw("les", "oppertet", "centraal", "Retrospectief: " + b, bron="retro")
        if v.get("titel") and v["titel"] not in {x.get("titel") for x in self.staat.voorstellen.values()}:
            vid = f"v{nu_ms()}-retro"
            body = {"id": vid, "titel": str(v["titel"]), "toelichting": str(v.get("toelichting", "")), "soort": str(v.get("soort", "werkwijze")),
                    "door": "oppertet", "status": "open", "created": nu_ms()}
            self.staat.voorstellen[vid] = body
            self.s.nieuw("voorstellen", vid, body)
            self.s.event("voorstel.ingediend", "oppertet", {"titel": body["titel"]})
        self._fase_klaar(stap["cyclus"], "retro")
        stap["status"] = "klaar"
        self._samen_klaar(stap, "retrospectief klaar")
        self.log(f"Retrospectief: {len(bevindingen)} bevindingen" + (", één voorstel aan de Raad." if v.get("titel") else "."))
        return {"uitkomst": "klaar", "klaar": True}

    # ---------- Brein bij het uitvoeren van taken ----------
    def _deel_uit_resultaat(self, t: dict):
        """Na goedkeuring: vragen, signalen en antwoorden uit het resultaat naar het Brein (labels van de taak gaan mee)."""
        b = sw.blokken_uit(t.get("resultaat") or "")
        labels = t.get("labels") or []
        for v in b["vragen"]:
            self._brein_nieuw("vraag", t["agent"], t["dept"], v["tekst"], aan=v["aan"], status="open", taak=t["id"], labels=labels)
        for s in b["signalen"]:
            voor = [x for x in s["voor"] if x in self.org.afdelingen and x != t["dept"]]
            if voor:
                self._brein_nieuw("signaal", t["agent"], t["dept"], s["tekst"], ook=voor, taak=t["id"], labels=labels)
        for a in b["antwoorden"]:
            vraag = next((x for x in self.staat.brein if x.get("id") == a["vraag"] and x.get("soort") == "vraag"), None)
            if vraag and vraag.get("status", "open") == "open":
                self.s.patch("brein", vraag["id"], {"status": "beantwoord", "antwoord": a["tekst"], "beantwoord_door": t["agent"], "beantwoord_ts": nu_ms(),
                                                    "labels": sorted(set(vraag.get("labels") or []) | set(labels))})
                self.s.event("brein.antwoord", t["agent"], {"vraag": vraag["id"]}, t["id"])
