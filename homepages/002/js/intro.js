(() => {
  'use strict';
  const hint = document.getElementById('explore-hint');
  const editing = new URLSearchParams(window.location.search).get('edit') === '1';
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const opts = {
    zoomInFraction: 0.045,
    zoomDurationSeconds: 1.65,
    initialDelayMs: 180,
    tileFadeMs: 420,
    tileStaggerMaxMs: 650,
    hintInteractionDelayMs: 1500
  };
  let started = false;
  let interacted = false;
  let fadeTimeout = null;
  let introTimeouts = [];
  let masks = [];
  let activeViewer = null;

  function queue(fn, delay) {
    const id = window.setTimeout(fn, delay);
    introTimeouts.push(id);
    return id;
  }
  function removeMasks() {
    if (!activeViewer) return;
    for (const mask of masks) {
      try { activeViewer.removeOverlay(mask); } catch (_) {}
    }
    masks = [];
  }
  function cancelIntro() {
    if (!started) return;
    for (const id of introTimeouts) window.clearTimeout(id);
    introTimeouts = [];
    removeMasks();
    if (activeViewer && activeViewer.viewport) {
      activeViewer.viewport.centerSpringX.resetTo(activeViewer.viewport.getCenter(true).x);
      activeViewer.viewport.centerSpringY.resetTo(activeViewer.viewport.getCenter(true).y);
      activeViewer.viewport.zoomSpring.resetTo(activeViewer.viewport.getZoom(true));
    }
  }
  function onInteraction() {
    if (!interacted) {
      interacted = true;
      cancelIntro();
      fadeTimeout = window.setTimeout(() => hint.classList.add('is-hidden'), opts.hintInteractionDelayMs);
    }
  }
  function attachInputEvents(viewer) {
    // Listen at capture phase; OpenSeadragon may prevent bubbling during gestures.
    const el = viewer.element;
    el.addEventListener('pointerdown', onInteraction, {capture:true,passive:true});
    el.addEventListener('wheel', onInteraction, {capture:true,passive:true});
    el.addEventListener('touchstart', onInteraction, {capture:true,passive:true});
    document.addEventListener('keydown', e => {
      if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','+','-','0','Home'].includes(e.key)) onInteraction();
    }, {passive:true});
  }
  function beginIntro(e) {
    if (started) return;
    started = true;
    const {viewer, config, introEndZoom} = e.detail;
    activeViewer = viewer;
    attachInputEvents(viewer);
    if (editing) {
      hint.hidden = true;
      return;
    }
    if (reducedMotion) return;

    // Reveal in 4x4 blocks per permanent region. HTML masks float in map
    // coordinates, so they pan/zoom precisely with the WebP image tiles.
    // Random delays apply only on initial page load, never to later tile fetching.
    for (const region of config.regions) {
      for (let y = 0; y < 4; y++) {
        for (let x = 0; x < 4; x++) {
          const mask = document.createElement('div');
          mask.className = 'intro-tile-mask';
          mask.setAttribute('aria-hidden', 'true');
          viewer.addOverlay({
            element:mask,
            location:new OpenSeadragon.Rect(region.x+x/4,region.y+y/4,1/4,1/4),
            checkResize:false
          });
          masks.push(mask);
          const delay = 80 + Math.random()*opts.tileStaggerMaxMs;
          queue(() => { if(!interacted) mask.style.opacity = '0'; }, delay);
        }
      }
    }
    queue(removeMasks, opts.tileStaggerMaxMs+opts.tileFadeMs+350);

    // Settle on a height-fitted origin region, keeping the subtle zoom-in.
    // Other viewing/zoom bounds remain untouched.
    queue(() => {
      if (interacted) return;
      const vp=viewer.viewport;
      const priorTime = viewer.animationTime;
      viewer.animationTime = opts.zoomDurationSeconds;
      vp.zoomTo(introEndZoom, vp.getCenter(true), false);
      queue(() => { viewer.animationTime = priorTime; }, opts.zoomDurationSeconds*1000+100);
    }, opts.initialDelayMs);
  }
  window.addEventListener('map-ready', beginIntro);
})();
