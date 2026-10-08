// De manager: één agent die alle andere agents aanstuurt.
//
// Belangrijk ontwerpprincipe: de manager *kijkt* naar de staat van de
// organisatie en *geeft commando's*. Hij verandert zelf nooit direct iets.
// De organisatie (org.js) voert de commando's uit. Daardoor kan deze
// regelgebaseerde manager later vervangen worden door een echte AI-agent die
// precies dezelfde commando's als tools krijgt (zie docs/PLAN.md):
//
//   { type: 'assign',      questId, agentIds }   werk toewijzen (1 of meer agents)
//   { type: 'meeting',     topic }               iedereen naar de vergaderzaal
//   { type: 'rest',        agentId }             agent naar de lounge sturen
//   { type: 'guard',       agentId }             agent bij de poort posten
//   { type: 'createQuest', dept, title?, difficulty? }  nieuw werk inplannen
//   { type: 'say',         agentId, text }       iets zeggen (tekstballon)
window.FC = window.FC || {};

(function (FC) {
  const PLAN_EVERY = 10;     // speelminuten tussen planrondes
  const STANDUP_HOUR = 9;

  const AVAILABLE = new Set(['idle', 'coffee', 'working']);

  class Director {
    constructor(org) {
      this.org = org;
      this.cooldown = 2;
    }

    // Wordt elke speelminuut aangeroepen.
    tick() {
      const org = this.org;
      const s = org.state;
      if (org.isNight() || !org.lead()) return;

      if (!s.meeting && s.minute >= STANDUP_HOUR * 60 && s.memory.lastStandupDay !== s.day) {
        s.memory.lastStandupDay = s.day;
        this.run([{ type: 'meeting', topic: 'Dagelijkse stand-up' }]);
        return;
      }
      if (!s.meeting && s.firewall < 60 && s.memory.lastCrisisDay !== s.day) {
        s.memory.lastCrisisDay = s.day;
        this.run([{ type: 'meeting', topic: 'Crisisoverleg: de firewall staat onder druk!' }]);
        return;
      }
      if (s.meeting) return;
      if (--this.cooldown > 0) return;
      this.cooldown = PLAN_EVERY;
      this.run(this.plan());
    }

    // Direct na een vergadering wordt het werk verdeeld.
    afterMeeting() {
      this.cooldown = 1;
    }

    run(cmds) {
      cmds.forEach(c => this.org.execute(c, 'manager'));
    }

    plan() {
      const s = this.org.state;
      const cmds = [];
      const workers = s.agents.filter(a => a.role === 'worker');
      const reserved = new Set();

      // 1. De poort moet altijd bewaakt zijn.
      const security = workers.filter(a => a.type === 'BEVEILIGING');
      const onDuty = security.find(a => a.state === 'guarding' || a.intent === 'guard');
      if (!onDuty) {
        const cand = security
          .filter(a => a.energy >= 40 && AVAILABLE.has(a.state))
          .sort((p, q) => q.energy - p.energy)[0];
        if (cand) { cmds.push({ type: 'guard', agentId: cand.id }); reserved.add(cand.id); }
      } else if (onDuty.energy < 30) {
        const relief = security.find(a => a !== onDuty && a.energy >= 70 && AVAILABLE.has(a.state));
        if (relief) {
          cmds.push({ type: 'guard', agentId: relief.id }, { type: 'rest', agentId: onDuty.id });
          reserved.add(relief.id);
        }
      }

      // 2. Uitgeputte medewerkers naar de lounge.
      workers
        .filter(a => a.state === 'working' && a.energy < 20)
        .forEach(a => { cmds.push({ type: 'rest', agentId: a.id }); reserved.add(a.id); });

      // 3. Werk verdelen per afdeling. Opdrachten van de baas gaan voor,
      //    zware klussen krijgen een duo.
      const free = workers.filter(a => a.state === 'idle' && !a.questId && a.energy >= 30 && !reserved.has(a.id));
      for (const dept of FC.QUEST_DEPTS) {
        const pool = free.filter(a => a.dept === dept).sort((p, q) => q.level - p.level);
        const open = s.quests
          .filter(q => q.dept === dept && q.status === 'open')
          .sort((p, q) => (q.custom - p.custom) || (q.difficulty - p.difficulty));
        for (const q of open) {
          if (!pool.length) break;
          const team = q.difficulty >= 4 && pool.length >= 2 ? pool.splice(0, 2) : pool.splice(0, 1);
          cmds.push({ type: 'assign', questId: q.id, agentIds: team.map(a => a.id) });
        }

        // 4. Backlog op peil houden.
        const backlog = s.quests.filter(q => q.dept === dept && q.status !== 'klaar').length;
        const staff = workers.filter(a => a.dept === dept).length;
        if (staff && backlog < staff + 1 && Math.random() < 0.5) cmds.push({ type: 'createQuest', dept });
      }
      return cmds;
    }
  }

  FC.Director = Director;
})(window.FC);
