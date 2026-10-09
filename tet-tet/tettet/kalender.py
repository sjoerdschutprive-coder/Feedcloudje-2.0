"""De gedeelde agenda van Tet Tet: het rooster van vaste HR- en overlegmomenten, en de koppeling met een agenda.

Ontwerp (zie de HR-opdracht, sectie 5):
- `rooster()` maakt de geplande momenten uit `config/instellingen.yaml` (`hr`, `overleg`). Niets hiervan zit in code.
- Een event heeft een deterministische UID `tettet-<soort>-<onderwerp>-<datum>@tettet`: twee keer exporteren of
  synchroniseren levert nooit dubbele events op.
- Tot de koppeling bestaat, genereert het rooster de events. Daarna is de agenda leidend voor het TIJDSTIP (een
  verplaatst event volgt de werkdag), en het rooster voor WAT er moet gebeuren.
- Agents maken en wijzigen alleen events met de eigen prefix en UID. Annuleren doet alleen de Raad; een geannuleerd
  moment wordt niet opnieuw ingepland.
- Nooit inhoud uit een HR-dossier in een event: de agenda is breder zichtbaar dan het label `hr-dossier`.

Drie implementaties met dezelfde interface: `MockKalender` (standaard, tests), `IcsKalender` (export als .ics om
in de nieuwe gedeelde Google Calendar te importeren) en `GoogleKalender` (vorm; de Raad koppelt hem later).
"""
from __future__ import annotations

import abc
import datetime as dt
import json
import pathlib
import re

DAGEN = {"ma": 1, "di": 2, "wo": 3, "do": 4, "vr": 5, "za": 6, "zo": 7}
SOORT_NAAM = {"checkin": "Check-in", "evaluatie": "Evaluatie", "zelfreflectie": "Zelfreflectie", "snapshot": "Snapshot",
              "kalibratie": "Kalibratie", "raadsreview": "Raadsreview", "mt": "MT-overleg", "retrospectief": "Retrospectief",
              "proefperiode": "Proefperiode", "incident": "Incidentevaluatie", "curatie": "Curatie Brein", "cultuurbrief": "Cultuurbrief"}
OMSCHRIJVING = {
    "checkin": "Wekelijkse check-in, max. 10 minuten, geen cijfers: waar werk je aan, wat heb je nodig, waar twijfel je, welk MT-besluit raakt jou.",
    "evaluatie": "Evaluatiegesprek, max. 20 minuten: zelfreflectie, snapshot, toekomstvragen, afspraken (één prestatiedoel, één leerdoel).",
    "zelfreflectie": "De agent schrijft zelf, vóór hij de snapshot ziet.",
    "snapshot": "Prestatieprofielen van de afgelopen periode, met gaming-signalen.",
    "kalibratie": "Hoofdtets leggen hun oordelen naast elkaar; eerst ieder apart, dan bespreken. Uitkomst: voorstellen aan de Raad.",
    "raadsreview": "De Raad beslist over de voorstellen uit de kalibratie (HR-pagina in het kantoor).",
    "mt": "MT-overleg: Oppertet en Hoofdtets.",
    "retrospectief": "Maandelijks retrospectief, blameless.",
    "proefperiode": "Evaluatie aan het eind van de proefperiode van een nieuwe agent.",
    "incident": "Blameless incidentevaluatie na een grensovertreding: welk systeem maakte het mogelijk?",
    "curatie": "Wekelijkse curatieronde van het Brein.",
    "cultuurbrief": "Maandelijkse cultuurbrief voor het retrospectief en de Raad.",
}


class KalenderFout(Exception):
    """Een handeling op de agenda valt buiten wat deze partij mag."""


# ---------- instellingen en werkdagen ----------
def instellingen(inst: dict) -> dict:
    k = ((inst.get("hr") or {}).get("kalender")) or {}
    return {"bron": k.get("bron", "mock"), "kalender_id": k.get("kalender_id") or "", "tijdzone": k.get("tijdzone") or "",
            "werkdagen": [DAGEN[d] for d in (k.get("werkdagen") or ["ma", "di", "wo", "do", "vr"])],
            "startdatum": k.get("startdatum") or "", "prefix": k.get("prefix") or "[Tet Tet]",
            "soorten_in_agenda": set(k.get("soorten_in_agenda") or []), "kleuren": k.get("kleuren") or {},
            "vooruit": int(k.get("vooruit_werkdagen", 15)), "begintijd": k.get("begintijd") or "10:00",
            "duur": k.get("duur_minuten") or {}}


