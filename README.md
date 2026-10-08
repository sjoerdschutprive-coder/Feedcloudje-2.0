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

## Wat zie je?

Een opengewerkt kantoorgebouw van bovenaf, in een afgesloten dal.

| Onderdeel | Betekenis |
|---|---|
| **Het dal** | De afgesloten omgeving. Bos eromheen, één poort onderaan. |
| **De manager (UILBERT)** | Eén agent die alle andere agents aanstuurt: verdeelt werk, roept vergaderingen bijeen, regelt de wacht en stuurt vermoeide agents naar de lounge. |
| **Afdelingen** | CODE-LAB, STUDIO, DATABIEB, WERKPLAATS en POORTWACHT. Elke afdeling heeft bureaus waar meerdere agents tegelijk werken. |
| **Vergaderzaal** | In het midden. Elke ochtend om 09:00 is er een stand-up en bij een crisis (firewall < 60%) een crisisoverleg. Iedereen loopt erheen, praat, en loopt terug. |
| **Lounge** | Koffie, zitzakken, 's nachts slapen. |
| **Berichtjes** | Witte envelopjes vliegen van de manager naar een agent (opdracht), gele terug (verslag). Bij grote klussen loopt een agent zelf naar het kantoor van de manager. |
| **Quests** | Taken. Zware quests krijgen een duo. Opdrachten van de baas (jij, ★) gaan voor. |
| **Bugs** | Tijdens het werk kan een wilde bug opduiken. Dan volgt een gevecht. |
| **Firewall** | Staat er niemand op wacht bij de poort, dan komen indringers erdoor. |

## Bediening

- **Klik op een wezentje** (op de kaart of in de TEAM-lijst) voor de dex-kaart.
- **QUESTS → Nieuwe opdracht**: als baas zelf werk uitzetten. De manager verdeelt het met voorrang.
- **VERGADER**: roep zelf een vergadering bijeen.
- **+ WERVEN**: nieuwe medewerker aannemen (200 credits).
- **Spatie**: pauze. **1x/2x/4x/8x**: snelheid. **↺**: opnieuw beginnen.

Voortgang wordt in je browser bewaard (localStorage).

## Structuur

```
index.html      pagina-opbouw
css/style.css   spelstijl (kaders, balken, gevechtsscherm)
js/map.js       plattegrond: ruimtes, bureaus, vergadertafel, routes zoeken
js/sprites.js   pixel-art wezentjes (16x16, gespiegeld getekend)
js/director.js  de manager: kijkt naar de staat en geeft commando's
js/org.js       organisatie-motor: voert commando's uit, beweging, vergaderingen, bugs
js/world.js     tekent de wereld op een canvas
js/ui.js        panelen, dialoogvenster, gevechtsscherm
js/main.js      opstarten en spel-lus
docs/PLAN.md    visie en vervolgstappen
```

Zie [docs/PLAN.md](docs/PLAN.md) voor hoe dit naar een echte organisatie
van AI-agents kan groeien.
