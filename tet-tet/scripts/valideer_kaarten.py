"""Valideert alle Tet Tet-kaarten: schema, verwijzingen, overerving en mandaat.

Gebruik:  python tet-tet/scripts/valideer_kaarten.py
Vereist:  pip install pyyaml jsonschema
"""
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from tettet.validatie import valideer  # noqa: E402

NAMEN = [("cultuurkaart_organisatie", "organisatiekaart"), ("cultuurkaart_afdeling", "afdelingskaarten"),
         ("profielkaart", "profielkaarten"), ("rolkaart", "rolkaarten"), ("toegangskaart_afdeling", "toegangskaarten")]

if __name__ == "__main__":
    kaarten, fouten = valideer()
    n = Counter(k["type"] for k in kaarten.values())
    print(", ".join(f"{n[t]} {naam}" for t, naam in NAMEN))
    if fouten:
        print("\n".join(f"FOUT  {f}" for f in fouten))
        sys.exit(1)
    print("Alle kaarten geldig.")
