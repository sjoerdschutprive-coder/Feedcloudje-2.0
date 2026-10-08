// Plattegrond van de organisatie: één opengewerkt kantoorgebouw in een
// afgesloten dal. Het bos eromheen is de grens, de poort onderaan de enige
// toegang. Binnen: afdelingen met bureaus (één hoofd + agents), een gang met
// in het midden het prikbord, een centrale vergaderzaal, het kantoor van
// directeur Godfred en een lounge.
window.FC = window.FC || {};

(function (FC) {
  const W = 40;
  const H = 26;

  const grid = fill => Array.from({ length: H }, () => new Array(W).fill(fill));
  // Tegels: T boom, . gras, , bloemen, = pad, ~ water, G poort,
  //         # muur, f vloer, d deur
  const tiles = grid('.');
  const roomAt = grid(null); // welke ruimte hoort bij een vloertegel
  const furn = grid(null);   // meubilair per tegel

  const inMap = (x, y) => x >= 0 && y >= 0 && x < W && y < H;
  const set = (x, y, t) => { if (inMap(x, y)) tiles[y][x] = t; };
  const hline = (y, x1, x2, t) => { for (let x = x1; x <= x2; x++) set(x, y, t); };
  const vline = (x, y1, y2, t) => { for (let y = y1; y <= y2; y++) set(x, y, t); };
  const place = (x, y, kind, extra) => { furn[y][x] = Object.assign({ kind }, extra); };

  // `type` = welk soort medewerker hier thuishoort.
  const ROOMS = [
    { id: 'lab',     name: 'CODE-LAB',     type: 'CODE',        x0: 2,  y0: 2,  x1: 11, y1: 9,  floor: 'wood',       doorSide: 'bottom' },
    { id: 'hq',      name: 'DIRECTIE',     type: 'STRATEGIE',   x0: 11, y0: 2,  x1: 20, y1: 9,  floor: 'carpetRed',  doorSide: 'bottom' },
    { id: 'studio',  name: 'STUDIO',       type: 'CREATIEF',    x0: 20, y0: 2,  x1: 29, y1: 9,  floor: 'wood',       doorSide: 'bottom' },
    { id: 'lounge',  name: 'LOUNGE',       type: null,          x0: 29, y0: 2,  x1: 37, y1: 9,  floor: 'tiles',      doorSide: 'bottom' },
    { id: 'bieb',    name: 'DATABIEB',     type: 'DATA',        x0: 2,  y0: 12, x1: 11, y1: 18, floor: 'wood',       doorSide: 'top' },
    { id: 'meeting', name: 'VERGADERZAAL', type: null,          x0: 11, y0: 12, x1: 29, y1: 18, floor: 'carpetBlue', doorSide: 'top', doorXs: [15, 25] },
    { id: 'werk',    name: 'WERKPLAATS',   type: 'OPERATIONS',  x0: 29, y0: 12, x1: 37, y1: 18, floor: 'wood',       doorSide: 'top' },
    { id: 'poort',   name: 'POORTWACHT',   type: 'BEVEILIGING', x0: 23, y0: 21, x1: 28, y1: 24, floor: 'concrete',   doorSide: 'top' },
  ];
  const CORRIDOR = { id: 'gang', name: 'GANG', floor: 'corridor' };

  const GATE = { x: 20, y: 25 };
  const GUARD_SPOT = { x: 20, y: 24 };

  // ---------- buitenkant ----------
  let seed = 11;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (rnd() < 0.06) set(x, y, ',');

  vline(1, 10, 20, '=');
  vline(38, 10, 20, '=');
  hline(20, 1, 38, '=');
  vline(20, 21, 24, '=');
  for (let y = 22; y <= 23; y++) hline(y, 6, 11, '~');

  hline(0, 0, W - 1, 'T');
  hline(H - 1, 0, W - 1, 'T');
  vline(0, 0, H - 1, 'T');
  vline(W - 1, 0, H - 1, 'T');
  [[3, 22], [14, 23], [16, 22], [34, 23], [36, 21], [1, 24], [2, 24], [38, 24], [37, 24], [1, 1], [38, 1]]
    .forEach(([x, y]) => set(x, y, 'T'));
  set(GATE.x, GATE.y, 'G');

  // ---------- het gebouw ----------
  function buildRoom(r) {
    for (let y = r.y0; y <= r.y1; y++) {
      for (let x = r.x0; x <= r.x1; x++) {
        const edge = x === r.x0 || x === r.x1 || y === r.y0 || y === r.y1;
        if (edge) { set(x, y, '#'); continue; }
        set(x, y, 'f');
        roomAt[y][x] = r.id;
      }
    }
  }
  ROOMS.forEach(buildRoom);

  // Gang tussen de twee rijen ruimtes, met uitgangen links en rechts.
  for (let y = 10; y <= 11; y++) {
    for (let x = 2; x <= 37; x++) {
      if (x === 2 || x === 37) { set(x, y, 'd'); roomAt[y][x] = 'gang'; continue; }
      set(x, y, 'f');
      roomAt[y][x] = 'gang';
    }
  }

  ROOMS.forEach(r => {
    r.ix0 = r.x0 + 1; r.ix1 = r.x1 - 1; r.iy0 = r.y0 + 1; r.iy1 = r.y1 - 1;
    const doorXs = r.doorXs || [Math.ceil((r.x0 + r.x1) / 2)];
    const dy = r.doorSide === 'bottom' ? r.y1 : r.y0;
    r.doors = doorXs.map(x => ({ x, y: dy }));
    r.doors.forEach(d => { set(d.x, d.y, 'd'); roomAt[d.y][d.x] = r.id; });
    r.seats = [];
  });

  const room = id => ROOMS.find(r => r.id === id);

  // Afdelingen met bureaus: rijen stoelen met het bureau eronder. De
  // medewerker zit "achter" zijn bureau en kijkt de kijker aan.
  // Werkafdelingen: een hoofd en een team van agents.
  const DEPTS = ['lab', 'studio', 'bieb', 'werk'];
  DEPTS.forEach(id => {
    const r = room(id);
    const doorXs = r.doors.map(d => d.x);
    const chairRows = r.doorSide === 'bottom' ? [r.iy0, r.iy0 + 3] : [r.iy0 + 1, r.iy0 + 3];
    chairRows.forEach(cy => {
      for (let x = r.ix0 + 1; x <= r.ix1 - 1; x++) {
        if (doorXs.includes(x)) continue;
        place(x, cy + 1, 'desk');
        place(x, cy, 'chair');
        r.seats.push({ x, y: cy });
      }
    });
  });

  // Het afdelingshoofd krijgt het bureau het dichtst bij de deur: snel naar
  // het prikbord en naar Godfred.
  DEPTS.forEach(id => {
    const r = room(id);
    const d = r.doors[0];
    const head = r.seats.slice().sort((p, q) =>
      (Math.abs(p.y - d.y) - Math.abs(q.y - d.y)) || (Math.abs(p.x - d.x) - Math.abs(q.x - d.x)))[0];
    r.headSeat = head;
    r.seats = r.seats.filter(s => s !== head);
    place(head.x, head.y + 1, 'headdesk', { dept: id });
  });

  // Poortwacht: het kantoor van RISK THREAT, met de serverkasten waar de
  // firewall op draait. Eén bureau; de poort zelf ligt er vlakbij.
  const RISK_SEAT = { x: 25, y: 22 };
  place(25, 22, 'chair');
  place(25, 23, 'headdesk', { dept: 'poort' });
  place(27, 22, 'server'); place(27, 23, 'server'); place(24, 23, 'plant');
  room('poort').headSeat = RISK_SEAT;

  // Kantoor van directeur Godfred.
  const BOSS_SEAT = { x: 16, y: 4 };
  place(16, 4, 'chair');
  [15, 16, 17].forEach(x => place(x, 5, 'bossdesk'));
  place(12, 3, 'shelf'); place(13, 3, 'shelf'); place(19, 3, 'plant'); place(12, 8, 'plant');
  const VISITOR_SPOTS = [{ x: 15, y: 7 }, { x: 17, y: 7 }, { x: 16, y: 7 }];

  // Lounge: self-service buffet langs de muur (betalen met XP) en
  // zitzakken om je versnapering op te eten.
  const BUFFET_ITEMS = ['koffie', 'fruit', 'broodje', 'smoothie', 'taart'];
  const BUFFET = BUFFET_ITEMS.map((item, i) => {
    place(31 + i, 3, 'buffet', { item });
    return { item, x: 31 + i, y: 4 };   // hier sta je om te pakken
  });
  place(30, 3, 'plant'); place(36, 3, 'plant');
  const REST_SPOTS = [[31, 6], [35, 6], [32, 7], [34, 7], [30, 6], [36, 6], [30, 8], [36, 8]]
    .map(([x, y]) => ({ x, y }));
  REST_SPOTS.forEach((s, i) => place(s.x, s.y, 'beanbag', { color: i % 3 }));

  // Centrale vergaderzaal: lange tafel met stoelen aan beide kanten.
  const MEETING_SEATS = [];
  for (let x = 16; x <= 24; x++) {
    place(x, 15, 'table', { end: x === 16 ? 'left' : x === 24 ? 'right' : null });
    place(x, 14, 'chair');
    place(x, 16, 'chair');
    MEETING_SEATS.push({ x, y: 14 }, { x, y: 16 });
  }
  const PRESENTER_SPOT = { x: 14, y: 15 };
  [14, 15, 16].forEach(y => place(12, y, 'board', { part: y - 14 }));
  place(28, 13, 'plant'); place(28, 17, 'plant'); place(12, 13, 'plant'); place(12, 17, 'plant');

  // Gang, met in het midden het prikbord aan de muur. Daar hangt Godfred
  // nieuwe taken op en halen de afdelingshoofden ze op.
  place(4, 10, 'plant'); place(35, 11, 'plant');
  const BOARD = { x0: 18, x1: 22, y: 9 };
  const BOARD_SPOTS = [{ x: 20, y: 10 }, { x: 19, y: 10 }, { x: 21, y: 10 }, { x: 18, y: 10 }, { x: 22, y: 10 }];

  const BLOCKING = new Set(['desk', 'headdesk', 'bossdesk', 'table', 'shelf', 'buffet', 'server', 'plant', 'board']);

  const walkable = (x, y) => {
    if (!inMap(x, y)) return false;
    const t = tiles[y][x];
    if (!(t === '.' || t === ',' || t === '=' || t === 'f' || t === 'd')) return false;
    const f = furn[y][x];
    return !(f && BLOCKING.has(f.kind));
  };

  // Kortste route (BFS) over beloopbare tegels, exclusief de starttegel.
  function findPath(sx, sy, tx, ty) {
    sx = Math.round(sx); sy = Math.round(sy);
    if (sx === tx && sy === ty) return [];
    const key = (x, y) => y * W + x;
    const prev = new Map([[key(sx, sy), null]]);
    const queue = [[sx, sy]];
    const dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]];
    for (let i = 0; i < queue.length; i++) {
      const [x, y] = queue[i];
      if (x === tx && y === ty) break;
      for (const [dx, dy] of dirs) {
        const nx = x + dx, ny = y + dy;
        const k = key(nx, ny);
        if (prev.has(k) || !walkable(nx, ny)) continue;
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

  FC.map = {
    W, H, tiles, roomAt, furn, ROOMS, CORRIDOR, GATE, GUARD_SPOT, DEPTS, BOARD, BOARD_SPOTS,
    BOSS_SEAT, RISK_SEAT, VISITOR_SPOTS, BUFFET, REST_SPOTS, MEETING_SEATS, PRESENTER_SPOT,
    room,
    roomForType: type => ROOMS.find(r => r.type === type),
    walkable, findPath,
    spotKey: s => `${s.x},${s.y}`,
  };
})(window.FC);
