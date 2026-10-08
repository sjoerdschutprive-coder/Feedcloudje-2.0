// Alle HTML-panelen rond de kaart: topbalk, team, prikbord, output,
// logboek en het dialoogvenster.
window.FC = window.FC || {};

(function (FC) {
  const $ = id => document.getElementById(id);
  const MAP = FC.map;

  const STATUS = {
    idle: 'WACHT OP TAAK', walking: 'ONDERWEG', working: 'AAN HET WERK', resting: 'PAUZE',
    guarding: 'OP WACHT', meeting: 'IN VERGADERING', coffee: 'KOFFIE', reviewing: 'CONTROLEERT',
  };
  const LEAD_IDLE = { director: 'AAN ZIJN BUREAU', head: 'STUURT TEAM AAN' };
  const INTENT = {
    desk: 'NAAR BUREAU', rest: 'NAAR LOUNGE', guard: 'NAAR POORT', meeting: 'NAAR VERGADERING',
    coffee: 'HAALT KOFFIE', post: 'NAAR PRIKBORD', pickup: 'HAALT TAKEN OP', deliver: 'NAAR GODFRED',
  };
  const ROLE_LABEL = { director: 'DIRECTEUR', head: 'HOOFD', agent: 'AGENT' };
  const DEPT_ORDER = ['hq', 'lab', 'studio', 'bieb', 'werk', 'poort'];
  // De pijplijn op het PRIKBORD-tabblad.
  const PIPELINE = [
    ['concept', 'BIJ GODFRED IN VOORBEREIDING'],
    ['bord', 'OP HET PRIKBORD'],
    ['opgehaald', 'OP DE STAPEL VAN HET HOOFD'],
    ['bezig', 'IN UITVOERING'],
    ['controle', 'CONTROLE DOOR HOOFD'],
    ['gecontroleerd', 'KLAAR VOOR GODFRED'],
    ['onderweg', 'ONDERWEG NAAR GODFRED'],
    ['ingeleverd', 'LIGT BIJ GODFRED'],
  ];
  // Gebeurtenissen die groot in het dialoogvenster verschijnen. De rest zie
  // je als vliegende berichtjes op de kaart en in het logboek.
  const DIALOG_KINDS = new Set(['opdracht', 'project', 'feedback', 'meeting', 'alarm', 'recruit', 'warn', 'info', 'levelup']);
  const LETTER_COLORS = { order: '#ffffff', output: '#ffe27a', rest: '#c8f0ff' };
  const POPUPS = {
    levelup: ['LEVEL UP!', '#ffd23f'], approve: ['GOEDGEKEURD!', '#7dff8a'], feedback: ['REVISIE!', '#ff8a7a'],
    security: ['GEBLOKT!', '#ffffff'], recruit: ['NIEUW!', '#ffb36b'],
  };

  const hpClass = pct => (pct < 25 ? 'low' : pct < 50 ? 'mid' : '');
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function setBar(el, pct, cls) {
    el.style.width = `${Math.max(0, Math.min(100, pct))}%`;
    el.className = `fill ${cls || hpClass(pct)}`;
  }

  class UI {
    constructor(org, world) {
      this.org = org;
      this.world = world;
      this.selectedId = null;
      this.tab = 'team';
      this.dialogQueue = [];
      this.dialogBusy = false;
      this.dialogTimer = null;
      this.rows = new Map();
      this.sections = new Map();

      world.onSelect = id => this.select(id);
      org.on(e => this.onEvent(e));
      this.bindControls();
      this.fillDeptSelect();
      this.renderLog();
      const latest = org.state.log[0];
      if (latest) { this.dialogQueue.push(latest.text); this.nextDialog(); }
    }

    tag(a) {
      if (a.role === 'director') return '<span class="type-tag role-director">DIRECTEUR</span>';
      const color = this.org.deptColor(a.dept);
      return `<span class="type-tag" style="background:${color}">${ROLE_LABEL[a.role]}</span>`;
    }

    bindControls() {
      const org = this.org;
      $('btn-pause').addEventListener('click', () => this.togglePause());
      $('btn-speed').addEventListener('click', () => {
        const speeds = [1, 2, 4, 8];
        org.speed = speeds[(speeds.indexOf(org.speed) + 1) % speeds.length];
        $('btn-speed').textContent = `${org.speed}x`;
      });
      $('btn-meeting').addEventListener('click', () => {
        if (!org.execute({ type: 'meeting', scope: 'alle', topic: 'Algemene vergadering op verzoek van de baas' })) {
          org.emit({ kind: 'warn', text: 'Er loopt al een vergadering.' });
        }
      });
      $('btn-recruit').addEventListener('click', () => {
        const a = org.recruit();
        if (a) this.select(a.id);
      });
      $('btn-reset').addEventListener('click', () => {
        if (!confirm('Weet je zeker dat je opnieuw wilt beginnen? Alle voortgang gaat verloren.')) return;
        this.rows.clear();
        this.sections.clear();
        $('team-list').innerHTML = '';
        this.select(null);
        org.reset();
        this.renderLog();
      });
      document.querySelectorAll('.tab').forEach(btn => {
        btn.addEventListener('click', () => this.showTab(btn.dataset.tab));
      });
      $('dialog').addEventListener('click', () => this.nextDialog());
      $('order-form').addEventListener('submit', e => {
        e.preventDefault();
        const title = $('o-title').value.trim();
        if (!title) return;
        org.execute({ type: 'order', title, dept: $('o-dept').value || null, difficulty: Number($('o-size').value) });
        $('o-title').value = '';
        this.render();
      });
      document.addEventListener('keydown', e => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
        if (e.code === 'Space') { e.preventDefault(); this.togglePause(); }
        if (e.key === 'Escape') this.select(null);
      });
    }

    togglePause() {
      this.org.paused = !this.org.paused;
      $('btn-pause').textContent = this.org.paused ? '▶' : '❚❚';
    }

    fillDeptSelect() {
      $('o-dept').innerHTML = '<option value="">GODFRED BESLIST</option>' + MAP.DEPTS
        .map(id => `<option value="${id}">${MAP.room(id).name}</option>`).join('');
    }

    showTab(tab) {
      this.tab = tab;
      document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
      ['team', 'board', 'output', 'log'].forEach(t => $(`tab-${t}`).classList.toggle('hidden', t !== tab));
      this.render();
    }

    select(id) {
      this.selectedId = id;
      this.world.selectedId = id;
      if (id !== null && this.tab !== 'team') this.showTab('team');
      this.render();
    }

    // ---------- gebeurtenissen ----------

    onEvent(e) {
      if (e.kind === 'say') { this.world.say(e.agentId, e.text); return; }
      if (e.from && e.to) {
        const color = e.color || LETTER_COLORS[e.kind] || '#ffffff';
        e.to.forEach(id => this.world.letter(e.from, id, color));
      }
      if (DIALOG_KINDS.has(e.kind)) {
        this.dialogQueue.push(e.text);
        if (this.dialogQueue.length > 6) this.dialogQueue.splice(0, this.dialogQueue.length - 6);
        if (!this.dialogBusy) this.nextDialog();
      }
      const p = POPUPS[e.kind];
      if (p && e.agentId) this.world.popup(e.agentId, p[0], p[1]);
      this.renderLogEntry(e);
    }

    nextDialog() {
      clearInterval(this.typer);
      clearTimeout(this.dialogTimer);
      const text = this.dialogQueue.shift();
      if (!text) { this.dialogBusy = false; return; }
      this.dialogBusy = true;
      const el = $('dialog-text');
      let i = 0;
      el.textContent = '';
      this.typer = setInterval(() => {
        i += 2;
        el.textContent = text.slice(0, i);
        if (i >= text.length) clearInterval(this.typer);
      }, 30);
      this.dialogTimer = setTimeout(() => this.nextDialog(), 1600 + text.length * 35);
    }

    renderLogEntry(e) {
      const li = document.createElement('li');
      li.className = e.kind;
      li.innerHTML = `<span class="time">${esc(e.time)}</span>${esc(e.text)}`;
      const list = $('log-list');
      list.prepend(li);
      while (list.children.length > 120) list.lastChild.remove();
    }

    renderLog() {
      const list = $('log-list');
      list.innerHTML = '';
      [...this.org.state.log].reverse().forEach(e => this.renderLogEntry(e));
    }

    // ---------- periodiek tekenen ----------

    render() {
      const s = this.org.state;
      $('clock').textContent = this.org.clockLabel();
      $('credits').textContent = `${s.credits} ⛁`;
      $('firewall').textContent = `${Math.round(s.firewall)}%`;
      setBar($('firewall-bar'), s.firewall);
      $('projects-done').textContent = s.stats.projectsDone;
      $('tasks-approved').textContent = s.stats.tasksApproved;
      $('revisions').textContent = s.stats.revisions;
      $('blocked').textContent = s.stats.intrudersBlocked;
      $('btn-recruit').disabled = s.credits < FC.RECRUIT_COST;
      $('btn-recruit').title = `Nieuwe agent werven (${FC.RECRUIT_COST} ⛁)`;
      $('board-count').textContent = s.tasks.filter(t => t.status === 'bord').length;

      if (this.tab === 'team') { this.renderTeam(); this.renderDetail(); }
      if (this.tab === 'board') this.renderBoard();
      if (this.tab === 'output') this.renderOutput();
    }

    statusLabel(a) {
      if (a.state === 'walking') return INTENT[a.intent] || STATUS.walking;
      if (a.state === 'idle' && LEAD_IDLE[a.role]) return LEAD_IDLE[a.role];
      return STATUS[a.state] || a.state;
    }

    section(dept) {
      let sec = this.sections.get(dept);
      if (sec) return sec;
      const list = $('team-list');
      sec = document.createElement('li');
      sec.className = 'dept';
      sec.dataset.dept = dept;
      sec.innerHTML = `<div class="dept-title"><span>${MAP.room(dept).name}</span><span class="dept-count"></span></div><ul></ul>`;
      sec.querySelector('.dept-title').style.borderLeft = `6px solid ${this.org.deptColor(dept)}`;
      const order = DEPT_ORDER.indexOf(dept);
      const after = [...list.children].find(el => DEPT_ORDER.indexOf(el.dataset.dept) > order);
      list.insertBefore(sec, after || null);
      this.sections.set(dept, sec);
      return sec;
    }

    renderTeam() {
      const counts = {};
      // Hoofden eerst, dan de agents.
      const rank = { director: 0, head: 1, agent: 2 };
      const agents = [...this.org.state.agents].sort((p, q) => rank[p.role] - rank[q.role] || p.id - q.id);
      for (const a of agents) {
        if (a.role === 'agent') counts[a.dept] = (counts[a.dept] || 0) + 1;
        let row = this.rows.get(a.id);
        if (!row) {
          row = document.createElement('li');
          row.className = `team-row role-${a.role}`;
          row.innerHTML = `
            <div class="pic"></div>
            <div>
              <div class="line"><span class="name"></span><span class="lvl"></span></div>
              <span class="bar"><span class="fill"></span></span>
              <div class="meta"><span class="kind"></span><span class="status"></span></div>
            </div>`;
          row.querySelector('.pic').appendChild(FC.sprites.spriteCanvas(a.species, 3));
          row.querySelector('.kind').innerHTML = this.tag(a);
          row.addEventListener('click', () => this.select(this.selectedId === a.id ? null : a.id));
          this.section(a.dept).querySelector('ul').appendChild(row);
          this.rows.set(a.id, row);
        }
        row.classList.toggle('selected', a.id === this.selectedId);
        row.querySelector('.name').textContent = a.name;
        row.querySelector('.lvl').textContent = `Lv${a.level}`;
        setBar(row.querySelector('.fill'), a.energy);
        const st = row.querySelector('.status');
        st.textContent = this.statusLabel(a);
        st.className = `status ${a.state}`;
      }
      this.sections.forEach((sec, dept) => {
        const n = counts[dept] || 0;
        sec.querySelector('.dept-count').textContent = dept === 'hq' ? '' : `HOOFD + ${n} agent${n === 1 ? '' : 's'}`;
      });
    }

    renderDetail() {
      const el = $('detail');
      const a = this.selectedId !== null ? this.org.agent(this.selectedId) : null;
      if (!a) { el.classList.add('hidden'); el.dataset.id = ''; return; }
      el.classList.remove('hidden');
      if (el.dataset.id !== String(a.id)) {
        el.dataset.id = a.id;
        el.innerHTML = `
          <div class="screen">
            <div class="pic"></div>
            <div>
              <h3></h3>
              <div class="sub"></div>
              <div class="kv">
                <span>ENERGIE</span><span class="bar"><span class="fill" data-k="hp"></span></span>
                <span>XP</span><span class="bar"><span class="fill xp" data-k="xp"></span></span>
                <span>AFDELING</span><span class="d-dept"></span>
                <span>STATUS</span><span class="d-status"></span>
                <span>TAAK</span><span class="d-task"></span>
                <span>RECORD</span><span class="d-record"></span>
              </div>
            </div>
          </div>
          <p class="dex"></p>
          <div class="actions">
            ${a.role === 'agent' ? '<button class="btn d-rest">STUUR NAAR PAUZE</button>' : ''}
            <button class="btn btn-ghost d-close">SLUIT</button>
          </div>`;
        el.querySelector('.pic').appendChild(FC.sprites.spriteCanvas(a.species, 6));
        const role = {
          director: 'Directeur. Krijgt opdrachten van de baas, knipt ze op in taken, hangt ze op het prikbord en beoordeelt de output van de afdelingen.',
          head: 'Afdelingshoofd. Haalt taken van het prikbord, verdeelt ze over het team, controleert het werk en brengt de output naar Godfred.',
          agent: 'Agent. Voert taken uit aan het eigen bureau en levert de output in bij het afdelingshoofd.',
        }[a.role];
        el.querySelector('.dex').textContent = `${role} ${FC.sprites.SPECIES[a.species].dex}`;
        const rest = el.querySelector('.d-rest');
        if (rest) rest.addEventListener('click', () => this.org.execute({ type: 'rest', agentId: a.id }));
        el.querySelector('.d-close').addEventListener('click', () => this.select(null));
      }
      el.querySelector('h3').textContent = `${a.name}  Lv${a.level}`;
      el.querySelector('.sub').innerHTML = `#${String(a.id).padStart(3, '0')} ${a.species} ${this.tag(a)}`;
      el.querySelector('.d-dept').textContent = MAP.room(a.dept).name;
      setBar(el.querySelector('[data-k=hp]'), a.energy);
      setBar(el.querySelector('[data-k=xp]'), a.xp / FC.xpNeeded(a.level) * 100, 'xp');
      el.querySelector('.d-status').textContent = this.statusLabel(a);
      const t = this.org.task(a.taskId || a.reviewTask);
      el.querySelector('.d-task').textContent = t ? `${t.title}${a.taskId ? ` (${Math.floor(t.progress / t.required * 100)}%)` : ''}` : '—';
      const st = a.stats;
      el.querySelector('.d-record').textContent = a.role === 'director'
        ? `${st.reviewed} beoordeeld`
        : a.role === 'head'
          ? `${st.checked} gecontroleerd · ${st.delivered} ingeleverd`
          : `${st.tasks} af · ${st.approved} goedgekeurd · ${st.revisions} revisies`;
      const rest = el.querySelector('.d-rest');
      if (rest) rest.disabled = a.state === 'resting' || a.intent === 'rest';
    }

    taskLine(t) {
      const who = this.org.agent(t.assignee);
      const pct = Math.floor(t.progress / t.required * 100);
      const flags = [
        t.boss ? '<span class="flag boss">BAAS</span>' : '',
        t.revision ? `<span class="flag rev">REVISIE ${t.revision}</span>` : '',
        t.headRevision ? '<span class="flag fix">BIJGESCHAAFD</span>' : '',
      ].join('');
      return `
        <li class="task">
          <div class="line"><span><i class="dot" style="background:${this.org.deptColor(t.dept)}"></i>${esc(t.title)}</span><span>${'★'.repeat(t.difficulty)}</span></div>
          <div class="meta"><span>${MAP.room(t.dept).name} ${flags}</span><span>${who ? esc(who.name) : ''}</span></div>
          ${t.status === 'bezig' ? `<span class="bar"><span class="fill progress" style="width:${pct}%"></span></span>` : ''}
          ${t.feedback && t.status !== 'goedgekeurd' ? `<div class="note">"${esc(t.feedback)}"</div>` : ''}
        </li>`;
    }

    renderBoard() {
      const tasks = this.org.state.tasks;
      let html = '';
      for (const [status, label] of PIPELINE) {
        const list = tasks.filter(t => t.status === status).sort((p, q) => (q.boss - p.boss) || p.id - q.id);
        if (!list.length) continue;
        html += `<li class="section-title">${label} <b>${list.length}</b></li>`;
        html += list.map(t => this.taskLine(t)).join('');
      }
      $('pipeline').innerHTML = html || '<li class="empty">Geen open taken. Geef Godfred een opdracht!</li>';
    }

    projectLine(p) {
      const org = this.org;
      const tasks = p.taskIds.map(id => org.task(id)).filter(Boolean);
      const done = tasks.filter(t => t.status === 'goedgekeurd').length;
      const pct = tasks.length ? done / tasks.length * 100 : 0;
      return `
        <li class="project ${p.status}">
          <div class="line"><span>${esc(p.title)}</span><span>${p.status === 'klaar' ? `<span class="stars">${'★'.repeat(FC.stars(p.quality))}</span>` : `${done}/${tasks.length}`}</span></div>
          <div class="meta"><span>${{ nieuw: 'GODFRED PLANT HET IN', loopt: 'LOOPT', klaar: 'AF, GEMELD AAN DE BAAS' }[p.status]}</span></div>
          <span class="bar"><span class="fill ${p.status === 'klaar' ? '' : 'progress'}" style="width:${pct}%"></span></span>
          <div class="chips">${tasks.map(t => `<span class="chip ${t.status === 'goedgekeurd' ? 'ok' : ''}" style="border-color:${org.deptColor(t.dept)}">${MAP.room(t.dept).name}</span>`).join('')}</div>
        </li>`;
    }

    renderOutput() {
      const org = this.org;
      const order = p => ({ loopt: 0, nieuw: 1, klaar: 2 }[p.status]);
      const boss = org.state.projects.filter(p => p.source === 'baas').sort((p, q) => order(p) - order(q) || q.id - p.id);
      const own = org.state.projects.filter(p => p.source !== 'baas').sort((p, q) => order(p) - order(q) || q.id - p.id);
      let html = '<li class="section-title">OPDRACHTEN VAN DE BAAS</li>';
      html += boss.map(p => this.projectLine(p)).join('') || '<li class="empty">Nog geen opdrachten gegeven. Dat doe je op het PRIKBORD-tabblad.</li>';
      html += '<li class="section-title">EIGEN INITIATIEF VAN GODFRED</li>';
      html += own.slice(0, 6).map(p => this.projectLine(p)).join('');
      const approved = org.state.tasks.filter(t => t.status === 'goedgekeurd').sort((p, q) => q.doneAt - p.doneAt).slice(0, 20);
      html += '<li class="section-title">GOEDGEKEURD DOOR GODFRED</li>';
      html += approved.map(t => {
        const who = org.agent(t.assignee);
        return `
          <li class="task">
            <div class="line"><span><i class="dot" style="background:${org.deptColor(t.dept)}"></i>${esc(t.title)}</span><span class="stars">${'★'.repeat(FC.stars(t.quality))}</span></div>
            <div class="meta"><span>${MAP.room(t.dept).name}${who ? ` · ${esc(who.name)}` : ''}</span><span>${t.revision ? `${t.revision}x revisie` : 'in één keer'}</span></div>
            <div class="note">GODFRED: "${esc(t.feedback)}"</div>
          </li>`;
      }).join('') || '<li class="empty">Nog niets goedgekeurd.</li>';
      $('output-list').innerHTML = html;
    }
  }

  FC.UI = UI;
})(window.FC);
