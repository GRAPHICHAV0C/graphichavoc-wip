(() => {
  'use strict';

  const root = document.querySelector('.home-002[data-homepage-variant="002"]');
  if (!root) return;

  const brandTab = root.querySelector('.brand-tab');
  const panel = root.querySelector('#home-002-contact-panel');
  const viewer = root.querySelector('#viewer');
  if (!brandTab || !panel || !viewer) return;

  let open = false;

  function setOpen(next) {
    open = Boolean(next);
    root.classList.toggle('is-contact-open', open);
    brandTab.setAttribute('aria-expanded', String(open));
    panel.setAttribute('aria-hidden', String(!open));
    panel.inert = !open;
  }

  brandTab.addEventListener('click', event => {
    event.preventDefault();
    setOpen(true);
  });

  const resumeMap = () => {
    if (open) setOpen(false);
  };

  viewer.addEventListener('pointerdown', resumeMap, { capture: true, passive: true });
  viewer.addEventListener('wheel', resumeMap, { capture: true, passive: true });
  viewer.addEventListener('touchstart', resumeMap, { capture: true, passive: true });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && open) {
      setOpen(false);
      brandTab.focus({ preventScroll: true });
      return;
    }

    if (open && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', '+', '-', '0', 'Home'].includes(event.key)) {
      const active = document.activeElement;
      if (panel.contains(active)) return;
      setOpen(false);
    }
  });

  setOpen(false);
})();
