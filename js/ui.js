// Alle HTML-panelen rond de kaart: topbalk, team, quests, logboek,
// dialoogvenster en het gevechtsscherm.
window.FC = window.FC || {};

(function (FC) {
  const $ = id => document.getElementById(id);
  const MAP = FC.map;

  const STATUS = {
    idle: 'WACHT OP OPDRACHT', walking: 'ONDERWEG', working: 'AAN HET WERK',
    resting: 'RUST UIT', guarding: 'OP WACHT', battling: 'IN GEVECHT',
    meeting: 'IN VERGADERING', coffee: 'KOFFIEPAUZE', visiting: 'BRENGT VERSLAG UIT',
  };
  const INTENT = {
    desk: 'NAAR BUREAU', rest: 'NAAR LOUNGE', guard: 'NAAR POORT', meeting: 'NAAR VERGADERING',
    coffee: 'HAALT KOFFIE', report: 'NAAR MANAGER',
  };
  // Volgorde van de afdelingen in de TEAM-lijst.
  const DEPT_ORDER = ['hq', 'lab', 'studio', 'bieb', 'werk', 'poort'];
  // Gebeurtenissen die groot in het dialoogvenster verschijnen. Opdrachten
  // en verslagen zie je als vliegende berichtjes op de kaart en in het logboek.
  const DIALOG_KINDS = new Set(['levelup', 'quest', 'bug', 'win', 'lose', 'alarm', 'security', 'recruit', 'warn', 'info', 'meeting']);
  const POPUPS = {
    levelup: ['LEVEL UP!', '#ffd23f'], quest: ['KLAAR!', '#7dff8a'], win: ['GEWONNEN!', '#c79bff'],
    lose: ['AU!', '#ff6b6b'], security: ['GEBLOKT!', '#ffffff'], recruit: ['NIEUW!', '#ffb36b'],
  };

  const hpClass = pct => (pct < 25 ? 'low' : pct < 50 ? 'mid' : '');
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function typeTag(type) {
    const color = FC.TYPES[type] ? FC.TYPES[type].color : '#888';
    return `<span class="type-tag" style="background:${color}">${type}</span>`;
  }

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
      this.lastBattle = null;
      this.lastHp = { ally: null, enemy: null };

      world.onSelect = id => this.select(id);
      org.on(e => this.onEvent(e));
      this.bindControls();
      this.fillDeptSelect();
      this.renderLog();
      const latest = org.state.log[0];
      if (latest) { this.dialogQueue.push(latest.text); this.nextDialog(); }
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
        if (!org.execute({ type: 'meeting', topic: 'Overleg op verzoek van de baas' }, 'baas')) {
          org.emit({ kind: 'warn', text: org.isNight() ? "Het is nacht. Vergaderen kan morgen weer." : 'Er loopt al een vergadering.' });
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
      $('quest-form').addEventListener('submit', e => {
        e.preventDefault();
        const title = $('q-title').value.trim();
        if (!title) return;
        org.execute({ type: 'createQuest', dept: $('q-dept').value, title, difficulty: Number($('q-diff').value) }, 'baas');
        $('q-title').value = '';
        this.renderQuests();
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
      $('q-dept').innerHTML = FC.QUEST_DEPTS
        .map(id => `<option value="${id}">${MAP.room(id).name}</option>`).join('');
    }

    showTab(tab) {
      this.tab = tab;
      document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
      ['team', 'quests', 'log'].forEach(t => $(`tab-${t}`).classList.toggle('hidden', t !== tab));
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
        const color = e.kind === 'report' ? '#ffe27a' : '#ffffff';
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
      while (list.children.length > 80) list.lastChild.remove();
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
      $('quests-done').textContent = s.stats.questsDone;
      $('bugs-beaten').textContent = s.stats.bugsBeaten;
      $('blocked').textContent = s.stats.intrudersBlocked;
      $('meetings').textContent = s.stats.meetings || 0;
      $('btn-recruit').disabled = s.credits < FC.RECRUIT_COST;
      $('btn-recruit').title = `Nieuwe medewerker werven (${FC.RECRUIT_COST} ⛁)`;

      if (this.tab === 'team') { this.renderTeam(); this.renderDetail(); }
      if (this.tab === 'quests') this.renderQuests();
      this.renderBattle();
    }

    statusLabel(a) {
      if (a.state === 'walking') return INTENT[a.intent] || STATUS.walking;
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
      // Op vaste volgorde invoegen.
      const order = DEPT_ORDER.indexOf(dept);
      const after = [...list.children].find(el => DEPT_ORDER.indexOf(el.dataset.dept) > order);
      list.insertBefore(sec, after || null);
      this.sections.set(dept, sec);
      return sec;
    }

    renderTeam() {
      const agents = this.org.state.agents;
      const counts = {};
      for (const a of agents) {
        counts[a.dept] = (counts[a.dept] || 0) + 1;
        let row = this.rows.get(a.id);
        if (!row) {
          row = document.createElement('li');
          row.className = 'team-row';
          row.innerHTML = `
            <div class="pic"></div>
            <div>
              <div class="line"><span class="name"></span><span class="lvl"></span></div>
              <span class="bar"><span class="fill"></span></span>
              <div class="meta"><span class="kind"></span><span class="status"></span></div>
            </div>`;
          row.querySelector('.pic').appendChild(FC.sprites.spriteCanvas(a.species, 3));
          row.addEventListener('click', () => this.select(this.selectedId === a.id ? null : a.id));
          this.section(a.dept).querySelector('ul').appendChild(row);
          this.rows.set(a.id, row);
        }
        row.classList.toggle('selected', a.id === this.selectedId);
        row.classList.toggle('lead', a.role === 'lead');
        row.querySelector('.name').textContent = a.name;
        row.querySelector('.lvl').textContent = `Lv${a.level}`;
        setBar(row.querySelector('.fill'), a.energy);
        row.querySelector('.kind').innerHTML = a.role === 'lead' ? '<span class="type-tag lead-tag">MANAGER</span>' : typeTag(a.type);
        const st = row.querySelector('.status');
        st.textContent = this.statusLabel(a);
        st.className = `status ${a.state}`;
      }
      this.sections.forEach((sec, dept) => {
        const n = counts[dept] || 0;
        sec.querySelector('.dept-count').textContent = dept === 'hq' ? '' : `${n} agent${n === 1 ? '' : 's'}`;
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
            <button class="btn d-rest">STUUR NAAR RUST</button>
            <button class="btn btn-ghost d-close">SLUIT</button>
          </div>`;
        el.querySelector('.pic').appendChild(FC.sprites.spriteCanvas(a.species, 6));
        el.querySelector('.dex').textContent = FC.sprites.SPECIES[a.species].dex;
        el.querySelector('.d-rest').addEventListener('click', () => this.org.execute({ type: 'rest', agentId: a.id }, 'baas'));
        el.querySelector('.d-close').addEventListener('click', () => this.select(null));
      }
      el.querySelector('h3').textContent = `${a.name}  Lv${a.level}`;
      el.querySelector('.sub').innerHTML = `#${String(a.id).padStart(3, '0')} ${a.species} ${a.role === 'lead' ? '<span class="type-tag lead-tag">MANAGER</span>' : typeTag(a.type)}`;
      el.querySelector('.d-dept').textContent = MAP.room(a.dept).name;
      setBar(el.querySelector('[data-k=hp]'), a.energy);
      setBar(el.querySelector('[data-k=xp]'), a.xp / FC.xpNeeded(a.level) * 100, 'xp');
      el.querySelector('.d-status').textContent = this.statusLabel(a);
      const q = this.org.quest(a.questId);
      el.querySelector('.d-task').textContent = a.role === 'lead'
        ? 'Werk verdelen, vergaderingen leiden, de poort bewaakt houden'
        : q ? `${q.title} (${Math.floor(q.progress / q.required * 100)}%)` : '—';
      el.querySelector('.d-record').textContent = `${a.stats.quests} quests · ${a.stats.bugs} bugs · ${a.stats.blocked} geblokt`;
      el.querySelector('.d-rest').disabled = a.state === 'resting' || a.intent === 'rest' || a.state === 'battling';
    }

    renderQuests() {
      const qs = this.org.state.quests;
      const order = { actief: 0, open: 1, klaar: 2 };
      const sorted = [...qs].sort((p, q) => order[p.status] - order[q.status] || (q.custom - p.custom) || q.id - p.id);
      let html = '';
      let lastStatus = null;
      for (const q of sorted) {
        if (q.status !== lastStatus) {
          html += `<li class="section-title">${{ actief: 'BEZIG', open: 'OPEN', klaar: 'AFGEROND' }[q.status]}</li>`;
          lastStatus = q.status;
        }
        const b = MAP.room(q.dept);
        const who = (q.assignees || []).map(id => this.org.agent(id)).filter(Boolean).map(a => a.name).join(' & ');
        const from = q.custom ? 'VAN DE BAAS' : `VAN ${this.org.lead().name}`;
        const pct = Math.floor(q.progress / q.required * 100);
        html += `
          <li class="quest ${q.status}${q.custom ? ' custom' : ''}">
            <div class="line"><span>${esc(q.title)}</span><span>${'★'.repeat(q.difficulty)}</span></div>
            <div class="meta"><span>${b.name} · ${from}</span><span>${who ? esc(who) : (q.status === 'klaar' ? '✓' : 'nog niet verdeeld')}</span></div>
            <span class="bar"><span class="fill progress" style="width:${pct}%"></span></span>
            <div class="meta"><span>${pct}%</span><span>+${q.reward.xp} XP · +${q.reward.credits} ⛁</span></div>
          </li>`;
      }
      $('quest-list').innerHTML = html;
    }

    renderBattle() {
      const b = this.org.state.battle;
      const box = $('battle');
      if (!b) {
        if (this.lastBattle) {
          box.classList.add('hidden');
          this.lastBattle = null;
        }
        return;
      }
      const a = this.org.agent(b.agentId);
      if (!a) return;
      if (this.lastBattle !== b) {
        this.lastBattle = b;
        box.classList.remove('hidden');
        $('b-enemy-sprite').innerHTML = '';
        $('b-enemy-sprite').appendChild(FC.sprites.spriteCanvas('BUG', 8));
        $('b-ally-sprite').innerHTML = '';
        $('b-ally-sprite').appendChild(FC.sprites.spriteCanvas(a.species, 8, true));
        this.lastHp = { ally: a.energy, enemy: b.bug.hp };
        ['b-enemy-sprite', 'b-ally-sprite'].forEach(id => $(id).className = 'mon-sprite');
      }
      $('b-enemy-name').textContent = b.bug.name;
      $('b-enemy-lvl').textContent = `Lv${b.bug.level}`;
      setBar($('b-enemy-hp'), b.bug.hp / b.bug.maxHp * 100);
      $('b-ally-name').textContent = a.name;
      $('b-ally-lvl').textContent = `Lv${a.level}`;
      setBar($('b-ally-hp'), a.energy);
      $('b-ally-num').textContent = `${Math.round(a.energy)}/100`;
      $('b-text').textContent = b.text;
      $('b-where').textContent = `· ${MAP.room(a.dept).name}`;

      const flash = (id, cls) => {
        const el = $(id);
        el.className = 'mon-sprite';
        void el.offsetWidth; // animatie opnieuw starten
        el.className = `mon-sprite ${cls}`;
      };
      if (b.bug.hp < this.lastHp.enemy) flash('b-enemy-sprite', b.bug.hp <= 0 ? 'faint' : 'hit');
      if (a.energy < this.lastHp.ally) flash('b-ally-sprite', b.over && b.bug.hp > 0 ? 'faint' : 'hit');
      this.lastHp = { ally: a.energy, enemy: b.bug.hp };
    }
  }

  FC.UI = UI;
})(window.FC);
