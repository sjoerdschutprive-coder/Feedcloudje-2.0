# Plan: Feedcloudje HQ

## Het idee

Een organisatie van AI-agents in een **afgesloten omgeving**, met een
duidelijke hiërarchie:

```
SJOERD (jij) → GODFRED (directeur) → AFDELINGSHOOFDEN → AGENTS
```

Jij stuurt alleen Godfred aan. Godfred stuurt de afdelingshoofden aan via
het **prikbord** in het midden van het gebouw. De hoofden sturen hun agents
aan. De output loopt dezelfde weg terug: agent → hoofd (controle) → Godfred
(goedkeuren of revisie) → baas (project af). Dat is de **feedbackloop**.

De vier hoofden heten **Finance Fred, Marketing Fred, Operations Fred en
Strategic Fred** (zie `godfred/profile.md`). Naast hen zitten twee MT-leden
die Godfred ook beoordelen en rechtstreeks aan Sjoerd rapporteren:
**Elsje** (Learning & Development, `elsje/profile.md`) en **RISK FRED**,
de risk & safety officer.
Hij scant ontwikkelwerk op lekken vóór het bij Godfred komt, bewaakt poort en
firewall en adviseert Godfred. Zie [ROLKAARTEN.md](ROLKAARTEN.md).

Agents verdienen **XP** met goedgekeurd werk. XP telt voor hun level en
betaalt het **buffet** in de lounge, waar ze energie bijtanken.

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
   **commando's**. Godfred, elk afdelingshoofd, Risk Fred en Elsje hebben een eigen brein.
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
| Hoofd | `rest` | Agent naar het buffet |
| Risk Fred | `review {taskId}` + `verdict {taskId, verdict, note}` | Security-scan: `veilig` of `lek` |
| Risk Fred | `harden`, `patrol` | Firewall versterken, inspectieronde bij de poort |
| Risk Fred | `advise {note}` | Signaal aan Godfred (leidt tot ad hoc overleg) |
| Risk Fred | `report {title, text}` | Dagelijks rapport aan Sjoerd |
| Elsje | `session {agentId}` | Verbetersessie: agent coachen |
| Elsje | `propose {tool, dept}` | Nieuwe tool voorstellen (eerst scan door Risk Fred) |
| Elsje | `report {title, text}` | Rapport aan Sjoerd over performance en Godfred |

### Levensloop van een taak

`concept` → `bord` → `opgehaald` → `bezig` → `controle` → (`scan`) →
`gecontroleerd` → `onderweg` → `ingeleverd` → `goedgekeurd`.

Drie terugkoppelingen: het hoofd kan een taak terugzetten op zijn stapel
(`beter`), RISK FRED stuurt hem terug bij een lek (`lek`), en Godfred kan
hem terughangen op het prikbord (`revisie`).

### Gebeurtenissen

```json
{ "kind": "feedback", "from": 1, "to": [8], "text": "GODFRED: \"Klantanalyse\" moet over. Graag met concrete cijfers.", "time": "DAG 2 10:15" }
```

Soorten: `opdracht`, `project`, `plan`, `post`, `pickup`, `order`, `output`,
`check`, `scan`, `advies`, `deliver`, `approve`, `feedback`, `meeting`, `rest`,
`snack`, `lnd`, `rapport`, `notulen`, `say`, `security`, `alarm`, `warn`, `info`, `levelup`.

## Fase 1: simulatie (klaar)

- Kantoor met vier afdelingen (Finance, Marketing, Operations, Strategie;
  elk een Fred + 3 agents), directiekamer, centraal prikbord, vergaderzaal,
  lounge met buffet, de poortwacht van Risk Fred en het L&D-gebouwtje van
  Elsje.
- Regelgebaseerde breinen voor Godfred en de hoofden, met de volledige
  keten en beide feedbackloops.
- Kwaliteit per taak (sterren) hangt af van level en revisies.

## Fase 2: echte agents

1. **Godfred wordt een AI-agent.** *(Eerste stap gezet: in het tabblad
   GODFRED praat je met hem via Claude; hij plant zelf de taken. De
   beoordeling van output is nog gesimuleerd.)* Zijn commando's worden zijn *tools*.
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
6. **Energie = budget, XP = verdiend budget.** Energie is hoeveel een agent
   nog mag doen; XP verdient hij met goedgekeurd werk en zet hij in het
   buffet om in nieuw budget. Goed werk levert dus letterlijk ruimte op.
7. **RISK FRED wordt echt:** hij leest code en configuratie op lekken en
   beheert het netwerkbeleid van de container.

### Welk model waarvoor (advies)

| Rol | Model | Waarom |
|---|---|---|
| Godfred | Claude Opus 5.5 | Plant en beoordeelt alles. Kwaliteit telt het zwaarst. |
| Afdelingshoofden | Claude Sonnet 5.5 | Verdelen en controleren binnen één afdeling. |
| RISK FRED | Claude Opus 5.5 | Security-review vraagt grondigheid; een gemist lek is duur. |
| ELSJE | Claude Opus 5.5 | Beoordeelt Godfred en verbetert instructies: daar moet ze minstens zo scherp voor zijn als hij. |
| Agents (denkwerk: code, data) | Claude Sonnet 5.5 | Goed en een stuk goedkoper. Er draaien er veel tegelijk. |
| Agents (simpel/veel: samenvatten, sorteren) | Claude Haiku 5.5 | Zeer goedkoop voor hoog volume. |
| Uitzonderlijk zware klussen | Claude Fable 5.1 | Het krachtigst, maar ruim 2x de prijs van Opus. Alleen gericht inzetten. |

## Fase 3: ideeën

- Goedkeuringen: een agent die iets riskants wil, vraagt het via het
  dialoogvenster aan Sjoerd ("BITBIT wil deployen. JA / NEE").
- Afdelingsoverleg (hoofd + eigen team) naast het MT-overleg.
- Jij als baas kunt een goedgekeurd project alsnog afkeuren: de lus gaat dan
  nog één laag hoger.
- Evolutie: na genoeg levels een nieuwe sprite en meer tools.
- Meerdere verdiepingen of gebouwen = meerdere projecten.

## Open vragen voor Sjoerd

- Wat moet de organisatie in het echt gaan doen?
- Waar draait de afgesloten omgeving: je eigen computer, een server, de cloud?
- Kloppen deze afdelingen, of wil je andere?