def is_werkdag(d: dt.date, werkdagen: list[int]) -> bool:
    return d.isoweekday() in werkdagen


def werkdagen_verschuif(d: dt.date, n: int, werkdagen: list[int]) -> dt.date:
    """n werkdagen vooruit (n > 0) of terug (n < 0)."""
    stap = 1 if n >= 0 else -1
    for _ in range(abs(n)):
        d += dt.timedelta(days=stap)
        while not is_werkdag(d, werkdagen):
            d += dt.timedelta(days=stap)
    return d


def werkdag_nummer(d: dt.date, startdatum: str, werkdagen: list[int]) -> int | None:
    """Werkdag 1 = `startdatum` (instelling `hr.kalender.startdatum`)."""
    if not startdatum:
        return None
    s, n = dt.date.fromisoformat(startdatum), 1
    while s < d:
        s += dt.timedelta(days=1)
        n += is_werkdag(s, werkdagen)
    return n


def uid(soort: str, onderwerp: str, datum: str) -> str:
    return f"tettet-{soort}-{re.sub(r'[^a-z0-9-]', '-', onderwerp.lower())}-{datum}@tettet"


# ---------- events ----------
def maak_event(soort: str, onderwerp: str, datum: dt.date, deelnemers: list[str], k: dict, *, extra: dict | None = None) -> dict:
    """Eén gepland moment. De beschrijving bevat eerst een leesbare agenda, dan een machineleesbaar blok."""
    e = {"uid": uid(soort, onderwerp, datum.isoformat()), "soort": soort, "onderwerp": onderwerp, "datum": datum.isoformat(),
         "gepland": datum.isoformat(), "tijd": k["begintijd"], "duur": int(k["duur"].get(soort, 30)),
         "titel": f"{k['prefix']} {SOORT_NAAM.get(soort, soort)} · {onderwerp}", "deelnemers": sorted(set(deelnemers)),
         "in_agenda": soort in k["soorten_in_agenda"], "status": "gepland", "kleur": k["kleuren"].get(soort),
         "voorbereiding": [], "verslag": None, **(extra or {})}
    e["beschrijving"] = beschrijving(e)
    return e


def beschrijving(e: dict) -> str:
    """Leesbare agenda + machineleesbaar blok. Nooit dossierinhoud: alleen soort, ids en verwijzingen."""
    mens = OMSCHRIJVING.get(e["soort"], "")
    blok = {"soort": e["soort"], "deelnemers": e["deelnemers"], "voorbereiding": e.get("voorbereiding") or [], "verslag": e.get("verslag")}
    return f"{mens}\nDeelnemers: {', '.join(e['deelnemers'])}\n\n--- tettet ---\n{json.dumps(blok, ensure_ascii=False)}\n--- /tettet ---"


def lees_blok(tekst: str) -> dict | None:
    m = re.search(r"--- tettet ---\n(.+?)\n--- /tettet ---", tekst or "", re.S)
    return json.loads(m.group(1)) if m else None


# ---------- het rooster ----------
def mt_data(van: dt.date, tot: dt.date, mt_dag: int) -> list[dt.date]:
    d = van + dt.timedelta(days=(mt_dag - van.isoweekday()) % 7)
    uit = []
    while d <= tot:
        uit.append(d)
        d += dt.timedelta(days=7)
    return uit


def checkin_datum(mt: dt.date, werkdagen: list[int], mt_dag: int) -> dt.date:
    """De werkdag na het MT, maar nooit op een MT-dag of een voorbereidingsdag (2 dagen vóór een MT)."""
    d = werkdagen_verschuif(mt, 1, werkdagen)
    while d.isoweekday() == mt_dag or (d + dt.timedelta(days=2)).isoweekday() == mt_dag:
        d = werkdagen_verschuif(d, 1, werkdagen)
    return d


def is_retro(mt: dt.date) -> bool:
    """Retrospectief bij het eerste MT van de maand (zie samenwerking.retro_nodig)."""
    return mt.day <= 7


