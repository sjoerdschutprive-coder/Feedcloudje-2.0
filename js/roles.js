// Rolkaarten: wie doet wat, wie mag wat, aan wie rapporteert iemand.
// Deze kaarten verschijnen in het dashboard en zijn later de basis voor de
// instructies (system prompts) van de echte AI-agents.
window.FC = window.FC || {};

FC.ROLES = {
  director: {
    title: 'DIRECTEUR',
    level: 'Top van de organisatie',
    mission: 'Vertaalt de opdrachten van de baas naar werk voor de afdelingen en bewaakt de kwaliteit van alles wat de organisatie oplevert.',
    tasks: [
      'Opdrachten van de baas opknippen in taken per afdeling',
      'Taken ophangen op het centrale prikbord',
      'Ingeleverde output beoordelen: goedkeuren of terug voor revisie',
      'Zelf werk bedenken als een afdeling zonder dreigt te vallen',
      'MT-overleg leiden; crisisoverleg bij advies van RISK THREAT',
      'Afgeronde projecten melden aan de baas',
    ],
    rights: ['plan', 'initiative', 'post', 'review', 'feedback', 'meeting'],
    reportsTo: 'DE BAAS',
    leads: 'Afdelingshoofden en RISK THREAT',
  },
  risk: {
    title: 'RISK & SAFETY OFFICER',
    level: 'MT-lid, zelfde niveau als een afdelingshoofd',
    mission: 'Houdt de afgesloten omgeving veilig: geen malware of virussen het netwerk in, en geen beveiligingsfouten in wat er ontwikkeld wordt waardoor de hele structuur kan vastlopen.',
    tasks: [
      'Poort en firewall bewaken; indringers, malware en virussen tegenhouden',
      'De firewall versterken zodra die verzwakt',
      'Security-scan op al het ontwikkelwerk (CODE-LAB) en op alles met een beveiligingsaspect, vóórdat het naar Godfred gaat',
      'Werk met een beveiligingslek terugsturen naar het afdelingshoofd',
      'Regelmatig een inspectieronde lopen bij de poort',
      'Godfred en het MT adviseren over risico’s; alarm slaan bij een zwakke firewall',
    ],
    rights: ['review', 'verdict', 'harden', 'patrol', 'advise'],
    reportsTo: 'GODFRED',
    leads: 'Niemand: werkt alleen',
  },
  head: {
    title: 'AFDELINGSHOOFD',
    level: 'MT-lid',
    mission: 'Zorgt dat de eigen afdeling efficiënt werkt en alleen goed werk aflevert.',
    tasks: [
      'Net genoeg taken van het prikbord halen voor wie vrij is',
      'Taken verdelen over de agents van de afdeling',
      'Output controleren en zo nodig laten bijschaven',
      'Ontwikkelwerk langs RISK THREAT laten gaan voor een security-scan',
      'Gecontroleerde output gebundeld naar Godfred brengen',
      'Vermoeide agents naar het buffet sturen',
    ],
    rights: ['pickup', 'assign', 'review', 'check', 'deliver', 'rest'],
    reportsTo: 'GODFRED',
    leads: 'De agents van de afdeling',
  },
  agent: {
    title: 'AGENT',
    level: 'Uitvoerend',
    mission: 'Voert taken uit aan het eigen bureau.',
    tasks: [
      'Taken van het afdelingshoofd uitvoeren',
      'Output inleveren bij het afdelingshoofd',
      'XP verdienen met goedgekeurd werk',
      'Met XP energie bijtanken bij het buffet in de lounge',
    ],
    rights: [],
    reportsTo: 'Het afdelingshoofd',
    leads: 'Niemand',
  },
};
