/* Liens de recherche vers l'accueil depuis les pages internes. */
(() => {
  'use strict';
  document.addEventListener('click', (event) => {
    const link = event.target.closest?.('a');
    if (!link || link.hasAttribute('data-lang-choice')) return;
    const href = link.getAttribute('href');
    if (!href || href === '#') return;
    const home = document.body.dataset.homeUrl || '/';
    if (href === '#organigramme') {
      link.setAttribute('href', document.body.dataset.organigrammeUrl || '/organigramme.html');
    } else if (href.startsWith('#') && !document.getElementById(href.slice(1))) {
      link.setAttribute('href', home + href);
    } else if (/^(?![a-z]+:|\/|#).*\.(html|php)(?:[?#]|$)/i.test(href)) {
      link.href = new URL(href, new URL(home, location.origin)).href;
    }
  }, true);
})();
