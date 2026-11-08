/* Actualise le compteur existant sans enregistrer de nouvelle consultation. */
(() => {
  function init() {
    const counter = document.querySelector('[data-footer-counter]');
    if (!counter || counter.dataset.bound) return;
    counter.dataset.bound = 'true';
    const digits = counter.querySelector('.footer-counter-digits');
    if (!digits) return;
    let pending = false;

    function show(total) {
      if (!Number.isSafeInteger(total) || total < 0) return;
      const value = String(total).padStart(6, '0');
      if (digits.textContent.replace(/\s/g, '') !== value) {
        const fragment = document.createDocumentFragment();
        for (const digit of value) {
          const span = document.createElement('span');
          span.className = 'odometer-digit';
          span.dataset.digit = digit;
          span.setAttribute('aria-hidden', 'true');
          span.textContent = digit;
          fragment.appendChild(span);
        }
        digits.replaceChildren(fragment);
      }
      digits.setAttribute('aria-label', `${total.toLocaleString('fr-FR')} consultations au total`);
    }

    async function refresh() {
      if (pending || document.hidden) return;
      pending = true;
      try {
        const response = await fetch(counter.dataset.statsUrl, {
          credentials: 'same-origin', cache: 'no-store',
          headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!response.ok) return;
        const result = await response.json();
        if (result.success && result.data) show(result.data.total_consultations);
      } catch (_) {
        // La valeur rendue par Django reste visible si le réseau est indisponible.
      } finally {
        pending = false;
      }
    }

    refresh();
    window.setInterval(refresh, 60000);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) refresh();
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
