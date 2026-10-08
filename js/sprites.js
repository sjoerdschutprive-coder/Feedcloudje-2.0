// Pixel-art wezentjes. Elke sprite is 16x16; we tekenen alleen de linker
// helft (8 kolommen) en spiegelen die, zodat alles symmetrisch blijft.
window.FC = window.FC || {};

(function (FC) {
  const BASE = { k: '#1a1c2c', w: '#ffffff', c: '#ff8fa3', y: '#ffd23f' };

  const SPECIES = {
    BITBIT: {
      type: 'CODE',
      dex: 'Een rond robotje dat 1 en 0 eet. Zijn antenne licht op bij elke geslaagde test.',
      palette: { b: '#4a90e2', l: '#9cc9ff' },
      half: [
        '........',
        '......ky',
        '.......k',
        '.......k',
        '....kkkk',
        '...kbbbb',
        '..kbbbbb',
        '..kbwwbb',
        '.kbbwkbb',
        '.kbbbbbb',
        '.kbcbbbb',
        '.kbbbbkk',
        '..kbbbll',
        '...kbbbb',
        '...kbk.k',
        '...kk...',
      ],
    },
    DATADIL: {
      type: 'DATA',
      dex: 'Een kalme krokodil die spreadsheets in één hap doorslikt en nooit een getal vergeet.',
      palette: { g: '#3fae5a', v: '#c8f0a0' },
      half: [
        '........',
        '..k...k.',
        '.kgk.kgk',
        '.kgggggg',
        'kggggggg',
        'kgwwgggg',
        'kgwkgggg',
        'kggggggg',
        'kgcggggg',
        '.kgkkkkk',
        '.kgvvvvv',
        '..kvvvvv',
        '..kgvvvv',
        '..kgkkgk',
        '..kk..kk',
        '........',
      ],
    },
    PIXELFEE: {
      type: 'CREATIEF',
      dex: 'Een fladderende fee die met haar vleugels kleuren mengt. Ziet overal een logo in.',
      palette: { p: '#f06bb5', u: '#a8e6ff' },
      half: [
        '....k...',
        '...kpk..',
        '....kkkk',
        '...kpppp',
        'kk.kpppp',
        'kukkpwwp',
        'kuukpwkp',
        'kuuukppp',
        '.kuukcpp',
        '..kukppk',
        '...kkppp',
        '....kppp',
        '....kkpp',
        '.....kpk',
        '.....kk.',
        '........',
      ],
    },
    KLUISBEER: {
      type: 'BEVEILIGING',
      dex: 'Een stevige beer met een gouden penning. Niemand komt het dal in zonder zijn knikje.',
      palette: { s: '#9aa3b5', d: '#5b6478', v: '#e6dccb' },
      half: [
        '........',
        '..kkk...',
        '.kdddk..',
        '.kdsdkkk',
        '..ksssss',
        '.kssssss',
        '.kswwsss',
        '.kswksss',
        '.kssssss',
        '.ksssvvv',
        '.kcssvvk',
        '..kssvvv',
        '..kkkkkk',
        '..kdyddd',
        '..kddddk',
        '..kkkkk.',
      ],
    },
    PLANUIL: {
      type: 'STRATEGIE',
      dex: 'Een wijze uil met een kroontje. Denkt drie kwartalen vooruit en knippert zelden.',
      palette: { o: '#8b5a2b', t: '#e9c99a' },
      half: [
        '....k.ky',
        '....kyyy',
        '.kk.kkkk',
        '.kokoooo',
        '.koooooo',
        'kowwwooo',
        'kowkwooo',
        'kowwwooy',
        '.kooooky',
        '.kootttt',
        '.kottttt',
        '..kotttt',
        '..kootto',
        '...koooo',
        '...kkkkk',
        '....y.y.',
      ],
    },
    MOERBOT: {
      type: 'OPERATIONS',
      dex: 'Draagt altijd een bouwhelm. Repareert alles met één moersleutel en een glimlach.',
      palette: { a: '#f08a2c', h: '#ffe066' },
      half: [
        '........',
        '...kkkkk',
        '..khhhhh',
        '.khhhhhh',
        '.kkkkkkk',
        '.kaaaaaa',
        '.kawwaaa',
        '.kawkaaa',
        '.kaaaaaa',
        '.kcaaaaa',
        '.kaaakkk',
        '..kaaaaa',
        '.kkkaaaa',
        'kak.kaaa',
        '.k..kkak',
        '.....kk.',
      ],
    },
  };

  const BUG = {
    palette: { r: '#d63c3c', m: '#7b3fa0' },
    half: [
      '........',
      '...k....',
      '....k...',
      '.....kkk',
      '....krrr',
      '...krwwr',
      '...krwkr',
      '..kkrrrr',
      '.k.kmmmk',
      'k.kmmmmk',
      '..kmmmmk',
      '.kkmmmmk',
      'k.kmmmmk',
      '...kmmmk',
      '....kkkk',
      '........',
    ],
  };

  function build(def) {
    const pal = Object.assign({}, BASE, def.palette);
    const canvas = document.createElement('canvas');
    canvas.width = 16;
    canvas.height = 16;
    const ctx = canvas.getContext('2d');
    def.half.forEach((row, y) => {
      const full = row + row.split('').reverse().join('');
      for (let x = 0; x < 16; x++) {
        const ch = full[x];
        if (ch === '.' || !pal[ch]) continue;
        ctx.fillStyle = pal[ch];
        ctx.fillRect(x, y, 1, 1);
      }
    });
    return canvas;
  }

  const cache = {};
  function sprite(species) {
    if (!cache[species]) cache[species] = build(species === 'BUG' ? BUG : SPECIES[species]);
    return cache[species];
  }

  // Tekent een sprite in een (nieuw) canvas-element op een bepaalde schaal,
  // handig voor de lijsten en kaarten in de UI.
  function spriteCanvas(species, scale, flip) {
    const c = document.createElement('canvas');
    c.width = 16 * scale;
    c.height = 16 * scale;
    c.className = 'sprite';
    const ctx = c.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    if (flip) { ctx.translate(c.width, 0); ctx.scale(-1, 1); }
    ctx.drawImage(sprite(species), 0, 0, c.width, c.height);
    return c;
  }

  FC.sprites = { SPECIES, sprite, spriteCanvas };
})(window.FC);
