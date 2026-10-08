# Feedcloudje 2.0 — Feedcloudje HQ

Een organisatie in een afgesloten omgeving, te volgen via een dashboard in
retro-handheldspelstijl.

![dal](docs/screenshot.png)

## Starten

Geen installatie nodig. Open `index.html` in je browser, of start een
lokale server:

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

## Hoe de organisatie werkt

```
DE BAAS (jij) ──opdracht──▶ GODFRED ──taken──▶ PRIKBORD ──ophalen──▶ AFDELINGSHOOFD ──verdelen──▶ AGENTS
      ▲                        │  ▲                                        │  ▲                        │
      └──── project af ────────┘  └──── output (goedkeuren of revisie) ────┘  └──── output ────────────┘
```

| Onderdeel | Betekenis |
|---|---|
| **GODFRED** (directeur) | Krijgt jouw opdrachten, knipt ze op in taken per afdeling, hangt ze op het prikbord en beoordeelt de output: goedkeuren of terug voor revisie. Meldt aan jou als een project af is. |
| **Afdelingshoofden** | Eén per afdeling, aan het bureau het dichtst bij de deur. Halen in één keer net genoeg taken van het prikbord voor wie vrij is, verdelen ze, controleren het werk en brengen de output gebundeld naar Godfred. |
| **Agents** | 2 à 3 per afdeling. Werken aan hun eigen bureau en leveren hun output in bij hun hoofd. Ze hoeven zelf niet te lopen voor werk. |
| **Prikbord** | In het midden van het gebouw. Elke kaart is een taak in de kleur van de afdeling (rood hoekje = revisie). |
| **Vergaderzaal** | Regelmatig MT-overleg (Godfred + hoofden). Met **VERGADER** roep je iedereen bijeen. |
| **Lounge** | Pauze en koffie, om energie bij te tanken. |
| **Poort + firewall** | De afgesloten omgeving. Het hoofd van POORTWACHT zorgt dat er altijd iemand op wacht staat. |

Op de kaart zie je het verkeer als vliegende envelopjes: wit = opdracht,
geel = output, rood = revisie, groen = goedgekeurd.

## Bediening

- **PRIKBORD → Opdracht aan Godfred**: geef een titel en omvang. Kies zelf
  een afdeling of laat Godfred beslissen (hij kijkt naar woorden als
  "website", "logo", "onderzoek" en verdeelt grote opdrachten over meerdere
  afdelingen).
- **PRIKBORD**: de hele pijplijn, van concept tot "ligt bij Godfred".
- **OUTPUT**: jouw projecten, en wat Godfred goedkeurde met zijn feedback.
- **Klik op een wezentje** voor de detailkaart.
- **VERGADER**, **+ WERVEN** (200 credits), **spatie** (pauze), **1x–8x**, **↺** (opnieuw).

Voortgang wordt in je browser bewaard (localStorage).

## Structuur

```
index.html      pagina-opbouw
css/style.css   spelstijl (kaders, balken, panelen)
js/map.js       plattegrond: ruimtes, bureaus, prikbord, vergadertafel, routes zoeken
js/sprites.js   pixel-art wezentjes (16x16, gespiegeld getekend)
js/brains.js    de besluitvormers: Godfred en de afdelingshoofden (geven commando's)
js/org.js       organisatie-motor: voert commando's uit, taken, beweging, vergaderingen
js/world.js     tekent de wereld op een canvas
js/ui.js        panelen: team, prikbord, output, logboek, dialoogvenster
js/main.js      opstarten en spel-lus
docs/PLAN.md    visie en vervolgstappen
```

Zie [docs/PLAN.md](docs/PLAN.md) voor hoe dit naar een echte organisatie
van AI-agents kan groeien.
