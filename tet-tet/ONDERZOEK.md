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
| Informeel contact is werk | Communicatiepatronen voorspellen teamsucces sterker dan talent; gezamenlijke pauzes en grotere lunchtafels hingen samen met hogere productiviteit en minder stress. Smalltalk verhoogt positieve emoties en burgerschapsgedrag, maar leidt ook af: daarom alleen in pauzes en kort. | `pentland-teams`, `sociometric-pauzes`, `methot-smalltalk` |
| Wie weet wat is zichtbaar | Teams met een goed 'wie weet wat'-systeem (transactief geheugen) presteren beter; het ontstaat in de planningsfase en door direct contact. | `transactief-geheugen` |
| Unieke informatie eerst | Groepen bespreken vooral wat iedereen al weet; unieke kennis blijft liggen, vooral als het om consensus gaat in plaats van om het juiste antwoord. | `hidden-profile` |
| Need-to-know, ook aan de koffietafel | Agents lekken vaker naarmate ze langer sociaal interacteren, en na één lek stijgt de kans op het volgende sterk. Instructies alleen helpen beperkt; daarom een deelfilter vooraf en toezicht door Risk & Safety. | `geheimen-multi-agent` |
| Een extra laag versnelt, filtert niet | Het aantal relaties dat een leidinggevende moet bijhouden groeit veel sneller dan het aantal mensen dat aan hem rapporteert. Een stafrol kan de leider ontlasten door coördinatie, opvolging en het voorbereiden van besluiten, mits rollen helder zijn en anderen erop kunnen vertrouwen dat zorgen accuraat worden doorgegeven. Unieke informatie verdwijnt makkelijk onderweg; daarom houdt ieder een directe lijn naar de Oppertet. | `span-of-control`, `ceo-staf`, `hidden-profile` |

## Kenmerken van de samenwerking

| Onderdeel | Ontwerpkeuze | Bron |
| --- | --- | --- |
| Kantine | Eén gemengde tafel van 4–6 agents uit minstens drie afdelingen, roulerend; één pauze per werkdagrun, nooit tijdens taakuitvoering. | `sociometric-pauzes`, `methot-smalltalk` |
| Afdelingshuddle | Dagelijks, kort, vlak vóór de pauze. Geen terugblik (staat op het bord), wel prioriteit, knelpunt en wie je nodig hebt. Roulerende voorzitter, gelijke spreektijd. | `rogelberg-huddle`, `standup-praktijk` |
| Voorbereiding MT | Eerst ieder zelfstandig op schrift (met 'wat alleen ik weet'), dan een afdelingsmemo, bilaterale afstemming en vooraf lezen. In het MT eerst ieders oordeel apart, dan bespreken; correctheid boven consensus. | `hidden-profile`, `debat-faalwijzen` |
| Afdelingsomvang | 1 Hoofdtet + 3 Tets per afdeling; nieuwe agents pas actief na een meting. Centrale coördinatie beperkt foutversterking; meer agents is niet vanzelf beter. | `teamomvang`, `schaal-agents` |
| Cultuurmeting | Energie (interacties), betrokkenheid (gelijke spreektijd), verkenning (contact buiten de eigen afdeling) en veiligheid (zelf gemelde fouten). | `pentland-teams`, `project-aristotle` |
| Eenvoudigste oplossing eerst | Complexiteit alleen toevoegen als metingen dat rechtvaardigen. | `anthropic-effectieve-agents` |
| Assistent-Oppertet | Een chief of staff onder de Oppertet en boven de Hoofdtets: vertaalt MT-besluiten door, bewaakt opvolging in een besluitenregister, coördineert tussen afdelingen en is eerste lijn voor operationele escalaties. Geen eigen strategische besluiten en geen filter: risico's, integriteit en onenigheid met de assistent gaan rechtstreeks naar de Oppertet, het blok 'alleen wij weten' gaat ongewijzigd door. Pas actief na een meting vóór en na. | `span-of-control`, `ceo-staf`, `hidden-profile`, `schaal-agents` |

## Kenmerken van de HR-afdeling

