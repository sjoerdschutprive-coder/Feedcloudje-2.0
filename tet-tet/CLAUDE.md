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

1. `kaarten/` (organisatiekaart v1.3.0): cultuur-, profiel-, rol- en toegangskaarten van alle 30 agents (22 ingezet, 8 `inzet: gepland`), het handboek (`kaarten/handboek/`) en de ijksets per rol (`kaarten/ijkset/`). Leidend voor wie de agents zijn en wat ze mogen. Controleer met `python tet-tet/scripts/valideer_kaarten.py`.
2. `WHITEPAPER.md`: architectuur, taakcontract, feedbackloops, governance, autonomieniveaus, KPI's en de bouwstappen. **De pilotcasus (hotelketen) en bijlagen A–C zijn verouderde voorbeelden**: gebruik de kaarten in `kaarten/` en bouw niets dat aan die casus vastzit.
3. `kantoor/index.html`: het Tet Tet-kantoor, de referentie voor design en interactie van de interface (isometrisch kantoor, afdelingseilanden, doelstellingenbord, takenpaneel, kaarten per agent). De data in dat bestand is afgeleid van de kaarten.
4. `ONDERZOEK.md`: onderbouwing van de `werkstijl`-velden en `edge_principes`.

## Uitgangspunt: doelstelling-onafhankelijk

- Er zit geen opdracht in de code of de kaarten. De Raad stelt een doelstelling in via het platform (naam, omschrijving, deadline).
- De Oppertet maakt daaruit afdelingsdoelen en hoofdlijnen; die vullen per agent het blok `opdracht` in de profielkaart (doelstelling, deliverables, deadline).
- Na afsluiten van een doelstelling blijven organisatie, kaarten en geleerde lessen bestaan; alleen `opdracht` en afdelingsdoelen worden leeg.
- `klantsysteem` in de toegangskaarten is het kernsysteem van de opdrachtgever en wordt per doelstelling gekoppeld.

## Stand van de bouw

Stap 1 t/m 4 zijn gebouwd in `tettet/` met tests (`python -m unittest discover -s tests -t .`, vanuit `tet-tet/`).

| Module | Wat het doet |
| --- | --- |
| `kaarten.py` | Laadt en valideert de kaarten, stelt de systeemprompt samen (harde grenzen → organisatie → afdeling → profiel → rol en toegang), berekent effectieve toegang |
| `validatie.py` | Schema-, verwijzings- en mandaatcontrole (ook gebruikt door `scripts/valideer_kaarten.py`) |
| `grootboek.py` | Onveranderlijk eventlog met hashketen; elk event met agent, taak, kaartversies en kosten |
| `brein.py` | Gedeeld geheugen; lessen na elke taak en na elke afkeuring (zekerheid laag tot de Hoofdtet bevestigt), dubbele lessen samengevoegd (`bevestigd`), gelezen vóór de volgende |
| `beleid.py` | Beleidsmotor (harde grenzen, rolkaart, goedkeuringsinbox), tool-gateway, budgetbewaking |
| `taken.py` | Taakcontract, takenmarkt, statussen, escalatie na `max_afkeuringen` |
| `runtime.py` | `MockClient` (tests, demo) en `AnthropicClient` (echt), de `Agent` die kosten en kaartversies logt |
| `keten.py` | `Kantoor`: Raad → Oppertet → Hoofdtet → Tet → Control Tet; risk-werk gaat naar de Raad |
| `__main__.py` | Opdrachtregel: `run`, `prompt`, `toegang`, `grootboek` |
| `samenwerking.py` | Collectief Brein (toegangslabels, wie-weet-wat, wie-werkt-waaraan, vraagbaak, signalen), kantinetafel, deelfilter, overlegcyclus, cultuurmeting, protocollen |
| `werkdag_samen.py` | Werkdagstappen voor huddle, kantine met toezicht en de overlegcyclus naar het MT |
| `prestatie.py` | Prestatieprofiel per agent (kwaliteit, betrouwbaarheid met pass^k en kalibratie, veiligheid, efficiëntie, samenwerking, stijl), Wilson-intervallen, uitblinker/aandachtspunt, gaming-signalen, blind beoordelen |
| `stijl.py` | Stijlcontrole tegen het handboek (schrijfstijl, woordenlijst): score en suggesties per zin, signalerend |
| `kalender.py` | Rooster van de vaste momenten, de interface `Kalender` (Mock, Ics, Google-vorm), deterministische UID's, .ics-export |
| `hr.py` | Evaluaties normaliseren (doelen met datum en eigenaar, feedback over de taak), onboarding-checklist, Brein-curatie, cultuurkloof, HR-cijfers per afdeling |
| `werkdag_hr.py` | Werkdagstappen voor HR: agenda, snapshot, check-ins, zelfreflectie, evaluaties, kalibratie, incidenten, patroon-oogst, curatie, cultuurbrief |

### Samenwerking (zie ONDERZOEK.md, 'Kenmerken van de samenwerking')

