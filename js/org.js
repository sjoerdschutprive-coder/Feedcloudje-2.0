// De organisatie-motor. Houdt de staat bij (medewerkers, quests, beveiliging)
// en publiceert gebeurtenissen. Het dashboard luistert alleen naar die
// gebeurtenissen, zodat we later echte AI-agents op dezelfde manier kunnen
// aansluiten (zie docs/PLAN.md).
window.FC = window.FC || {};

(function (FC) {
  const MAP = FC.map;
  const SAVE_KEY = 'feedcloudje.org.v1';
  const GAME_MINUTES_PER_SECOND = 8; // bij 1x snelheid: een dag ≈ 3 minuten
  const WALK_SPEED = 3.2;            // tegels per seconde
  const BATTLE_TURN_SECONDS = 1.3;   // echte tijd, zodat je gevechten kunt volgen
  const RECRUIT_COST = 200;

  const TYPES = {
    CODE:        { color: '#4a90e2', moves: ['REFACTOR', 'UNIT TEST', 'DEBUGGER'],      bugs: ['NULLPOINTER', 'MEMLEAK', 'OFF-BY-ONE', 'DEADLOCK'] },
    DATA:        { color: '#3fae5a', moves: ['QUERY', 'REGRESSIE', 'SCHOONMAAK'],      bugs: ['CORRUPTE CSV', 'DUBBELE RIJ', 'NaN-GEEST'] },
    CREATIEF:    { color: '#f06bb5', moves: ['BRAINSTORM', 'SCHETS', 'KLEURSPAT'],     bugs: ['WRITERS BLOCK', 'COMIC SANS', 'LOREM IPSUM'] },
    BEVEILIGING: { color: '#7d879b', moves: ['FIREWALL', 'SCAN', 'QUARANTAINE'],       bugs: ['PHISHING', 'WACHTWOORD123', 'TROJAN'] },
    STRATEGIE:   { color: '#a8743f', moves: ['ROADMAP', 'PRIORITEIT', 'VERGADERING'],  bugs: ['SCOPE CREEP', 'DEADLINE', 'MEETINGMONSTER'] },
    OPERATIONS:  { color: '#f08a2c', moves: ['HERSTART', 'PATCH', 'OPRUIMEN'],         bugs: ['STORING', 'VOLLE SCHIJF', 'KABELKNOOP'] },
  };

  const QUEST_TEMPLATES = {
    lab:    ['Login-pagina bouwen', 'API koppelen', 'Tests schrijven', 'Database migreren', 'Performance tunen', 'Bug-backlog wegwerken'],
    bieb:   ['Marktonderzoek', 'Data opschonen', 'Klantanalyse', 'Weekrapport maken', 'Trends voorspellen'],
    studio: ['Logo ontwerpen', 'Social post maken', 'Video monteren', 'Websiteteksten', 'Campagne bedenken'],
    werk:   ['Serveronderhoud', 'Back-up maken', 'Facturen verwerken', 'Planning bijwerken', 'Voorraad tellen'],
    hq:     ['Kwartaalplan', 'Partneroverleg', 'Budget verdelen', 'Visie aanscherpen', 'Team-evaluatie'],
    poort:  ['Toegang auditen', 'Wachtwoorden roteren', 'Pentest uitvoeren', 'Logs controleren'],
  };

  const NICKNAMES = ['PIP', 'NOVA', 'BRAM', 'LOTTE', 'JUUL', 'DEX', 'FENNA', 'MILO', 'SAAR', 'TIJN',
    'ROOS', 'KAI', 'LIEKE', 'OTTO', 'EVI', 'SEM', 'NOOR', 'GUUS', 'ISA', 'TEUN'];

  const rand = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
  const pick = arr => arr[Math.floor(Math.random() * arr.length)];
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const xpNeeded = lvl => 20 + lvl * lvl * 8;

  class Org {
    constructor() {
      this.listeners = [];
      this.speed = 1;
      this.paused = false;
      this.minuteAcc = 0;
      this.battleAcc = 0;
      this.state = null;
    }

    on(fn) { this.listeners.push(fn); }
    emit(event) {
      event.time = this.clockLabel();
      this.state.log.unshift(event);
      this.state.log.length = Math.min(this.state.log.length, 80);
      this.listeners.forEach(fn => fn(event));
    }

    // ---------- opstarten & opslaan ----------

    newGame() {
      this.state = {
        name: 'FEEDCLOUDJE',
        day: 1,
        minute: 7 * 60,
        credits: 150,
        firewall: 100,
        nextId: 1,
        agents: [],
        quests: [],
        battle: null,
        stats: { questsDone: 0, bugsBeaten: 0, intrudersBlocked: 0, breaches: 0 },
        log: [],
      };
      ['PLANUIL', 'BITBIT', 'DATADIL', 'PIXELFEE', 'MOERBOT', 'KLUISBEER']
        .forEach(sp => this.addAgent(sp, true));
      for (let i = 0; i < 8; i++) this.addQuest();
      this.emit({ kind: 'info', text: `Welkom bij ${this.state.name}! Je team staat klaar in het dal.` });
    }

    load() {
      try {
        const raw = localStorage.getItem(SAVE_KEY);
        if (!raw) return false;
        const data = JSON.parse(raw);
        if (!data || !Array.isArray(data.agents)) return false;
        this.state = data;
        this.state.battle = null;
        // Iedereen die halverwege iets was, begint weer fris.
        this.state.agents.forEach(a => {
          if (a.state === 'battling') a.state = 'idle';
          a.path = [];
        });
        return true;
      } catch (e) {
        return false;
      }
    }

    save() {
      try { localStorage.setItem(SAVE_KEY, JSON.stringify(this.state)); } catch (e) { /* geen opslag beschikbaar */ }
    }

    reset() {
      try { localStorage.removeItem(SAVE_KEY); } catch (e) { /* idem */ }
      this.newGame();
    }

    // ---------- helpers ----------

    clockLabel() {
      if (!this.state) return '';
      const h = Math.floor(this.state.minute / 60);
      const m = Math.floor(this.state.minute % 60);
      return `DAG ${this.state.day} ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    }

    isNight() {
      const h = this.state.minute / 60;
      return h >= 22 || h < 6;
    }

    agent(id) { return this.state.agents.find(a => a.id === id); }
    quest(id) { return this.state.quests.find(q => q.id === id); }
    typeInfo(type) { return TYPES[type]; }

    addAgent(species, initial) {
      const used = new Set(this.state.agents.map(a => a.name));
      const free = NICKNAMES.filter(n => !used.has(n));
      const name = free.length ? pick(free) : `${pick(NICKNAMES)}${this.state.nextId}`;
      const spot = MAP.randomOpenTile();
      const a = {
        id: this.state.nextId++,
        name,
        species,
        type: FC.sprites.SPECIES[species].type,
        level: initial ? rand(3, 6) : rand(1, 3),
        xp: 0,
        energy: 100,
        state: 'idle',
        intent: null,      // waar is de medewerker naartoe onderweg?
        questId: null,
        x: spot.x, y: spot.y,
        path: [],
        facing: 1,
        wanderWait: rand(10, 40),
        stats: { quests: 0, bugs: 0, blocked: 0 },
        hired: this.clockLabel(),
      };
      this.state.agents.push(a);
      return a;
    }

    addQuest(deptId, title, difficulty) {
      const depts = Object.keys(QUEST_TEMPLATES);
      const dept = deptId || pick(depts);
      const diff = difficulty || rand(1, 5);
      const q = {
        id: this.state.nextId++,
        dept,
        title: title || pick(QUEST_TEMPLATES[dept]),
        difficulty: diff,
        required: diff * 40,
        progress: 0,
        status: 'open',      // open | actief | klaar
        assignee: null,
        reward: { xp: diff * 12, credits: diff * 10 },
        custom: !!title,
      };
      this.state.quests.push(q);
      return q;
    }

    recruit() {
      if (this.state.credits < RECRUIT_COST) {
        this.emit({ kind: 'warn', text: `Niet genoeg credits. Werven kost ${RECRUIT_COST} ⛁.` });
        return null;
      }
      this.state.credits -= RECRUIT_COST;
      const species = pick(Object.keys(FC.sprites.SPECIES));
      const a = this.addAgent(species, false);
      this.emit({ kind: 'recruit', agentId: a.id, text: `Gelukt! ${a.name} de ${species} sluit zich aan bij het team!` });
      return a;
    }

    sendToRest(id) {
      const a = this.agent(id);
      if (!a || a.state === 'battling') return;
      this.releaseQuest(a);
      this.goTo(a, MAP.building('rust').door, 'rest');
      this.emit({ kind: 'info', agentId: a.id, text: `${a.name} gaat even uitrusten in het HERSTELHUIS.` });
    }

    // ---------- beweging ----------

    goTo(a, target, intent) {
      const path = MAP.findPath(a.x, a.y, target.x, target.y);
      a.x = Math.round(a.x); a.y = Math.round(a.y);
      if (path === null) { a.state = 'idle'; a.intent = null; return; }
      a.path = path;
      a.intent = intent;
      a.state = 'walking';
      if (path.length === 0) this.arrive(a);
    }

    arrive(a) {
      const intent = a.intent;
      a.intent = null;
      if (intent === 'work') {
        const q = this.quest(a.questId);
        if (!q || q.status === 'klaar') { a.state = 'idle'; return; }
        a.state = 'working';
      } else if (intent === 'rest') {
        a.state = 'resting';
      } else if (intent === 'guard') {
        a.state = 'guarding';
      } else {
        a.state = 'idle';
        a.wanderWait = rand(15, 60);
      }
    }

    moveAgents(dt) {
      for (const a of this.state.agents) {
        if (a.state !== 'walking' || !a.path.length) continue;
        let step = WALK_SPEED * dt;
        while (step > 0 && a.path.length) {
          const t = a.path[0];
          const dx = t.x - a.x, dy = t.y - a.y;
          const dist = Math.abs(dx) + Math.abs(dy);
          if (dx !== 0) a.facing = dx > 0 ? 1 : -1;
          if (dist <= step) {
            a.x = t.x; a.y = t.y;
            a.path.shift();
            step -= dist;
          } else {
            a.x += Math.sign(dx) * Math.min(step, Math.abs(dx));
            a.y += Math.sign(dy) * Math.min(step, Math.abs(dy));
            step = 0;
          }
        }
        if (!a.path.length) this.arrive(a);
      }
    }

    // ---------- de spel-lus ----------

    update(realDt) {
      if (!this.state || this.paused) return;
      const dt = Math.min(realDt, 0.25) * this.speed;
      this.moveAgents(dt);

      this.minuteAcc += dt * GAME_MINUTES_PER_SECOND;
      while (this.minuteAcc >= 1) {
        this.minuteAcc -= 1;
        this.tickMinute();
      }

      if (this.state.battle) {
        this.battleAcc += Math.min(realDt, 0.25);
        if (this.battleAcc >= BATTLE_TURN_SECONDS) {
          this.battleAcc = 0;
          this.battleTurn();
        }
      }
    }

    tickMinute() {
      const s = this.state;
      s.minute += 1;
      if (s.minute >= 24 * 60) {
        s.minute = 0;
        s.day += 1;
        this.emit({ kind: 'info', text: `Een nieuwe dag breekt aan: DAG ${s.day}.` });
      }
      if (s.minute === 22 * 60) this.emit({ kind: 'info', text: 'Het wordt donker. Het team gaat slapen, de wacht blijft op post.' });
      if (s.minute === 6 * 60) this.emit({ kind: 'info', text: 'Goedemorgen! De zon komt op boven het dal.' });

      for (const a of s.agents) this.tickAgent(a);

      // Altijd genoeg werk op de plank.
      const open = s.quests.filter(q => q.status !== 'klaar').length;
      if (open < s.agents.length + 2 && Math.random() < 0.05) this.addQuest();
      // Afgeronde quests opruimen (laatste 15 bewaren voor de historie).
      const done = s.quests.filter(q => q.status === 'klaar');
      if (done.length > 15) s.quests = s.quests.filter(q => q.status !== 'klaar' || done.indexOf(q) >= done.length - 15);

      this.tickSecurity();
      if (s.minute % 30 === 0) this.save();
    }

    tickAgent(a) {
      const night = this.isNight();
      switch (a.state) {
        case 'working': {
          const q = this.quest(a.questId);
          if (!q) { a.state = 'idle'; break; }
          const match = MAP.building(q.dept).type === a.type;
          q.progress += (1 + a.level * 0.25) * (match ? 1.5 : 1);
          a.energy = clamp(a.energy - (match ? 0.12 : 0.18), 0, 100);
          if (q.progress >= q.required) this.completeQuest(a, q);
          else if (!this.state.battle && Math.random() < 0.0035) this.startBattle(a);
          else if (a.energy < 15) {
            this.emit({ kind: 'warn', agentId: a.id, text: `${a.name} is moe en pauzeert "${q.title}".` });
            this.sendToRestQuiet(a);
          } else if (night && a.type !== 'BEVEILIGING') {
            this.sendToRestQuiet(a);
          }
          break;
        }
        case 'resting':
          a.energy = clamp(a.energy + 1.1, 0, 100);
          if (a.energy >= 100 && !night) {
            a.state = 'idle';
            a.wanderWait = 0;
            this.goTo(a, MAP.randomOpenTile(), 'wander');
          }
          break;
        case 'guarding':
          a.energy = clamp(a.energy - 0.04, 0, 100);
          if (a.energy < 20) this.sendToRestQuiet(a);
          else if (!night && Math.random() < 0.01) {
            // Overdag af en toe een beveiligingsquest oppakken als er nog een wacht is.
            const otherGuard = this.state.agents.some(o => o !== a && o.state === 'guarding');
            if (otherGuard) this.findWork(a);
          }
          break;
        case 'idle':
          if (night && a.type !== 'BEVEILIGING') { this.sendToRestQuiet(a); break; }
          if (a.energy < 30) { this.sendToRestQuiet(a); break; }
          if (a.type === 'BEVEILIGING' && !this.state.agents.some(o => o.state === 'guarding' || o.intent === 'guard')) {
            this.goTo(a, MAP.GUARD_SPOT, 'guard');
            break;
          }
          if (this.findWork(a)) break;
          if (--a.wanderWait <= 0) this.goTo(a, MAP.randomOpenTile(), 'wander');
          break;
        default:
          break;
      }
    }

    sendToRestQuiet(a) {
      this.releaseQuest(a);
      this.goTo(a, MAP.building('rust').door, 'rest');
    }

    releaseQuest(a) {
      const q = this.quest(a.questId);
      if (q && q.status === 'actief') { q.status = 'open'; q.assignee = null; }
      a.questId = null;
    }

    findWork(a) {
      const open = this.state.quests.filter(q => q.status === 'open');
      if (!open.length) return false;
      const home = MAP.buildingForType(a.type);
      // Voorkeur voor werk in de eigen afdeling, daarna eigen quests van de baas.
      const own = open.filter(q => home && q.dept === home.id);
      const custom = open.filter(q => q.custom);
      const q = custom[0] || own[0] || (Math.random() < 0.35 ? pick(open) : null);
      if (!q) return false;
      q.status = 'actief';
      q.assignee = a.id;
      a.questId = q.id;
      this.goTo(a, MAP.building(q.dept).door, 'work');
      if (a.state === 'idle') { this.releaseQuest(a); return false; }
      this.emit({ kind: 'info', agentId: a.id, text: `${a.name} pakt de quest "${q.title}" op.` });
      return true;
    }

    completeQuest(a, q) {
      q.status = 'klaar';
      q.progress = q.required;
      a.questId = null;
      a.stats.quests++;
      this.state.stats.questsDone++;
      this.state.credits += q.reward.credits;
      this.emit({ kind: 'quest', agentId: a.id, text: `${a.name} rondde "${q.title}" af! +${q.reward.credits} ⛁` });
      this.gainXp(a, q.reward.xp);
      a.state = 'idle';
      this.goTo(a, MAP.randomOpenTile(), 'wander');
    }

    gainXp(a, xp) {
      a.xp += xp;
      while (a.xp >= xpNeeded(a.level)) {
        a.xp -= xpNeeded(a.level);
        a.level++;
        this.emit({ kind: 'levelup', agentId: a.id, text: `${a.name} is gegroeid naar LEVEL ${a.level}!` });
      }
    }

    // ---------- beveiliging van de afgesloten omgeving ----------

    tickSecurity() {
      const s = this.state;
      const guard = s.agents.find(a => a.state === 'guarding');
      if (guard) s.firewall = clamp(s.firewall + 0.03, 0, 100);
      if (Math.random() > 0.004) return;
      const intruder = pick(['een onbekende bot', 'een spammer', 'een port-scanner', 'een nieuwsgierige crawler', 'een verdwaalde hacker']);
      if (guard) {
        s.stats.intrudersBlocked++;
        guard.stats.blocked++;
        this.emit({ kind: 'security', agentId: guard.id, text: `${guard.name} hield ${intruder} tegen bij de POORT!` });
        this.gainXp(guard, 8);
      } else {
        const dmg = rand(5, 12);
        s.firewall = clamp(s.firewall - dmg, 0, 100);
        s.stats.breaches++;
        this.emit({ kind: 'alarm', text: `ALARM! ${intruder} tikte tegen de poort. Firewall -${dmg}%. Er staat geen wacht!` });
      }
    }

    // ---------- gevechten tegen bugs ----------

    startBattle(a) {
      const t = TYPES[a.type];
      const lvl = clamp(a.level + rand(-2, 2), 1, 99);
      const maxHp = 18 + lvl * 6;
      this.state.battle = {
        agentId: a.id,
        bug: { name: pick(t.bugs), level: lvl, hp: maxHp, maxHp },
        text: '',
        turn: 0,
        over: false,
      };
      a.state = 'battling';
      this.battleAcc = 0;
      this.state.battle.text = `Een wilde ${this.state.battle.bug.name} verscheen!`;
      this.emit({ kind: 'bug', agentId: a.id, text: `Een wilde ${this.state.battle.bug.name} viel ${a.name} aan!` });
    }

    battleTurn() {
      const b = this.state.battle;
      const a = this.agent(b.agentId);
      if (!a) { this.state.battle = null; return; }
      if (b.over) { this.state.battle = null; return; }
      b.turn++;
      if (b.turn % 2 === 1) {
        const move = pick(TYPES[a.type].moves);
        const crit = Math.random() < 0.15;
        const dmg = Math.round((rand(6, 11) + a.level * 2) * (crit ? 1.8 : 1));
        b.bug.hp = Math.max(0, b.bug.hp - dmg);
        b.text = `${a.name} gebruikt ${move}!${crit ? ' Een voltreffer!' : ''}`;
        if (b.bug.hp <= 0) {
          b.over = true;
          b.text = `${b.bug.name} is verslagen! ${a.name} krijgt XP.`;
          a.stats.bugs++;
          this.state.stats.bugsBeaten++;
          this.emit({ kind: 'win', agentId: a.id, text: `${a.name} versloeg ${b.bug.name}!` });
          this.gainXp(a, 10 + b.bug.level * 4);
          a.state = 'working';
        }
      } else {
        const dmg = rand(4, 8) + Math.round(b.bug.level * 1.2);
        a.energy = Math.max(0, a.energy - dmg);
        b.text = `${b.bug.name} valt aan! ${a.name} verliest ${dmg} energie.`;
        if (a.energy <= 0) {
          b.over = true;
          a.energy = 5;
          const q = this.quest(a.questId);
          if (q) q.progress = Math.max(0, q.progress - q.required * 0.2);
          b.text = `${a.name} is uitgeput! ${b.bug.name} ontsnapt...`;
          this.emit({ kind: 'lose', agentId: a.id, text: `${a.name} verloor van ${b.bug.name} en moet herstellen.` });
          a.state = 'idle';
          this.sendToRestQuiet(a);
        }
      }
    }
  }

  FC.Org = Org;
  FC.TYPES = TYPES;
  FC.xpNeeded = xpNeeded;
  FC.RECRUIT_COST = RECRUIT_COST;
  FC.QUEST_DEPTS = Object.keys(QUEST_TEMPLATES);
})(window.FC);