| Onderdeel | Ontwerpkeuze | Bron |
| --- | --- | --- |
| Structuur | 1 Hoofdtet + 3 Tets: de Hoofdtet is businesspartner, Prestatie-Tet en Governance-Tet zijn expertisecentra, Personeels-Tet is shared services. Een kleine organisatie heeft geen aparte pijlers nodig. | `ulrich-hr` |
| Check-in | Wekelijks, kort, tussen Hoofdtet en Tet. Over de komende week, niet over een cijfer. | `deloitte-checkins` |
| Prestatieprofiel | Meerdere maten per agent (kwaliteit, betrouwbaarheid, veiligheid, efficiëntie, samenwerking, stijl), met intervallen en een minimale steekproef. Geen totaalscore, geen ranglijst, geen automatische gevolgen. | `rater-effect`, `surrogatie` |
| Beoordelaars | Blind (geen naam, afdeling of eerdere scores), lengte telt niet mee, bij paarsgewijze vergelijking de volgorde wisselen; een steekproef voor de Raad houdt de beoordelaar eerlijk. | `llm-rechter` |
| Betrouwbaarheid | pass^k op een vaste ijkset per rol: dezelfde taak k keer goed, niet één keer. | `pass-k` |
| Evaluatiegesprek | Maandelijks: eerst zelfreflectie (zonder de cijfers te zien), dan de snapshot, dan toekomstvragen van de Hoofdtet. Uitkomst: één prestatiedoel en één leerdoel met datum en actieplan. Feedback alleen over de taak. | `doelen-locke-latham`, `feedback-interventie`, `deloitte-checkins` |
| Kalibratie | Per kwartaal leggen de Hoofdtets hun oordelen naast elkaar om verschillen in strengheid te corrigeren; eerst ieder apart, dan bespreken. | `rater-effect` |
| Fouten melden | Zelf gemelde fouten tellen positief; elke grensovertreding krijgt binnen een werkdag een blameless incidentevaluatie. | `psychologische-veiligheid`, `google-sre-postmortems` |
| Handboek | Eén handboek (werkwijze, schrijfstijl, woordenlijst, huisstijl, mappenstructuur) is de enige bron van waarheid; documentatie volgt de vier soorten van Diátaxis. | `handboek-eerst`, `diataxis` |

## Kenmerken van de sturing en het rooster

