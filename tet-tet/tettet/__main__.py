"""Opdrachtregel voor Tet Tet.

  python -m tettet run "Naam doelstelling" --omschrijving "..." --deadline 2026-12-18 --afdelingen fin,mkt [--echt] [--opslaan]
  python -m tettet prompt fin-1        # toont de samengestelde systeemprompt van een agent
  python -m tettet toegang fin-1       # toont de effectieve toegang van een agent
  python -m tettet grootboek           # controleert de hashketen van het opgeslagen grootboek
"""
import argparse
import sys

from . import BASIS
from .grootboek import Grootboek
from .kaarten import RECHT, Organisatie
from .keten import Doelstelling, Kantoor
from .runtime import laad_instellingen


def main(argv=None):
    p = argparse.ArgumentParser(prog="tettet")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="draai een doelstelling door de hele keten")
    r.add_argument("naam")
    r.add_argument("--omschrijving", default="")
    r.add_argument("--deadline")
    r.add_argument("--afdelingen", help="komma-gescheiden ids, bv. fin,mkt (standaard: alle)")
    r.add_argument("--echt", action="store_true", help="gebruik de Anthropic API in plaats van de mockmodus")
    r.add_argument("--opslaan", action="store_true", help="bewaar grootboek en Brein in data/")
    for naam in ("prompt", "toegang"):
        s = sub.add_parser(naam)
        s.add_argument("agent")
    sub.add_parser("grootboek")
    a = p.parse_args(argv)

    if a.cmd == "run":
        kantoor = Kantoor(mock=not a.echt, opslaan=a.opslaan)
        afdelingen = a.afdelingen.split(",") if a.afdelingen else None
        print(kantoor.draai(Doelstelling(a.naam, a.omschrijving, a.deadline), afdelingen))
    elif a.cmd == "prompt":
        print(Organisatie().systeemprompt(a.agent))
    elif a.cmd == "toegang":
        t = Organisatie().effectieve_toegang(a.agent)
        print("\n".join(f"{b}: {RECHT[v]}" for b, v in sorted(t.bronnen.items())))
        if t.regels:
            print("\nRegels:\n" + "\n".join(f"- {x}" for x in t.regels))
    elif a.cmd == "grootboek":
        gb = Grootboek(BASIS / laad_instellingen()["opslag"]["grootboek"])
        fouten = gb.controleer()
        print(f"{len(gb.events)} events, " + ("keten intact" if not fouten else "\n".join(fouten)))
        sys.exit(1 if fouten else 0)


if __name__ == "__main__":
    main()
