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

## Stand van de bouw

Stap 1 t/m 4 zijn gebouwd in `tettet/` met 23 tests (`python -m unittest discover -s tests -t .`, vanuit `tet-tet/`).

| Module | Wat het doet |
| --- | --- |
| `kaarten.py` | Laadt en valideert de kaarten, stelt de systeemprompt samen (harde grenzen → organisatie → afdeling → profiel → rol en toegang), berekent effectieve toegang |
| `validatie.py` | Schema-, verwijzings- en mandaatcontrole (ook gebruikt door `scripts/valideer_kaarten.py`) |
| `grootboek.py` | Onveranderlijk eventlog met hashketen; elk event met agent, taak, kaartversies en kosten |
| `brein.py` | Gedeeld geheugen; lessen na elke taak, gelezen vóór de volgende |
| `beleid.py` | Beleidsmotor (harde grenzen, rolkaart, goedkeuringsinbox), tool-gateway, budgetbewaking |
| `taken.py` | Taakcontract, takenmarkt, statussen, escalatie na `max_afkeuringen` |
| `runtime.py` | `MockClient` (tests, demo) en `AnthropicClient` (echt), de `Agent` die kosten en kaartversies logt |
| `keten.py` | `Kantoor`: Raad → Oppertet → Hoofdtet → Tet → Control Tet; risk-werk gaat naar de Raad |
| `__main__.py` | Opdrachtregel: `run`, `prompt`, `toegang`, `grootboek` |

### Het live kantoor

`kantoor/index.html` is gepubliceerd als artifact (`https://claude.ai/code/artifact/ed7cfae4-f453-4b86-bf01-b9304f737e70`) met de capabilities `db`, `user` en `sample`:

- **Gedeelde opslag** (`db`): collecties `staat` (doel, instellingen, connectors), `afdelingsdoelen`, `taken`, `berichten`, `brein`, `voorstellen` en `grootboek` (blokken van 100 events). Lezen en schrijven kan ook vanuit Claude Code met de ArtifactData-tool.
- **Agents**: modus `mock` (gratis, voorspelbaar) of `claude` (via `sample`, op het Claude-account van de kijker). De keten in de pagina volgt `tettet/keten.py`: dezelfde protocollen en dezelfde samengestelde prompts.
- **Kaarten in het kantoor**: het blok tussen `@@KAARTEN:BEGIN` en `@@KAARTEN:END` wordt gegenereerd door `scripts/bouw_kantoor.py`. Draai dat na elke kaartwijziging en publiceer opnieuw.
- **Zelfontwikkeling**: zie `ZELFONTWIKKELING.md`. Een dagelijkse geplande taak bouwt de door de Raad goedgekeurde verbetervoorstellen in.

Nog te bouwen, in deze volgorde:

1. **Echte tools achter de tool-gateway**: Brein-zoeken, webzoeken en rekenmodule eerst, daarna connectors. Elke tool-aanroep via `Beleidsmotor.gebruik_bron`.
2. **Kantoor koppelen**: een kleine API (FastAPI) boven `Kantoor`, en `kantoor/index.html` leest live daaruit in plaats van uit localStorage. De goedkeuringsinbox wordt daar bedienbaar.
3. **Afdelingsloop en organisatieloop**: verslag per afdeling met KPI's uit het grootboek; reputatie- en stabiliteitsscore in `meetwaarden`.

## Draaien

```bash
cd tet-tet
pip install -r requirements.txt
python -m tettet run "Naam van de doelstelling" --deadline 2026-12-31 --afdelingen fin,mkt   # mockmodus
python -m tettet prompt fin-1      # samengestelde systeemprompt van een agent
python -m tettet toegang fin-1     # effectieve toegang
ANTHROPIC_API_KEY=... python -m tettet run "..." --afdelingen fin --echt --opslaan        # echte agents
```

Begin met `--echt` op één afdeling. Controleer de prijzen in `config/instellingen.yaml` voordat je dat doet: de budgetbewaking rekent ermee.

## Werkafspraken

- Leg een kort plan per stap voor en vraag akkoord bij afwijkingen van de whitepaper.
- Niets organisatie-specifieks in code: alles komt uit `kaarten/` en `config/`.
- Geen externe communicatie, betalingen of echte persoonsgegevens; dat vraagt altijd akkoord van de Raad.
- Taal: interface, kaarten en logteksten in het Nederlands.
- Wijzig je een kaart, verhoog dan `versie` en draai de validator.
