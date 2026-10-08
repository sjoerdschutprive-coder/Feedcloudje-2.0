// De besluitvormers van de organisatie, in drie lagen:
//
//   SJOERD (jij)   ──opdracht──▶  GODFRED  ──taken op het prikbord──▶  AFDELINGSHOOFDEN  ──▶  AGENTS
//                  ◀──project af──          ◀──output (goed / revisie)──                  ◀──output──
//
//   RISK FRED (MT-lid) scant ontwikkelwerk vóór het naar Godfred gaat,
//   bewaakt poort en firewall en adviseert Godfred over risico's.
//   ELSJE (MT-lid, L&D) maakt de agents beter: coaching en nieuwe tools.
//   Risk Fred en Elsje rapporteren rechtstreeks aan Sjoerd, ook over Godfred.
//
// Elk brein *kijkt* naar de staat en *geeft commando's*; het verandert zelf
// nooit iets. org.js voert de commando's uit. Daardoor kan elk brein later
// vervangen worden door een echte AI-agent die dezelfde commando's als tools
// krijgt (zie docs/PLAN.md).
//
// Commando's van Godfred:   plan, initiative, post, review, feedback, meeting, say
// Commando's van een hoofd: pickup, assign, review, check, deliver, rest, say
// Commando's van RISK FRED: review, verdict, harden, patrol, advise, report, say
// Commando's van ELSJE: session, propose, report, say
window.FC = window.FC || {};

