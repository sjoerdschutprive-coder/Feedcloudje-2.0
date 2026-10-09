# Onderzoek: kenmerken die het Tet Tet-kantoor een voorsprong geven

De `bron`-velden in de kaarten verwijzen naar de ids hieronder. Per bron: wat het onderzoek laat zien en waar het in de kaarten terugkomt.

## Kenmerken op agentniveau

| Kenmerk (veld in `werkstijl`) | Waarom | Bron |
| --- | --- | --- |
| `definitie_van_klaar` | Agents die niet weten wanneer een taak af is, stoppen te vroeg of draaien door. | `mast` |
| `verduidelijken` | Doorwerken op verkeerde aannames in plaats van vragen is een terugkerende faalwijze. | `mast` |
| `informatie_delen` | Informatie achterhouden en input van collega's negeren breekt samenwerking tussen agents. | `mast` |
| `standvastigheid` | In debatten tussen agents veranderen goede antwoorden vaker in foute dan andersom, vooral als een agent alleen staat. | `debat-faalwijzen`, `sycofantie-propagatie` |
| `kalibratie` | Onthouden of markeren bij onzekerheid verhoogt de juistheid en vermindert verzonnen antwoorden. | `kalibratie-onthouding` |
| `zelfreflectie` | Een korte les na elke poging, bewaard in een geheugen, verbetert agents zonder hertraining. | `reflexion` |
| `inspanning_schalen` | Zonder expliciete regels zetten agents te veel middelen in voor simpele vragen. | `anthropic-multi-agent-onderzoek` |
| `delegeren` (Oppertet, Hoofdtets) | Elke opdracht met doel, outputformat, bronnen en grenzen voorkomt dubbel werk en gaten. | `anthropic-multi-agent-onderzoek` |
| `toetsen` (Control Tets) | Toetsen op detail én op doel levert aantoonbaar meer correcte uitkomsten op. | `mast` |
| `meetwaarden.stabiliteitsscore` | Als agents weten hoe meegaand hun collega's zijn, stijgt de groepsnauwkeurigheid. | `sycofantie-propagatie` |

## Kenmerken op cultuurniveau

| Principe (in `edge_principes`) | Waarom | Bron |
| --- | --- | --- |
| Context, geen controle | Teams die context krijgen in plaats van stappenplannen beslissen sneller en beter. | `netflix-cultuur` |
| Eén eigenaar per besluit | Eén agent met beslisbevoegdheid, ook over 'klaar', verminderde fouten in multi-agentsystemen. | `mast`, `netflix-cultuur`, `amazon-working-backwards` |
| Oneens zijn, dan committeren | Bezwaren vooraf, daarna volledige uitvoering. | `netflix-cultuur` |
| Eerst zelf oordelen | Voorkomt conformiteit en meegaandheid tussen agents. | `debat-faalwijzen`, `sycofantie-propagatie` |
| Verificatie op twee niveaus | Ontbrekende of foute verificatie is een hoofdcategorie van falen. | `mast` |
| Bijna-fouten tellen mee | Bijna-incidenten zijn signalen van zwakke plekken in het systeem. | `hro`, `google-sre-postmortems` |
| Deskundigheid beslist | Vakoordeel weegt zwaarder dan positie bij inhoudelijke vragen. | `hro` |
| Veilig om te melden | Psychologische veiligheid was de belangrijkste factor voor effectieve teams. | `project-aristotle` |
| Duidelijke rollen en structuur | Heldere doelen en rollen horen bij de kern van teameffectiviteit. | `project-aristotle`, `mast` |
| Eenvoudigste oplossing eerst | Complexiteit alleen toevoegen als metingen dat rechtvaardigen. | `anthropic-effectieve-agents` |

## Bronnen

- `mast`: Cemri e.a., *Why Do Multi-Agent LLM Systems Fail?* (NeurIPS 2025). https://arxiv.org/abs/2503.13657
- `debat-faalwijzen`: *Talk Isn't Always Cheap: Understanding Failure Modes in Multi-Agent Debate*. https://arxiv.org/abs/2509.05396
- `sycofantie-propagatie`: *Too Polite to Disagree: Understanding Sycophancy Propagation in Multi-Agent Systems*. https://arxiv.org/abs/2604.02668
- `kalibratie-onthouding`: *Uncertainty-Based Abstention in LLMs Improves Safety and Reduces Hallucinations*. https://arxiv.org/abs/2404.10960
- `reflexion`: Shinn e.a., *Reflexion: Language Agents with Verbal Reinforcement Learning* (NeurIPS 2023). https://arxiv.org/abs/2303.11366
- `anthropic-effectieve-agents`: Anthropic, *Building effective agents*. https://www.anthropic.com/engineering/building-effective-agents
- `anthropic-multi-agent-onderzoek`: Anthropic, *How we built our multi-agent research system*. https://www.anthropic.com/engineering/multi-agent-research-system
- `project-aristotle`: Google, Project Aristotle. https://leaderfactor.com/learn/project-aristotle-psychological-safety
- `hro`: Weick & Sutcliffe, principes van high reliability organizations. https://www.ghx.com/the-healthcare-hub/hro-healthcare-guide/
- `google-sre-postmortems`: Google SRE Book, *Postmortem Culture*. https://sre.google/sre-book/postmortem-culture/
- `netflix-cultuur`: Netflix Culture Memo. https://jobs.netflix.com/culture
- `amazon-working-backwards`: Bryar & Carr, *Working Backwards*. https://www.charterworks.com/book-briefing-working-backwards-by-colin-bryar-and-bill-carr/
