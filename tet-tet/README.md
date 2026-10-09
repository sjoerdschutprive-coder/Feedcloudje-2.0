# Tet Tet: kaarten

Kaarten voor alle agents van het Tet Tet-kantoor, klaar om door Claude Code te laten inlezen. De specificatie staat in de whitepaper *Tet Tet: De Agentische Organisatie*; de agents en afdelingen komen uit het artifact *Tet Tet-kantoor*.

## Inhoud

```text
tet-tet/
  kaarten/
    schema/kaarten.schema.json   # JSON Schema voor alle kaarttypes
    organisatie/tet-tet.yaml     # cultuurkaart organisatie (laag 1)
    afdelingen/<afdeling>.yaml   # 7 cultuurkaarten afdeling (laag 2)
    agents/<agent-id>.yaml       # 31 profielkaarten (laag 3); allemaal ingezet, ook de Assistent-Oppertet
    rollen/<rol>.yaml            # 5 rolkaarten: wat een rol mag en waar hij staat in de lijn (`niveau`)
    toegang/<afdeling>.yaml      # 8 toegangskaarten: tools en data per afdeling, plus centraal
    handboek/<onderdeel>.yaml    # het handboek: werkwijze, schrijfstijl, woordenlijst, huisstijl, mappenstructuur
    ijkset/<rol>.yaml            # vaste ijktaken per rol voor pass^k (betrouwbaarheid)
  config/                        # instellingen (model, budget) en harde grenzen (beleid.yaml)
  tettet/                        # het platform: kaartenlader, grootboek, Brein, beleid, taken, agents, keten, samenwerking, HR
  tests/                         # tests, draaien zonder API-sleutel
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

## De lijn

```text
Raad
 └─ Oppertet (orchestrator)
     └─ Assistent-Oppertet (directie; telt pas mee als hij is ingezet)
         └─ 7 Hoofdtets
             └─ Tets          (Control Tets onder Risk & Safety, buiten de lijn)
```

- `niveau` in de rolkaart legt de rangorde vast (1 = Oppertet). De validator controleert dat iedereen aan een hoger niveau rapporteert, dat er geen cirkels zijn, dat er hoogstens één Assistent-Oppertet is met toegang binnen die van de Oppertet, en dat geen rol lager in de lijn een handeling heeft die `voorbehouden` is aan een hogere rol.
- De Hoofdtets houden `rapporteert_aan: oppertet` in hun kaart. Zodra de Assistent-Oppertet is ingezet, rapporteren ze aan hem (`Organisatie.leidinggevende`), met een **directe lijn** naar de Oppertet voor risico's, integriteit en onenigheid (`directe_lijn` in `config/beleid.yaml`).
- De assistent is ingezet sinds 9 oktober 2026. Terug naar de oude lijn: zet `inzet: gepland` in `kaarten/agents/oppertet-a.yaml`, verhoog de versie, draai de validator en `scripts/bouw_kantoor.py`. De Oppertet-pagina vergelijkt vóór en na het inzetten.

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

## Gedeelde agenda koppelen

De HR-momenten (check-ins, evaluaties, kalibratie, raadsreview, MT, retrospectief, proefperiodes en incidenten) staan in een gedeelde agenda. Tot die bestaat, plant de werkdag ze in de collectie `kalender` van het kantoor; zo koppel je de echte Google-agenda:

1. **Agenda aanmaken.** Maak in Google Calendar een nieuwe agenda, bijvoorbeeld "Tet Tet", en deel hem met wie hem moet zien. Zet hem op dezelfde tijdzone als `hr.kalender.tijdzone`.
2. **Instellingen invullen.** Zet in `config/instellingen.yaml` onder `hr.kalender`: `tijdzone` (bijv. `Europe/Amsterdam`), `startdatum` (werkdag 1) en `kalender_id` (Instellingen van de agenda → *Agenda-ID*). Commit en draai `python scripts/bouw_kantoor.py`, zodat het kantoor een link naar de agenda toont.
3. **.ics importeren.** Maak het bestand met `python -m tettet agenda --ics tet-tet-agenda.ics` (of `--dump <map>` met een dump van het kantoor, dan gaan verplaatsingen en annuleringen mee), of gebruik op de HR-pagina *Evaluatiekalender → Exporteer naar agenda* (het kantoor slaat het op als `.txt`: hernoem naar `.ics`). Importeer in Google Calendar via *Instellingen → Importeren* in de nieuwe agenda. Opnieuw importeren levert geen dubbele events op: elke UID is vast.
4. **Verplaatsen en annuleren.** Doe dat in het kantoor (HR → Evaluatiekalender): de werkdag volgt het nieuwe tijdstip, een geannuleerd moment komt niet terug. Exporteer daarna opnieuw.
5. **Later: de connector.** Zet `hr.kalender.bron` op `google` zodra `GoogleKalender` in `tettet/kalender.py` is uitgebouwd via de Google Calendar-connector (zelfde interface; elke aanroep via `Beleidsmotor.gebruik_bron(agent, 'gcal', 'rw')`). Dan is de gedeelde agenda leidend voor het tijdstip en is exporteren niet meer nodig.

In de agenda staat nooit inhoud uit een HR-dossier: alleen soort, deelnemers en verwijzingen.

## Opdracht voor Claude Code

> Lees `tet-tet/kaarten/` in volgens de sectie *Cultuur- en profielkaarten* en *Rol- en toegangskaarten* van de whitepaper. Bouw een kaartenlader die elke kaart valideert met `kaarten.schema.json` en `valideer_kaarten.py`, de instructies per agent samenstelt in de volgorde hierboven, en de effectieve toegang berekent als doorsnede van rolkaart, toegangskaart en profielmandaat. Neem de velden onder `werkstijl` letterlijk op in de systeemprompt van elke agent en vul `meetwaarden` vanuit het grootboek.

Alle kaarten zijn generieke startversies (status `concept`), los van een specifieke doelstelling. Per doelstelling vul je alleen het blok `opdracht` in de profielkaarten in (doelstelling, deliverables, deadline); de rest van de kaarten blijft gelijk.

`klantsysteem` in de toegangskaarten staat voor het kernsysteem van de opdrachtgever (bijvoorbeeld een CRM, ERP of reserveringssysteem) en wordt per doelstelling gekoppeld.