(function (FC) {
  const MT_EVERY = 6 * 60;         // speelminuten tussen MT-overleggen
  const INITIATIVE_EVERY = 15;     // hoe vaak Godfred zelf werk bedenkt
  const DELIVER_AFTER = 20;        // max. wachttijd voor gecontroleerde output
  const PATROL_EVERY = 90;         // inspectieronde bij de poort
  const ADVICE_EVERY = 240;        // niet vaker adviseren dan dit
  const RISK_REPORT_EVERY = 1440;  // dagelijks beveiligingsrapport aan Sjoerd

  // Godfred: direct, kort, licht van toon (zie godfred/profile.md).
  const REVISE_NOTES = ['Te vaag. Maak het concreet.', 'Waar is de onderbouwing?', 'Mist de klant. Opnieuw.',
    'Te lang. Halveer het.', 'Cijfers erbij, dan praten we verder.'];
  const GOOD_NOTES = ['Goed. Door.', 'Strak werk. Dit wil ik vaker zien.', 'Klopt. Volgende.',
    'Netjes. Sjoerd gaat dit leuk vinden.', 'Precies goed, niks aan doen.'];
  const HEAD_NOTES = ['Check de randgevallen nog even.', 'Kan strakker.', 'Mist nog een stukje.'];
  const LEAK_NOTES = ['Wachtwoord staat in de code.', 'Invoer wordt niet gecontroleerd.', 'Te ruime toegangsrechten.',
    'Verouderde bibliotheek met bekend lek.', 'Gevoelige data niet versleuteld.'];
  const pick = arr => arr[Math.floor(Math.random() * arr.length)];

  // ---------- Godfred: de directeur ----------

  class GodfredBrain {
    constructor(org) { this.org = org; }

    tick(g) {
      const org = this.org;
      const s = org.state;
      if (s.meeting || g.state !== 'idle') return;
      const now = org.now();
      const mem = s.memory;
      const cmd = c => org.execute(c, g.id);

      // 1. Een beoordeling afronden: goedkeuren of terug voor revisie.
      if (g.reviewDone) {
        const t = org.task(g.reviewDone);
        const ok = t.quality >= 0.55 || t.revision >= 2;
        cmd({ type: 'feedback', taskId: t.id, verdict: ok ? 'goed' : 'revisie', note: pick(ok ? GOOD_NOTES : REVISE_NOTES) });
        return;
      }

      // 2. Vaste overleggen.
      if (now - mem.lastMt >= MT_EVERY) {
        mem.lastMt = now;
        cmd({ type: 'meeting', scope: 'mt', topic: 'Management-overleg: voortgang' });
        return;
      }
      // Advies van RISK FRED over de firewall: crisisoverleg.
      // Signalen van Risk Fred gaan voor op snelheid.
      if (mem.adviceAt > mem.lastCrisis) {
        mem.lastCrisis = now;
        mem.adviceResponse = now - mem.adviceAt;
        cmd({ type: 'meeting', scope: 'mt', topic: 'Ad hoc: signaal van RISK FRED' });
        return;
      }

      // 3. Nieuwe opdrachten van Sjoerd opknippen in taken per afdeling.
      s.projects.filter(p => p.status === 'nieuw').forEach(p => cmd({ type: 'plan', projectId: p.id }));

      // 4. Ingeleverde output beoordelen.
      const inbox = s.tasks.filter(t => t.status === 'ingeleverd').sort((p, q) => p.id - q.id);
      if (inbox.length) { cmd({ type: 'review', taskId: inbox[0].id }); return; }

      // 5. Nieuwe taken naar het prikbord brengen.
      if (s.tasks.some(t => t.status === 'concept')) { cmd({ type: 'post' }); return; }

      // 6. Zelf werk bedenken voor afdelingen die zonder dreigen te vallen.
      if (now - mem.lastInitiative >= INITIATIVE_EVERY) {
        mem.lastInitiative = now;
        for (const dept of FC.map.DEPTS) {
          const load = s.tasks.filter(t => t.dept === dept && ['concept', 'bord', 'opgehaald'].includes(t.status)).length;
          const staff = s.agents.filter(a => a.role === 'agent' && a.dept === dept).length;
          if (load < staff) cmd({ type: 'initiative', dept });
        }
      }
    }
  }

  // ---------- Afdelingshoofd ----------

  class HeadBrain {
    constructor(org) { this.org = org; }

    tick(h) {
      const org = this.org;
      const s = org.state;
      if (h.state !== 'idle') return;
      if (s.meeting && s.meeting.attendees.includes(h.id)) return;
      const cmd = c => org.execute(c, h.id);
      const deptTasks = status => s.tasks.filter(t => t.dept === h.dept && t.status === status);
      const team = s.agents.filter(a => a.role === 'agent' && a.dept === h.dept);

      // 1. Een controle afronden.
      if (h.reviewDone) {
        const t = org.task(h.reviewDone);
        const better = t.quality < 0.45 && t.headRevision < 1;
        cmd({ type: 'check', taskId: t.id, verdict: better ? 'beter' : 'ok', note: better ? pick(HEAD_NOTES) : '' });
        return;
      }

      // 2. Zorgen voor het team: wie leeg raakt, gaat naar het buffet.
      team.filter(a => a.state === 'working' && a.energy < 25).forEach(a => cmd({ type: 'rest', agentId: a.id }));

      // 3. Taken van de eigen stapel verdelen (geen gelopen nodig).
      const free = team.filter(a => a.state === 'idle' && !a.taskId && a.energy >= 30);
      const stack = deptTasks('opgehaald').sort((p, q) =>
        (q.revision + q.headRevision) - (p.revision + p.headRevision) || (q.boss - p.boss) || p.id - q.id);
      while (free.length && stack.length) {
        const a = free.sort((p, q) => q.level - p.level).shift();
        cmd({ type: 'assign', taskId: stack.shift().id, agentId: a.id });
      }

      // 4. Output van het team controleren.
      const toCheck = deptTasks('controle');
      if (toCheck.length) { cmd({ type: 'review', taskId: toCheck[0].id }); return; }

      // 5. Gecontroleerde output in één keer naar Godfred brengen.
      const checked = deptTasks('gecontroleerd');
      const oldest = Math.min(...checked.map(t => t.checkedAt));
      if (checked.length >= 2 || (checked.length && org.now() - oldest >= DELIVER_AFTER)) {
        cmd({ type: 'deliver' });
        return;
      }

      // 6. Nieuwe taken van het prikbord halen, net genoeg voor wie vrij is.
      const board = deptTasks('bord');
      if (board.length && free.length && !s.meeting) cmd({ type: 'pickup', count: free.length + 1 });
    }
  }

  // ---------- RISK FRED: risk & safety officer ----------

  class RiskBrain {
    constructor(org) { this.org = org; }

    tick(r) {
      const org = this.org;
      const s = org.state;
      if (r.state !== 'idle') return;
      if (s.meeting && s.meeting.attendees.includes(r.id)) return;
      const now = org.now();
      const mem = s.memory;
      const cmd = c => org.execute(c, r.id);

      // 1. Een scan afronden: veilig of lek.
      if (r.reviewDone) {
        const t = org.task(r.reviewDone);
        // Tools van Elsje: alleen afkeuren als er echt iets mis mee is.
        const leak = t.kind === 'tool' ? t.quality < 0.25 : t.secRevision < 1 && (t.quality < 0.5 || Math.random() < 0.15);
        cmd({ type: 'verdict', taskId: t.id, verdict: leak ? 'lek' : 'veilig', note: leak ? pick(LEAK_NOTES) : '' });
        return;
      }

      // 2. Godfred adviseren als de firewall zwak wordt.
      if (s.firewall < 65 && now - mem.lastAdvice >= ADVICE_EVERY) {
        cmd({ type: 'advise', note: `De firewall staat op ${Math.round(s.firewall)}%. Ik adviseer een crisisoverleg en extra waakzaamheid.` });
        return;
      }

      // Dagelijks rapport aan Sjoerd, ook over hoe Godfred met signalen omgaat.
      if (now - mem.lastRiskReport >= RISK_REPORT_EVERY) {
        mem.lastRiskReport = now;
        const st = s.stats;
        const response = mem.adviceResponse === null ? 'Godfred had nog geen signaal van mij nodig.'
          : `Godfred volgde mijn laatste signaal op na ${mem.adviceResponse} minuten.`;
        cmd({ type: 'report', title: 'Dagelijks beveiligingsrapport',
          text: `Firewall ${Math.round(s.firewall)}%. ${st.intrudersBlocked} aanvallen geblokt, ${st.breaches} doorgekomen. ` +
            `${st.leaks} lekken onderschept. ${response}` });
        return;
      }

      // 3. Ontwikkelwerk scannen gaat voor.
      const queue = s.tasks.filter(t => t.status === 'scan').sort((p, q) => p.id - q.id);
      if (queue.length) { cmd({ type: 'review', taskId: queue[0].id }); return; }

      // 4. Firewall versterken.
      if (s.firewall < 100) { cmd({ type: 'harden' }); return; }

      // 5. Inspectieronde bij de poort.
      if (now - mem.lastPatrol >= PATROL_EVERY) cmd({ type: 'patrol' });
    }
  }

  // ---------- ELSJE: Learning & Development ----------

  const LND_TOOLS = ['spreadsheet-skill', 'nieuwe prompttechniek', 'samenvat-extensie', 'onderzoeksagent', 'planningstool', 'nieuw model'];

  class LndBrain {
    constructor(org) { this.org = org; }

    tick(e) {
      const org = this.org;
      const s = org.state;
      if (e.state !== 'idle' || s.meeting) return;
      if (org.now() < s.memory.nextSession) return;
      const cmd = c => org.execute(c, e.id);

      // Waar levert verbetering het meeste op? De agent met de meeste
      // revisies per taak (bij gelijkspel: het laagste level).
      const agents = s.agents.filter(a => a.role === 'agent');
      const score = a => (a.stats.revisions + 1) / (a.stats.tasks + 2) - a.level * 0.01;
      const target = agents.sort((p, q) => score(q) - score(p))[0];

      // Rapport aan Sjoerd over Godfred, en een nieuwe tool laten scannen.
      const done = s.tasks.filter(t => t.status === 'goedgekeurd' && t.kind !== 'tool' && t.deliveredAt);
      const firstTime = done.length ? Math.round(done.filter(t => !t.revision).length / done.length * 100) : 100;
      const speed = done.length ? Math.round(done.reduce((sum, t) => sum + (t.doneAt - t.deliveredAt), 0) / done.length) : 0;
      cmd({ type: 'report', title: 'Verbetersessie: performance en Godfred',
        text: `Godfred keurt ${firstTime}% in één keer goed en beoordeelt binnen gemiddeld ${speed} minuten. ` +
          `${s.stats.revisions} revisies totaal. Vandaag coach ik ${target ? target.name : 'niemand'}.` });
      const dept = target ? target.dept : FC.map.DEPTS[0];
      cmd({ type: 'propose', tool: pick(LND_TOOLS), dept });
      if (target) cmd({ type: 'session', agentId: target.id });
    }
  }

  FC.GodfredBrain = GodfredBrain;
  FC.HeadBrain = HeadBrain;
  FC.RiskBrain = RiskBrain;
  FC.LndBrain = LndBrain;
})(window.FC);