def rooster(org, inst: dict, van: dt.date, tot: dt.date) -> list[dict]:
    """Alle geplande vaste momenten met een datum in [van, tot]. Incidenten en proefperiodes plant de werkdag zelf."""
    k = instellingen(inst)
    wd = k["werkdagen"]
    hr = inst.get("hr") or {}
    ritme = hr.get("ritme") or {}
    mt_dag = int((inst.get("overleg") or {}).get("mt_dag", 5))
    hoofden = [org.hoofdtet(d)["id"] for d in org.afdelingen if any(a["rol"] == "hoofdtet" for a in org.team(d))]
    uit: list[dict] = []
    def plus(e):
        if van.isoformat() <= e["datum"] <= tot.isoformat():
            uit.append(e)
    ruim_tot = tot + dt.timedelta(days=40)
    for mt in mt_data(van - dt.timedelta(days=14), ruim_tot, mt_dag):
        plus(maak_event("mt", "mt", mt, ["oppertet", *hoofden], k))
        if ritme.get("checkin", True):
            cd = checkin_datum(mt, wd, mt_dag)
            for d in org.afdelingen:
                tets = [a["id"] for a in org.team(d) if a["rol"] in ("tet", "controltet")]
                if tets:
                    plus(maak_event("checkin", d, cd, [org.hoofdtet(d)["id"], *tets], k, extra={"mt": mt.isoformat()}))
        if not is_retro(mt):
            continue
        plus(maak_event("retrospectief", "mt", mt, ["oppertet", *hoofden], k))
        snap = werkdagen_verschuif(mt, -int(ritme.get("snapshot_voor_retro", 3)), wd)
        ev = werkdagen_verschuif(mt, -int(ritme.get("evaluatie_voor_retro", 2)), wd)
        prestatie = beoordelaar_hr(org, "prestatie")
        gov = beoordelaar_hr(org, "governance")
        extra = {"retro": mt.isoformat()}
        plus(maak_event("snapshot", "hr", snap, [prestatie], k, extra=extra))
        plus(maak_event("cultuurbrief", "hr", snap, [gov], k, extra=extra))
        for a in te_evalueren(org):
            plus(maak_event("zelfreflectie", a["id"], snap, [a["id"]], k, extra=extra))
            plus(maak_event("evaluatie", a["id"], ev, evaluatie_deelnemers(org, a["id"]), k, extra=extra))
        elke = max(1, int(ritme.get("kalibratie_elke_maanden", 3)))
        if mt.month % elke == 0:
            kal = werkdagen_verschuif(mt, 1, wd)
            plus(maak_event("kalibratie", "hr", kal, [org.hoofdtet("hr")["id"], *hoofden, prestatie], k, extra=extra))
            plus(maak_event("raadsreview", "hr", werkdagen_verschuif(kal, 1, wd), ["raad", org.hoofdtet("hr")["id"]], k, extra=extra))
    cur = int(ritme.get("curatie_dag", 1))
    d = van
    while d <= tot:
        if d.isoweekday() == cur and is_werkdag(d, wd):
            plus(maak_event("curatie", "brein", d, [beoordelaar_hr(org, "governance")], k))
        d += dt.timedelta(days=1)
    return sorted(uit, key=lambda e: (e["datum"], e["soort"], e["onderwerp"]))


# ---------- wie doet wat (uit de kaarten, niet uit ids in code) ----------
def beoordelaar_hr(org, wat: str) -> str:
    """De ingezette HR-agent voor een rol ('prestatie' of 'governance'), anders de Hoofdtet HR.
    Gevonden via het specialisme in de profielkaart."""
    for a in org.team("hr"):
        if a["rol"] == "tet" and (wat in a["specialisme"].lower() or wat in a["naam"].lower()):
            return a["id"]
    return org.hoofdtet("hr")["id"]


def te_evalueren(org) -> list[dict]:
    return [a for a in org.actieve_agents() if a["rol"] != "oppertet"]


def evaluator(org, agent_id: str) -> str:
    """Wie het evaluatiegesprek voert: de leidinggevende. HR-agents: de Hoofdtet HR (met de Oppertet)."""
    a = org.agent(agent_id)
    return a["rapporteert_aan"] if a["rapporteert_aan"] in org.agents else "oppertet"


