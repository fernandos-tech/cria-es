'use strict';
(() => {
  const root = document.documentElement;
  const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const toggle = document.getElementById('motionToggle');
  const visual = document.getElementById('heroVisual');
  const hero = document.getElementById('hero');
  let stored = null;
  let frame = 0;
  try { stored = localStorage.getItem('cria-motion-paused'); } catch { /* Optional preferences. */ }
  let paused = stored === null ? preference.matches : stored === 'true';
  function applyMotion() {
    // A system accessibility preference always takes precedence.
    const reduced = paused || preference.matches;
    root.dataset.motion = reduced ? 'paused' : 'full';
    toggle.setAttribute('aria-pressed', String(reduced));
    document.getElementById('motionToggleText').textContent = reduced ? 'Animações pausadas' : 'Pausar animações';
    toggle.title = preference.matches ? 'Movimento reduzido ativado nas preferências do seu dispositivo.' : 'Controlar animações da interface';
    if (reduced) {
      resetPointer();
      visual.getAnimations().forEach(animation => animation.cancel());
    }
  }
  function resetPointer() {
    cancelAnimationFrame(frame);
    hero.style.removeProperty('--pointer-x'); hero.style.removeProperty('--pointer-y');
    visual.style.removeProperty('--tilt-x'); visual.style.removeProperty('--tilt-y');
  }
  toggle.addEventListener('click', () => {
    paused = preference.matches || !paused;
    try { localStorage.setItem('cria-motion-paused', String(paused)); } catch { /* Optional preferences. */ }
    applyMotion();
  });
  preference.addEventListener('change', applyMotion);
  document.querySelectorAll('.motion-option').forEach(button => button.addEventListener('click', () => {
    const look = button.dataset.look;
    visual.dataset.look = look;
    document.querySelectorAll('.motion-option').forEach(option => {
      const selected = option === button;
      option.classList.toggle('selected', selected);
      option.setAttribute('aria-pressed', String(selected));
    });
    document.getElementById('motionAnnouncement').textContent = `Motion ${button.querySelector('span:nth-child(2)').textContent.trim()} selecionado.`;
    if (root.dataset.motion !== 'paused' && typeof visual.animate === 'function') {
      visual.animate([{ opacity: .5, filter: 'blur(5px)' }, { opacity: 1, filter: 'blur(0)' }], { duration: 450, easing: 'cubic-bezier(.16,1,.3,1)' });
    }
  }));
  hero.addEventListener('pointermove', event => {
    if (event.pointerType !== 'mouse' || root.dataset.motion === 'paused') return;
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const rect = hero.getBoundingClientRect();
      const x = (event.clientX-rect.left)/rect.width;
      const y = (event.clientY-rect.top)/rect.height;
      hero.style.setProperty('--pointer-x', `${x*100}%`);
      hero.style.setProperty('--pointer-y', `${y*100}%`);
      visual.style.setProperty('--tilt-x', `${(0.5-y)*5}deg`);
      visual.style.setProperty('--tilt-y', `${(x-0.5)*6}deg`);
    });
  });
  hero.addEventListener('pointerleave', resetPointer);
  document.addEventListener('visibilitychange', () => {
    root.classList.toggle('tab-hidden', document.hidden);
    if (document.hidden) resetPointer();
  });
  // One reveal per section; unsupported browsers simply show all content.
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add('in-view'); observer.unobserve(entry.target);
      }
    }, { threshold: .08 });
    document.querySelectorAll('.panel, .exports-section').forEach(node => {
      node.classList.add('motion-reveal'); observer.observe(node);
    });
  }
  applyMotion();
})();
