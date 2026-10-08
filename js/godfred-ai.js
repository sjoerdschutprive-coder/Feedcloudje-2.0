// De echte Godfred: als de pagina in Claude geopend is, denkt Godfred echt
// na via de `sample`-capability (op het Claude-account van de kijker).
// Hij krijgt zijn profiel (godfred/profile.md), de actuele stand van de
// organisatie en het gesprek mee, en antwoordt met JSON: een antwoord in
// zijn eigen stijl en, als Sjoerd werk opdraagt, een plan met taken per
// afdeling. Dat plan gaat via het gewone `order`-commando de organisatie in.
window.FC = window.FC || {};

(function (FC) {
  const MAP = FC.map;
  const HISTORY = 8; // zoveel eerdere berichten gaan mee als context

  const DEPT_INFO = {
    finance: 'Finance Fred (cijfers, prijzen, begroting)',
    marketing: 'Marketing Fred (merk, content, campagnes, sales-ondersteuning)',
    operations: 'Operations Fred (processen, systemen, tools, uitvoering)',
    strategie: 'Strategic Fred (markt, concurrentie, positionering, plannen)',
  };

  function status(org) {
    const s = org.state;
    const lines = [`Tijd in het dashboard: ${org.clockLabel()}. Firewall: ${Math.round(s.firewall)}%.`];
    for (const d of MAP.DEPTS) {
      const head = org.head(d);
      const agents = s.agents.filter(a => a.role === 'agent' && a.dept === d).length;
      const open = s.tasks.filter(t => t.dept === d && !['goedgekeurd'].includes(t.status)).length;
      lines.push(`- ${MAP.room(d).name} (id "${d}"): ${head ? head.name : 'geen hoofd'}, ${agents} agents, ${open} open taken.`);
    }
    const boss = s.projects.filter(p => p.source === 'baas').slice(-6);
    if (boss.length) {
      lines.push('Opdrachten van Sjoerd:');
      boss.forEach(p => {
        const tasks = p.taskIds.map(id => org.task(id)).filter(Boolean);
        const done = tasks.filter(t => t.status === 'goedgekeurd').length;
        lines.push(`- "${p.title}": ${p.status}, ${done}/${tasks.length} taken goedgekeurd.`);
      });
    }
    const reports = s.reports.slice(0, 2);
    if (reports.length) {
      lines.push('Laatste rapporten aan Sjoerd:');
      reports.forEach(r => lines.push(`- ${r.from}: ${r.text}`));
    }
    return lines.join('\n');
  }

  function rules(org) {
    return [
      'Je bent GODFRED, de general manager van het AI-agent-team van Sjoerd in het dashboard "Feedcloudje HQ".',
      'Blijf volledig in je rol. Dit is je profiel:',
      '<profiel>', FC.PROFILES.godfred, '</profiel>',
      '',
      'Je team:',
      ...MAP.DEPTS.map(d => `- "${d}": ${DEPT_INFO[d]}`),
      '- RISK FRED (risk & safety, MT-lid) scant alles met een technisch of beveiligingsaspect.',
      '- ELSJE (Learning & Development, MT-lid) maakt de agents beter.',
      '',
      'Actuele stand van de organisatie:', status(org),
      '',
      'Eerlijkheid: je worker agents zijn in deze versie nog gesimuleerd. Ze kunnen buiten het dashboard nog niets echt doen',
      '(geen internet, e-mail, bestanden of klanten). Beloof dus geen echte resultaten buiten het dashboard en zeg dat eerlijk als het ertoe doet.',
      '',
      'Antwoord ALTIJD met alleen één JSON-object, zonder andere tekst:',
      '{"antwoord": string, "project": null | {"titel": string, "taken": [{"afdeling": "finance"|"marketing"|"operations"|"strategie", "titel": string, "omvang": 1-5, "security": boolean}]}}',
      '- "antwoord": Nederlands, in jouw stijl: direct, kort (hooguit 150 woorden), licht van toon. Nooit eindigen met "Kan ik je nog ergens mee helpen?" of iets vergelijkbaars.',
      '- "project": alleen als Sjoerd werk opdraagt en je genoeg weet om te beginnen. Titels hooguit 50 tekens, 1 tot 6 taken, elke taak bij de best passende afdeling.',
      '  "security": true als er een technisch of beveiligingsaspect aan zit (dan scant Risk Fred het).',
      '- Ontbreekt essentiële informatie, stel dan in "antwoord" hooguit 3 gerichte vragen. Je mag tegelijk een eerste verkennend project starten als dat zinvol is; anders "project": null.',
    ].join('\n');
  }

  // De invoer voor Claude: vaste instructies, recente geschiedenis, nieuw bericht.
  function buildInput(org, message) {
    const turns = [{ role: 'user', content: rules(org) }];
    for (const m of org.state.chat.slice(-HISTORY)) {
      if (m.role === 'sjoerd') turns.push({ role: 'user', content: m.text });
      else turns.push({ role: 'assistant', content: JSON.stringify({ antwoord: m.text, project: m.projectTitle ? { titel: m.projectTitle } : null }) });
    }
    turns.push({ role: 'user', content: message });
    return turns;
  }

  // Wat Claude terugstuurt netjes maken: niets wordt blind vertrouwd.
  function normalize(res) {
    const antwoord = res && typeof res.antwoord === 'string' ? res.antwoord.trim() : '';
    let project = null;
    const p = res && res.project;
    if (p && typeof p === 'object' && Array.isArray(p.taken)) {
      const taken = p.taken
        .filter(t => t && MAP.DEPTS.includes(t.afdeling) && typeof t.titel === 'string' && t.titel.trim())
        .slice(0, 6)
        .map(t => ({
          dept: t.afdeling,
          title: t.titel.trim().slice(0, 50),
          difficulty: Math.max(1, Math.min(5, Math.round(Number(t.omvang) || 2))),
          security: !!t.security,
        }));
      if (taken.length) project = { title: String(p.titel || 'Opdracht van Sjoerd').trim().slice(0, 50), tasks: taken };
    }
    return { antwoord, project };
  }

  const ERRORS = {
    not_granted: 'Je hebt de pagina (nog) geen toestemming gegeven om Claude te gebruiken. Godfred kan dan niet echt nadenken; het formulier op het PRIKBORD werkt wel.',
    sampling_disabled: 'Claude is voor dit account niet beschikbaar in pagina\'s. Gebruik het formulier op het PRIKBORD.',
    rate_limited: 'Even te veel tegelijk, of je gebruikslimiet is bereikt. Probeer het zo nog eens.',
    session_expired: 'Je sessie is verlopen. Log opnieuw in bij Claude en probeer het nog eens.',
    refused: 'Godfred kan op dit bericht niet ingaan. Formuleer het anders.',
    invalid_json: 'Godfred gaf een antwoord dat het dashboard niet kon lezen. Probeer het nog eens.',
    prompt_too_large: 'Het gesprek is te lang geworden. Begin opnieuw (↺) of houd het korter.',
  };
  const errorText = code => ERRORS[code] || 'Er ging iets mis bij het nadenken. Probeer het nog eens.';

  FC.GodfredAI = { buildInput, normalize, errorText };
})(window.FC);