def evaluatie_deelnemers(org, agent_id: str) -> list[str]:
    a = org.agent(agent_id)
    uit = [agent_id, evaluator(org, agent_id)]
    prestatie = beoordelaar_hr(org, "prestatie")
    if a["afdeling"] == "hr" or agent_id == prestatie:
        uit.append("oppertet")          # wie bewaakt de bewakers: HR-agents met de Oppertet, nooit door zichzelf
    if prestatie != agent_id and prestatie not in uit:
        uit.append(prestatie)
    return sorted(set(uit) - {"raad"})


# ---------- de agenda ----------
class Kalender(abc.ABC):
    """Interface voor de gedeelde agenda. `door` is de partij die de handeling doet: een agent-id of 'raad'."""

    def __init__(self, inst: dict):
        self.k = instellingen(inst)

    @abc.abstractmethod
    def lees(self, van: dt.date, tot: dt.date) -> list[dict]: ...

    @abc.abstractmethod
    def _bewaar(self, e: dict) -> dict: ...

    @abc.abstractmethod
    def _haal(self, uid_: str) -> dict | None: ...

    def zet(self, e: dict, door: str) -> dict:
        """Maak of wijzig een event. Agents alleen met de eigen prefix en UID; een geannuleerd event blijft geannuleerd."""
        if door != "raad" and (not e["titel"].startswith(self.k["prefix"]) or not e["uid"].startswith("tettet-")):
            raise KalenderFout(f"{door} mag alleen events met de prefix {self.k['prefix']} en een tettet-UID maken of wijzigen")
        oud = self._haal(e["uid"])
        if oud and oud.get("status") == "geannuleerd" and door != "raad":
            return oud
        if oud and door != "raad":
            e = {**e, "datum": oud["datum"], "tijd": oud.get("tijd", e.get("tijd"))}   # de agenda is leidend voor het tijdstip
        return self._bewaar(e)

    def verplaats(self, uid_: str, datum: str, door: str) -> dict:
        if door != "raad":
            raise KalenderFout("Alleen de Raad verplaatst events in de agenda")
        e = self._haal(uid_)
        return self._bewaar({**e, "datum": datum})

    def annuleer(self, uid_: str, door: str) -> dict:
        if door != "raad":
            raise KalenderFout("Alleen de Raad annuleert events")
        e = self._haal(uid_)
        return self._bewaar({**e, "status": "geannuleerd"})

    def synchroniseer(self, events: list[dict], door: str) -> int:
        """Zet geplande events die nog niet bestaan. Idempotent: bestaande UID's blijven zoals ze zijn."""
        n = 0
        for e in events:
            if not self._haal(e["uid"]):
                self.zet(e, door)
                n += 1
        return n

    def van_dag(self, d: dt.date) -> list[dict]:
        return [e for e in self.lees(d, d) if e.get("status") != "geannuleerd"]


class MockKalender(Kalender):
    """In het geheugen, of als JSON-bestand. Standaard en voor tests."""

    def __init__(self, inst: dict, pad: pathlib.Path | None = None, events: list[dict] | None = None):
        super().__init__(inst)
        self.pad = pad
        self.events: dict[str, dict] = {}
        if pad and pad.exists():
            self.events = {e["uid"]: e for e in json.loads(pad.read_text(encoding="utf-8"))}
        for e in events or []:
            self.events[e["uid"]] = e

    def lees(self, van, tot):
        return sorted((e for e in self.events.values() if van.isoformat() <= e["datum"] <= tot.isoformat()), key=lambda e: (e["datum"], e["uid"]))

    def _haal(self, uid_):
        return self.events.get(uid_)

    def _bewaar(self, e):
        self.events[e["uid"]] = e
        if self.pad:
            self.pad.parent.mkdir(parents=True, exist_ok=True)
            self.pad.write_text(json.dumps(list(self.events.values()), ensure_ascii=False, indent=1), encoding="utf-8")
        return e


