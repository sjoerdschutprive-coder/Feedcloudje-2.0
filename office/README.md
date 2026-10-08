# Tet Tet-kantoor

Interactief, isometrisch kantoor voor de Tet Tet-organisatie (pilot: consultancyadvies Stichtse Hotelgroep).
Open `index.html` in een browser; er is geen build of server nodig.

## Werking

- **Het kantoor** vult het hele scherm. Zoom met scrollen, knijpen of de knoppen rechtsonder en sleep om te verschuiven. Ver ingezoomd verschijnen de namen van de agents bij hun bureau. De knop **?** toont de legenda.
- **Doelstellingenbord** bij het Brein: de voortgang van de hele pilot, de dagen tot de deadline en drie KPI's. Klik erop voor alle KPI's.
- **Klik op een eiland** en je gaat naar de pagina van die afdeling, met tegels voor Team, Cultuurkaart, Toegangskaart, Directe lijnen, Taken, Berichten, Rollen en Geschiedenis. Een tegel toont alleen de kern. Tik erop voor de volledige kaart.
- **Klik op een bureau** (of kies iemand onder Team) voor de pagina van een agent, met Profielkaart, Cultuurkaarten, Rolkaart, Toegangskaart, Taken en Geschiedenis.
- **Klik op het midden** voor Oppertet & Brein, met het volledige doelstellingenbord, alle taken, berichten die op de Oppertet wachten en wat op de Raad wacht.
- **Klik op een directe lijn** voor de kanaalkaart: het doel, de spelregels en de berichten. De onderbouwing staat in [ANALYSE-afdelingscommunicatie.md](ANALYSE-afdelingscommunicatie.md).

Taken en berichten worden lokaal in de browser bewaard.

Elke pagina heeft een eigen adres (`#fin`, `#agent-fin-1`, `#oppertet`, `#lijn-fin-prod`), zodat je er direct naartoe kunt linken.

## Kaarten en KPI's aanpassen

Alle data staat bovenin het script, in het blok `DATA`:

| Object | Wat |
|---|---|
| `PILOT` | Doelstelling en deadline van het project |
| `KPIS`, `BORD_KPIS` | KPI's op het doelstellingenbord (voorlopige set) en welke drie op het bord in het kantoor staan |
| `CULTUUR_ORG` | Cultuurkaart organisatie (laag 1, waarden winnen) |
| `DEPTS[].cultuur` | Cultuurkaart per afdeling (laag 2) |
| `AGENTS` | Profielkaart per agent (laag 3; `inperking` kan rechten alleen beperken) |
| `ROLKAARTEN` | Rolkaarten: Oppertet, Hoofdtet, Tet, Control Tet |
| `DEPTS[].toegang` | Toegangskaart per afdeling (`rw`, `r`, `no`) |
| `KANALEN`, `SPELREGELS` | Directe lijnen tussen afdelingen en de spelregels |

De inhoud is fictief en bedoeld om later te vervangen door de echte kaarten uit de whitepaper.
