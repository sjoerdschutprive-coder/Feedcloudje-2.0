// Wereldkaart van de organisatie: een afgesloten dal, omringd door bos,
// met één poort die bewaakt wordt door het beveiligingsteam.
window.FC = window.FC || {};

(function (FC) {
  const W = 32;
  const H = 20;

  // Afdelingen = gebouwen op de kaart. `type` bepaalt welke medewerkers
  // er het best werken (zoals een type-voordeel in een spel).
  const BUILDINGS = [
    { id: 'hq',     name: 'HOOFDKANTOOR', short: 'HQ',      type: 'STRATEGIE',   x: 13, y: 1,  w: 6, h: 4, roof: '#c0392b' },
    { id: 'lab',    name: 'CODE-LAB',     short: 'LAB',     type: 'CODE',        x: 3,  y: 3,  w: 5, h: 3, roof: '#2e6fd8' },
    { id: 'studio', name: 'STUDIO',       short: 'STUDIO',  type: 'CREATIEF',    x: 24, y: 3,  w: 5, h: 3, roof: '#d64fa0' },
    { id: 'bieb',   name: 'DATABIEB',     short: 'BIEB',    type: 'DATA',        x: 3,  y: 11, w: 5, h: 3, roof: '#2f9e5b' },
    { id: 'werk',   name: 'WERKPLAATS',   short: 'WERK',    type: 'OPERATIONS',  x: 24, y: 11, w: 5, h: 3, roof: '#e07b24' },
    { id: 'rust',   name: 'HERSTELHUIS',  short: 'RUST',    type: null,          x: 10, y: 11, w: 4, h: 3, roof: '#ef6f8f' },
    { id: 'poort',  name: 'POORTWACHT',   short: 'POORT',   type: 'BEVEILIGING', x: 18, y: 14, w: 3, h: 3, roof: '#5b6478' },
  ];
  BUILDINGS.forEach(b => {
    b.door = { x: b.x + Math.floor(b.w / 2), y: b.y + b.h - 1 };
  });

  const GATE = { x: 16, y: 19 };      // de enige toegang tot het dal
  const GUARD_SPOT = { x: 16, y: 18 }; // waar de wachter staat

  // Tegels: T boom, . gras, , bloemen, = pad, ~ water, B gebouw, D deur, G poort
  const tiles = [];
  for (let y = 0; y < H; y++) {
    tiles.push(new Array(W).fill('.'));
  }
  const set = (x, y, t) => { if (x >= 0 && y >= 0 && x < W && y < H) tiles[y][x] = t; };
  const hline = (y, x1, x2, t) => { for (let x = x1; x <= x2; x++) set(x, y, t); };
  const vline = (x, y1, y2, t) => { for (let y = y1; y <= y2; y++) set(x, y, t); };

  // Deterministische "random" zodat de kaart altijd hetzelfde is.
  let seed = 7;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;

  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      if (rnd() < 0.07) set(x, y, ',');
    }
  }

  // Paden
  hline(8, 2, 29, '=');
  hline(17, 2, 29, '=');
  vline(2, 8, 17, '=');
  vline(29, 8, 17, '=');
  vline(16, 5, 18, '=');
  vline(5, 6, 8, '=');
  vline(26, 6, 8, '=');
  vline(5, 14, 17, '=');
  vline(26, 14, 17, '=');
  vline(12, 14, 17, '=');

  // Vijver
  for (let y = 10; y <= 12; y++) hline(y, 20, 22, '~');

  // Bosrand (de afsluiting van de omgeving)
  hline(0, 0, W - 1, 'T');
  hline(H - 1, 0, W - 1, 'T');
  vline(0, 0, H - 1, 'T');
  vline(W - 1, 0, H - 1, 'T');
  [[1, 1], [2, 1], [1, 2], [30, 1], [29, 1], [30, 2], [1, 18], [2, 18], [30, 18], [29, 18],
   [9, 2], [10, 3], [21, 2], [22, 3], [9, 15], [8, 16], [23, 16], [22, 6], [9, 6]]
    .forEach(([x, y]) => set(x, y, 'T'));
  set(GATE.x, GATE.y, 'G');

  BUILDINGS.forEach(b => {
    for (let y = b.y; y < b.y + b.h; y++) hline(y, b.x, b.x + b.w - 1, 'B');
    set(b.door.x, b.door.y, 'D');
  });

  const walkable = (x, y) => {
    if (x < 0 || y < 0 || x >= W || y >= H) return false;
    const t = tiles[y][x];
    return t === '.' || t === ',' || t === '=' || t === 'D';
  };

  // Kortste route over beloopbare tegels (BFS). Geeft lijst tegels terug
  // exclusief de starttegel.
  function findPath(sx, sy, tx, ty) {
    sx = Math.round(sx); sy = Math.round(sy);
    if (sx === tx && sy === ty) return [];
    const key = (x, y) => y * W + x;
    const prev = new Map();
    const queue = [[sx, sy]];
    prev.set(key(sx, sy), null);
    const dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]];
    while (queue.length) {
      const [x, y] = queue.shift();
      if (x === tx && y === ty) break;
      for (const [dx, dy] of dirs) {
        const nx = x + dx, ny = y + dy;
        const k = key(nx, ny);
        if (prev.has(k) || !walkable(nx, ny)) continue;
        // Deuren alleen betreden als het de bestemming is.
        if (tiles[ny][nx] === 'D' && !(nx === tx && ny === ty)) continue;
        prev.set(k, [x, y]);
        queue.push([nx, ny]);
      }
    }
    if (!prev.has(key(tx, ty))) return null;
    const path = [];
    let cur = [tx, ty];
    while (cur && !(cur[0] === sx && cur[1] === sy)) {
      path.unshift({ x: cur[0], y: cur[1] });
      cur = prev.get(key(cur[0], cur[1]));
    }
    return path;
  }

  function randomOpenTile() {
    for (let i = 0; i < 200; i++) {
      const x = 2 + Math.floor(Math.random() * (W - 4));
      const y = 2 + Math.floor(Math.random() * (H - 4));
      if (walkable(x, y) && tiles[y][x] !== 'D') return { x, y };
    }
    return { x: 16, y: 8 };
  }

  FC.map = {
    W, H, tiles, BUILDINGS, GATE, GUARD_SPOT,
    building: id => BUILDINGS.find(b => b.id === id),
    buildingForType: type => BUILDINGS.find(b => b.type === type),
    walkable, findPath, randomOpenTile,
  };
})(window.FC);
