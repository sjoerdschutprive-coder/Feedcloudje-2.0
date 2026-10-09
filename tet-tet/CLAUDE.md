# Tet Tet – projectbrief voor Claude Code

Tet Tet is een platform waarop AI-agents zelfstandig werken en samen één centraal aangestuurde organisatie vormen. Deze map bevat alles wat je nodig hebt om het te bouwen.

## Namen (overal zo gebruiken)

- **Raad**: de mens (Sjoerd). Stelt de doelstelling, mandaten en budgetten vast; keurt onomkeerbare acties goed.
- **Oppertet**: centrale orchestrator. Vertaalt de doelstelling naar afdelingsdoelen en budget.
- **Hoofdtet**: hoofd van een afdeling. Verdeelt werk, accordeert output.
- **Tet**: uitvoerende agent. Nooit "uitvoerder".
- **Control Tet**: onafhankelijke controle-agent (valt onder Risk & Safety). Nooit "evaluator".
- **Afdelingen** (ids): `ops` Operations, `fin` Finance, `mkt` Marketing, `rnd` R&D, `hr` HR, `risk` Risk & Safety, `prod` Product.
- **Brein**: het gedeelde geheugen.

## Bronnen en rangorde

Bij tegenstrijdigheid wint de hogere bron.

1. `kaarten/` (v1.1.0): cultuur-, profiel-, rol- en toegangskaarten van alle 21 agents. Leidend voor wie de agents zijn en wat ze mogen. Controleer met `python tet-tet/scripts/valideer_kaarten.py`.
2. `WHITEPAPER.md`: architectuur, taakcontract, feedbackloops, governance, autonomieniveaus, KPI's en de bouwstappen. **De pilotcasus (hotelketen) en bijlagen A–C zijn verouderde voorbeelden**: gebruik de kaarten in `kaarten/` en bouw niets dat aan die casus vastzit.
3. `kantoor/index.html`: het Tet Tet-kantoor, de referentie voor design en interactie van de interface (isometrisch kantoor, afdelingseilanden, doelstellingenbord, takenpaneel, kaarten per agent). De data in dat bestand is afgeleid van de kaarten.
4. `ONDERZOEK.md`: onderbouwing van de `werkstijl`-velden en `edge_principes`.

## Uitgangspunt: doelstelling-onafhankelijk

- Er zit geen opdracht in de code of de kaarten. De Raad stelt een doelstelling in via het platform (naam, omschrijving, deadline).
- De Oppertet maakt daaruit afdelingsdoelen en hoofdlijnen; die vullen per agent het blok `opdracht` in de profielkaart (doelstelling, deliverables, deadline).
- Na afsluiten van een doelstelling blijven organisatie, kaarten en geleerde lessen bestaan; alleen `opdracht` en afdelingsdoelen worden leeg.
- `klantsysteem` in de toegangskaarten is het kernsysteem van de opdrachtgever en wordt per doelstelling gekoppeld.

## Volgende fase: de agents inbouwen

Werk in deze volgorde; elke stap is pas klaar met groene tests. Details per stap staan in de sectie *Bouwopdracht voor Claude Code* van de whitepaper.

1. **Kaartenlader**: laadt en valideert `kaarten/`, stelt per agent de instructies samen (harde grenzen → organisatie → afdeling → profiel → taakcontract) en berekent effectieve toegang (doorsnede van rolkaart, toegangskaart en profielmandaat).
2. **Agent-runtime**: Anthropic Python SDK, met een mockmodus zonder API-aanroepen voor tests. Model, sleutel en budgetlimieten via configuratie. De velden onder `werkstijl` gaan letterlijk in de systeemprompt.
3. **Taken en grootboek**: taakcontract, takenmarkt, statussen, escalatie, en een onveranderlijk eventlog met per event agent, taak, kaartversies en kosten.
4. **De keten**: Raad → Oppertet → Hoofdtet → Tet → Control Tet, met de taakloop en afdelingsloop actief. Begin met één afdeling en twee agents; schaal pas op als het werkt.
5. **Kantoor koppelen**: de interface uit `kantoor/index.html` leest live uit het platform in plaats van uit localStorage.

## Werkafspraken

- Leg een kort plan per stap voor en vraag akkoord bij afwijkingen van de whitepaper.
- Niets organisatie-specifieks in code: alles komt uit `kaarten/` en `config/`.
- Geen externe communicatie, betalingen of echte persoonsgegevens; dat vraagt altijd akkoord van de Raad.
- Taal: interface, kaarten en logteksten in het Nederlands.
- Wijzig je een kaart, verhoog dan `versie` en draai de validator.
