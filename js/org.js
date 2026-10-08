// De organisatie-motor. Houdt de staat bij (team, taken, projecten,
// vergaderingen, beveiliging), voert commando's uit en publiceert
// gebeurtenissen. Het dashboard luistert alleen naar die gebeurtenissen.
//
// De levensloop van een taak:
//   concept        Godfred heeft hem bedacht, nog niet opgehangen
//   bord           hangt op het prikbord
//   opgehaald      op de stapel van het afdelingshoofd
//   bezig          een agent werkt eraan
//   controle       output ligt bij het hoofd
//   gecontroleerd  goedgekeurd door het hoofd, wacht op bezorging
//   onderweg       het hoofd loopt ermee naar Godfred
//   ingeleverd     ligt bij Godfred
//   goedgekeurd    klaar. (Of terug naar 'bord' als revisie.)
window.FC = window.FC || {};

(function (FC) {
  const MAP = FC.map;
  const SAVE_KEY = 'feedcloudje.org.v3';
  const GAME_MINUTES_PER_SECOND = 8;
  const WALK_SPEED = 3.6;
  const RECRUIT_COST = 200;
  const MEETING_LENGTH = 25;
  const MEETING_MAX_WAIT = 40;
  const HEAD_REVIEW_MINUTES = 4;
  const GODFRED_REVIEW_MINUTES = 4;

  const TYPES = {
    CODE: { color: '#4a90e2' }, DATA: { color: '#3fae5a' }, CREATIEF: { color: '#f06bb5' },
    BEVEILIGING: { color: '#7d879b' }, STRATEGIE: { color: '#a8743f' }, OPERATIONS: { color: '#f08a2c' },
  };

  // Hoe Godfred een opdracht per afdeling formuleert.
  const PHASE = { lab: 'Bouwen', studio: 'Ontwerpen', bieb: 'Onderzoeken', werk: 'Organiseren', poort: 'Beveiligen' };
  const KEYWORDS = {
    lab:    ['app', 'website', 'site', 'api', 'code', 'bouw', 'software', 'tool', 'systeem', 'koppel', 'test'],
    studio: ['logo', 'ontwerp', 'campagne', 'video', 'post', 'tekst', 'huisstijl', 'design', 'social', 'nieuwsbrief', 'merk'],
    bieb:   ['onderzoek', 'analyse', 'data', 'rapport', 'markt', 'cijfers', 'klant', 'trend', 'concurrent'],
    werk:   ['planning', 'factuur', 'server', 'proces', 'inkoop', 'voorraad', 'backup', 'lancer', 'uitrol', 'support'],
    poort:  ['beveilig', 'toegang', 'wachtwoord', 'privacy', 'audit', 'avg', 'veilig'],
  };
  const TEMPLATES = {
    lab:    ['Login-pagina bouwen', 'API koppelen', 'Tests schrijven', 'Database migreren', 'Performance tunen'],
    studio: ['Logo ontwerpen', 'Social post maken', 'Video monteren', 'Websiteteksten', 'Campagne bedenken'],
    bieb:   ['Marktonderzoek', 'Data opschonen', 'Klantanalyse', 'Weekrapport maken', 'Trends voorspellen'],
    werk:   ['Serveronderhoud', 'Back-up maken', 'Facturen verwerken', 'Planning bijwerken', 'Voorraad tellen'],
    poort:  ['Toegang auditen', 'Wachtwoorden roteren', 'Pentest uitvoeren', 'Logs controleren'],
  };

  const NICKNAMES = ['PIP', 'NOVA', 'BRAM', 'LOTTE', 'JUUL', 'DEX', 'FENNA', 'MILO', 'SAAR', 'TIJN',
    'ROOS', 'KAI', 'LIEKE', 'OTTO', 'EVI', 'SEM', 'NOOR', 'GUUS', 'ISA', 'TEUN', 'MAX', 'ZOE',
    'JIP', 'FEM', 'BOAZ', 'LUUK', 'MAAN', 'STAN', 'VERA', 'WOUT', 'YARA', 'ZEP', 'HUGO', 'NINA',
    'BAS', 'DEMI', 'FLOOR', 'GIJS', 'JET', 'KOEN', 'MEES', 'PUCK', 'RIK', 'TESS'];

  // Wie mag welk commando geven.
  const PERMISSIONS = {
    baas:     ['order', 'meeting', 'rest'],
    director: ['plan', 'initiative', 'post', 'review', 'feedback', 'meeting', 'say'],
    head:     ['pickup', 'assign', 'review', 'check', 'deliver', 'rest', 'guard', 'say'],
  };

  const rand = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
  const pick = arr => arr[Math.floor(Math.random() * arr.length)];
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const xpNeeded = lvl => 20 + lvl * lvl * 8;
  const stars = q => Math.max(1, Math.ceil(q * 5));
  const roomName = dept => MAP.room(dept).name;
  const plural = n => (n === 1 ? '1 taak' : `${n} taken`);

  class Org {
    constructor() {
      this.listeners = [];
      this.speed = 1;
      this.paused = false;
      this.minuteAcc = 0;
      this.state = null;
      this.spots = new Map(); // bezette plekken (stoelen, zitzakken, ...) → agentId
      this.godfredBrain = new FC.GodfredBrain(this);
      this.headBrain = new FC.HeadBrain(this);
    }

    on(fn) { this.listeners.push(fn); }
    emit(event) {
      event.time = this.clockLabel();
      if (event.kind !== 'say') {
        this.state.log.unshift(event);
        this.state.log.length = Math.min(this.state.log.length, 150);
      }
      this.listeners.forEach(fn => fn(event));
    }

    // ---------- opstarten & opslaan ----------

    newGame() {
      this.spots.clear();
      this.state = {
        name: 'FEEDCLOUDJE',
        clock: 8 * 60 + 30,
        credits: 150,
        firewall: 100,
        nextId: 1,
        agents: [],
        tasks: [],
        projects: [],
        meeting: null,
        memory: { lastMt: 0, lastCrisis: -9999, lastInitiative: 0 },
        stats: { projectsDone: 0, tasksApproved: 0, revisions: 0, intrudersBlocked: 0, breaches: 0, meetings: 0 },
        log: [],
      };
      this.state.memory.lastMt = this.state.clock - 6 * 60 + 20; // eerste MT-overleg na ~20 minuten
      this.addAgent('PLANUIL', { role: 'director', name: 'GODFRED' });
      [['BITBIT', 3], ['PIXELFEE', 3], ['DATADIL', 3], ['MOERBOT', 3], ['KLUISBEER', 2]].forEach(([species, n]) => {
        this.addAgent(species, { role: 'head' });
        for (let i = 0; i < n; i++) this.addAgent(species, { initial: true });
      });
      // Om mee te beginnen hangt er al wat werk op het prikbord.
      MAP.DEPTS.forEach(dept => {
        const p = this.addProject(pick(TEMPLATES[dept]), rand(1, 3), 'godfred', dept);
        this.planProject(p, true);
      });
      this.emit({ kind: 'info', text: `Welkom bij ${this.state.name}! Geef GODFRED een opdracht via het PRIKBORD-tabblad.` });
    }

    load() {
      try {
        const raw = localStorage.getItem(SAVE_KEY);
        if (!raw) return false;
        const data = JSON.parse(raw);
        if (!data || !Array.isArray(data.agents) || !Array.isArray(data.tasks)) return false;
        this.state = data;
        this.state.meeting = null;
        this.spots.clear();
        this.state.tasks.forEach(t => { if (t.status === 'onderweg') t.status = 'gecontroleerd'; });
        // Iedereen begint weer op zijn eigen plek.
        this.state.agents.forEach(a => {
          a.path = []; a.intent = null; a.carry = []; a.reviewTask = null; a.reviewDone = null;
          a.x = a.seat.x; a.y = a.seat.y;
          a.state = this.hasActiveTask(a) ? 'working' : 'idle';
          if (a.state === 'idle') a.taskId = null;
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

    now() { return this.state.clock; }

    clockLabel() {
      if (!this.state) return '';
      const c = this.state.clock;
      const day = Math.floor(c / 1440) + 1;
      const h = Math.floor((c % 1440) / 60);
      const m = c % 60;
      return `DAG ${day} ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    }

    agent(id) { return this.state.agents.find(a => a.id === id); }
    task(id) { return this.state.tasks.find(t => t.id === id); }
    project(id) { return this.state.projects.find(p => p.id === id); }
    director() { return this.state.agents.find(a => a.role === 'director'); }
    head(dept) { return this.state.agents.find(a => a.role === 'head' && a.dept === dept); }
    deptColor(dept) { const r = MAP.room(dept); return r.type ? TYPES[r.type].color : '#a8743f'; }

    freeDesk(dept) {
      return MAP.room(dept).seats.find(s => !this.state.agents.some(a => a.seat.x === s.x && a.seat.y === s.y));
    }

    addAgent(species, opts = {}) {
      const role = opts.role || 'agent';
      const type = FC.sprites.SPECIES[species].type;
      const dept = role === 'director' ? 'hq' : MAP.roomForType(type).id;
      const seat = role === 'director' ? MAP.BOSS_SEAT : role === 'head' ? MAP.room(dept).headSeat : this.freeDesk(dept);
      if (!seat) return null;
      const used = new Set(this.state.agents.map(a => a.name));
      const free = NICKNAMES.filter(n => !used.has(n));
      const name = opts.name || (free.length ? pick(free) : `${pick(NICKNAMES)}${this.state.nextId}`);
      const a = {
        id: this.state.nextId++,
        name, species, type, role, dept,
        seat: { x: seat.x, y: seat.y },
        level: role === 'director' ? 10 : role === 'head' ? rand(6, 8) : opts.initial ? rand(2, 5) : rand(1, 3),
        xp: 0,
        energy: 100,
        state: 'idle',
        intent: null,
        taskId: null,
        carry: [],          // taken die iemand fysiek bij zich draagt
        reviewTask: null,   // waar een hoofd/Godfred nu naar kijkt
        reviewDone: null,   // bekeken, wacht op een oordeel
        x: seat.x, y: seat.y,
        path: [],
        facing: 1,
        timer: 0,
        stats: { tasks: 0, approved: 0, revisions: 0, checked: 0, delivered: 0, reviewed: 0, blocked: 0 },
      };
      this.state.agents.push(a);
      return a;
    }

    addProject(title, difficulty, source, dept) {
      const p = {
        id: this.state.nextId++,
        title, difficulty, source,
        dept: dept || null,
        status: 'nieuw',  // nieuw | loopt | klaar
        taskIds: [],
        created: this.now(),
        doneAt: null,
        quality: 0,
      };
      this.state.projects.push(p);
      return p;
    }

    addTask(project, dept, title) {
      const d = project.difficulty;
      const t = {
        id: this.state.nextId++,
        projectId: project.id,
        boss: project.source === 'baas',
        dept, title,
        difficulty: d,
        required: d * 100,
        progress: 0,
        status: 'concept',
        assignee: null,
        quality: 0,
        revision: 0,      // keren teruggestuurd door Godfred
        headRevision: 0,  // keren teruggestuurd door het hoofd
        feedback: '',
        reward: { xp: d * 12, credits: d * 15 },
        checkedAt: 0,
        doneAt: null,
      };
      this.state.tasks.push(t);
      project.taskIds.push(t.id);
      return t;
    }

    // Godfred knipt een project op in taken per afdeling.
    planProject(p, direct) {
      let depts;
      if (p.dept) depts = [p.dept];
      else {
        const lower = p.title.toLowerCase();
        depts = MAP.DEPTS.filter(d => KEYWORDS[d].some(k => lower.includes(k)));
        if (!depts.length) {
          const pool = ['lab', 'studio', 'bieb', 'werk'].sort(() => Math.random() - 0.5);
          depts = pool.slice(0, p.difficulty >= 4 ? 3 : p.difficulty >= 2 ? 2 : 1);
        }
      }
      const plain = depts.length === 1;
      depts.forEach(d => {
        const t = this.addTask(p, d, plain ? p.title : `${PHASE[d]}: ${p.title}`);
        if (direct) t.status = 'bord';
      });
      p.status = 'loopt';
      return depts;
    }

    recruit() {
      if (this.state.credits < RECRUIT_COST) {
        this.emit({ kind: 'warn', text: `Niet genoeg credits. Werven kost ${RECRUIT_COST} ⛁.` });
        return null;
      }
      const options = Object.keys(FC.sprites.SPECIES)
        .filter(sp => sp !== 'PLANUIL' && this.freeDesk(MAP.roomForType(FC.sprites.SPECIES[sp].type).id));
      if (!options.length) {
        this.emit({ kind: 'warn', text: 'Alle bureaus zijn bezet. Er past niemand meer bij.' });
        return null;
      }
      this.state.credits -= RECRUIT_COST;
      const species = pick(options);
      const a = this.addAgent(species);
      a.x = MAP.GUARD_SPOT.x; a.y = MAP.GUARD_SPOT.y; // komt binnen via de poort
      this.toDesk(a);
      this.emit({ kind: 'recruit', agentId: a.id, text: `${a.name} de ${species} komt door de poort binnen en versterkt ${roomName(a.dept)}!` });
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

    goToSpot(a, list, intent) {
      this.releaseSpot(a);
      const spot = this.claimSpot(a, list);
      if (!spot) return false;
      this.moveTo(a, spot, intent);
      return true;
    }

    toDesk(a) { this.releaseSpot(a); this.moveTo(a, a.seat, 'desk'); }

    toRest(a) {
      // Lounge vol? Dan maar even pauze aan het eigen bureau.
      if (!this.goToSpot(a, MAP.REST_SPOTS, 'rest')) this.moveTo(a, a.seat, 'rest');
    }

    hasActiveTask(a) {
      const t = this.task(a.taskId);
      return !!(t && t.status === 'bezig' && t.assignee === a.id);
    }

    arrive(a) {
      const intent = a.intent;
      a.intent = null;
      switch (intent) {
        case 'desk':
          a.carry = [];
          a.state = this.hasActiveTask(a) ? 'working' : 'idle';
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
        case 'guard':
          a.state = 'guarding';
          this.say(a, 'Ik sta op wacht!');
          break;
        case 'post':
          this.pinTasks(a);
          this.toDesk(a);
          break;
        case 'pickup':
          this.takeFromBoard(a);
          this.toDesk(a);
          break;
        case 'deliver':
          this.handOver(a);
          this.toDesk(a);
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

    // ---------- wat er bij het prikbord en bij Godfred gebeurt ----------

    pinTasks(g) {
      const pinned = this.state.tasks.filter(t => t.status === 'concept');
      pinned.forEach(t => { t.status = 'bord'; });
      if (!pinned.length) return;
      const depts = [...new Set(pinned.map(t => roomName(t.dept)))].join(', ');
      this.emit({ kind: 'post', agentId: g.id, text: `${g.name} hangt ${plural(pinned.length)} op het prikbord (${depts}).` });
      this.say(g, 'Nieuwe taken op het bord!');
    }

    takeFromBoard(h) {
      const cards = this.state.tasks
        .filter(t => t.dept === h.dept && t.status === 'bord')
        .sort((p, q) => q.revision - p.revision || (q.boss - p.boss) || p.id - q.id)
        .slice(0, Math.max(1, h.pickupCount || 1));
      cards.forEach(t => { t.status = 'opgehaald'; });
      h.carry = cards.map(t => t.id);
      if (!cards.length) return;
      this.emit({ kind: 'pickup', agentId: h.id, text: `${h.name} haalt ${plural(cards.length)} op voor ${roomName(h.dept)}.` });
      this.say(h, `${plural(cards.length)} voor ons!`);
    }

    handOver(h) {
      const g = this.director();
      const tasks = h.carry.map(id => this.task(id)).filter(t => t && t.status === 'onderweg');
      tasks.forEach(t => { t.status = 'ingeleverd'; });
      h.stats.delivered += tasks.length;
      if (!tasks.length) return;
      this.emit({ kind: 'deliver', agentId: h.id, text: `${h.name} brengt de output van ${roomName(h.dept)} naar ${g.name} (${plural(tasks.length)}).` });
      this.say(h, `Output van ${roomName(h.dept)}!`);
      this.say(g, 'Dank, ik kijk ernaar.');
    }

    // ---------- commando's ----------

    roleOf(actor) { return actor ? actor.role : 'baas'; }

    execute(cmd, actorId) {
      const actor = actorId ? this.agent(actorId) : null;
      const role = this.roleOf(actor);
      if (!(PERMISSIONS[role] || []).includes(cmd.type)) return false;
      const g = this.director();
      switch (cmd.type) {
        case 'order': {
          const title = String(cmd.title || '').trim().slice(0, 50);
          if (!title) return false;
          const p = this.addProject(title, clamp(cmd.difficulty || 2, 1, 5), 'baas', cmd.dept || null);
          this.emit({ kind: 'opdracht', agentId: g.id, text: `DE BAAS → ${g.name}: "${p.title}"` });
          return p;
        }
        case 'plan': {
          const p = this.project(cmd.projectId);
          if (!p || p.status !== 'nieuw') return false;
          const depts = this.planProject(p);
          this.emit({ kind: 'project', agentId: actor.id, text: `${actor.name} verdeelt "${p.title}" over ${depts.map(roomName).join(', ')}.` });
          this.say(actor, `Plan klaar: ${p.title}`);
          return true;
        }
        case 'initiative': {
          const p = this.addProject(pick(TEMPLATES[cmd.dept]), rand(1, 4), 'godfred', cmd.dept);
          this.planProject(p);
          this.emit({ kind: 'plan', agentId: actor.id, text: `${actor.name} bedenkt werk voor ${roomName(cmd.dept)}: "${p.title}".` });
          return true;
        }
        case 'post':
          if (actor.state !== 'idle') return false;
          return this.goToSpot(actor, MAP.BOARD_SPOTS, 'post');
        case 'pickup':
          if (actor.state !== 'idle') return false;
          actor.pickupCount = cmd.count || 1;
          return this.goToSpot(actor, MAP.BOARD_SPOTS, 'pickup');
        case 'assign': {
          const t = this.task(cmd.taskId);
          const a = this.agent(cmd.agentId);
          if (!t || !a || t.status !== 'opgehaald' || t.dept !== actor.dept || a.dept !== actor.dept || a.role !== 'agent' || a.taskId) return false;
          t.status = 'bezig';
          t.assignee = a.id;
          a.taskId = t.id;
          if (a.state === 'idle') a.state = 'working';
          this.emit({ kind: 'order', from: actor.id, to: [a.id], agentId: a.id, text: `${actor.name} → ${a.name}: "${t.title}"` });
          this.say(actor, `${a.name}: ${t.title}`);
          return true;
        }
        case 'review': {
          const t = this.task(cmd.taskId);
          const wanted = role === 'director' ? 'ingeleverd' : 'controle';
          if (!t || t.status !== wanted || actor.state !== 'idle') return false;
          if (role === 'head' && t.dept !== actor.dept) return false;
          actor.state = 'reviewing';
          actor.reviewTask = t.id;
          actor.timer = role === 'director' ? GODFRED_REVIEW_MINUTES : HEAD_REVIEW_MINUTES;
          return true;
        }
        case 'check': {
          const t = this.task(cmd.taskId);
          actor.reviewDone = null;
          if (!t || t.status !== 'controle' || t.dept !== actor.dept) return false;
          actor.stats.checked++;
          const worker = this.agent(t.assignee);
          if (cmd.verdict === 'beter') {
            // Terug op de stapel van het hoofd, met extra werk.
            t.status = 'opgehaald';
            t.assignee = null;
            t.headRevision++;
            t.required += Math.round(t.required * 0.3);
            t.feedback = cmd.note;
            this.emit({ kind: 'check', from: actor.id, to: worker ? [worker.id] : [], agentId: actor.id, color: '#ff8a7a',
              text: `${actor.name} stuurt "${t.title}" terug: ${cmd.note}` });
            this.say(actor, cmd.note);
          } else {
            t.status = 'gecontroleerd';
            t.checkedAt = this.now();
            this.emit({ kind: 'check', agentId: actor.id, text: `${actor.name} keurt "${t.title}" goed voor Godfred.` });
          }
          return true;
        }
        case 'deliver': {
          if (actor.state !== 'idle') return false;
          const tasks = this.state.tasks.filter(t => t.dept === actor.dept && t.status === 'gecontroleerd');
          if (!tasks.length || !this.goToSpot(actor, MAP.VISITOR_SPOTS, 'deliver')) return false;
          tasks.forEach(t => { t.status = 'onderweg'; });
          actor.carry = tasks.map(t => t.id);
          return true;
        }
        case 'feedback': {
          const t = this.task(cmd.taskId);
          actor.reviewDone = null;
          if (!t || t.status !== 'ingeleverd') return false;
          actor.stats.reviewed++;
          const head = this.head(t.dept);
          const worker = this.agent(t.assignee);
          if (cmd.verdict === 'revisie') {
            t.status = 'bord';
            t.revision++;
            t.progress = 0;
            t.required = Math.max(60, Math.round(t.required * 0.5));
            t.assignee = null;
            t.feedback = cmd.note;
            this.state.stats.revisions++;
            if (worker) worker.stats.revisions++;
            this.emit({ kind: 'feedback', from: actor.id, to: head ? [head.id] : [], agentId: actor.id, color: '#ff8a7a',
              text: `${actor.name}: "${t.title}" moet over. ${cmd.note} Hij hangt weer op het bord.` });
            this.say(actor, `Revisie: ${cmd.note}`);
          } else {
            this.approve(t, cmd.note, actor, head, worker);
          }
          return true;
        }
        case 'rest': {
          const a = this.agent(cmd.agentId);
          if (!a || a.role !== 'agent' || a.state === 'resting' || a.intent === 'rest') return false;
          if (role === 'head' && a.dept !== actor.dept) return false;
          // Een lopende taak blijft van deze agent; na de pauze gaat die verder.
          this.emit({ kind: 'rest', from: actor ? actor.id : null, to: [a.id], agentId: a.id,
            text: `${actor ? actor.name : 'DE BAAS'} stuurt ${a.name} naar de LOUNGE voor een pauze.` });
          this.toRest(a);
          return true;
        }
        case 'guard': {
          const a = this.agent(cmd.agentId);
          if (!a || a.dept !== actor.dept || a.role !== 'agent' || a.taskId) return false;
          this.releaseSpot(a);
          this.moveTo(a, MAP.GUARD_SPOT, 'guard');
          this.emit({ kind: 'order', from: actor.id, to: [a.id], agentId: a.id, text: `${actor.name} → ${a.name}: bewaak de POORT!` });
          return true;
        }
        case 'meeting':
          return this.callMeeting(cmd.topic, cmd.scope || 'alle');
        case 'say':
          this.say(actor, cmd.text);
          return true;
        default:
          return false;
      }
    }

    say(a, text) {
      if (a) this.emit({ kind: 'say', agentId: a.id, text });
    }

    approve(t, note, g, head, worker) {
      const s = this.state;
      t.status = 'goedgekeurd';
      t.feedback = note;
      t.doneAt = this.now();
      s.credits += t.reward.credits;
      s.stats.tasksApproved++;
      if (worker) { worker.stats.approved++; this.gainXp(worker, t.reward.xp); }
      if (head) this.gainXp(head, Math.round(t.reward.xp / 3));
      this.emit({ kind: 'approve', from: g.id, to: head ? [head.id] : [], agentId: g.id, color: '#9dff9d',
        text: `${g.name} keurt "${t.title}" goed ${'★'.repeat(stars(t.quality))}: ${note} +${t.reward.credits} ⛁` });

      const p = this.project(t.projectId);
      if (!p || p.status === 'klaar') return;
      const tasks = p.taskIds.map(id => this.task(id)).filter(Boolean);
      if (!tasks.every(x => x.status === 'goedgekeurd')) return;
      p.status = 'klaar';
      p.doneAt = this.now();
      p.quality = tasks.reduce((sum, x) => sum + x.quality, 0) / tasks.length;
      s.stats.projectsDone++;
      if (p.source === 'baas') {
        const bonus = p.difficulty * 20;
        s.credits += bonus;
        this.emit({ kind: 'project', agentId: g.id,
          text: `${g.name} → DE BAAS: "${p.title}" is af! ${plural(tasks.length)}, kwaliteit ${'★'.repeat(stars(p.quality))}. +${bonus} ⛁ bonus` });
        this.say(g, `Baas, "${p.title}" is af!`);
      }
    }

    // ---------- vergaderingen ----------

    callMeeting(topic, scope) {
      const s = this.state;
      if (s.meeting) return false;
      const g = this.director();
      const busyWalking = a => ['post', 'pickup', 'deliver', 'guard'].includes(a.intent);
      const attendees = s.agents.filter(a =>
        (scope === 'mt' ? a.role !== 'agent' : true) &&
        a.state !== 'guarding' && a.state !== 'reviewing' && !busyWalking(a));
      s.meeting = { topic, scope, phase: 'verzamelen', attendees: [], timer: 0 };
      attendees.forEach(a => {
        const ok = a.role === 'director'
          ? this.goToSpot(a, [MAP.PRESENTER_SPOT], 'meeting')
          : this.goToSpot(a, MAP.MEETING_SEATS, 'meeting');
        if (ok) s.meeting.attendees.push(a.id);
      });
      s.stats.meetings++;
      this.emit({ kind: 'meeting', agentId: g.id, text: `${g.name} roept ${scope === 'mt' ? 'de afdelingshoofden' : 'iedereen'} bij elkaar: ${topic}.` });
      this.say(g, scope === 'mt' ? 'Hoofden, naar de vergaderzaal!' : 'Allemaal naar de vergaderzaal!');
      return true;
    }

    tickMeeting() {
      const m = this.state.meeting;
      if (!m) return;
      m.timer++;
      const present = m.attendees.map(id => this.agent(id)).filter(a => a && a.state === 'meeting');
      if (m.phase === 'verzamelen') {
        const everyone = m.attendees.every(id => { const a = this.agent(id); return !a || a.state === 'meeting'; });
        if (everyone || m.timer > MEETING_MAX_WAIT) {
          m.phase = 'bezig';
          m.timer = 0;
          this.say(this.director(), m.topic);
        }
        return;
      }
      if (m.timer % 5 === 0 && present.length) {
        const speaker = pick(present);
        this.say(speaker, this.meetingLine(speaker));
      }
      if (m.timer >= MEETING_LENGTH) this.endMeeting();
    }

    meetingLine(a) {
      const s = this.state;
      if (a.role === 'director') {
        const running = s.projects.filter(p => p.status === 'loopt').length;
        const inbox = s.tasks.filter(t => t.status === 'ingeleverd').length;
        return pick([`${running} projecten lopen.`, `Firewall: ${Math.round(s.firewall)}%.`,
          inbox ? `${inbox} stukken liggen bij mij.` : 'Mijn inbox is leeg!', 'Kwaliteit boven snelheid.', 'Hoe staan de afdelingen ervoor?']);
      }
      if (a.role === 'head') {
        const mine = s.tasks.filter(t => t.dept === a.dept);
        const busy = mine.filter(t => t.status === 'bezig').length;
        const stack = mine.filter(t => t.status === 'opgehaald').length;
        return `${roomName(a.dept)}: ${busy} bezig, ${stack} op de stapel`;
      }
      const t = this.task(a.taskId);
      if (t) return `Bezig met ${t.title} (${Math.floor(t.progress / t.required * 100)}%)`;
      return pick(['Ik heb ruimte voor werk!', 'Klaar voor de volgende taak.', 'Ik heb een idee...']);
    }

    endMeeting() {
      const m = this.state.meeting;
      if (!m) return;
      this.state.meeting = null;
      m.attendees.forEach(id => {
        const a = this.agent(id);
        if (a && (a.state === 'meeting' || a.intent === 'meeting')) this.toDesk(a);
      });
      this.emit({ kind: 'meeting', agentId: this.director().id, text: 'Vergadering afgelopen. Iedereen terug naar zijn plek!' });
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
    }

    tickMinute() {
      const s = this.state;
      s.clock += 1;
      for (const a of s.agents) this.tickAgent(a);
      this.tickMeeting();
      this.tickSecurity();
      for (const a of s.agents) {
        if (a.role === 'director') this.godfredBrain.tick(a);
        else if (a.role === 'head') this.headBrain.tick(a);
      }
      // Oude afgeronde taken en projecten opruimen.
      const done = s.tasks.filter(t => t.status === 'goedgekeurd');
      if (done.length > 60) {
        const drop = new Set(done.slice(0, done.length - 60).map(t => t.id));
        s.tasks = s.tasks.filter(t => !drop.has(t.id));
      }
      const finished = s.projects.filter(p => p.status === 'klaar');
      if (finished.length > 30) {
        const drop = new Set(finished.slice(0, finished.length - 30).map(p => p.id));
        s.projects = s.projects.filter(p => !drop.has(p.id));
      }
      if (s.clock % 30 === 0) this.save();
    }

    tickAgent(a) {
      switch (a.state) {
        case 'working': {
          const t = this.task(a.taskId);
          if (!t || t.status !== 'bezig' || t.assignee !== a.id) { a.taskId = null; a.state = 'idle'; break; }
          t.progress += (1 + a.level * 0.25) * 1.5;
          a.energy = clamp(a.energy - 0.12, 0, 100);
          if (t.progress >= t.required) this.finishTask(a, t);
          break;
        }
        case 'idle':
          if (a.role !== 'agent') break;
          if (a.energy < 15) { this.toRest(a); break; }
          if (!this.state.meeting && Math.random() < 0.003) this.goToSpot(a, MAP.COFFEE_SPOTS, 'coffee');
          break;
        case 'reviewing':
          if (--a.timer <= 0) {
            a.state = 'idle';
            a.reviewDone = a.reviewTask;
            a.reviewTask = null;
          }
          break;
        case 'resting':
          a.energy = clamp(a.energy + (a.spot ? 1.5 : 0.8), 0, 100);
          if (a.energy >= 100) this.toDesk(a);
          break;
        case 'coffee':
          a.energy = clamp(a.energy + 0.3, 0, 100);
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

    // Agent is klaar: de output gaat naar het afdelingshoofd.
    finishTask(a, t) {
      t.status = 'controle';
      t.progress = t.required;
      t.quality = clamp(0.3 + a.level * 0.06 + Math.random() * 0.35 + t.revision * 0.2 + t.headRevision * 0.15, 0.05, 1);
      a.taskId = null;
      a.state = 'idle';
      a.stats.tasks++;
      const head = this.head(a.dept);
      this.emit({ kind: 'output', from: a.id, to: head ? [head.id] : [], agentId: a.id, color: '#ffe27a',
        text: `${a.name} levert "${t.title}" in bij ${head ? head.name : 'het hoofd'}.` });
      this.say(a, 'Klaar, naar het hoofd!');
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
  }

  FC.Org = Org;
  FC.TYPES = TYPES;
  FC.xpNeeded = xpNeeded;
  FC.stars = stars;
  FC.RECRUIT_COST = RECRUIT_COST;
})(window.FC);
