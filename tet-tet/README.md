# Tet Tet: kaarten

Kaarten voor alle agents van het Tet Tet-kantoor, klaar om door Claude Code te laten inlezen. De specificatie staat in de whitepaper *Tet Tet: De Agentische Organisatie*; de agents en afdelingen komen uit het artifact *Tet Tet-kantoor*.

## Inhoud

```text
tet-tet/
  kaarten/
    schema/kaarten.schema.json   # JSON Schema voor alle kaarttypes
    organisatie/tet-tet.yaml     # cultuurkaart organisatie (laag 1)
    afdelingen/<afdeling>.yaml   # 7 cultuurkaarten afdeling (laag 2)
    agents/<agent-id>.yaml       # 21 profielkaarten (laag 3)
    rollen/<rol>.yaml            # 4 rolkaarten: wat een rol mag
    toegang/<afdeling>.yaml      # 7 toegangskaarten: tools en data per afdeling
  scripts/valideer_kaarten.py    # controleert schema, verwijzingen en mandaten
  kantoor/index.html             # het Tet Tet-kantoor (interface-referentie)
  WHITEPAPER.md                  # de whitepaper als Markdown
  CLAUDE.md                      # projectbrief en bouwvolgorde voor Claude Code
  ONDERZOEK.md                   # onderbouwing van de 'edge'-kenmerken, met bronnen
```

Afdelings-ids: `ops` Operations, `fin` Finance, `mkt` Marketing, `rnd` R&D, `hr` HR, `risk` Risk & Safety, `prod` Product.

## Hoe de kaarten samenwerken

Bij elke taak stelt het platform de instructies van een agent samen in deze volgorde:

1. harde grenzen en beleid
2. cultuurkaart organisatie
3. cultuurkaart afdeling (`erft_van`)
4. profielkaart van de agent
5. taakcontract

- **Waarden:** het hogere niveau wint. Een afdelingskaart mag een waarde aanscherpen, nooit afzwakken.
- **Werkwijze:** het lagere niveau wint; de profielkaart is het meest specifiek.
- **Toegang:** alleen wat in rolkaart, toegangskaart én profielmandaat is toegestaan. Het mandaat in een profielkaart kan alleen inperken.

## Kaarten toevoegen of wijzigen

- Nieuw bestand in de juiste map, zelfde velden als de bestaande kaarten.
- Eigen kenmerken onder `kenmerken:`; daar mag alles in, zonder het schema aan te passen.
- Verhoog `versie` bij elke wijziging en zet `status` op `actief` na akkoord van de Raad.
- `opdracht` vul je per doelstelling; leeg laten mag.
- `meetwaarden` (reputatie, stabiliteitsscore, kwaliteitsscore) worden door het platform gevuld.

Controleer daarna:

```bash
pip install pyyaml jsonschema
python tet-tet/scripts/valideer_kaarten.py
```

## Opdracht voor Claude Code

> Lees `tet-tet/kaarten/` in volgens de sectie *Cultuur- en profielkaarten* en *Rol- en toegangskaarten* van de whitepaper. Bouw een kaartenlader die elke kaart valideert met `kaarten.schema.json` en `valideer_kaarten.py`, de instructies per agent samenstelt in de volgorde hierboven, en de effectieve toegang berekent als doorsnede van rolkaart, toegangskaart en profielmandaat. Neem de velden onder `werkstijl` letterlijk op in de systeemprompt van elke agent en vul `meetwaarden` vanuit het grootboek.

Alle kaarten zijn generieke startversies (status `concept`), los van een specifieke doelstelling. Per doelstelling vul je alleen het blok `opdracht` in de profielkaarten in (doelstelling, deliverables, deadline); de rest van de kaarten blijft gelijk.

`klantsysteem` in de toegangskaarten staat voor het kernsysteem van de opdrachtgever (bijvoorbeeld een CRM, ERP of reserveringssysteem) en wordt per doelstelling gekoppeld.
