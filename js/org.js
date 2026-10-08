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
//   scan           ligt bij RISK FRED voor een security-scan (ontwikkelwerk)
//   gecontroleerd  goedgekeurd door het hoofd (en veilig), wacht op bezorging
//   onderweg       het hoofd loopt ermee naar Godfred
//   ingeleverd     ligt bij Godfred
//   goedgekeurd    klaar. (Of terug naar 'bord' als revisie.)
//
// XP: goedgekeurd werk levert XP op. XP telt voor het level en komt ook op
// het XP-saldo, waarmee agents in de lounge iets van het buffet pakken om
// hun energie aan te vullen.
window.FC = window.FC || {};

(function (FC) {
  const MAP = FC.map;
  const SAVE_KEY = 'feedcloudje.org.v5';
  const GAME_MINUTES_PER_SECOND = 8;
  const WALK_SPEED = 3.6;
  const EAT_MINUTES = 6;
  // Het self-service buffet in de lounge. Prijs in XP, energie erbij.
  const MENU = [
    { id: 'koffie',   name: 'KOFFIE',   cost: 5,  energy: 15, color: '#7a4a24' },
    { id: 'fruit',    name: 'FRUIT',    cost: 8,  energy: 25, color: '#5dbb3a' },
    { id: 'broodje',  name: 'BROODJE',  cost: 12, energy: 40, color: '#e0b060' },
    { id: 'smoothie', name: 'SMOOTHIE', cost: 18, energy: 60, color: '#f06bb5' },
    { id: 'taart',    name: 'TAART',    cost: 30, energy: 100, color: '#ffe6f0' },
  ];
  const MEETING_LENGTH = 25;
  const MEETING_MAX_WAIT = 40;
  const HEAD_REVIEW_MINUTES = 4;
  const GODFRED_REVIEW_MINUTES = 4;
  const RISK_SCAN_MINUTES = 3;

  const TYPES = {
    FINANCE: { color: '#3fae5a' }, MARKETING: { color: '#f06bb5' }, OPERATIONS: { color: '#f08a2c' },
    STRATEGIE: { color: '#4a90e2' }, DIRECTIE: { color: '#a8743f' }, RISK: { color: '#7b3fa0' }, LND: { color: '#2bb3a3' },
  };

  // De vier afdelingshoofden uit het profiel van Godfred.
  const HEAD_NAMES = { finance: 'FINANCE FRED', marketing: 'MARKETING FRED', operations: 'OPERATIONS FRED', strategie: 'STRATEGIC FRED' };

  // Hoe Godfred een opdracht per afdeling formuleert.
  const PHASE = { finance: 'Doorrekenen', marketing: 'Vermarkten', operations: 'Uitvoeren', strategie: 'Onderzoeken' };
  const KEYWORDS = {
    finance:    ['geld', 'budget', 'factuur', 'kosten', 'prijs', 'begroting', 'cijfers', 'omzet', 'betaal', 'financ', 'winst'],
    marketing:  ['logo', 'campagne', 'video', 'post', 'tekst', 'huisstijl', 'social', 'nieuwsbrief', 'merk', 'website', 'sales', 'klant'],
    operations: ['app', 'website', 'api', 'systeem', 'proces', 'planning', 'server', 'bouw', 'lancer', 'uitrol', 'support', 'tool', 'portaal', 'automat'],
    strategie:  ['onderzoek', 'analyse', 'markt', 'strategie', 'plan', 'concurrent', 'trend', 'kans', 'visie', 'groei'],
  };
  // Ontwikkel- en beveiligingswerk gaat altijd langs RISK FRED.
  const SECURITY_WORDS = ['app', 'website', 'site', 'api', 'code', 'systeem', 'server', 'portaal', 'login', 'betaal',
    'wachtwoord', 'privacy', 'toegang', 'beveilig', 'avg', 'tool', 'automat', 'koppel'];
  const TEMPLATES = {
    finance:    ['Kwartaalcijfers opstellen', 'Facturen verwerken', 'Begroting bijwerken', 'Cashflowprognose', 'Kostenanalyse'],
    marketing:  ['Campagne bedenken', 'Social posts maken', 'Websiteteksten', 'Nieuwsbrief schrijven', 'Salespitch aanscherpen'],
    operations: ['Proces automatiseren', 'Planning bijwerken', 'Serveronderhoud', 'Leveranciers afstemmen', 'Klantportaal bouwen'],
    strategie:  ['Marktonderzoek', 'Concurrentieanalyse', 'Kansen in kaart brengen', 'Kwartaalplan', 'Scenario doorrekenen'],
  };
  // Wat Elsje tijdens haar verbetersessies vindt en uitprobeert.
  const LND_TIPS = ['kortere, scherpere instructies', 'een checklist voor het inleveren', 'eerst de klantvraag herhalen',
    'voorbeelden van goedgekeurd werk', 'cijfers altijd onderbouwen'];

  const NICKNAMES = ['PIP', 'NOVA', 'BRAM', 'LOTTE', 'JUUL', 'DEX', 'FENNA', 'MILO', 'SAAR', 'TIJN',
    'ROOS', 'KAI', 'LIEKE', 'OTTO', 'EVI', 'SEM', 'NOOR', 'GUUS', 'ISA', 'TEUN', 'MAX', 'ZOE',
    'JIP', 'FEM', 'BOAZ', 'LUUK', 'MAAN', 'STAN', 'VERA', 'WOUT', 'YARA', 'ZEP', 'HUGO', 'NINA',
    'BAS', 'DEMI', 'FLOOR', 'GIJS', 'JET', 'KOEN', 'MEES', 'PUCK', 'RIK', 'TESS'];

  // Wie mag welk commando geven.
  const PERMISSIONS = {
    baas:     ['order', 'meeting', 'rest'],
    director: ['plan', 'initiative', 'post', 'review', 'feedback', 'meeting', 'say'],
    head:     ['pickup', 'assign', 'review', 'check', 'deliver', 'rest', 'say'],
    risk:     ['review', 'verdict', 'harden', 'patrol', 'advise', 'report', 'say'],
    lnd:      ['session', 'coach', 'propose', 'report', 'say'],
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
      this.riskBrain = new FC.RiskBrain(this);
      this.lndBrain = new FC.LndBrain(this);
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
        firewall: 100,
        nextId: 1,
        agents: [],
        tasks: [],
        projects: [],
        meeting: null,
        memory: { lastMt: 0, lastCrisis: -9999, lastInitiative: 0, lastPatrol: 0, lastAdvice: -9999, adviceAt: -9999,
          adviceResponse: null, lastRiskReport: 0, nextSession: 0 },
        reports: [],     // rapporten aan Sjoerd (van Elsje en Risk Fred)
        chat: [],        // gesprek tussen Sjoerd en Godfred
        minutes: [],     // notulen van het management-overleg
        improvements: [], // verbeterlog van Elsje
        deptBonus: {},   // kwaliteitswinst per afdeling door uitgerolde tools
        stats: { projectsDone: 0, tasksApproved: 0, revisions: 0, leaks: 0, intrudersBlocked: 0, breaches: 0, meetings: 0, snacks: 0, xpSpent: 0 },
        log: [],
      };
      this.state.memory.lastMt = this.state.clock - 6 * 60 + 20; // eerste MT-overleg na ~20 minuten
      this.addAgent('PLANUIL', { role: 'director', name: 'GODFRED' });
      this.addAgent('KLUISBEER', { role: 'risk', name: 'RISK FRED' });
      this.addAgent('BOEKKONIJN', { role: 'lnd', name: 'ELSJE' });
      [['DATADIL', 3], ['PIXELFEE', 3], ['MOERBOT', 3], ['BITBIT', 3]].forEach(([species, n]) => {
        const head = this.addAgent(species, { role: 'head' });
        head.name = HEAD_NAMES[head.dept];
        for (let i = 0; i < n; i++) this.addAgent(species, { initial: true });
      });
      this.state.memory.nextSession = this.state.clock + 4 * 60; // eerste verbetersessie van Elsje
      // Om mee te beginnen hangt er al wat werk op het prikbord.
      MAP.DEPTS.forEach(dept => {
        const p = this.addProject(pick(TEMPLATES[dept]), rand(1, 3), 'godfred', dept);
        this.planProject(p, true);
      });
      this.emit({ kind: 'info', text: `Welkom bij ${this.state.name}! Klik rechtsboven op "OPDRACHT AAN GODFRED" om met hem te praten en hem aan het werk te zetten.` });
    }

    load() {
      try {
        const raw = localStorage.getItem(SAVE_KEY);
        if (!raw) return false;
        const data = JSON.parse(raw);
        if (!data || !Array.isArray(data.agents) || !Array.isArray(data.tasks)) return false;
        this.state = data;
        this.state.meeting = null;
        if (!Array.isArray(this.state.chat)) this.state.chat = [];
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
    risk() { return this.state.agents.find(a => a.role === 'risk'); }
    elsje() { return this.state.agents.find(a => a.role === 'lnd'); }
    deptColor(dept) { const r = MAP.room(dept); return r.type ? TYPES[r.type].color : '#a8743f'; }

    freeDesk(dept) {
      return MAP.room(dept).seats.find(s => !this.state.agents.some(a => a.seat.x === s.x && a.seat.y === s.y));
    }

    addAgent(species, opts = {}) {
      const role = opts.role || 'agent';
      const type = FC.sprites.SPECIES[species].type;
      const dept = role === 'director' ? 'hq' : MAP.roomForType(type).id;
      const seat = role === 'director' ? MAP.BOSS_SEAT : role === 'risk' ? MAP.RISK_SEAT : role === 'lnd' ? MAP.ELSJE_SEAT
        : role === 'head' ? MAP.room(dept).headSeat : this.freeDesk(dept);
      if (!seat) return null;
      const used = new Set(this.state.agents.map(a => a.name));
      const free = NICKNAMES.filter(n => !used.has(n));
      const name = opts.name || (free.length ? pick(free) : `${pick(NICKNAMES)}${this.state.nextId}`);
      const a = {
        id: this.state.nextId++,
        name, species, type, role, dept,
        seat: { x: seat.x, y: seat.y },
        level: role === 'director' ? 10 : role === 'agent' ? (opts.initial ? rand(2, 5) : rand(1, 3)) : rand(6, 8),
        xp: 0,
        wallet: role === 'agent' ? rand(15, 40) : 0, // XP-saldo voor het buffet
        snack: null,
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
        stats: { tasks: 0, approved: 0, revisions: 0, checked: 0, delivered: 0, reviewed: 0, scanned: 0, leaks: 0, blocked: 0, snacks: 0 },
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

    addTask(project, dept, title, difficulty) {
      const d = difficulty || project.difficulty;
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
        secCheck: SECURITY_WORDS.some(w => `${project.title} ${title}`.toLowerCase().includes(w)),
        secRevision: 0,   // keren teruggestuurd door RISK FRED
        secured: false,
        feedback: '',
        reward: { xp: d * 12 },
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
          const pool = MAP.DEPTS.slice().sort(() => Math.random() - 0.5);
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
      // Gratis pauze (alleen water): langzaam bijtanken. Lounge vol? Dan aan
      // het eigen bureau.
      if (!this.goToSpot(a, MAP.REST_SPOTS, 'rest')) this.moveTo(a, a.seat, 'rest');
    }

    // Naar het buffet: kies de goedkoopste versnapering die de energie
    // helemaal aanvult, of anders de beste die het XP-saldo toelaat.
    toBuffet(a) {
      const need = 100 - a.energy;
      const affordable = MENU.filter(m => m.cost <= a.wallet);
      if (!affordable.length) { this.toRest(a); return 'water'; }
      const wanted = affordable.find(m => m.energy >= need) || affordable[affordable.length - 1];
      const order = [wanted, ...affordable.filter(m => m !== wanted).reverse()];
      for (const m of order) {
        const spot = MAP.BUFFET.find(b => b.item === m.id);
        if (this.goToSpot(a, [spot], 'buffet')) { a.snack = m.id; return m.id; }
      }
      return null; // buffet druk, straks nog een keer
    }

    buy(a) {
      const m = MENU.find(x => x.id === a.snack);
      if (!m || a.wallet < m.cost) { a.snack = null; this.toRest(a); return; }
      a.wallet -= m.cost;
      a.stats.snacks++;
      this.state.stats.snacks++;
      this.state.stats.xpSpent += m.cost;
      this.emit({ kind: 'snack', agentId: a.id, text: `${a.name} pakt een ${m.name} bij het buffet (-${m.cost} XP).` });
      this.say(a, `${m.name}! -${m.cost} XP`);
      if (!this.goToSpot(a, MAP.REST_SPOTS, 'eat')) this.moveTo(a, a.seat, 'eat');
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
        case 'buffet':
          this.buy(a);
          break;
        case 'eat': {
          const m = MENU.find(x => x.id === a.snack);
          a.state = 'eating';
          a.timer = EAT_MINUTES;
          a.eatGain = m ? m.energy / EAT_MINUTES : 0;
          break;
        }
        case 'coach':
          this.coach(a);
          this.toDesk(a);
          break;
        case 'patrol':
          a.state = 'patrol';
          a.timer = 15;
          this.say(a, 'Inspectieronde bij de poort.');
          break;
        case 'meeting':
          if (!this.state.meeting) { this.toDesk(a); break; }
          a.state = 'meeting';
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
      tasks.forEach(t => { t.status = 'ingeleverd'; t.deliveredAt = this.now(); });
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
          this.emit({ kind: 'opdracht', agentId: g.id, text: `SJOERD → ${g.name}: "${p.title}"` });
          // Een plan dat Godfred (de echte, via Claude) zelf al bedacht heeft.
          const tasks = (cmd.tasks || []).filter(t => MAP.DEPTS.includes(t.dept)).slice(0, 6);
          if (tasks.length) {
            tasks.forEach(t => {
              const task = this.addTask(p, t.dept, String(t.title).slice(0, 50), clamp(Number(t.difficulty) || p.difficulty, 1, 5));
              if (t.security) task.secCheck = true;
            });
            p.status = 'loopt';
            p.aiPlanned = true;
            this.emit({ kind: 'project', agentId: g.id,
              text: `${g.name} verdeelt "${p.title}" in ${plural(tasks.length)} over ${[...new Set(tasks.map(t => roomName(t.dept)))].join(', ')}.` });
          }
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
          const wanted = { director: 'ingeleverd', head: 'controle', risk: 'scan' }[role];
          if (!t || t.status !== wanted || actor.state !== 'idle') return false;
          if (role === 'head' && t.dept !== actor.dept) return false;
          actor.state = 'reviewing';
          actor.reviewTask = t.id;
          actor.timer = role === 'director' ? GODFRED_REVIEW_MINUTES : role === 'risk' ? RISK_SCAN_MINUTES : HEAD_REVIEW_MINUTES;
          return true;
        }
        case 'verdict': {
          const t = this.task(cmd.taskId);
          actor.reviewDone = null;
          if (!t || t.status !== 'scan') return false;
          actor.stats.scanned++;
          if (t.kind === 'tool') return this.toolVerdict(t, cmd.verdict === 'lek', cmd.note, actor);
          const head = this.head(t.dept);
          if (cmd.verdict === 'lek') {
            t.status = 'opgehaald';
            t.assignee = null;
            t.secRevision++;
            t.required += Math.round(t.required * 0.3);
            t.feedback = cmd.note;
            actor.stats.leaks++;
            this.state.stats.leaks++;
            this.emit({ kind: 'scan', from: actor.id, to: head ? [head.id] : [], agentId: actor.id, color: '#ff8a7a',
              text: `${actor.name} vindt een beveiligingslek in "${t.title}": ${cmd.note} Terug naar ${head ? head.name : 'het hoofd'}.` });
            this.say(actor, `Lek gevonden! ${cmd.note}`);
          } else {
            t.status = 'gecontroleerd';
            t.secured = true;
            t.checkedAt = this.now();
            this.emit({ kind: 'scan', from: actor.id, to: head ? [head.id] : [], agentId: actor.id, color: '#b9a3ff',
              text: `${actor.name} keurt "${t.title}" veilig. 🔒` });
          }
          return true;
        }
        case 'harden':
          if (actor.state !== 'idle') return false;
          actor.state = 'hardening';
          actor.timer = 10;
          return true;
        case 'patrol':
          if (actor.state !== 'idle') return false;
          this.state.memory.lastPatrol = this.now();
          return this.goToSpot(actor, [MAP.GUARD_SPOT], 'patrol');
        case 'advise': {
          this.state.memory.lastAdvice = this.now();
          this.state.memory.adviceAt = this.now();
          this.emit({ kind: 'advies', from: actor.id, to: [g.id], agentId: actor.id, color: '#b9a3ff',
            text: `${actor.name} → ${g.name}: ${cmd.note}` });
          this.say(actor, 'Advies aan Godfred!');
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
          } else if (t.secCheck && !t.secured) {
            // Ontwikkelwerk eerst langs RISK FRED.
            t.status = 'scan';
            const r = this.risk();
            this.emit({ kind: 'check', from: actor.id, to: r ? [r.id] : [], agentId: actor.id, color: '#b9a3ff',
              text: `${actor.name} keurt "${t.title}" goed en laat hem scannen door RISK FRED.` });
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
          if (a.energy >= 95) return false;
          if (role === 'head' && a.dept !== actor.dept) return false;
          if (['buffet', 'eat'].includes(a.intent) || a.state === 'eating') return false;
          // Een lopende taak blijft van deze agent; na de pauze gaat die verder.
          const went = this.toBuffet(a);
          if (!went) return false;
          this.emit({ kind: 'rest', from: actor ? actor.id : null, to: [a.id], agentId: a.id,
            text: `${actor ? actor.name : 'SJOERD'} stuurt ${a.name} naar de lounge${went === 'water' ? ' (geen XP, dus water)' : ' voor iets van het buffet'}.` });
          return true;
        }
        case 'report':
          this.addReport(actor, cmd.title, cmd.text);
          return true;
        case 'session': {
          // Elsje start een verbetersessie: ze loopt naar de afdeling van de
          // agent waar verbetering het meeste oplevert.
          if (actor.state !== 'idle') return false;
          const a = this.agent(cmd.agentId);
          if (!a) return false;
          this.state.memory.nextSession = this.now() + 3 * 1440;
          actor.coachTarget = a.id;
          this.emit({ kind: 'lnd', agentId: actor.id, text: `${actor.name} start haar verbetersessie en gaat langs bij ${a.name} (${roomName(a.dept)}).` });
          this.say(actor, 'Verbetersessie!');
          this.moveTo(actor, MAP.room(a.dept).doors[0], 'coach');
          return true;
        }
        case 'propose': {
          // Een nieuwe tool of skill: eerst langs Risk Fred.
          const r = this.risk();
          const t = {
            id: this.state.nextId++, kind: 'tool', projectId: null, boss: false, dept: 'academy',
            targetDept: cmd.dept, title: `Tool: ${cmd.tool} voor ${roomName(cmd.dept)}`, difficulty: 1,
            required: 1, progress: 1, status: 'scan', assignee: null, quality: Math.random(), revision: 0,
            headRevision: 0, secCheck: true, secRevision: 0, secured: false, feedback: '', reward: { xp: 0 },
            checkedAt: 0, doneAt: null,
          };
          this.state.tasks.push(t);
          this.emit({ kind: 'lnd', from: actor.id, to: r ? [r.id] : [], agentId: actor.id, color: '#7fe0d4',
            text: `${actor.name} wil "${cmd.tool}" invoeren bij ${roomName(cmd.dept)} en laat het eerst scannen door RISK FRED.` });
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

    // Elsje coacht een agent: een gerichte tip, de agent wordt er beter van.
    coach(e) {
      const a = this.agent(e.coachTarget);
      e.coachTarget = null;
      if (!a) return;
      const tip = pick(LND_TIPS);
      a.level++;
      this.state.improvements.unshift({ time: this.clockLabel(), agent: a.name, dept: roomName(a.dept),
        what: `Coaching: ${tip}`, why: `${a.stats.revisions} revisies op ${a.stats.tasks} taken`, result: `${a.name} naar level ${a.level}` });
      this.state.improvements.length = Math.min(this.state.improvements.length, 20);
      this.emit({ kind: 'lnd', from: e.id, to: [a.id], agentId: e.id, color: '#7fe0d4',
        text: `${e.name} coacht ${a.name}: ${tip}. ${a.name} gaat naar level ${a.level}.` });
      this.say(e, `Tip: ${tip}`);
    }

    toolVerdict(t, leak, note, r) {
      const e = this.elsje();
      t.status = 'goedgekeurd';
      t.doneAt = this.now();
      t.secured = !leak;
      if (leak) {
        t.feedback = `Afgewezen door Risk Fred: ${note}`;
        this.state.stats.leaks++;
        r.stats.leaks++;
        this.emit({ kind: 'scan', from: r.id, to: e ? [e.id] : [], agentId: r.id, color: '#ff8a7a',
          text: `${r.name} wijst "${t.title}" af: ${note}` });
        this.say(r, 'Deze tool komt er niet in.');
      } else {
        const bonus = this.state.deptBonus;
        bonus[t.targetDept] = Math.min(0.3, (bonus[t.targetDept] || 0) + 0.05);
        t.feedback = 'Veilig bevonden en uitgerold.';
        this.state.improvements.unshift({ time: this.clockLabel(), agent: MAP.room(t.targetDept).name, dept: roomName(t.targetDept),
          what: t.title, why: 'Nieuwe ontwikkeling in AI', result: `Kwaliteit +${Math.round(bonus[t.targetDept] * 100)}% voor de afdeling` });
        this.emit({ kind: 'lnd', from: r.id, to: e ? [e.id] : [], agentId: e ? e.id : r.id, color: '#b9a3ff',
          text: `${r.name} keurt "${t.title}" veilig. ${e ? e.name : 'Elsje'} rolt hem uit.` });
      }
      return true;
    }

    addReport(from, title, text) {
      this.state.reports.unshift({ time: this.clockLabel(), from: from.name, title, text });
      this.state.reports.length = Math.min(this.state.reports.length, 20);
      this.emit({ kind: 'rapport', agentId: from.id, text: `${from.name} → SJOERD: ${title}` });
    }

    approve(t, note, g, head, worker) {
      const s = this.state;
      t.status = 'goedgekeurd';
      t.feedback = note;
      t.doneAt = this.now();
      s.stats.tasksApproved++;
      if (worker) {
        worker.stats.approved++;
        worker.wallet += t.reward.xp;
        this.gainXp(worker, t.reward.xp);
      }
      if (head) this.gainXp(head, Math.round(t.reward.xp / 3));
      if (worker && stars(t.quality) === 5) this.say(g, `Topper, ${worker.name}.`);
      this.emit({ kind: 'approve', from: g.id, to: head ? [head.id] : [], agentId: g.id, color: '#9dff9d',
        text: `${g.name} keurt "${t.title}" goed ${'★'.repeat(stars(t.quality))}: ${note}${worker ? ` +${t.reward.xp} XP voor ${worker.name}` : ''}` });

      const p = this.project(t.projectId);
      if (!p || p.status === 'klaar') return;
      const tasks = p.taskIds.map(id => this.task(id)).filter(Boolean);
      if (!tasks.every(x => x.status === 'goedgekeurd')) return;
      p.status = 'klaar';
      p.doneAt = this.now();
      p.quality = tasks.reduce((sum, x) => sum + x.quality, 0) / tasks.length;
      s.stats.projectsDone++;
      if (p.source === 'baas') {
        this.emit({ kind: 'project', agentId: g.id,
          text: `${g.name} → SJOERD: "${p.title}" is af! ${plural(tasks.length)}, kwaliteit ${'★'.repeat(stars(p.quality))}.` });
        this.say(g, `Baas, "${p.title}" is af!`);
      }
    }

    // ---------- vergaderingen ----------

    callMeeting(topic, scope) {
      const s = this.state;
      if (s.meeting) return false;
      const g = this.director();
      const busy = a => ['post', 'pickup', 'deliver', 'patrol', 'buffet', 'eat', 'coach'].includes(a.intent) ||
        ['reviewing', 'hardening', 'patrol', 'eating'].includes(a.state);
      const attendees = s.agents.filter(a => (scope === 'mt' ? a.role !== 'agent' : true) && !busy(a));
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
        return pick([`${running} projecten lopen. Tempo houden.`, 'Kort: waar zit het knelpunt?',
          inbox ? `${inbox} stukken liggen bij mij. Komt goed.` : 'Inbox leeg. Prima.', 'Wat hebben jullie nodig?',
          'Sales loopt achter? Dan sturen we daarop.', 'Signalen van Risk Fred gaan voor.']);
      }
      if (a.role === 'lnd') {
        const last = s.improvements[0];
        return pick([last ? `Laatste verbetering: ${last.what}.` : 'Ik zoek uit wat ons sneller maakt.',
          'Geen hype, alleen wat werkt.', 'Performance ligt bij mij, Godfred.', 'Volgende sessie: nieuwe tools testen.']);
      }
      if (a.role === 'risk') {
        return pick([`Firewall: ${Math.round(s.firewall)}%.`, `${s.stats.intrudersBlocked} aanvallen geblokt.`,
          `${s.stats.leaks} lekken onderschept.`, 'Advies: security vanaf het begin meenemen.', 'Geen onbekende bijlagen openen!']);
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
      if (m.scope === 'mt') this.writeMinutes(m);
    }

    // Godfred legt notulen en actiepunten centraal vast.
    writeMinutes(m) {
      const s = this.state;
      const actions = MAP.DEPTS.map(d => {
        const mine = s.tasks.filter(t => t.dept === d && t.status !== 'goedgekeurd');
        const stuck = mine.filter(t => ['bord', 'opgehaald'].includes(t.status)).length;
        const head = this.head(d);
        return `${head ? head.name : roomName(d)}: ${stuck ? `${plural(stuck)} oppakken` : 'op schema'}`;
      });
      if (s.firewall < 80) actions.push(`RISK FRED: firewall terug naar 100% (nu ${Math.round(s.firewall)}%)`);
      const pending = s.projects.filter(p => p.source === 'baas' && p.status !== 'klaar');
      if (pending.length) actions.push(`GODFRED: ${pending.length} opdracht${pending.length === 1 ? '' : 'en'} van Sjoerd bewaken`);
      s.minutes.unshift({ time: this.clockLabel(), topic: m.topic, actions });
      s.minutes.length = Math.min(s.minutes.length, 10);
      this.emit({ kind: 'notulen', agentId: this.director().id, text: `GODFRED legt notulen vast: ${actions.length} actiepunten.` });
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
        else if (a.role === 'risk') this.riskBrain.tick(a);
        else if (a.role === 'lnd') this.lndBrain.tick(a);
      }
      // Oude afgeronde taken en projecten van Godfred zelf opruimen.
      // Opdrachten van Sjoerd blijven altijd bewaard.
      const own = id => { const p = this.project(id); return !p || p.source !== 'baas'; };
      const done = s.tasks.filter(t => t.status === 'goedgekeurd' && own(t.projectId));
      if (done.length > 60) {
        const drop = new Set(done.slice(0, done.length - 60).map(t => t.id));
        s.tasks = s.tasks.filter(t => !drop.has(t.id));
      }
      const finished = s.projects.filter(p => p.status === 'klaar' && p.source !== 'baas');
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
          a.energy = clamp(a.energy - 0.2, 0, 100);
          if (t.progress >= t.required) this.finishTask(a, t);
          break;
        }
        case 'idle':
          if (a.role !== 'agent' || this.state.meeting) break;
          // Zelf iets halen als de energie laag is, of af en toe een koffie.
          if (a.energy < 35) this.toBuffet(a);
          else if (a.energy < 85 && a.wallet >= 20 && Math.random() < 0.004) this.toBuffet(a);
          break;
        case 'reviewing':
          if (--a.timer <= 0) {
            a.state = 'idle';
            a.reviewDone = a.reviewTask;
            a.reviewTask = null;
          }
          break;
        case 'resting':
          a.energy = clamp(a.energy + (a.spot ? 1 : 0.6), 0, 100);
          if (a.energy >= 70) this.toDesk(a);
          break;
        case 'eating':
          a.energy = clamp(a.energy + a.eatGain, 0, 100);
          if (--a.timer <= 0) { a.snack = null; this.toDesk(a); }
          break;
        case 'hardening':
          this.state.firewall = clamp(this.state.firewall + 1, 0, 100);
          if (--a.timer <= 0 || this.state.firewall >= 100) a.state = 'idle';
          break;
        case 'patrol':
          if (--a.timer <= 0) this.toDesk(a);
          break;
        default:
          break;
      }
    }

    // Agent is klaar: de output gaat naar het afdelingshoofd.
    finishTask(a, t) {
      t.status = 'controle';
      t.progress = t.required;
      const bonus = this.state.deptBonus[a.dept] || 0;
      t.quality = clamp(0.3 + a.level * 0.06 + Math.random() * 0.35 + bonus +
        t.revision * 0.2 + t.headRevision * 0.15 + t.secRevision * 0.15, 0.05, 1);
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

    // RISK FRED houdt de poort en de firewall in de gaten. Zit hij in een
    // vergadering, dan is de poort kwetsbaarder.
    tickSecurity() {
      const s = this.state;
      if (Math.random() > 0.005) return;
      const r = this.risk();
      const threat = pick(['een onbekende bot', 'malware in een bijlage', 'een virus via een download', 'een port-scanner',
        'een phishingmail', 'een verdwaalde hacker']);
      // Alleen in een vergadering is hij echt weg van zijn post.
      const onDuty = r && r.state !== 'meeting' && r.intent !== 'meeting';
      const chance = !onDuty ? 0.25 : r.state === 'patrol' ? 1 : 0.6 + s.firewall / 250;
      if (Math.random() < chance) {
        s.stats.intrudersBlocked++;
        if (r) {
          r.stats.blocked++;
          this.emit({ kind: 'security', agentId: r.id, text: `${r.name} hield ${threat} tegen bij de POORT.` });
          this.say(r, 'Hier kom je niet langs!');
          this.gainXp(r, 6);
        }
      } else {
        const dmg = rand(6, 14);
        s.firewall = clamp(s.firewall - dmg, 0, 100);
        s.stats.breaches++;
        this.emit({ kind: 'alarm', text: `ALARM! ${threat} glipte langs de poort. Firewall -${dmg}%.${onDuty ? '' : ' RISK FRED was niet op zijn post.'}` });
      }
    }
  }

  FC.Org = Org;
  FC.TYPES = TYPES;
  FC.xpNeeded = xpNeeded;
  FC.stars = stars;
  FC.MENU = MENU;
})(window.FC);
