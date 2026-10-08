# Plan: Feedcloudje HQ

## Het idee

Een organisatie van AI-agents in een **afgesloten omgeving**. Eén agent, de
**manager**, stuurt de andere agents aan. Jij bent de baas en volgt alles via
een **dashboard in spelletjesstijl**: een kantoorgebouw van bovenaf, waar je
de agents ziet werken, lopen, vergaderen en rusten, zoals in een echt
bedrijf.

| Spelelement | Wat het in de organisatie betekent |
|---|---|
| Manager (UILBERT) | De orkestrator-agent die werk verdeelt en bewaakt |
| Bureau in een afdeling | Een worker-agent met een specialisme |
| Envelopje heen / terug | Een opdracht van de manager / een verslag terug |
| Vergaderzaal | Overleg: status ophalen, daarna werk verdelen |
| Energie | Capaciteit (later: resterend budget van een agent) |
| Level / XP | Ervaring, afgeronde taken |
| Wilde bug + gevecht | Een fout of incident tijdens het werk |
| Poort + firewall | De grens van de afgesloten omgeving |

## Architectuur

```
            ┌──────────────┐  commando's   ┌──────────────┐  gebeurtenissen  ┌─────────────┐
 staat ───▶ │   MANAGER    │ ────────────▶ │ ORGANISATIE  │ ───────────────▶ │  DASHBOARD  │
            │ director.js  │               │   org.js     │                  │ world/ui.js │
            └──────────────┘               └──────────────┘                  └─────────────┘
                   ▲                              │
                   └──────────── staat ───────────┘
```

Drie lagen, strikt gescheiden:

1. **Manager** (`js/director.js`) kijkt naar de staat en geeft alleen
   **commando's**. Hij verandert zelf niets.
2. **Organisatie** (`js/org.js`) voert commando's uit, laat agents lopen,
   werken en vergaderen, en publiceert **gebeurtenissen**.
3. **Dashboard** (`js/world.js`, `js/ui.js`) luistert alleen naar
   gebeurtenissen en de staat.

De baas (jij) gebruikt dezelfde commando's via de knoppen. Er is dus één
weg om iets in de organisatie te veranderen.

### Commando's (wat de manager kan)

| Commando | Velden | Effect |
|---|---|---|
| `assign` | `questId`, `agentIds[]` | Werk toewijzen aan één of meer agents |
| `meeting` | `topic` | Iedereen naar de vergaderzaal |
| `rest` | `agentId` | Agent naar de lounge |
| `guard` | `agentId` | Agent bij de poort posten |
| `createQuest` | `dept`, `title?`, `difficulty?` | Nieuw werk inplannen |
| `say` | `agentId`, `text` | Tekstballon |

### Gebeurtenissen (wat het dashboard ziet)

```json
{ "kind": "order", "from": 1, "to": [4, 5], "text": "UILBERT → DEX & PIP: \"API koppelen\"", "time": "DAG 2 10:15" }
```

Soorten: `order`, `report`, `plan`, `meeting`, `say`, `quest`, `levelup`,
`bug`, `win`, `lose`, `security`, `alarm`, `recruit`, `warn`, `info`.

## Fase 1: simulatie (klaar)

- Opengewerkt kantoor met vijf afdelingen, een managerkantoor, een centrale
  vergaderzaal, een lounge en een wachthuisje bij de poort.
- Regelgebaseerde manager: dagelijkse stand-up, crisisoverleg, werk
  verdelen (duo's voor zware klussen), wachtrooster, rust geven, backlog
  aanvullen.
- Agents lopen echt over de plattegrond (routes zoeken), zitten aan hun
  eigen bureau, halen koffie, rapporteren bij de manager en slapen 's nachts
  in de lounge.

## Fase 2: echte agents

1. **Manager wordt een AI-agent.** De commando's hierboven worden zijn
   *tools* (`assign_task`, `call_meeting`, `send_to_rest`, `post_guard`,
   `create_task`). De staat van de organisatie gaat als context mee.
   `director.js` wordt dan een dunne laag die de tool-calls van het model
   doorgeeft aan `org.execute()`.
2. **Workers worden AI-agents.** Elke worker krijgt een rol-prompt passend
   bij zijn afdeling en alleen de tools van die afdeling. Een `assign`
   start een echte taak, en het resultaat komt terug als `report`.
3. **Vergaderingen worden echt.** Elke worker levert een korte status in,
   de manager vat samen en verdeelt het werk opnieuw.
4. **Afgesloten omgeving.** Agents draaien in een container zonder vrije
   internettoegang. Het netwerkbeleid is de poort: geblokte verbindingen
   verschijnen als "indringer geblokt".
5. **Eventbus.** Een kleine server stuurt de gebeurtenissen via een
   WebSocket naar het dashboard, in precies het formaat van nu.
6. **Energie = budget.** Hoeveel tokens of kosten een agent nog mag
   gebruiken. Op = naar de lounge.

### Welk model waarvoor (advies)

| Rol | Model | Waarom |
|---|---|---|
| Manager | Claude Opus 5.5 | Beslist over iedereen. Kwaliteit van plannen telt het zwaarst. |
| Workers (denkwerk: code, data) | Claude Sonnet 5.5 | Goed en een stuk goedkoper. Er draaien er veel tegelijk. |
| Workers (simpel/veel: samenvatten, sorteren) | Claude Haiku 5.5 | Zeer goedkoop voor hoog volume. |
| Uitzonderlijk zware klussen | Claude Fable 5.1 | Het krachtigst, maar ruim 2x de prijs van Opus. Alleen gericht inzetten. |

## Fase 3: ideeën

- Goedkeuringen: een agent die iets riskants wil, vraagt het via het
  dialoogvenster aan de baas ("BITBIT wil deployen. JA / NEE").
- Afdelingsoverleg (alleen één team) naast de grote vergadering.
- Evolutie: na genoeg levels een nieuwe sprite en meer tools.
- Meerdere verdiepingen of gebouwen = meerdere projecten.

## Open vragen voor de baas

- Wat moet de organisatie in het echt gaan doen?
- Waar draait de afgesloten omgeving: je eigen computer, een server, de cloud?
- Kloppen deze afdelingen, of wil je andere?
