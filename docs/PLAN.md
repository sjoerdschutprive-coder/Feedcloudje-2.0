# Plan: Feedcloudje HQ

## Het idee

Een organisatie die bestaat uit (AI-)medewerkers in een **afgesloten
omgeving**. Jij bent de baas. Je volgt alles via een **dashboard in
spelletjesstijl**: de organisatie is een dal, de afdelingen zijn gebouwen,
de medewerkers zijn wezentjes die levelen, en problemen zijn "wilde bugs"
waar tegen gevochten wordt.

Het spelletjesgevoel is meer dan een jasje. Het maakt een paar dingen in één
oogopslag zichtbaar:

| Spelelement | Wat het in de organisatie betekent |
|---|---|
| Energie / HP | Werkbelasting en capaciteit van een medewerker |
| Level / XP | Ervaring, afgeronde taken |
| Type | Specialisme (CODE, DATA, CREATIEF, ...) en welke afdeling past |
| Quest | Een taak met moeilijkheid, voortgang en beloning |
| Wilde bug + gevecht | Een incident of fout tijdens het werk |
| Poort + firewall | De grens van de afgesloten omgeving en hoe veilig die is |
| Dag/nacht | Werkritme. Wie wacht houdt, wie rust |

## Fase 1: simulatie + dashboard (nu klaar)

- Volledig offline, geen server, geen externe bestanden.
- Zes afdelingen, zes soorten medewerkers, zelfsturend quest-systeem.
- Bug-gevechten, levels, credits, werven.
- Indringers bij de poort en een firewall-meter.
- De baas kan zelf opdrachten geven.
- Alles draait om **gebeurtenissen** (`org.emit({...})`). Het dashboard
  luistert alleen daarnaar. Dat is bewust: zo kunnen we in fase 2 de
  simulatie vervangen door echte agents zonder het dashboard om te bouwen.

## Fase 2: echte agents in een afgesloten omgeving

Doel: de wezentjes worden echte AI-agents die echt werk doen.

1. **Afgesloten omgeving**: een Docker-container (of een paar) zonder
   internettoegang, behalve naar de AI-API. Elke afdeling krijgt een eigen
   werkmap. De "poort" is het netwerkbeleid: alles wat naar buiten wil,
   wordt gelogd en eventueel tegengehouden.
2. **Agents**: elke medewerker is een agent (bijv. via de Claude Agent SDK)
   met een rol-prompt die bij zijn type past, en alleen de tools van zijn
   afdeling.
3. **Orkestrator** (de "Planuil"): verdeelt quests, bewaakt het budget en
   zet medewerkers in rust als ze hun limiet (tokens/kosten) bereiken.
   Energie wordt dan echt: resterend budget per agent.
4. **Eventbus**: een kleine Node-server die gebeurtenissen van de agents via
   een WebSocket naar het dashboard stuurt, in hetzelfde formaat als nu:

   ```json
   { "kind": "quest", "agentId": 3, "text": "DEX rondde 'API koppelen' af!", "time": "DAG 2 10:15" }
   ```

   Soorten: `info`, `quest`, `levelup`, `bug`, `win`, `lose`, `security`,
   `alarm`, `recruit`, `warn`.
5. **Bugs worden echt**: een mislukte test, een fout in een tool-aanroep of
   een geweigerde actie verschijnt als "wilde bug". Het gevecht is de poging
   van de agent om het op te lossen.
6. **Poort wordt echt**: elke uitgaande verbinding die het netwerkbeleid
   tegenhoudt, verschijnt als "indringer geblokt".

## Fase 3: uitbreidingen (ideeën)

- Goedkeuringen: een agent die iets riskants wil doen, vraagt het via een
  dialoogvenster aan de baas ("BITBIT wil deployen. JA / NEE").
- Evolutie: na genoeg levels krijgt een medewerker een nieuwe sprite en
  meer tools.
- Prestaties/badges per afdeling.
- Geluid (8-bit piepjes bij level-up en alarm).
- Meerdere dalen = meerdere projecten.

## Open vragen voor de baas

- Wat moet de organisatie in het echt gaan doen? (Software bouwen,
  content maken, onderzoek, een webshop draaien, ...)
- Waar draait de afgesloten omgeving: je eigen computer, een server of in
  de cloud?
- Welke afdelingen wil je echt hebben? De huidige zes zijn een begin.
