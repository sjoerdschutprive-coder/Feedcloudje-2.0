// De organisatie-motor. Houdt de staat bij (agents, quests, vergaderingen,
// beveiliging), voert commando's van de manager uit en publiceert
// gebeurtenissen. Het dashboard luistert alleen naar die gebeurtenissen.
window.FC = window.FC || {};

(function (FC) {
  const MAP = FC.map;
  const SAVE_KEY = 'feedcloudje.org.v2';
  const GAME_MINUTES_PER_SECOND = 8; // bij 1x snelheid: een dag ≈ 3 minuten
  const WALK_SPEED = 3.6;            // tegels per seconde
  const BATTLE_TURN_SECONDS = 1.3;   // echte tijd, zodat je gevechten kunt volgen
  const RECRUIT_COST = 200;
  const MEETING_LENGTH = 30;         // speelminuten
  const MEETING_MAX_WAIT = 50;

  const TYPES = {
    CODE:        { color: '#4a90e2', moves: ['REFACTOR', 'UNIT TEST', 'DEBUGGER'],     bugs: ['NULLPOINTER', 'MEMLEAK', 'OFF-BY-ONE', 'DEADLOCK'] },
    DATA:        { color: '#3fae5a', moves: ['QUERY', 'REGRESSIE', 'SCHOONMAAK'],     bugs: ['CORRUPTE CSV', 'DUBBELE RIJ', 'NaN-GEEST'] },
    CREATIEF:    { color: '#f06bb5', moves: ['BRAINSTORM', 'SCHETS', 'KLEURSPAT'],    bugs: ['WRITERS BLOCK', 'COMIC SANS', 'LOREM IPSUM'] },
    BEVEILIGING: { color: '#7d879b', moves: ['FIREWALL', 'SCAN', 'QUARANTAINE'],      bugs: ['PHISHING', 'WACHTWOORD123', 'TROJAN'] },
    STRATEGIE:   { color: '#a8743f', moves: ['ROADMAP', 'PRIORITEIT', 'VERGADERING'], bugs: ['SCOPE CREEP', 'DEADLINE', 'MEETINGMONSTER'] },
    OPERATIONS:  { color: '#f08a2c', moves: ['HERSTART', 'PATCH', 'OPRUIMEN'],        bugs: ['STORING', 'VOLLE SCHIJF', 'KABELKNOOP'] },
  };

  const QUEST_TEMPLATES = {
    lab:    ['Login-pagina bouwen', 'API koppelen', 'Tests schrijven', 'Database migreren', 'Performance tunen', 'Bug-backlog wegwerken'],
    studio: ['Logo ontwerpen', 'Social post maken', 'Video monteren', 'Websiteteksten', 'Campagne bedenken'],
    bieb:   ['Marktonderzoek', 'Data opschonen', 'Klantanalyse', 'Weekrapport maken', 'Trends voorspellen'],
    werk:   ['Serveronderhoud', 'Back-up maken', 'Facturen verwerken', 'Planning bijwerken', 'Voorraad tellen'],
    poort:  ['Toegang auditen', 'Wachtwoorden roteren', 'Pentest uitvoeren', 'Logs controleren'],
  };

  const NICKNAMES = ['PIP', 'NOVA', 'BRAM', 'LOTTE', 'JUUL', 'DEX', 'FENNA', 'MILO', 'SAAR', 'TIJN',
    'ROOS', 'KAI', 'LIEKE', 'OTTO', 'EVI', 'SEM', 'NOOR', 'GUUS', 'ISA', 'TEUN', 'MAX', 'ZOE',
    'JIP', 'FEM', 'BOAZ', 'LUUK', 'MAAN', 'STAN', 'VERA', 'WOUT', 'YARA', 'ZEP', 'HUGO', 'NINA'];

  const rand = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
  const pick = arr => arr[Math.floor(Math.random() * arr.length)];
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const xpNeeded = lvl => 20 + lvl * lvl * 8;
  const names = list => list.map(a => a.name).join(' & ');

  class Org {
    constructor() {
      this.listeners = [];
      this.speed = 1;
      this.paused = false;
      this.minuteAcc = 0;
      this.battleAcc = 0;
      this.state = null;
      this.spots = new Map(); // bezette plekken (stoelen, zitzakken, ...) → agentId
      this.director = new FC.Director(this);
    }

    on(fn) { this.listeners.push(fn); }
    emit(event) {
      event.time = this.clockLabel();
      if (event.kind !== 'say') {
        this.state.log.unshift(event);
        this.state.log.length = Math.min(this.state.log.length, 120);
      }
      this.listeners.forEach(fn => fn(event));
    }

    // ---------- opstarten & opslaan ----------

    newGame() {
      this.spots.clear();
      this.state = {
        name: 'FEEDCLOUDJE',
        day: 1,
        minute: 8 * 60 + 40,
        credits: 150,
        firewall: 100,
        nextId: 1,
        agents: [],
        quests: [],
        battle: null,
        meeting: null,
        memory: { lastStandupDay: 0, lastCrisisDay: 0 },
        stats: { questsDone: 0, bugsBeaten: 0, intrudersBlocked: 0, breaches: 0, meetings: 0 },
        log: [],
      };
      this.addAgent('PLANUIL', { role: 'lead', name: 'UILBERT' });
      [['BITBIT', 3], ['PIXELFEE', 3], ['DATADIL', 3], ['MOERBOT', 2], ['KLUISBEER', 2]]
        .forEach(([sp, n]) => { for (let i = 0; i < n; i++) this.addAgent(sp, { initial: true }); });
      FC.QUEST_DEPTS.forEach(d => { this.addQuest(d); this.addQuest(d); });
      this.director.cooldown = 2;
      this.emit({ kind: 'info', text: `Welkom bij ${this.state.name}! Manager UILBERT en het team zitten klaar op kantoor.` });
    }

    load() {
      try {
        const raw = localStorage.getItem(SAVE_KEY);
        if (!raw) return false;
        const data = JSON.parse(raw);
        if (!data || !Array.isArray(data.agents)) return false;
        this.state = data;
        this.state.battle = null;
        this.state.meeting = null;
        this.spots.clear();
        // Iedereen begint weer aan zijn eigen bureau.
        this.state.agents.forEach(a => {
          a.path = [];
          a.intent = null;
          a.x = a.seat.x; a.y = a.seat.y;
          const q = this.quest(a.questId);
          a.state = q && q.status === 'actief' ? 'working' : 'idle';
          if (!q || q.status !== 'actief') a.questId = null;
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
    lead() { return this.state.agents.find(a => a.role === 'lead'); }

    freeDesk(dept) {
      const r = MAP.room(dept);
      return r.seats.find(s => !this.state.agents.some(a => a.seat.x === s.x && a.seat.y === s.y));
    }

    addAgent(species, opts = {}) {
      const role = opts.role || 'worker';
      const type = FC.sprites.SPECIES[species].type;
      const dept = role === 'lead' ? 'hq' : MAP.roomForType(type).id;
      const seat = role === 'lead' ? MAP.BOSS_SEAT : this.freeDesk(dept);
      if (!seat) return null;
      const used = new Set(this.state.agents.map(a => a.name));
      const free = NICKNAMES.filter(n => !used.has(n));
      const name = opts.name || (free.length ? pick(free) : `${pick(NICKNAMES)}${this.state.nextId}`);
      const a = {
        id: this.state.nextId++,
        name, species, type, role, dept,
        seat: { x: seat.x, y: seat.y },
        level: role === 'lead' ? 9 : opts.initial ? rand(3, 6) : rand(1, 3),
        xp: 0,
        energy: 100,
        state: 'idle',
        intent: null,
        questId: null,
        x: seat.x, y: seat.y,
        path: [],
        facing: 1,
        timer: 0,
        stats: { quests: 0, bugs: 0, blocked: 0 },
      };
      this.state.agents.push(a);
      return a;
    }

    addQuest(dept, title, difficulty, source) {
      const diff = difficulty || rand(1, 5);
      const q = {
        id: this.state.nextId++,
        dept,
        title: title || pick(QUEST_TEMPLATES[dept]),
        difficulty: diff,
        required: diff * 100,
        progress: 0,
        status: 'open',      // open | actief | klaar
        assignees: [],
        reward: { xp: diff * 12, credits: diff * 10 },
        custom: source === 'baas',
        source: source || 'manager',
      };
      this.state.quests.push(q);
      return q;
    }

    recruit() {
      if (this.state.credits < RECRUIT_COST) {
        this.emit({ kind: 'warn', text: `Niet genoeg credits. Werven kost ${RECRUIT_COST} ⛁.` });
        return null;
      }
      const options = Object.keys(FC.sprites.SPECIES).filter(sp => sp !== 'PLANUIL');
      const species = pick(options.filter(sp => this.freeDesk(MAP.roomForType(FC.sprites.SPECIES[sp].type).id)));
      if (!species) {
        this.emit({ kind: 'warn', text: 'Alle bureaus zijn bezet. Er past niemand meer bij.' });
        return null;
      }
      this.state.credits -= RECRUIT_COST;
      const a = this.addAgent(species);
      // Nieuwkomers komen door de poort binnen en lopen naar hun bureau.
      a.x = MAP.GUARD_SPOT.x; a.y = MAP.GUARD_SPOT.y;
      this.toDesk(a);
      this.emit({ kind: 'recruit', agentId: a.id, text: `${a.name} de ${species} komt door de poort binnen en loopt naar de ${MAP.room(a.dept).name}!` });
      return a;
    }

    // ---------- plekken & beweging ----------

    claimSpot(a, list) {
      const free = list.find(s => !this.spots.has(MAP.spotKey(s)));
      if (!free) return null;
      this.spots.set(MAP.spotKey(free), a.id);
      a.spot = MAP.spotKey(free);
      return free;
    }

    releaseSpot(a) {
      if (a.spot && this.spots.get(a.spot) === a.id) this.spots.delete(a.spot);
      a.spot = null;
    }

    moveTo(a, target, intent) {
      const path = MAP.findPath(a.x, a.y, target.x, target.y);
      a.x = Math.round(a.x); a.y = Math.round(a.y);
      a.intent = intent;
      if (path === null) { a.x = target.x; a.y = target.y; a.path = []; this.arrive(a); return; }
      a.path = path;
      a.state = 'walking';
      if (!path.length) this.arrive(a);
    }

    toDesk(a) { this.releaseSpot(a); this.moveTo(a, a.seat, 'desk'); }

    toRest(a) {
      this.releaseSpot(a);
      const spot = this.claimSpot(a, MAP.REST_SPOTS);
      // Lounge vol? Dan maar een dutje aan het eigen bureau.
      this.moveTo(a, spot || a.seat, 'rest');
    }

    toCoffee(a) {
      this.releaseSpot(a);
      const spot = this.claimSpot(a, MAP.COFFEE_SPOTS);
      if (!spot) return false;
      this.moveTo(a, spot, 'coffee');
      return true;
    }

    toMeeting(a) {
      this.releaseSpot(a);
      const spot = a.role === 'lead'
        ? this.claimSpot(a, [MAP.PRESENTER_SPOT])
        : this.claimSpot(a, MAP.MEETING_SEATS);
      if (!spot) return false;
      this.moveTo(a, spot, 'meeting');
      return true;
    }

    toReport(a, text) {
      this.releaseSpot(a);
      const spot = this.claimSpot(a, MAP.VISITOR_SPOTS);
      if (!spot) return false;
      a.reportText = text;
      this.moveTo(a, spot, 'report');
      return true;
    }

    hasActiveQuest(a) {
      const q = this.quest(a.questId);
      return !!(q && q.status === 'actief' && q.assignees.includes(a.id));
    }

    arrive(a) {
      const intent = a.intent;
      a.intent = null;
      switch (intent) {
        case 'desk':
          a.state = this.hasActiveQuest(a) ? 'working' : 'idle';
          break;
        case 'rest':
          a.state = 'resting';
          break;
        case 'coffee':
          a.state = 'coffee';
          a.timer = rand(8, 15);
          break;
        case 'meeting':
          if (!this.state.meeting) { this.toDesk(a); break; }
          a.state = 'meeting';
          break;
        case 'report':
          a.state = 'visiting';
          a.timer = 10;
          this.onReportArrive(a);
          break;
        case 'guard':
          a.state = 'guarding';
          this.say(a, 'Ik sta op wacht!');
          break;
        default:
          a.state = 'idle';
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

    // ---------- commando's (de interface van de manager) ----------

    execute(cmd, source) {
      const lead = this.lead();
      const by = source === 'baas' ? 'DE BAAS' : lead.name;
      switch (cmd.type) {
        case 'assign':
          return this.assign(cmd.questId, cmd.agentIds);
        case 'meeting':
          return this.callMeeting(cmd.topic);
        case 'rest': {
          const a = this.agent(cmd.agentId);
          if (!a || a.state === 'battling' || a.state === 'resting' || a.intent === 'rest') return false;
          this.emit({ kind: 'order', from: lead.id, to: [a.id], agentId: a.id, text: `${by} stuurt ${a.name} naar de LOUNGE om bij te komen.` });
          this.toRest(a);
          return true;
        }
        case 'guard': {
          const a = this.agent(cmd.agentId);
          if (!a || a.state === 'battling') return false;
          this.releaseQuest(a);
          this.releaseSpot(a);
          this.moveTo(a, MAP.GUARD_SPOT, 'guard');
          this.emit({ kind: 'order', from: lead.id, to: [a.id], agentId: a.id, text: `${by} → ${a.name}: bewaak de POORT!` });
          return true;
        }
        case 'createQuest': {
          const q = this.addQuest(cmd.dept, cmd.title, cmd.difficulty, source === 'baas' ? 'baas' : 'manager');
          this.emit({ kind: 'plan', agentId: lead.id, text: `${by} zet nieuw werk klaar voor ${MAP.room(q.dept).name}: "${q.title}".` });
          return q;
        }
        case 'say': {
          const a = this.agent(cmd.agentId);
          if (a) this.say(a, cmd.text);
          return true;
        }
        default:
          return false;
      }
    }

    say(a, text) {
      this.emit({ kind: 'say', agentId: a.id, text });
    }

    assign(questId, agentIds) {
      const q = this.quest(questId);
      if (!q || q.status === 'klaar') return false;
      const team = agentIds.map(id => this.agent(id)).filter(a => a && a.role === 'worker' && !a.questId);
      if (!team.length) return false;
      q.status = 'actief';
      q.assignees = team.map(a => a.id);
      team.forEach(a => {
        a.questId = q.id;
        if (a.state === 'idle') a.state = 'working';
      });
      const lead = this.lead();
      this.emit({
        kind: 'order', from: lead.id, to: q.assignees, agentId: team[0].id,
        text: `${lead.name} → ${names(team)}: "${q.title}"${team.length > 1 ? ' (samen)' : ''}`,
      });
      this.say(lead, `${names(team)}: ${q.title}!`);
      return true;
    }

    releaseQuest(a) {
      const q = this.quest(a.questId);
      if (q && q.status === 'actief') {
        q.assignees = q.assignees.filter(id => id !== a.id);
        if (!q.assignees.length) q.status = 'open';
      }
      a.questId = null;
    }

    // ---------- vergaderingen ----------

    callMeeting(topic) {
      const s = this.state;
      if (s.meeting || this.isNight()) return false;
      const lead = this.lead();
      const attendees = s.agents.filter(a =>
        a.state !== 'guarding' && a.intent !== 'guard' && a.state !== 'battling' &&
        !(a.state === 'resting' && a.energy < 40));
      s.meeting = { topic, phase: 'verzamelen', attendees: [], timer: 0 };
      attendees.forEach(a => { if (this.toMeeting(a)) s.meeting.attendees.push(a.id); });
      s.stats.meetings++;
      this.emit({ kind: 'meeting', agentId: lead.id, text: `${lead.name} roept iedereen bij elkaar: ${topic}.` });
      this.say(lead, 'Allemaal naar de vergaderzaal!');
      return true;
    }

    tickMeeting() {
      const m = this.state.meeting;
      if (!m) return;
      if (this.isNight()) { this.endMeeting(); return; }
      m.timer++;
      const present = m.attendees.map(id => this.agent(id)).filter(a => a && a.state === 'meeting');
      if (m.phase === 'verzamelen') {
        const everyone = m.attendees.every(id => { const a = this.agent(id); return !a || a.state === 'meeting'; });
        if (everyone || m.timer > MEETING_MAX_WAIT) {
          m.phase = 'bezig';
          m.timer = 0;
          const lead = this.lead();
          this.say(lead, m.topic);
          this.emit({ kind: 'info', text: `De vergadering begint (${present.length} aanwezig).` });
        }
        return;
      }
      if (m.timer % 6 === 0 && present.length) {
        const speaker = pick(present);
        this.say(speaker, this.meetingLine(speaker));
      }
      if (m.timer >= MEETING_LENGTH) this.endMeeting();
    }

    meetingLine(a) {
      if (a.role === 'lead') {
        return pick(['Wie heeft er blokkades?', 'Goed werk, team!', 'Focus: de backlog wegwerken.',
          `De firewall staat op ${Math.round(this.state.firewall)}%.`, `We hebben ${this.state.credits} credits.`,
          'Ik verdeel zo het werk.']);
      }
      const q = this.quest(a.questId);
      if (q) return `Bezig met ${q.title} (${Math.floor(q.progress / q.required * 100)}%)`;
      return pick(['Ik heb ruimte voor werk!', 'Klaar voor de volgende quest.', 'Ik heb een idee...',
        'Gisteren een bug verslagen!', 'Kan iemand me helpen?']);
    }

    endMeeting() {
      const m = this.state.meeting;
      if (!m) return;
      this.state.meeting = null;
      m.attendees.forEach(id => {
        const a = this.agent(id);
        if (a && (a.state === 'meeting' || a.intent === 'meeting')) this.toDesk(a);
      });
      this.emit({ kind: 'meeting', agentId: this.lead().id, text: 'Vergadering afgelopen. Iedereen terug naar zijn bureau!' });
      this.director.afterMeeting();
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
      if (s.minute === 22 * 60) this.emit({ kind: 'info', text: 'Het wordt donker. Het team gaat naar de lounge, de wacht blijft op post.' });
      if (s.minute === 6 * 60) this.emit({ kind: 'info', text: 'Goedemorgen! De zon komt op boven het dal.' });

      for (const a of s.agents) this.tickAgent(a);
      this.tickMeeting();
      this.tickSecurity();
      this.director.tick();

      const done = s.quests.filter(q => q.status === 'klaar');
      if (done.length > 15) s.quests = s.quests.filter(q => q.status !== 'klaar' || done.indexOf(q) >= done.length - 15);
      if (s.minute % 30 === 0) this.save();
    }

    tickAgent(a) {
      const night = this.isNight();
      switch (a.state) {
        case 'working': {
          const q = this.quest(a.questId);
          if (!q || q.status !== 'actief') { a.questId = null; a.state = 'idle'; break; }
          const match = MAP.room(q.dept).type === a.type;
          q.progress += (1 + a.level * 0.25) * (match ? 1.5 : 1);
          a.energy = clamp(a.energy - 0.12, 0, 100);
          if (q.progress >= q.required) this.completeQuest(q);
          else if (!this.state.battle && Math.random() < 0.001) this.startBattle(a);
          else if (night) this.toRest(a); // quest blijft van hem, morgen verder
          break;
        }
        case 'idle':
          if (night || a.energy < 30) { this.toRest(a); break; }
          if (a.role === 'worker' && !this.state.meeting && Math.random() < 0.004) this.toCoffee(a);
          break;
        case 'resting':
          a.energy = clamp(a.energy + (a.spot ? 1.2 : 0.7), 0, 100);
          if (!night && a.energy >= 100) this.toDesk(a);
          break;
        case 'coffee':
          a.energy = clamp(a.energy + 0.3, 0, 100);
          if (--a.timer <= 0) this.toDesk(a);
          break;
        case 'visiting':
          if (--a.timer <= 0) this.toDesk(a);
          break;
        case 'guarding':
          a.energy = clamp(a.energy - 0.05, 0, 100);
          if (a.energy < 12) {
            this.emit({ kind: 'warn', agentId: a.id, text: `${a.name} is te moe om de wacht te houden en verlaat de POORT!` });
            this.toRest(a);
          }
          break;
        default:
          break;
      }
    }

    completeQuest(q) {
      const s = this.state;
      q.status = 'klaar';
      q.progress = q.required;
      const team = q.assignees.map(id => this.agent(id)).filter(Boolean);
      s.credits += q.reward.credits;
      s.stats.questsDone++;
      this.emit({ kind: 'quest', agentId: team[0] && team[0].id, text: `${names(team)} rondde "${q.title}" af! +${q.reward.credits} ⛁` });
      team.forEach(a => {
        a.questId = null;
        a.stats.quests++;
        if (a.state === 'working') a.state = 'idle';
        this.gainXp(a, q.reward.xp);
      });
      // Rapporteren bij de manager: bij grote klussen loopt iemand langs,
      // anders gaat er een berichtje naar boven.
      const reporter = team[0];
      const lead = this.lead();
      if (!reporter) return;
      const walk = q.difficulty >= 3 && reporter.state === 'idle' && !s.meeting && !this.isNight() &&
        this.toReport(reporter, q.title);
      if (!walk) {
        this.emit({ kind: 'report', from: reporter.id, to: [lead.id], agentId: reporter.id,
          text: `${reporter.name} meldt aan ${lead.name}: "${q.title}" is klaar.` });
      }
    }

    onReportArrive(a) {
      const lead = this.lead();
      this.say(a, `${a.reportText}: klaar!`);
      this.emit({ kind: 'report', agentId: a.id, text: `${a.name} brengt persoonlijk verslag uit bij ${lead.name}: "${a.reportText}" is af.` });
      this.say(lead, `Top werk, ${a.name}!`);
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
        this.say(guard, 'Hier kom je niet langs!');
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
      const bug = { name: pick(t.bugs), level: lvl, hp: maxHp, maxHp };
      this.state.battle = { agentId: a.id, bug, text: `Een wilde ${bug.name} verscheen!`, turn: 0, over: false };
      a.state = 'battling';
      this.battleAcc = 0;
      this.emit({ kind: 'bug', agentId: a.id, text: `Een wilde ${bug.name} viel ${a.name} aan!` });
    }

    battleTurn() {
      const b = this.state.battle;
      const a = this.agent(b.agentId);
      if (!a || b.over) { this.state.battle = null; return; }
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
          a.state = this.hasActiveQuest(a) ? 'working' : 'idle';
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
          this.toRest(a);
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
