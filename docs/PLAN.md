# Plan: Feedcloudje HQ

## Het idee

Een organisatie van AI-agents in een **afgesloten omgeving**, met een
duidelijke hiërarchie:

```
DE BAAS (jij) → GODFRED (directeur) → AFDELINGSHOOFDEN → AGENTS
```

Jij stuurt alleen Godfred aan. Godfred stuurt de afdelingshoofden aan via
het **prikbord** in het midden van het gebouw. De hoofden sturen hun agents
aan. De output loopt dezelfde weg terug: agent → hoofd (controle) → Godfred
(goedkeuren of revisie) → baas (project af). Dat is de **feedbackloop**.

Je volgt alles via een dashboard in retro-spelstijl: een kantoorgebouw van
bovenaf waar je ziet wie werkt, wie taken ophaalt en wie output brengt.

## Architectuur

```
            ┌──────────────────────┐  commando's   ┌──────────────┐  gebeurtenissen  ┌─────────────┐
 staat ───▶ │ BREINEN (brains.js)  │ ────────────▶ │ ORGANISATIE  │ ───────────────▶ │  DASHBOARD  │
            │ Godfred + hoofden    │               │   org.js     │                  │ world/ui.js │
            └──────────────────────┘               └──────────────┘                  └─────────────┘
```

1. **Breinen** (`js/brains.js`) kijken naar de staat en geven alleen
   **commando's**. Godfred heeft één brein, elk afdelingshoofd een eigen.
2. **Organisatie** (`js/org.js`) controleert of iemand een commando mag geven
   (een hoofd kan alleen zijn eigen team aansturen), voert het uit, laat
   iedereen lopen en publiceert **gebeurtenissen**.
3. **Dashboard** (`js/world.js`, `js/ui.js`) luistert alleen.

### Commando's

| Wie | Commando | Effect |
|---|---|---|
| Baas | `order {title, dept?, difficulty}` | Opdracht aan Godfred |
| Baas | `meeting`, `rest` | Algemene vergadering, agent naar pauze |
| Godfred | `plan {projectId}` | Opdracht opknippen in taken per afdeling |
| Godfred | `initiative {dept}` | Zelf werk bedenken |
| Godfred | `post` | Naar het prikbord lopen en taken ophangen |
| Godfred | `review {taskId}` + `feedback {taskId, verdict, note}` | Output beoordelen: `goed` of `revisie` |
| Godfred | `meeting {scope: 'mt'|'alle'}` | Overleg |
| Hoofd | `pickup {count}` | Taken van het prikbord halen |
| Hoofd | `assign {taskId, agentId}` | Taak aan een agent geven |
| Hoofd | `review {taskId}` + `check {taskId, verdict, note}` | Werk controleren: `ok` of `beter` |
| Hoofd | `deliver` | Gecontroleerde output naar Godfred brengen |
| Hoofd | `rest`, `guard` | Agent naar pauze, agent op wacht |

### Levensloop van een taak

`concept` → `bord` → `opgehaald` → `bezig` → `controle` → `gecontroleerd`
→ `onderweg` → `ingeleverd` → `goedgekeurd`.

Twee terugkoppelingen: het hoofd kan een taak terugzetten op zijn stapel
(`beter`), Godfred kan hem terughangen op het prikbord (`revisie`).

### Gebeurtenissen

```json
{ "kind": "feedback", "from": 1, "to": [8], "text": "GODFRED: \"Klantanalyse\" moet over. Graag met concrete cijfers.", "time": "DAG 2 10:15" }
```

Soorten: `opdracht`, `project`, `plan`, `post`, `pickup`, `order`, `output`,
`check`, `deliver`, `approve`, `feedback`, `meeting`, `rest`, `say`,
`security`, `alarm`, `recruit`, `warn`, `info`, `levelup`.

## Fase 1: simulatie (klaar)

- Kantoor met vijf afdelingen (elk een hoofd + 2 à 3 agents), directiekamer,
  centraal prikbord, vergaderzaal, lounge en poortwacht.
- Regelgebaseerde breinen voor Godfred en de hoofden, met de volledige
  keten en beide feedbackloops.
- Kwaliteit per taak (sterren) hangt af van level en revisies.

## Fase 2: echte agents

1. **Godfred wordt een AI-agent.** Zijn commando's worden zijn *tools*.
   `brains.js` stuurt dan de staat naar het model en geeft de tool-calls
   door aan `org.execute()`. Het beoordelen (`feedback`) wordt echt: Godfred
   leest de output en legt de lat.
2. **Afdelingshoofden worden AI-agents** met hun eigen, kleinere set tools
   en alleen zicht op hun eigen afdeling.
3. **Agents worden AI-agents.** Een `assign` start een echte taak; het
   resultaat is de output die door de keten terugloopt.
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
| Godfred | Claude Opus 5.5 | Plant en beoordeelt alles. Kwaliteit telt het zwaarst. |
| Afdelingshoofden | Claude Sonnet 5.5 | Verdelen en controleren binnen één afdeling. |
| Agents (denkwerk: code, data) | Claude Sonnet 5.5 | Goed en een stuk goedkoper. Er draaien er veel tegelijk. |
| Agents (simpel/veel: samenvatten, sorteren) | Claude Haiku 5.5 | Zeer goedkoop voor hoog volume. |
| Uitzonderlijk zware klussen | Claude Fable 5.1 | Het krachtigst, maar ruim 2x de prijs van Opus. Alleen gericht inzetten. |

## Fase 3: ideeën

- Goedkeuringen: een agent die iets riskants wil, vraagt het via het
  dialoogvenster aan de baas ("BITBIT wil deployen. JA / NEE").
- Afdelingsoverleg (hoofd + eigen team) naast het MT-overleg.
- Jij als baas kunt een goedgekeurd project alsnog afkeuren: de lus gaat dan
  nog één laag hoger.
- Evolutie: na genoeg levels een nieuwe sprite en meer tools.
- Meerdere verdiepingen of gebouwen = meerdere projecten.

## Open vragen voor de baas

- Wat moet de organisatie in het echt gaan doen?
- Waar draait de afgesloten omgeving: je eigen computer, een server, de cloud?
- Kloppen deze afdelingen, of wil je andere?