| Onderdeel | Ontwerpkeuze | Bron |
| --- | --- | --- |
| Eén ingang voor de Raad | De Raad stuurt alleen via de chat met de Oppertet; de Assistent-Oppertet vertaalt door naar de Hoofdtets. Afdelingspagina's zijn alleen-lezen. | `span-of-control`, `ceo-staf` |
| Back-ups | Drie kopieën op twee soorten opslag, één buiten de werkplek: git, Google Drive en de lokale spiegel. | `back-up-3-2-1` |
| Herstelproef | Herstel bij elke sessiestart en maandelijks een herstelproef in de sandbox; een back-up zonder bewezen herstel telt niet. | `herstel-testen` |
| Onderhoud | Dagelijks, wekelijks en maandelijks onderhoud volgens een runbook, zoveel mogelijk geautomatiseerd. | `sre-toil` |
| Weekrooster | Overleg geclusterd in vaste vensters (07:30–08:30 en 15:00–16:30); het onderzoeksblok 12:30–15:00 blijft vrij van overleg. Agents in rust draaien niet en kosten niets. | `makers-schedule`, `schaal-agents` |
| Dagelijks MT | Elke dag 15 minuten met vaste agenda en zonder terugblik; maandag het lange MT met besluitvragen. | `rogelberg-huddle`, `standup-praktijk` |

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
- `pentland-teams`: Pentland, *The New Science of Building Great Teams* (HBR 2012). https://capacity-building.com/favorite-articles/the-new-science-of-building-great-teams/
- `sociometric-pauzes`: MIT News, *Behavioral analytics: moneyball for business* (2014), over gezamenlijke pauzes en lunchtafels. https://news.mit.edu/2014/behavioral-analytics-moneyball-for-business-1114
- `methot-smalltalk`: Methot e.a., *Office Chit-Chat as a Social Ritual* (Academy of Management Journal 2021). https://ore.exeter.ac.uk/repository/handle/10871/123633
- `transactief-geheugen`: Lewis, *Knowledge and Performance in Knowledge-Worker Teams: A Longitudinal Study of Transactive Memory Systems* (Management Science 2004). https://pubsonline.informs.org/doi/10.1287/mnsc.1040.0257
- `hidden-profile`: Stasser & Titus, hidden-profileparadigma. https://en.wikipedia.org/wiki/Hidden_profile
- `rogelberg-huddle`: Rogelberg, *The Surprising Science of Meetings*, over huddles van 10–15 minuten. https://ideas.ted.com/how-to-reap-big-benefits-from-meetings-that-are-just-10-to-15-minutes-long
- `standup-praktijk`: Stray e.a., *Daily Stand-Up Meetings: Start Breaking the Rules* (IEEE Software 2018). https://arxiv.org/abs/1808.07650
- `schaal-agents`: Google Research en MIT, *Towards a Science of Scaling Agent Systems* (2025). https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/
- `teamomvang`: Hackman & Vidmar (1970), samengevat in GWU-gids teameffectiviteit. https://guides.himmelfarb.gwu.edu/teameffectiveness/structural-factors
- `geheimen-multi-agent`: *Got a Secret? LLM Agents Can't Keep It: Evaluating Privacy in Multi-Agent Systems* (2026). https://arxiv.org/abs/2605.27766
- `deloitte-checkins`: Buckingham & Goodall, *Reinventing Performance Management* (HBR 2015). https://hbr.org/2015/04/reinventing-performance-management
- `rater-effect`: Scullen, Mount & Goff, *Understanding the Latent Structure of Job Performance Ratings* (Journal of Applied Psychology 2000). https://doi.org/10.1037/0021-9010.85.6.956
- `feedback-interventie`: Kluger & DeNisi, *The Effects of Feedback Interventions on Performance* (Psychological Bulletin 1996). https://doi.org/10.1037/0033-2909.119.2.254
- `surrogatie`: Harris & Tayler, *Don't Let Metrics Undermine Your Business* (HBR 2019). https://hbr.org/2019/09/dont-let-metrics-undermine-your-business
- `doelen-locke-latham`: Locke & Latham, *Building a Practically Useful Theory of Goal Setting and Task Motivation* (American Psychologist 2002). https://doi.org/10.1037/0003-066X.57.9.705
- `psychologische-veiligheid`: Edmondson, *Psychological Safety and Learning Behavior in Work Teams* (Administrative Science Quarterly 1999). https://doi.org/10.2307/2666999
- `llm-rechter`: Zheng e.a., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena* (NeurIPS 2023). https://arxiv.org/abs/2306.05685
- `pass-k`: Yao e.a., *τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains* (2024). https://arxiv.org/abs/2406.12045
- `ulrich-hr`: Ulrich; Ulrich & Brockbank, *The HR Value Proposition* (2005), samengevat door HRworks. https://www.hrworks.de/news/dave-ulrich-modell-was-das-3-saeulen-modell-fuer-hr-bedeutet/
- `handboek-eerst`: GitLab Handbook, *Handbook-first*. https://handbook.gitlab.com/handbook/company/culture/all-remote/handbook-first/
- `diataxis`: Procida, *Diátaxis*. https://diataxis.fr/
- `span-of-control`: Graicunas, *Relationship in Organization* (Bulletin of the International Management Institute, 1933): bij n ondergeschikten groeit het aantal relaties volgens n(2^(n−1) + n − 1); bij 7 zijn dat er 490. https://nickols.us/graicunas.htm
- `ceo-staf`: Barton, Cave, Cook & Reeves, *The Heart of CEO Effectiveness* (BCG 2020), over de staf rond de CEO: het bereik van de leider vergroten, integreren tussen afdelingen, heldere rollen, en vertrouwen dat zorgen accuraat worden doorgegeven. https://www.bcg.com/publications/2020/heart-ceo-effectiveness
- `back-up-3-2-1`: US-CERT/CISA, *Data Backup Options* (2012): bewaar drie kopieën op twee soorten opslag, waarvan één buiten de werkplek. https://www.cisa.gov/sites/default/files/publications/data_backup_options.pdf
- `herstel-testen`: Google, *Site Reliability Engineering*, hoofdstuk 26 'Data Integrity: What You Read Is What You Wrote' (2016): niemand wil back-ups, iedereen wil herstel; test herstel regelmatig. https://sre.google/sre-book/data-integrity/
- `sre-toil`: Google, *Site Reliability Engineering*, hoofdstuk 5 'Eliminating Toil' (2016). https://sre.google/sre-book/eliminating-toil/
- `makers-schedule`: Paul Graham, *Maker's Schedule, Manager's Schedule* (2009): één vergadering kan een blok diep werk breken. https://paulgraham.com/makersschedule.html