- **Collectief Brein**: elk item draagt `labels` (de bronnen waarop het steunt, uit het blok `## Bronnen` van een resultaat). Wie die bronnen niet mag zien, krijgt het item niet; Risk & Safety (`alle_afdelingsoutput`) ziet alles voor het toezicht. Elke taakprompt bevat lessen, wie weet wat, wie werkt waaraan, open vragen en signalen. Tets kunnen vragen, signalen en antwoorden toevoegen (`## Vragen aan het Brein`, `## Signalen`, `## Antwoorden`).
- **Kantine**: één gemengde tafel per werkdagrun (4–6 agents, minstens 3 afdelingen, roulerend). Elke beurt gaat eerst door het deelfilter en daarna langs de **Privacy-Tet** (`risk-2`); tegengehouden beurten worden zonder inhoud vastgelegd, met een blameless les en strenger toezicht in de volgende pauzes.
- **Overleg**: dagelijkse huddle per afdeling; per week voorbereiding → afdelingsoverleg (memo) → bilateraal → vooraf lezen → eigen oordeel → MT; retrospectief bij het eerste MT van de maand. Instellingen in `config/instellingen.yaml` (`overleg`, `kantine`).
- **Afdelingsomvang**: norm 1 Hoofdtet + 3 Tets. Nieuwe agents staan op `inzet: gepland` tot de Raad ze activeert na een meting; `Organisatie.team()` en `tets()` geven alleen ingezette agents.
- **Kantoor**: kantine en vergaderzaal onder het plein, een overleghoek op elk eiland, agents lopen erheen (veld `plek` in `activiteit`; collecties `kantine` en `overleggen`). Wie een vraag uit de vraagbaak beantwoordt, loopt naar het bureau van de vraagsteller (`beantwoord_ts`). Knop 'Terugkijken' speelt de laatste werkdag af. HR toont de cultuurmeting, Risk & Safety het toezicht met een testknop.

### HR (zie ONDERZOEK.md, 'Kenmerken van de HR-afdeling')

- **Structuur**: Hoofdtet HR (businesspartner), Prestatie-Tet `hr-2` en Governance-Tet `hr-3` (expertisecentra, `inzet: gepland`; tot de Raad ze activeert doet de Hoofdtet HR hun werk), Personeels-Tet `hr-1` (shared services: onboarding, kaarten, vraagbaak). Wie welke HR-rol heeft, volgt uit het specialisme of de naam in de kaart (`kalender.beoordelaar_hr`).
- **Meten**: een profiel per agent, nooit een totaalscore of ranglijst; onder `hr.meting.min_taken` "te weinig data". Grensnaleving is een poortcriterium. Tets geven in `## Zekerheid` een getal 0–1; de werkdag bewaart de eerste oplevering (`zekerheid_eerste`, `zelf_gemeld_eerste`) en het eerste oordeel (`eerste_oordeel`, `claims`). Control Tets beoordelen blind (geen naam, id of afdeling) en negeren lengte. Ijksets: events `ijkset.run` (`data: {ijktaak, geslaagd}`).
- **Toegang**: alles over één agent (`prestaties`, `evaluaties`) draagt `hr-dossier:<agent-id>`: zichtbaar voor de agent zelf, zijn leidinggevende, HR en de Oppertet (`config/beleid.yaml`, `hr_dossier`), niet voor het toezicht, nooit in de kantine.
- **Cyclus en agenda**: zie WERKDAG.md, punt 8, en README.md, 'Gedeelde agenda koppelen'. Instellingen onder `hr:` in `config/instellingen.yaml`. Geen enkel cijfer leidt vanzelf tot een besluit: voorstellen (`soort: "hr"`) gaan naar de Raad.
- **Governance**: het handboek is de enige bron van waarheid; `bouw_kantoor.py` haalt de huisstijltokens uit `huisstijl.yaml`; de validator waarschuwt bij bestanden buiten `mappenstructuur.yaml`.

### Het live kantoor

`kantoor/index.html` is gepubliceerd als artifact (`https://claude.ai/code/artifact/ed7cfae4-f453-4b86-bf01-b9304f737e70`) met de capabilities `db`, `user`, `sample` en `downloads` (export van de agenda):

- **Gedeelde opslag** (`db`): collecties `staat` (doel, instellingen, connectors), `afdelingsdoelen`, `taken`, `berichten`, `brein`, `voorstellen`, `grootboek` (blokken van 100 events), en alleen-toevoegen `overleggen`, `kantine`, `prestaties` en `evaluaties`, en `kalender` (de agenda; de Raad verplaatst of annuleert). Lezen en schrijven kan ook vanuit Claude Code met de ArtifactData-tool.
- **Agents**: modus `mock` (gratis, voorspelbaar) of `claude` (via `sample`, op het Claude-account van de kijker). De keten in de pagina volgt `tettet/keten.py`: dezelfde protocollen en dezelfde samengestelde prompts.
- **Kaarten in het kantoor**: het blok tussen `@@KAARTEN:BEGIN` en `@@KAARTEN:END` wordt gegenereerd door `scripts/bouw_kantoor.py`. Draai dat na elke kaartwijziging en publiceer opnieuw.
- **Live-zicht**: collectie `activiteit` (alleen-toevoegen, per agent wat hij doet); de pagina toont tekstballonnen en het paneel 'Nu bezig'. Werk van buitenaf komt binnen als `patches`; documenten dragen `bijgewerkt` en de nieuwste wint.
- **Werkdag**: zie `WERKDAG.md` en `tettet/werkdag.py`. Een geplande taak laat de agents meerdere keren per dag zelfstandig werken, met subagents per agentbeurt.
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
