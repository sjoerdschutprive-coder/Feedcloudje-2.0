// Opstarten: organisatie laden (of nieuw beginnen), wereld en UI koppelen
// en de spel-lus draaien.
(function (FC) {
  const org = new FC.Org();
  if (!org.load()) org.newGame();

  const world = new FC.World(document.getElementById('world'), org);
  const ui = new FC.UI(org, world);

  let last = performance.now();
  let uiAcc = 0;
  function frame(now) {
    const dt = (now - last) / 1000;
    last = now;
    org.update(dt);
    world.draw(org.paused ? 0 : dt);
    uiAcc += dt;
    if (uiAcc > 0.25) { uiAcc = 0; ui.render(); }
    requestAnimationFrame(frame);
  }
  ui.render();
  requestAnimationFrame(frame);

  window.addEventListener('beforeunload', () => org.save());
  // Handig voor debuggen in de console.
  FC.org = org;
})(window.FC);