class IcsKalender(MockKalender):
    """Exporteert de events als .ics (RFC 5545), om handmatig in de gedeelde Google Calendar te importeren.
    Alleen soorten uit `hr.kalender.soorten_in_agenda`. Opnieuw importeren werkt bij: zelfde UID, hogere SEQUENCE."""

    def export(self, van: dt.date, tot: dt.date) -> str:
        return ics(self.lees(van, tot), self.k)


class GoogleKalender(Kalender):
    """Adapter voor de gedeelde Google Calendar, via de connector van het platform (later).

    Dezelfde interface als MockKalender. Te bouwen zodra de Raad de agenda heeft aangemaakt en `hr.kalender.kalender_id`
    heeft ingevuld: `lees` = events.list op kalender_id (filter op prefix), `_haal` = events.list met iCalUID,
    `_bewaar` = events.import (iCalUID = uid, zodat dubbele events onmogelijk zijn). De tool-gateway
    (`Beleidsmotor.gebruik_bron(agent, 'gcal', 'rw')`) toetst elke aanroep. Er wordt hier geen toegang toegevoegd."""

    MELDING = ("De gedeelde Google Calendar is nog niet gekoppeld. Gebruik hr.kalender.bron = mock of ics; "
               "zie README.md, 'Gedeelde agenda koppelen'.")

    def lees(self, van, tot):
        raise NotImplementedError(self.MELDING)

    def _haal(self, uid_):
        raise NotImplementedError(self.MELDING)

    def _bewaar(self, e):
        raise NotImplementedError(self.MELDING)


def maak_kalender(inst: dict, pad: pathlib.Path | None = None) -> Kalender:
    bron = instellingen(inst)["bron"]
    if bron == "google":
        return GoogleKalender(inst)
    return (IcsKalender if bron == "ics" else MockKalender)(inst, pad)


# ---------- .ics ----------
def _esc(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def _vouw(regel: str) -> list[str]:
    """Regels langer dan 75 octets vouwen (RFC 5545, 3.1)."""
    uit, b = [], regel.encode("utf-8")
    while len(b) > 75:
        knip = 75 if not uit else 74
        while knip > 0 and (b[knip] & 0xC0) == 0x80:   # niet midden in een UTF-8-teken knippen
            knip -= 1
        uit.append(b[:knip].decode("utf-8"))
        b = b[knip:]
    uit.append(b.decode("utf-8"))
    return [uit[0]] + [" " + x for x in uit[1:]]


def ics(events: list[dict], k: dict) -> str:
    regels = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Tet Tet//Kantoor//NL", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
              f"X-WR-CALNAME:{_esc(k['prefix'].strip('[]') or 'Tet Tet')}"]
    if k.get("tijdzone"):
        regels.append(f"X-WR-TIMEZONE:{k['tijdzone']}")
    for e in events:
        if not e.get("in_agenda"):
            continue
        d = dt.date.fromisoformat(e["datum"])
        u, m = (int(x) for x in (e.get("tijd") or "10:00").split(":"))
        start = dt.datetime(d.year, d.month, d.day, u, m)
        eind = start + dt.timedelta(minutes=int(e.get("duur") or 30))
        f = lambda x: x.strftime("%Y%m%dT%H%M%S")
        tz = f";TZID={k['tijdzone']}" if k.get("tijdzone") else ""
        geannuleerd = e.get("status") == "geannuleerd"
        regels += ["BEGIN:VEVENT", f"UID:{e['uid']}", f"DTSTAMP:{dt.date.fromisoformat(e['gepland']).strftime('%Y%m%d')}T000000Z",
                   f"DTSTART{tz}:{f(start)}", f"DTEND{tz}:{f(eind)}", f"SUMMARY:{_esc(e['titel'])}",
                   f"DESCRIPTION:{_esc(e.get('beschrijving') or beschrijving(e))}", f"CATEGORIES:{_esc(SOORT_NAAM.get(e['soort'], e['soort']))}",
                   f"STATUS:{'CANCELLED' if geannuleerd else 'CONFIRMED'}",
                   f"SEQUENCE:{int(e.get('sequence', 0)) + (1 if geannuleerd else 0) + (e['datum'] != e['gepland'])}", "END:VEVENT"]
    regels.append("END:VCALENDAR")
    return "\r\n".join(r2 for r in regels for r2 in _vouw(r)) + "\r\n"
