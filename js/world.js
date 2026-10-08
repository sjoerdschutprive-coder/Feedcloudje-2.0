// Tekent de bovenaanzicht-wereld in retro-handheldstijl op een canvas.
window.FC = window.FC || {};

(function (FC) {
  const MAP = FC.map;
  const T = 16; // tegelgrootte in "pixels"
  const S = 3;  // schaal naar echte canvas-pixels

  const C = {
    grass: '#8bd45b', grassDark: '#6cb848', grassLight: '#a6e57a',
    path: '#ecd9a5', pathEdge: '#d4bd82',
    water: '#4aa3df', waterLight: '#9fd8ff',
    trunk: '#7a4a24', leaf: '#2f8a3c', leafDark: '#1f6a2c', leafLight: '#4fb05a',
    wall: '#f4ead2', wallShade: '#d9cba8', door: '#5a3a22', window: '#7fc8ff',
    outline: '#1a1c2c',
  };

  function px(ctx, x, y, w, h, color) {
    ctx.fillStyle = color;
    ctx.fillRect(x, y, w, h);
  }

  function drawGrass(ctx, x, y, variant) {
    px(ctx, x, y, T, T, C.grass);
    const seed = (x * 7 + y * 13) % 5;
    px(ctx, x + 3 + seed, y + 4, 1, 2, C.grassDark);
    px(ctx, x + 4 + seed, y + 3, 1, 2, C.grassDark);
    px(ctx, x + 11 - seed, y + 11, 1, 2, C.grassDark);
    px(ctx, x + 12 - seed, y + 10, 1, 2, C.grassDark);
    if (variant === ',') {
      const flowers = ['#ffffff', '#ffd23f', '#ff7aa8'];
      const col = flowers[(x + y) % 3];
      [[4, 9], [10, 4], [12, 12]].forEach(([fx, fy]) => {
        px(ctx, x + fx, y + fy, 2, 2, col);
        px(ctx, x + fx, y + fy + 2, 1, 1, C.grassDark);
      });
    }
  }

  function drawPath(ctx, x, y) {
    px(ctx, x, y, T, T, C.path);
    px(ctx, x + 3, y + 5, 2, 1, C.pathEdge);
    px(ctx, x + 10, y + 11, 2, 1, C.pathEdge);
    px(ctx, x + 12, y + 3, 1, 1, C.pathEdge);
  }

  function drawWater(ctx, x, y) {
    px(ctx, x, y, T, T, C.water);
  }

  function drawTree(ctx, x, y) {
    drawGrass(ctx, x, y);
    px(ctx, x + 6, y + 11, 4, 4, C.trunk);
    px(ctx, x + 2, y + 2, 12, 9, C.leafDark);
    px(ctx, x + 1, y + 4, 14, 6, C.leafDark);
    px(ctx, x + 3, y + 1, 10, 8, C.leaf);
    px(ctx, x + 2, y + 3, 12, 5, C.leaf);
    px(ctx, x + 4, y + 2, 3, 2, C.leafLight);
    px(ctx, x + 3, y + 4, 2, 2, C.leafLight);
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

  function shade(hex, f) {
    const n = parseInt(hex.slice(1), 16);
    const r = Math.min(255, Math.round(((n >> 16) & 255) * f));
    const g = Math.min(255, Math.round(((n >> 8) & 255) * f));
    const b = Math.min(255, Math.round((n & 255) * f));
    return `rgb(${r},${g},${b})`;
  }

  function drawBuilding(ctx, b) {
    const x = b.x * T, y = b.y * T, w = b.w * T, h = b.h * T;
    const roofH = Math.round(h * 0.55);
    // schaduw
    px(ctx, x + 2, y + h - 2, w, 4, 'rgba(0,0,0,0.18)');
    // muren
    px(ctx, x, y + roofH - 2, w, h - roofH + 2, C.outline);
    px(ctx, x + 1, y + roofH, w - 2, h - roofH - 1, C.wall);
    px(ctx, x + 1, y + h - 4, w - 2, 3, C.wallShade);
    // dak
    px(ctx, x - 1, y, w + 2, roofH + 1, C.outline);
    px(ctx, x, y + 1, w, roofH - 1, b.roof);
    for (let ry = y + 4; ry < y + roofH - 1; ry += 4) px(ctx, x, ry, w, 1, shade(b.roof, 0.78));
    px(ctx, x, y + 1, w, 2, shade(b.roof, 1.25));
    // ramen
    const dx = b.door.x * T;
    for (let wx = x + 5; wx < x + w - 10; wx += 14) {
      if (Math.abs(wx - dx) < 14) continue;
      px(ctx, wx, y + roofH + 3, 8, 6, C.outline);
      px(ctx, wx + 1, y + roofH + 4, 6, 4, C.window);
      px(ctx, wx + 1, y + roofH + 4, 2, 2, '#ffffff');
    }
    // deur
    px(ctx, dx + 3, b.door.y * T + 3, 10, 13, C.outline);
    px(ctx, dx + 4, b.door.y * T + 4, 8, 12, C.door);
    px(ctx, dx + 10, b.door.y * T + 10, 1, 1, '#ffd23f');
    // naambordje op het dak
    ctx.font = `bold 7px "Courier New", monospace`;
    const label = b.short;
    const tw = Math.ceil(ctx.measureText(label).width) + 6;
    const lx = Math.round(x + w / 2 - tw / 2), ly = y + Math.round(roofH / 2) - 5;
    px(ctx, lx - 1, ly - 1, tw + 2, 11, C.outline);
    px(ctx, lx, ly, tw, 9, '#fffbe8');
    ctx.fillStyle = C.outline;
    ctx.textBaseline = 'top';
    ctx.fillText(label, lx + 3, ly + 1);
    // extra's
    if (b.id === 'hq') {
      px(ctx, x + w - 8, y - 12, 1, 13, C.outline);
      px(ctx, x + w - 7, y - 12, 7, 5, '#ffd23f');
    }
    if (b.id === 'rust') {
      px(ctx, x + 3, y + roofH + 3, 7, 7, '#ffffff');
      px(ctx, x + 5, y + roofH + 4, 3, 5, '#ef3f5f');
      px(ctx, x + 4, y + roofH + 5, 5, 3, '#ef3f5f');
    }
  }

  function renderBackground() {
    const c = document.createElement('canvas');
    c.width = MAP.W * T;
    c.height = MAP.H * T;
    const ctx = c.getContext('2d');
    for (let y = 0; y < MAP.H; y++) {
      for (let x = 0; x < MAP.W; x++) {
        const t = MAP.tiles[y][x];
        const X = x * T, Y = y * T;
        if (t === '=' || t === 'D') drawPath(ctx, X, Y);
        else if (t === '~') drawWater(ctx, X, Y);
        else if (t === 'T') drawTree(ctx, X, Y);
        else if (t === 'G') drawGate(ctx, X, Y);
        else drawGrass(ctx, X, Y, t);
      }
    }
    MAP.BUILDINGS.forEach(b => drawBuilding(ctx, b));
    return c;
  }

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
      this.popups = []; // zwevende teksten zoals "LEVEL UP!"
      canvas.addEventListener('click', e => this.handleClick(e));
      canvas.addEventListener('mousemove', e => {
        const hit = this.hitTest(e);
        canvas.style.cursor = hit ? 'pointer' : 'default';
      });
    }

    toWorld(e) {
      const r = this.canvas.getBoundingClientRect();
      return {
        x: (e.clientX - r.left) / r.width * MAP.W,
        y: (e.clientY - r.top) / r.height * MAP.H,
      };
    }

    hitTest(e) {
      const p = this.toWorld(e);
      let best = null, bestD = 0.9;
      for (const a of this.org.state.agents) {
        if (!this.isVisible(a)) continue;
        const d = Math.hypot(a.x + 0.5 - p.x, a.y + 0.4 - p.y);
        if (d < bestD) { best = a; bestD = d; }
      }
      return best;
    }

    handleClick(e) {
      const a = this.hitTest(e);
      if (a && this.onSelect) this.onSelect(a.id);
    }

    isVisible(a) {
      // Wie binnen werkt of uitrust, zit in het gebouw.
      return !(a.state === 'working' || a.state === 'resting' || a.state === 'battling');
    }

    popup(agentId, text, color) {
      this.popups.push({ agentId, text, color, t: 0 });
    }

    draw(dt) {
      this.time += dt;
      const ctx = this.ctx;
      const org = this.org;
      ctx.imageSmoothingEnabled = false;
      ctx.setTransform(S, 0, 0, S, 0, 0);
      ctx.drawImage(this.bg, 0, 0);

      // Golfjes op het water
      for (let y = 0; y < MAP.H; y++) {
        for (let x = 0; x < MAP.W; x++) {
          if (MAP.tiles[y][x] !== '~') continue;
          const o = Math.floor(this.time * 3 + x + y) % 8;
          px(ctx, x * T + o + 1, y * T + 4, 4, 1, C.waterLight);
          px(ctx, x * T + ((o + 5) % 8) + 4, y * T + 11, 4, 1, C.waterLight);
        }
      }

      // Activiteit in gebouwen tonen (rookpluimpjes / aantal binnen)
      const inside = {};
      for (const a of org.state.agents) {
        if (this.isVisible(a)) continue;
        let bid = 'rust';
        if (a.state !== 'resting') {
          const q = org.quest(a.questId);
          if (q) bid = q.dept;
        }
        inside[bid] = (inside[bid] || 0) + 1;
      }
      MAP.BUILDINGS.forEach(b => {
        const n = inside[b.id];
        if (!n) return;
        const bx = (b.x + b.w) * T - 10, by = b.y * T - 2;
        for (let i = 0; i < 3; i++) {
          const ph = (this.time * 0.8 + i / 3) % 1;
          ctx.globalAlpha = 1 - ph;
          px(ctx, bx + Math.sin(ph * 6 + i) * 2, by - ph * 14, 3, 3, '#ffffff');
        }
        ctx.globalAlpha = 1;
        const label = `${n}`;
        px(ctx, b.x * T + 2, b.y * T + 2, 11, 10, C.outline);
        px(ctx, b.x * T + 3, b.y * T + 3, 9, 8, b.id === 'rust' ? '#ffb3c6' : '#ffd23f');
        ctx.fillStyle = C.outline;
        ctx.font = 'bold 7px "Courier New", monospace';
        ctx.textBaseline = 'top';
        ctx.fillText(label, b.x * T + 5, b.y * T + 3);
      });

      // Medewerkers, gesorteerd op y zodat diepte klopt
      const visible = org.state.agents.filter(a => this.isVisible(a)).sort((p, q) => p.y - q.y);
      for (const a of visible) {
        const walking = a.state === 'walking';
        const bob = walking ? (Math.floor(this.time * 8 + a.id) % 2) : (Math.floor(this.time * 2 + a.id) % 2);
        const X = Math.round(a.x * T), Y = Math.round(a.y * T) - 3 - bob;
        px(ctx, X + 3, Math.round(a.y * T) + 12, 10, 3, 'rgba(0,0,0,0.25)');
        if (a.id === this.selectedId) {
          const blink = Math.floor(this.time * 4) % 2;
          px(ctx, X + 6, Y - 6 - blink, 5, 2, '#ff3b3b');
          px(ctx, X + 7, Y - 4 - blink, 3, 1, '#ff3b3b');
          px(ctx, X + 8, Y - 3 - blink, 1, 1, '#ff3b3b');
        }
        ctx.save();
        if (a.facing < 0) {
          ctx.translate(X + 16, Y);
          ctx.scale(-1, 1);
          ctx.drawImage(FC.sprites.sprite(a.species), 0, 0);
        } else {
          ctx.drawImage(FC.sprites.sprite(a.species), X, Y);
        }
        ctx.restore();
        if (a.state === 'guarding') {
          px(ctx, X + 12, Y - 1, 5, 6, C.outline);
          px(ctx, X + 13, Y, 3, 4, '#ffd23f');
        }
        if (org.isNight() && a.state === 'idle') {
          ctx.fillStyle = '#ffffff';
          ctx.font = 'bold 6px "Courier New", monospace';
          ctx.fillText('z', X + 13, Y - 2 + bob);
        }
      }

      // Zwevende teksten
      this.popups = this.popups.filter(p => p.t < 2.2);
      for (const p of this.popups) {
        p.t += dt;
        const a = org.agent(p.agentId);
        if (!a) continue;
        let X = a.x * T + 8, Y = a.y * T - 8 - p.t * 10;
        if (!this.isVisible(a)) {
          const q = org.quest(a.questId);
          const b = MAP.building(a.state === 'resting' ? 'rust' : (q ? q.dept : 'rust'));
          X = b.door.x * T + 8; Y = b.y * T - 4 - p.t * 10;
        }
        ctx.font = 'bold 7px "Courier New", monospace';
        const w = ctx.measureText(p.text).width;
        ctx.globalAlpha = Math.min(1, 2.2 - p.t);
        ctx.fillStyle = C.outline;
        ctx.fillText(p.text, X - w / 2 + 1, Y + 1);
        ctx.fillStyle = p.color;
        ctx.fillText(p.text, X - w / 2, Y);
        ctx.globalAlpha = 1;
      }

      // Dag/nacht-kleuring
      const h = org.state.minute / 60;
      let night = 0;
      if (h >= 20 || h < 5) night = 1;
      if (h >= 18 && h < 20) night = (h - 18) / 2;
      if (h >= 5 && h < 7) night = 1 - (h - 5) / 2;
      if (night > 0) {
        ctx.fillStyle = `rgba(20, 24, 80, ${0.45 * night})`;
        ctx.fillRect(0, 0, MAP.W * T, MAP.H * T);
        // verlichte ramen
        ctx.globalAlpha = night;
        MAP.BUILDINGS.forEach(b => {
          const dx = b.door.x * T;
          px(ctx, dx + 4, b.door.y * T + 4, 8, 3, '#ffe27a');
        });
        ctx.globalAlpha = 1;
      }
      if (h >= 17 && h < 19) {
        ctx.fillStyle = `rgba(255, 140, 60, ${0.12 * (1 - Math.abs(h - 18))})`;
        ctx.fillRect(0, 0, MAP.W * T, MAP.H * T);
      }

      ctx.setTransform(1, 0, 0, 1, 0, 0);
    }
  }

  FC.World = World;
})(window.FC);
