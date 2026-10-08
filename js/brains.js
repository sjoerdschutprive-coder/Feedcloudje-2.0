// De besluitvormers van de organisatie, in drie lagen:
//
//   DE BAAS (jij)  ──opdracht──▶  GODFRED  ──taken op het prikbord──▶  AFDELINGSHOOFDEN  ──▶  AGENTS
//                  ◀──project af──          ◀──output (goed / revisie)──                  ◀──output──
//
// Elk brein *kijkt* naar de staat en *geeft commando's*; het verandert zelf
// nooit iets. org.js voert de commando's uit. Daardoor kan elk brein later
// vervangen worden door een echte AI-agent die dezelfde commando's als tools
// krijgt (zie docs/PLAN.md).
//
// Commando's van Godfred:   plan, initiative, post, review, feedback, meeting, say
// Commando's van een hoofd: pickup, assign, review, check, deliver, rest, guard, say
window.FC = window.FC || {};

(function (FC) {
  const MT_EVERY = 6 * 60;         // speelminuten tussen MT-overleggen
  const INITIATIVE_EVERY = 15;     // hoe vaak Godfred zelf werk bedenkt
  const DELIVER_AFTER = 20;        // max. wachttijd voor gecontroleerde output

  const REVISE_NOTES = ['Te oppervlakkig, ga dieper.', 'Mist de klantkant.', 'Maak het scherper.',
    'Graag met concrete cijfers.', 'Sluit nog niet aan op de rest van het project.'];
  const GOOD_NOTES = ['Precies wat we nodig hadden.', 'Sterk werk!', 'Goedgekeurd.', 'Netjes afgerond.', 'Hier kunnen we mee verder.'];
  const HEAD_NOTES = ['Check de randgevallen nog even.', 'Kan strakker.', 'Mist nog een stukje.'];
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
        cmd({ type: 'meeting', scope: 'mt', topic: 'MT-overleg met de afdelingshoofden' });
        return;
      }
      if (s.firewall < 60 && now - mem.lastCrisis >= MT_EVERY) {
        mem.lastCrisis = now;
        cmd({ type: 'meeting', scope: 'alle', topic: 'Crisisoverleg: de firewall staat onder druk!' });
        return;
      }

      // 3. Nieuwe opdrachten van de baas opknippen in taken per afdeling.
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

      // 2. Zorgen voor het team.
      team.filter(a => a.state === 'working' && a.energy < 25).forEach(a => cmd({ type: 'rest', agentId: a.id }));
      if (h.dept === 'poort') this.guardDuty(team, cmd);

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

    guardDuty(team, cmd) {
      const onDuty = team.find(a => a.state === 'guarding' || a.intent === 'guard');
      const available = a => (a.state === 'idle' || a.state === 'coffee') && !a.taskId;
      if (!onDuty) {
        const cand = team.filter(a => a.energy >= 40 && available(a)).sort((p, q) => q.energy - p.energy)[0];
        if (cand) cmd({ type: 'guard', agentId: cand.id });
      } else if (onDuty.energy < 30) {
        const relief = team.find(a => a !== onDuty && a.energy >= 70 && available(a));
        if (relief) {
          cmd({ type: 'guard', agentId: relief.id });
          cmd({ type: 'rest', agentId: onDuty.id });
        }
      }
    }
  }

  FC.GodfredBrain = GodfredBrain;
  FC.HeadBrain = HeadBrain;
})(window.FC);
