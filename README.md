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

| Onderdeel | Betekenis |
|---|---|
| **Het dal** | De afgesloten omgeving. Omringd door bos, met één poort onderaan. |
| **Gebouwen** | Afdelingen: HQ (strategie), LAB (code), STUDIO (creatief), BIEB (data), WERK (operations), POORT (beveiliging), RUST (herstel). |
| **Wezentjes** | Medewerkers. Elk heeft een type, level, XP en energie. |
| **Quests** | Taken. Medewerkers pakken ze zelf op, het liefst in hun eigen afdeling. Afronden levert XP en credits op. |
| **Bugs** | Tijdens het werk kan er een wilde bug verschijnen. Dan volgt een gevecht. |
| **Firewall** | Hoe goed de omgeving dicht zit. Staat er niemand op wacht bij de poort, dan komen indringers erdoor en daalt de firewall. |
| **Dag/nacht** | 's Nachts slaapt het team in het HERSTELHUIS. De beveiliging blijft op wacht. |

## Bediening

- **Klik op een wezentje** (op de kaart of in de TEAM-lijst) voor de dex-kaart.
- **QUESTS → Nieuwe opdracht**: als baas zelf werk uitzetten. Jouw opdrachten (★) gaan voor.
- **+ WERVEN**: nieuwe medewerker aannemen (200 credits).
- **Spatie**: pauze. **1x/2x/4x/8x**: snelheid. **↺**: opnieuw beginnen.

Voortgang wordt in je browser bewaard (localStorage).

## Structuur

```
index.html      pagina-opbouw
css/style.css   spelstijl (kaders, balken, gevechtsscherm)
js/map.js       kaart, gebouwen, routes zoeken
js/sprites.js   pixel-art wezentjes (16x16, gespiegeld getekend)
js/org.js       organisatie-motor: medewerkers, quests, bugs, beveiliging
js/world.js     tekent de wereld op een canvas
js/ui.js        panelen, dialoogvenster, gevechtsscherm
js/main.js      opstarten en spel-lus
docs/PLAN.md    visie en vervolgstappen
```

Zie [docs/PLAN.md](docs/PLAN.md) voor hoe dit naar een echte organisatie
van AI-agents kan groeien.
