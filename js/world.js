// Tekent het opengewerkte kantoor in retro-handheldstijl op een canvas.
window.FC = window.FC || {};

(function (FC) {
  const MAP = FC.map;
  const T = 16; // tegelgrootte in "pixels"
  const S = 3;  // schaal naar echte canvas-pixels

  const C = {
    grass: '#8bd45b', grassDark: '#6cb848',
    path: '#ecd9a5', pathEdge: '#d4bd82',
    water: '#4aa3df', waterLight: '#9fd8ff',
    trunk: '#7a4a24', leaf: '#2f8a3c', leafDark: '#1f6a2c', leafLight: '#4fb05a',
    wallTop: '#4b4f6b', wallHi: '#6a7092', wallFace: '#efe6d2', wallBase: '#b9ad94',
    outline: '#1a1c2c',
  };

  const FLOORS = {
    wood:       { a: '#dcae74', b: '#c9965c' },
    carpetRed:  { a: '#b5484a', b: '#a23d40' },
    carpetBlue: { a: '#6683c7', b: '#5873b5' },
    tiles:      { a: '#f3dbe5', b: '#e6c6d4' },
    concrete:   { a: '#bcc3cf', b: '#a9b1bf' },
    corridor:   { a: '#e8e2d2', b: '#d9d0bb' },
  };

  // Toestanden waarin een agent zit (geen loop-animatie).
  const SEATED = new Set(['working', 'idle', 'meeting', 'battling', 'resting', 'coffee', 'visiting']);

  function px(ctx, x, y, w, h, color) {
    ctx.fillStyle = color;
    ctx.fillRect(x, y, w, h);
  }

  function text(ctx, str, x, y, color, size) {
    ctx.font = `bold ${size || 7}px "Courier New", monospace`;
    ctx.textBaseline = 'top';
    ctx.fillStyle = color;
    ctx.fillText(str, x, y);
  }

  // ---------- statische tegels ----------

  function drawGrass(ctx, x, y, flowers) {
    px(ctx, x, y, T, T, C.grass);
    const s = (x * 7 + y * 13) % 5;
    px(ctx, x + 3 + s, y + 4, 1, 2, C.grassDark);
    px(ctx, x + 4 + s, y + 3, 1, 2, C.grassDark);
    px(ctx, x + 11 - s, y + 11, 1, 2, C.grassDark);
    if (flowers) {
      const col = ['#ffffff', '#ffd23f', '#ff7aa8'][(x + y) % 3];
      [[4, 9], [10, 4], [12, 12]].forEach(([fx, fy]) => px(ctx, x + fx, y + fy, 2, 2, col));
    }
  }

  function drawPath(ctx, x, y) {
    px(ctx, x, y, T, T, C.path);
    px(ctx, x + 3, y + 5, 2, 1, C.pathEdge);
    px(ctx, x + 10, y + 11, 2, 1, C.pathEdge);
  }

  function drawTree(ctx, x, y) {
    drawGrass(ctx, x, y);
    px(ctx, x + 6, y + 11, 4, 4, C.trunk);
    px(ctx, x + 2, y + 2, 12, 9, C.leafDark);
    px(ctx, x + 1, y + 4, 14, 6, C.leafDark);
    px(ctx, x + 3, y + 1, 10, 8, C.leaf);
    px(ctx, x + 2, y + 3, 12, 5, C.leaf);
    px(ctx, x + 4, y + 2, 3, 2, C.leafLight);
  }

  function drawGate(ctx, x, y) {
    drawPath(ctx, x, y);
    px(ctx, x, y + 2, 2, 14, '#6d4a2a');
    px(ctx, x + 14, y + 2, 2, 14, '#6d4a2a');
    for (let i = 3; i < 14; i += 3) px(ctx, x + i, y + 4, 1, 11, '#9aa3b5');
    px(ctx, x + 2, y + 4, 12, 1, '#5b6478');
    px(ctx, x + 2, y + 9, 12, 1, '#5b6478');
    px(ctx, x + 6, y + 6, 4, 3, '#ffd23f');
  }

  function drawFloor(ctx, x, y, kind, tx, ty) {
    const f = FLOORS[kind] || FLOORS.corridor;
    px(ctx, x, y, T, T, f.a);
    if (kind === 'wood') {
      const off = (ty % 2) * 6;
      px(ctx, x, y + 7, T, 1, f.b);
      px(ctx, x + ((4 + off) % T), y, 1, 7, f.b);
      px(ctx, x + ((12 + off) % T), y + 8, 1, 8, f.b);
    } else if (kind === 'tiles' || kind === 'corridor') {
      px(ctx, x, y, 8, 8, f.b);
      px(ctx, x + 8, y + 8, 8, 8, f.b);
    } else {
      const s = (tx * 5 + ty * 3) % 4;
      px(ctx, x + 3 + s, y + 4, 1, 1, f.b);
      px(ctx, x + 11 - s, y + 10, 1, 1, f.b);
      px(ctx, x + 7, y + 13 - s, 1, 1, f.b);
    }
  }

  const isWall = (x, y) => y >= 0 && y < MAP.H && x >= 0 && x < MAP.W && MAP.tiles[y][x] === '#';

  function drawWall(ctx, x, y, tx, ty) {
    const faceBelow = !isWall(tx, ty + 1);
    if (!faceBelow) { px(ctx, x, y, T, T, C.wallTop); return; }
    px(ctx, x, y, T, 7, C.wallTop);
    px(ctx, x, y, T, 1, C.wallHi);
    px(ctx, x, y + 7, T, 9, C.wallFace);
    px(ctx, x, y + 14, T, 2, C.wallBase);
  }

  function floorKindAt(tx, ty) {
    const id = MAP.roomAt[ty] && MAP.roomAt[ty][tx];
    if (!id) return 'corridor';
    if (id === 'gang') return 'corridor';
    return MAP.room(id).floor;
  }

  function drawDoor(ctx, x, y, tx, ty) {
    // Deuropening: vloer van de gang/ruimte met een deurmat.
    const outside = MAP.tiles[ty][tx + 1] === '=' || MAP.tiles[ty][tx - 1] === '=';
    if (outside) drawPath(ctx, x, y);
    else drawFloor(ctx, x, y, floorKindAt(tx, ty), tx, ty);
    const vertical = isWall(tx, ty - 1) || isWall(tx, ty + 1);
    if (vertical) {
      px(ctx, x + 3, y + 2, 10, 12, '#a0703f');
      px(ctx, x + 4, y + 3, 8, 10, '#c48a52');
    } else {
      px(ctx, x, y, 2, T, C.wallTop);
      px(ctx, x + 14, y, 2, T, C.wallTop);
      px(ctx, x + 3, y + 4, 10, 8, '#a0703f');
      px(ctx, x + 4, y + 5, 8, 6, '#c48a52');
    }
  }

  // Statisch meubilair (alles wat nooit voor een agent langs hoeft).
  function drawStaticFurniture(ctx, f, x, y) {
    switch (f.kind) {
      case 'chair':
        px(ctx, x + 3, y + 3, 10, 3, '#6b3f22');
        px(ctx, x + 4, y + 6, 8, 6, '#8b5a32');
        px(ctx, x + 4, y + 12, 1, 3, C.outline);
        px(ctx, x + 11, y + 12, 1, 3, C.outline);
        break;
      case 'beanbag': {
        const col = ['#ff9eb5', '#9ed8ff', '#ffe08a'][f.color || 0];
        px(ctx, x + 2, y + 6, 12, 8, C.outline);
        px(ctx, x + 3, y + 5, 10, 8, col);
        px(ctx, x + 4, y + 6, 4, 2, '#ffffff');
        break;
      }
      case 'coffee':
        px(ctx, x + 2, y + 1, 12, 14, C.outline);
        px(ctx, x + 3, y + 2, 10, 12, '#9aa3b5');
        px(ctx, x + 4, y + 3, 8, 4, '#2a3b5c');
        px(ctx, x + 10, y + 4, 1, 1, '#ff3b3b');
        px(ctx, x + 6, y + 10, 4, 3, '#ffffff');
        px(ctx, x + 7, y + 11, 2, 1, '#7a4a24');
        break;
      case 'plant':
        px(ctx, x + 5, y + 10, 6, 5, '#b5643a');
        px(ctx, x + 5, y + 10, 6, 1, '#8a4a2a');
        px(ctx, x + 3, y + 3, 10, 7, C.leafDark);
        px(ctx, x + 4, y + 2, 8, 6, C.leaf);
        px(ctx, x + 5, y + 3, 3, 2, C.leafLight);
        break;
      case 'shelf':
        px(ctx, x + 1, y + 1, 14, 14, '#6b3f22');
        [[3, '#e85d5d'], [5, '#5d9be8'], [7, '#f2c14e'], [10, '#5dbb7a'], [12, '#b07de0']]
          .forEach(([bx, c]) => { px(ctx, x + bx, y + 2, 2, 5, c); px(ctx, x + bx, y + 9, 2, 5, c); });
        px(ctx, x + 1, y + 7, 14, 1, '#4a2a14');
        break;
      case 'board':
        px(ctx, x + 4, y, 6, T, C.outline);
        px(ctx, x + 5, y, 4, T, '#ffffff');
        if (f.part === 0) px(ctx, x + 6, y + 6, 2, 6, '#e85d5d');
        if (f.part === 1) { px(ctx, x + 6, y + 3, 2, 1, '#5d9be8'); px(ctx, x + 6, y + 7, 2, 1, '#5d9be8'); px(ctx, x + 6, y + 11, 2, 1, '#5d9be8'); }
        if (f.part === 2) px(ctx, x + 6, y + 2, 2, 8, '#5dbb7a');
        break;
      default:
        break;
    }
  }

  function renderBackground() {
    const c = document.createElement('canvas');
    c.width = MAP.W * T;
    c.height = MAP.H * T;
    const ctx = c.getContext('2d');
    for (let ty = 0; ty < MAP.H; ty++) {
      for (let tx = 0; tx < MAP.W; tx++) {
        const t = MAP.tiles[ty][tx];
        const x = tx * T, y = ty * T;
        if (t === '=') drawPath(ctx, x, y);
        else if (t === '~') px(ctx, x, y, T, T, C.water);
        else if (t === 'T') drawTree(ctx, x, y);
        else if (t === 'G') drawGate(ctx, x, y);
        else if (t === '#') drawWall(ctx, x, y, tx, ty);
        else if (t === 'f') drawFloor(ctx, x, y, floorKindAt(tx, ty), tx, ty);
        else if (t === 'd') drawDoor(ctx, x, y, tx, ty);
        else drawGrass(ctx, x, y, t === ',');
        const f = MAP.furn[ty][tx];
        if (f) drawStaticFurniture(ctx, f, x, y);
      }
    }
    // Naambordjes op de bovenmuur van elke ruimte
    MAP.ROOMS.forEach(r => {
      const label = r.name;
      ctx.font = 'bold 7px "Courier New", monospace';
      const tw = Math.ceil(ctx.measureText(label).width) + 6;
      const cx = (r.x0 + r.x1 + 1) / 2 * T;
      const lx = Math.round(cx - tw / 2), ly = r.y0 * T + 5;
      px(ctx, lx - 1, ly - 1, tw + 2, 11, C.outline);
      px(ctx, lx, ly, tw, 9, '#fffbe8');
      text(ctx, label, lx + 3, ly + 1, C.outline);
    });
    return c;
  }

  // ---------- de wereld ----------

  class World {
    constructor(canvas, org) {
      this.canvas = canvas;
      this.org = org;
      this.ctx = canvas.getContext('2d');
      canvas.width = MAP.W * T * S;
      canvas.height = MAP.H * T * S;
      this.bg = renderBackground();
      this.selectedId = null;
      this.onSelect = null;
      this.time = 0;
      this.popups = [];   // zwevende teksten ("LEVEL UP!")
      this.bubbles = new Map(); // agentId → tekstballon
      this.letters = [];  // berichtjes tussen manager en agents

      // Meubels die voor/achter agents kunnen staan, worden mee-gesorteerd.
      this.props = [];
      for (let y = 0; y < MAP.H; y++) {
        for (let x = 0; x < MAP.W; x++) {
          const f = MAP.furn[y][x];
          if (f && (f.kind === 'desk' || f.kind === 'bossdesk' || f.kind === 'table')) this.props.push({ x, y, f });
        }
      }

      canvas.addEventListener('click', e => {
        const a = this.hitTest(e);
        if (a && this.onSelect) this.onSelect(a.id);
      });
      canvas.addEventListener('mousemove', e => {
        canvas.style.cursor = this.hitTest(e) ? 'pointer' : 'default';
      });
    }

    hitTest(e) {
      const r = this.canvas.getBoundingClientRect();
      const p = { x: (e.clientX - r.left) / r.width * MAP.W, y: (e.clientY - r.top) / r.height * MAP.H };
      let best = null, bestD = 0.8;
      for (const a of this.org.state.agents) {
        const d = Math.hypot(a.x + 0.5 - p.x, a.y + 0.3 - p.y);
        if (d < bestD) { best = a; bestD = d; }
      }
      return best;
    }

    popup(agentId, label, color) {
      this.popups.push({ agentId, text: label, color, t: 0 });
    }

    say(agentId, label) {
      this.bubbles.set(agentId, { text: label.length > 34 ? `${label.slice(0, 33)}…` : label, t: 0, dur: 2.2 + label.length * 0.05 });
    }

    letter(fromId, toId, color) {
      this.letters.push({ fromId, toId, color, t: 0, dur: 1.2 });
    }

    // ---------- tekenen ----------

    drawProp(ctx, p, occupants) {
      const x = p.x * T, y = p.y * T;
      if (p.f.kind === 'table') {
        px(ctx, x, y - 3, T, 15, C.outline);
        px(ctx, x, y - 2, T, 11, '#a8743f');
        px(ctx, x, y + 9, T, 3, '#7a4a24');
        if (p.f.end === 'left') px(ctx, x, y - 3, 1, 15, C.outline);
        if (p.f.end === 'right') px(ctx, x + 15, y - 3, 1, 15, C.outline);
        if ((p.x + p.y) % 2) { px(ctx, x + 4, y + 1, 6, 5, '#ffffff'); px(ctx, x + 5, y + 2, 4, 1, '#9aa3b5'); }
        return;
      }
      const boss = p.f.kind === 'bossdesk';
      px(ctx, x, y - 3, T, 14, C.outline);
      px(ctx, x + (boss ? 0 : 1), y - 2, T - (boss ? 0 : 2), 8, boss ? '#7a3a2a' : '#b07a48');
      px(ctx, x + (boss ? 0 : 1), y + 6, T - (boss ? 0 : 2), 4, boss ? '#5a2a1e' : '#86562f');
      // Beeldscherm: licht op als er iemand achter werkt.
      const occ = occupants.get(`${p.x},${p.y - 1}`);
      if (!boss || p.x === 16) {
        const working = occ && (occ.state === 'working' || occ.state === 'battling');
        const flick = Math.floor(this.time * 6 + p.x) % 3;
        px(ctx, x + 4, y - 7, 8, 6, C.outline);
        px(ctx, x + 5, y - 6, 6, 4, working ? (occ.state === 'battling' ? '#ff6b6b' : flick ? '#7fe0ff' : '#b8f0ff') : '#2a3b5c');
        if (working && occ.state === 'working') px(ctx, x + 6, y - 5 + flick % 2, 3, 1, '#2a3b5c');
        px(ctx, x + 7, y - 1, 2, 1, C.outline);
      }
      if (boss && p.x === 15) { px(ctx, x + 4, y - 6, 2, 5, '#ffd23f'); px(ctx, x + 3, y - 7, 4, 2, '#ffe27a'); }
      if (boss && p.x === 17) { px(ctx, x + 4, y - 3, 7, 4, '#ffffff'); px(ctx, x + 5, y - 2, 5, 1, '#9aa3b5'); }
    }

    drawAgent(ctx, a) {
      const seated = SEATED.has(a.state);
      const bob = seated ? 0 : Math.floor(this.time * 8 + a.id) % 2;
      const breathe = seated ? Math.floor(this.time * 1.5 + a.id) % 2 : 0;
      const X = Math.round(a.x * T), Y = Math.round(a.y * T) - 5 - bob + breathe;
      px(ctx, X + 3, Math.round(a.y * T) + 10, 10, 3, 'rgba(0,0,0,0.22)');
      ctx.save();
      if (a.facing < 0) {
        ctx.translate(X + 16, Y);
        ctx.scale(-1, 1);
        ctx.drawImage(FC.sprites.sprite(a.species), 0, 0);
      } else {
        ctx.drawImage(FC.sprites.sprite(a.species), X, Y);
      }
      ctx.restore();
    }

    drawAgentOverlay(ctx, a) {
      const X = Math.round(a.x * T), Y = Math.round(a.y * T) - 5;
      const org = this.org;
      if (a.id === this.selectedId) {
        const blink = Math.floor(this.time * 4) % 2;
        px(ctx, X + 5, Y - 9 - blink, 7, 2, '#ff3b3b');
        px(ctx, X + 6, Y - 7 - blink, 5, 1, '#ff3b3b');
        px(ctx, X + 7, Y - 6 - blink, 3, 1, '#ff3b3b');
        px(ctx, X + 8, Y - 5 - blink, 1, 1, '#ff3b3b');
      }
      if (a.state === 'working') {
        const q = org.quest(a.questId);
        if (q) {
          const pct = Math.min(1, q.progress / q.required);
          px(ctx, X + 1, Y - 3, 14, 4, C.outline);
          px(ctx, X + 2, Y - 2, Math.round(12 * pct), 2, '#ffd23f');
        }
      } else if (a.state === 'battling') {
        if (Math.floor(this.time * 4) % 2) { px(ctx, X + 7, Y - 8, 3, 6, '#ff3b3b'); px(ctx, X + 7, Y - 1, 3, 2, '#ff3b3b'); }
      } else if (a.state === 'resting') {
        const ph = (this.time * 0.7 + a.id * 0.3) % 1;
        ctx.globalAlpha = 1 - ph;
        text(ctx, 'z', X + 11 + ph * 3, Y - 2 - ph * 8, '#ffffff', 7);
        ctx.globalAlpha = 1;
      } else if (a.state === 'coffee') {
        px(ctx, X + 12, Y + 1, 4, 4, '#ffffff');
        px(ctx, X + 13, Y + 2, 2, 1, '#7a4a24');
      } else if (a.state === 'guarding') {
        px(ctx, X + 12, Y - 1, 5, 6, C.outline);
        px(ctx, X + 13, Y, 3, 4, '#ffd23f');
      }
      if (a.role === 'lead') {
        const lbl = 'MANAGER';
        ctx.font = 'bold 5px "Courier New", monospace';
        const w = Math.ceil(ctx.measureText(lbl).width) + 4;
        px(ctx, X + 8 - w / 2, Y + 19, w, 7, '#ffd23f');
        text(ctx, lbl, X + 10 - w / 2, Y + 20, C.outline, 5);
      }
    }

    drawBubble(ctx, a, b, taken) {
      ctx.font = 'bold 6px "Courier New", monospace';
      const w = Math.ceil(ctx.measureText(b.text).width) + 8;
      const h = 11;
      let x = Math.round(a.x * T + 8 - w / 2);
      x = Math.max(2, Math.min(MAP.W * T - w - 2, x));
      let y = Math.max(2, Math.round(a.y * T) - 26);
      // Niet over andere ballonnen heen: dan een regel hoger.
      const hits = r => !(x + w < r.x || r.x + r.w < x || y + h + 2 < r.y || r.y + r.h + 2 < y);
      for (let i = 0; i < 6 && taken.some(hits); i++) y -= h + 3;
      taken.push({ x, y, w, h });
      const fade = Math.min(1, (b.dur - b.t) * 3);
      ctx.globalAlpha = Math.max(0, fade);
      px(ctx, x - 1, y - 1, w + 2, h + 2, C.outline);
      px(ctx, x, y, w, h, '#ffffff');
      const tx = Math.round(a.x * T + 7);
      px(ctx, tx, y + h + 1, 3, 2, C.outline);
      px(ctx, tx + 1, y + h, 1, 2, '#ffffff');
      text(ctx, b.text, x + 4, y + 2, C.outline, 6);
      ctx.globalAlpha = 1;
    }

    drawLetter(ctx, l) {
      const from = this.org.agent(l.fromId), to = this.org.agent(l.toId);
      if (!from || !to) { l.t = l.dur; return; }
      const p = Math.min(1, l.t / l.dur);
      const x = (from.x + (to.x - from.x) * p) * T + 4;
      const y = (from.y + (to.y - from.y) * p) * T - 4 - Math.sin(p * Math.PI) * 30;
      px(ctx, x - 1, y - 1, 10, 8, C.outline);
      px(ctx, x, y, 8, 6, l.color);
      px(ctx, x + 1, y + 1, 3, 1, C.outline);
      px(ctx, x + 4, y + 1, 3, 1, C.outline);
      px(ctx, x + 3, y + 2, 2, 2, '#e8453c');
    }

    draw(dt) {
      this.time += dt;
      const ctx = this.ctx;
      const org = this.org;
      ctx.imageSmoothingEnabled = false;
      ctx.setTransform(S, 0, 0, S, 0, 0);
      ctx.drawImage(this.bg, 0, 0);

      // Golfjes op de vijver
      for (let y = 0; y < MAP.H; y++) {
        for (let x = 0; x < MAP.W; x++) {
          if (MAP.tiles[y][x] !== '~') continue;
          const o = Math.floor(this.time * 3 + x + y) % 8;
          px(ctx, x * T + o + 1, y * T + 4, 4, 1, C.waterLight);
          px(ctx, x * T + ((o + 5) % 8) + 4, y * T + 11, 4, 1, C.waterLight);
        }
      }

      // Agents en meubels samen sorteren op diepte.
      const occupants = new Map();
      for (const a of org.state.agents) occupants.set(`${Math.round(a.x)},${Math.round(a.y)}`, a);
      const items = [];
      for (const p of this.props) items.push({ y: p.y, draw: () => this.drawProp(ctx, p, occupants) });
      for (const a of org.state.agents) items.push({ y: a.y + 0.5, draw: () => this.drawAgent(ctx, a) });
      items.sort((p, q) => p.y - q.y);
      items.forEach(i => i.draw());
      for (const a of org.state.agents) this.drawAgentOverlay(ctx, a);

      // Berichtjes van/naar de manager
      this.letters = this.letters.filter(l => l.t < l.dur);
      for (const l of this.letters) { l.t += dt; this.drawLetter(ctx, l); }

      // Tekstballonnen
      const taken = [];
      for (const [id, b] of this.bubbles) {
        b.t += dt;
        const a = org.agent(id);
        if (!a || b.t > b.dur) { this.bubbles.delete(id); continue; }
        this.drawBubble(ctx, a, b, taken);
      }

      // Zwevende teksten
      this.popups = this.popups.filter(p => p.t < 2.2);
      for (const p of this.popups) {
        p.t += dt;
        const a = org.agent(p.agentId);
        if (!a) continue;
        const X = a.x * T + 8, Y = a.y * T - 14 - p.t * 10;
        ctx.font = 'bold 7px "Courier New", monospace';
        const w = ctx.measureText(p.text).width;
        ctx.globalAlpha = Math.min(1, 2.2 - p.t);
        text(ctx, p.text, X - w / 2 + 1, Y + 1, C.outline);
        text(ctx, p.text, X - w / 2, Y, p.color);
        ctx.globalAlpha = 1;
      }

      // Dag/nacht
      const h = org.state.minute / 60;
      let night = 0;
      if (h >= 20 || h < 5) night = 1;
      if (h >= 18 && h < 20) night = (h - 18) / 2;
      if (h >= 5 && h < 7) night = 1 - (h - 5) / 2;
      if (night > 0) {
        ctx.fillStyle = `rgba(20, 24, 80, ${0.42 * night})`;
        ctx.fillRect(0, 0, MAP.W * T, MAP.H * T);
      }
      if (h >= 17 && h < 19) {
        ctx.fillStyle = `rgba(255, 140, 60, ${0.1 * (1 - Math.abs(h - 18))})`;
        ctx.fillRect(0, 0, MAP.W * T, MAP.H * T);
      }

      ctx.setTransform(1, 0, 0, 1, 0, 0);
    }
  }

  FC.World = World;
})(window.FC);
