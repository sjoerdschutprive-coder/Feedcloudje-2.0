# Tet Tet-kantoor

Interactief, isometrisch kantoor voor de Tet Tet-organisatie (pilot: consultancyadvies Stichtse Hotelgroep).
Open `index.html` in een browser; er is geen build of server nodig.

## Wat je ziet

- **Midden:** de Oppertet en het Brein (gedeeld geheugen), met informatiestromen naar elke afdeling.
- **Zeven afdelingseilanden** in een eigen kleur: Operations, Finance, Marketing, R&D, HR, Risk & Safety en Product. Elk eiland heeft bureaus voor de Hoofdtet (kroontje), de Tets en de Control Tets (rode stippelring).
- **Statuskaart per afdeling:** het aantal agents, een kerncijfer, de stand bezig / volgende / klaar, de voortgang van het advieshoofdstuk en een rode badge als iets wacht op goedkeuring van de Raad.
- **Takenpaneel rechts:** maak een taak aan voor een afdeling of een specifieke Tet. Klik op de status om die door te zetten (volgende → bezig → klaar) en keur taken goed als Raad. De taken worden lokaal in de browser bewaard.
- **Klik op een bureau** voor de profielkaart, de cultuurkaarten (organisatie en afdeling), de rolkaart, de toegangskaart en de geschiedenis. **Klik op een eiland** voor hetzelfde op afdelingsniveau.

## Kaarten aanpassen

Alle data staat bovenin het script, in het blok `DATA`:

| Object | Kaartlaag |
|---|---|
| `CULTUUR_ORG` | Cultuurkaart organisatie (laag 1, waarden winnen) |
| `DEPTS[].cultuur` | Cultuurkaart per afdeling (laag 2) |
| `AGENTS` | Profielkaart per agent (laag 3; `inperking` kan rechten alleen beperken) |
| `ROLKAARTEN` | Rolkaarten: Oppertet, Hoofdtet, Tet, Control Tet |
| `DEPTS[].toegang` | Toegangskaart per afdeling (`rw`, `r`, `no`) |

De inhoud is fictief en bedoeld om later te vervangen door de echte kaarten uit de whitepaper.
