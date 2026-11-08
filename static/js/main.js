/**
 * EST Fquih Ben Salah - Script Principal & Animations
 * Université Sultan Moulay Slimane
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Initialisation Dark / Light Mode
  initThemeToggle();

  // 2. Gestion du Menu Mobile
  initMobileMenu();

  // 3. Slider Bannière Hero
  initHeroSlider();

  // 4. Compteurs Animés (Stats)
  initCounterAnimation();

  // 5. Révélations au Défilement (Scroll Reveal)
  initScrollReveal();

  // 6. Filtrage des Formations & Modale de Détails
  initFormations();

  // 7. Galerie Photos & Lightbox
  initGallery();

  // 8. E-Services Simulateur de Demande & MySQL
  initEServices();

  // 8b. Formulaire de Contact MySQL
  initContactForm();

  // 9. Modale Mot du Directeur
  initDirectorModal();

  // 10. Bouton Retour en Haut avec Progression Circulaire
  initScrollTopProgress();

  // 11. Assistant Virtuel IA (EST-Bot)
  initChatbot();

  // 12. Recherche Globale (Ctrl + K)
  initGlobalSearch();
});

/* ==========================================================================
   1. Theme Toggle (Dark / Light)
   ========================================================================== */
function initThemeToggle() {
  const themeToggleBtns = document.querySelectorAll('.theme-toggle-btn');
  const html = document.documentElement;

  // Récupérer la préférence stockée ou celle du système
  const savedTheme = localStorage.getItem('estfbs-theme');
  if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    html.classList.add('dark');
  } else {
    html.classList.remove('dark');
  }

  themeToggleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      if (html.classList.contains('dark')) {
        html.classList.remove('dark');
        localStorage.setItem('estfbs-theme', 'light');
      } else {
        html.classList.add('dark');
        localStorage.setItem('estfbs-theme', 'dark');
      }
    });
  });
}

/* ==========================================================================
   2. Menu Mobile
   ========================================================================== */
function initMobileMenu() {
  const toggleBtn = document.getElementById('mobile-menu-toggle');
  const closeBtn = document.getElementById('mobile-menu-close');
  const mobileMenu = document.getElementById('mobile-menu-drawer');
  const backdrop = document.getElementById('mobile-menu-backdrop');
  if (!toggleBtn || !closeBtn || !mobileMenu || !backdrop) return;

  const desktop = window.matchMedia('(min-width: 1280px)');
  let isOpen = false;
  let previousOverflow = '';

  function openMenu() {
    if (isOpen || desktop.matches) return;
    isOpen = true;
    previousOverflow = document.body.style.overflow;
    mobileMenu.inert = false;
    mobileMenu.dataset.menuState = 'open';
    mobileMenu.setAttribute('aria-hidden', 'false');
    toggleBtn.setAttribute('aria-expanded', 'true');
    mobileMenu.classList.remove('translate-x-full');
    backdrop.classList.remove('opacity-0', 'pointer-events-none');
    document.body.style.overflow = 'hidden';
    closeBtn.focus({ preventScroll: true });
  }

  function closeMenu(restoreFocus = true) {
    if (!isOpen) return;
    isOpen = false;
    // Déplacer le focus avant de masquer le panneau aux lecteurs d’écran.
    if (mobileMenu.contains(document.activeElement)) {
      if (restoreFocus && !desktop.matches) {
        toggleBtn.focus({ preventScroll: true });
      } else {
        document.activeElement.blur();
      }
    }
    mobileMenu.inert = true;
    mobileMenu.dataset.menuState = 'closed';
    mobileMenu.setAttribute('aria-hidden', 'true');
    toggleBtn.setAttribute('aria-expanded', 'false');
    mobileMenu.classList.add('translate-x-full');
    backdrop.classList.add('opacity-0', 'pointer-events-none');
    document.body.style.overflow = previousOverflow;
  }

  window.closeMobileMenu = closeMenu;
  toggleBtn.addEventListener('click', openMenu);
  closeBtn.addEventListener('click', () => closeMenu());
  backdrop.addEventListener('click', () => closeMenu());

  mobileMenu.querySelectorAll('a[href]').forEach(link => {
    link.addEventListener('click', () => closeMenu(false));
  });
  document.querySelectorAll('.search-trigger-btn').forEach(btn => {
    btn.addEventListener('click', () => closeMenu(false));
  });

  document.addEventListener('keydown', event => {
    if (!isOpen) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      closeMenu();
    } else if (event.key === 'Tab') {
      const focusable = Array.from(mobileMenu.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]'
      )).filter(element => element.getClientRects().length > 0);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first) {
        event.preventDefault();
        mobileMenu.focus();
      } else if (event.shiftKey && (document.activeElement === first || document.activeElement === mobileMenu)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });

  document.querySelectorAll('.mobile-dropdown-toggle').forEach(btn => {
    const targetId = btn.getAttribute('data-target');
    const submenu = document.getElementById(targetId);
    if (!submenu) return;
    const chevron = btn.querySelector('.mobile-chevron');
    btn.setAttribute('aria-controls', targetId);
    btn.setAttribute('aria-expanded', String(!submenu.classList.contains('hidden')));
    btn.addEventListener('click', () => {
      const expanded = submenu.classList.contains('hidden');
      submenu.classList.toggle('hidden', !expanded);
      btn.setAttribute('aria-expanded', String(expanded));
      if (chevron) chevron.classList.toggle('rotate-180', expanded);
    });
  });

  const onDesktopChange = event => {
    if (event.matches) closeMenu(false);
  };
  if (desktop.addEventListener) desktop.addEventListener('change', onDesktopChange);
  else desktop.addListener(onDesktopChange);
}

/* ==========================================================================
   3. Hero Background Slider
   ========================================================================== */
function initHeroSlider() {
  const slides = document.querySelectorAll('.hero-slide');
  const dotsContainer = document.getElementById('hero-dots');
  if (!slides.length) return;

  let currentIndex = 0;
  let interval;

  // Création des puces (dots)
  if (dotsContainer) {
    dotsContainer.innerHTML = '';
    slides.forEach((_, idx) => {
      const dot = document.createElement('button');
      dot.className = `w-3 h-3 rounded-full transition-all duration-300 ${idx === 0 ? 'bg-amber-400 w-8' : 'bg-white/50 hover:bg-white'}`;
      dot.setAttribute('aria-label', `Slide ${idx + 1}`);
      dot.addEventListener('click', () => {
        goToSlide(idx);
        resetAutoSlide();
      });
      dotsContainer.appendChild(dot);
    });
  }

  function updateDots() {
    if (!dotsContainer) return;
    const dots = dotsContainer.children;
    Array.from(dots).forEach((dot, idx) => {
      if (idx === currentIndex) {
        dot.className = 'w-8 h-3 rounded-full bg-amber-400 transition-all duration-300';
      } else {
        dot.className = 'w-3 h-3 rounded-full bg-white/50 hover:bg-white transition-all duration-300';
      }
    });
  }

  function goToSlide(index) {
    slides[currentIndex].classList.remove('active');
    currentIndex = (index + slides.length) % slides.length;
    slides[currentIndex].classList.add('active');
    updateDots();
  }

  function nextSlide() {
    goToSlide(currentIndex + 1);
  }

  function resetAutoSlide() {
    clearInterval(interval);
    interval = setInterval(nextSlide, 6500);
  }

  interval = setInterval(nextSlide, 6500);
}

/* ==========================================================================
   4. Compteurs Chiffres Clés (Affichage Direct Sans Animation)
   ========================================================================== */
function initCounterAnimation() {
  const counters = document.querySelectorAll('.stat-counter');
  counters.forEach(counter => {
    const target = +counter.getAttribute('data-target') || 0;
    counter.textContent = target.toLocaleString('fr-FR');
  });
}
/* ==========================================================================
   5. Révélations au Défilement (Désactivées - Rendu Instantané)
   ========================================================================== */
function initScrollReveal() {
  const reveals = document.querySelectorAll('.reveal-on-scroll');
  reveals.forEach(el => {
    el.classList.add('revealed');
    el.style.opacity = '1';
    el.style.transform = 'none';
    el.style.transition = 'none';
  });
}
/* ==========================================================================
   6. Formations : Filtrage et Modale Détail
   ========================================================================== */
const FORMATIONS_DATA = {
  'dut-gi': {
    title: 'DUT Génie Informatique (GI)',
    category: 'DUT (Bac+2)',
    badge: 'Filière d\'excellence',
    icon: 'fa-laptop-code',
    duration: '2 ans (4 semestres)',
    diplome: 'Diplôme Universitaire de Technologie',
    description: 'Formation technologique pointue orientée développement logiciel, architecture réseau, bases de données relationnelles & NoSQL, sécurité informatique et technologies web modernes.',
    debouches: [
      'Développeur Full-Stack (Web & Mobile)',
      'Administrateur Systèmes & Réseaux',
      'Intégrateur de solutions Cloud',
      'Poursuite d\'études en Cycle d\'Ingénieur (ENSA, ENSIAS, etc.) ou Licences Professionnelles'
    ],
    modules: ['Algorithmique & C/C++', 'Développement Web (React, Node, PHP)', 'Bases de Données (Oracle, MySQL)', 'Réseaux & Protocoles Cisco', 'Génie Logiciel & UML', 'Systèmes Linux & DevOps']
  },
  'dut-gc': {
    title: 'DUT Génie Civil (GC)',
    category: 'DUT (Bac+2)',
    badge: 'BTP & Construction',
    icon: 'fa-hard-hat',
    duration: '2 ans (4 semestres)',
    diplome: 'Diplôme Universitaire de Technologie',
    description: 'Apprentissage des techniques de construction de bâtiments, des ouvrages d\'art, de la mécanique des sols, de la topographie et de la gestion de chantiers respectueux de l\'environnement.',
    debouches: [
      'Conducteur de travaux & Chef de chantier',
      'Technicien en bureau d\'études BTP',
      'Responsable contrôle qualité et métré',
      'Poursuite en Écoles d\'Ingénieurs (EHTP, EMI, ENSA) ou Master Pro'
    ],
    modules: ['Résistance des Matériaux (RDM)', 'Béton Armé & Calcul de structures', 'Topographie & SIG', 'Dessin Assisté par Ordinateur (AutoCAD/BIM)', 'Mécanique des Sols', 'Gestion de Marchés BTP']
  },
  'dut-iaa': {
    title: 'DUT Industries Agroalimentaires (IAA)',
    category: 'DUT (Bac+2)',
    badge: 'Industrie & Qualité',
    icon: 'fa-seedling',
    duration: '2 ans (4 semestres)',
    diplome: 'Diplôme Universitaire de Technologie',
    description: 'Expertise dans les procédés de transformation des produits agricoles, la sécurité sanitaire des aliments, la biochimie et le management de la qualité industrielle dans la région clé de Tadla-Azilal.',
    debouches: [
      'Technicien supérieur de contrôle qualité (HACCP/ISO)',
      'Responsable de ligne de production agro-industrielle',
      'Technicien en laboratoire d\'analyses microbiologiques',
      'Poursuite en Écoles d\'Ingénieurs Agronomes (IAV, ENAM) ou Licences'
    ],
    modules: ['Microbiologie Alimentaire', 'Procédés de Conservation & Emballage', 'Normes ISO 22000 & HACCP', 'Biochimie & Chimie Analytique', 'Maintenance Industrielle', 'Gestion de la Chaîne du Froid']
  },
  'dut-gb': {
    title: 'DUT Génie Biologique (GB)',
    category: 'DUT (Bac+2)',
    badge: 'Biotechnologies',
    icon: 'fa-dna',
    duration: '2 ans (4 semestres)',
    diplome: 'Diplôme Universitaire de Technologie',
    description: 'Préparation aux techniques d\'analyses biologiques, médicales, environnementales et aux biotechnologies végétales et animales.',
    debouches: [
      'Technicien d\'analyses médicales et pharmaceutiques',
      'Technicien en laboratoire de biotechnologie végétale',
      'Contrôleur environnement et traitement des eaux'
    ],
    modules: ['Biologie Moléculaire', 'Immunologie & Hématologie', 'Biochimie Clinique', 'Écologie & Dépollution', 'Bio-informatique']
  },
  'dut-chimie': {
    title: 'DUT Chimie & Techniques d\'Analyses',
    category: 'DUT (Bac+2)',
    badge: 'Analyses & Environnement',
    icon: 'fa-flask-vial',
    duration: '2 ans (4 semestres)',
    diplome: 'Diplôme Universitaire de Technologie',
    description: 'Formation complète sur les techniques spectroscopiques, chromatographiques et physico-chimiques appliquées aux secteurs minier, agricole et pharmaceutique.',
    debouches: [
      'Technicien chimiste en laboratoire de recherche/contrôle',
      'Analyste dans l\'industrie minière et chimique (OCP)',
      'Technicien environnement et traitement physico-chimique'
    ],
    modules: ['Chromatographie (HPLC, CPG)', 'Spectroscopie (UV, IR, RMN)', 'Chimie Minérale & Organique', 'Traitement des Effluents', 'Sécurité Chimique']
  },
  'lp-bigdata': {
    title: 'Bachelor Big Data & Intelligence Artificielle',
    category: 'Licence Pro / Bachelor (Bac+3)',
    badge: 'Numérique & IA',
    icon: 'fa-brain',
    duration: '1 an (après Bac+2) / 3 ans',
    diplome: 'Licence Professionnelle / Bachelor Universitaire',
    description: 'Formation d\'avant-garde visant à maîtriser le traitement massif de données (Hadoop, Spark), le Machine Learning, le Deep Learning et la Data Visualisation pour les entreprises.',
    debouches: [
      'Data Analyst / Data Engineer junior',
      'Développeur solutions IA & Automatisation',
      'Consultant Business Intelligence',
      'Poursuite en Master Spécialisé ou Doctorat'
    ],
    modules: ['Python pour la Data Science', 'Machine Learning & Scikit-Learn', 'Écosystème Hadoop & Spark', 'Cloud Computing (AWS/GCP)', 'Deep Learning & Vision par Ordinateur', 'PowerBI & Tableau']
  },
  'lp-gc': {
    title: 'Bachelor Génie Civil & Efficacité Énergétique',
    category: 'Licence Pro / Bachelor (Bac+3)',
    badge: 'Éco-Construction',
    icon: 'fa-building-columns',
    duration: '1 an (après Bac+2)',
    diplome: 'Licence Professionnelle',
    description: 'Perfectionnement sur le BIM (Building Information Modeling), les énergies renouvelables intégrées au bâti et la gestion avancée des projets de génie civil.',
    debouches: [
      'Coordinateur BIM',
      'Ingénieur d\'application BTP',
      'Auditeur énergétique des bâtiments',
      'Chef de projet éco-construction'
    ],
    modules: ['Modélisation BIM & Revit', 'Audit Énergétique & RE2020', 'Structures Mixtes & Géotechnique Avancée', 'Gestion Économique de Projet']
  },
  'formation-continue': {
    title: 'Programmes de Formation Continue & Certifications',
    category: 'Formation Continue',
    badge: 'Professionnels & Cadres',
    icon: 'fa-user-tie',
    duration: 'Modules courts / Cours du week-end',
    diplome: 'Certificats Universitaires d\'Excellence USMS',
    description: 'Modules qualifiants conçus pour les cadres, techniciens et professionnels en exercice désirant actualiser leurs compétences en IA, management de la qualité, sécurité industrielle et gestion de l\'eau.',
    debouches: [
      'Montée en compétences interne',
      'Reconversion professionnelle',
      'Certification officielle USMS'
    ],
    modules: ['Transformation Digitale', 'Management QHSE', 'Gestion des Eaux et Énergies Vertes', 'Sécurité des Systèmes d\'Information']
  }
};

function initFormations() {
  const filterBtns = document.querySelectorAll('.formation-filter-btn');
  const cards = document.querySelectorAll('.formation-card');
  const detailModal = document.getElementById('formation-detail-modal');
  const closeModalBtn = document.getElementById('close-formation-modal');

  // Filtrage
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active', 'bg-slate-900', 'text-white'));
      btn.classList.add('active', 'bg-slate-900', 'text-white');

      const filter = btn.getAttribute('data-filter');

      cards.forEach(card => {
        const cat = card.getAttribute('data-category');
        if (filter === 'all' || cat === filter) {
          card.style.display = 'block';
          setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
          }, 50);
        } else {
          card.style.opacity = '0';
          card.style.transform = 'translateY(20px)';
          setTimeout(() => {
            card.style.display = 'none';
          }, 250);
        }
      });
    });
  });

  // Ouverture Modale Détail
  document.querySelectorAll('.open-formation-detail').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const formationId = btn.getAttribute('data-id');
      const data = FORMATIONS_DATA[formationId];
      if (!data) return;

      document.getElementById('modal-formation-title').textContent = data.title;
      document.getElementById('modal-formation-badge').textContent = data.badge;
      document.getElementById('modal-formation-duration').textContent = data.duration;
      document.getElementById('modal-formation-diplome').textContent = data.diplome;
      document.getElementById('modal-formation-desc').textContent = data.description;

      const debouchesList = document.getElementById('modal-formation-debouches');
      debouchesList.innerHTML = data.debouches.map(item => `<li class="flex items-start gap-2"><i class="fas fa-check-circle text-emerald-500 mt-1"></i><span>${item}</span></li>`).join('');

      const modulesList = document.getElementById('modal-formation-modules');
      modulesList.innerHTML = data.modules.map(item => `<span class="bg-amber-50 dark:bg-slate-700 text-slate-900 dark:text-slate-200 text-xs font-semibold px-3 py-1.5 rounded-full border border-amber-200 dark:border-slate-600">${item}</span>`).join('');

      detailModal.classList.remove('hidden');
      detailModal.classList.add('flex');
      document.body.style.overflow = 'hidden';
    });
  });

  if (closeModalBtn) {
    closeModalBtn.addEventListener('click', () => {
      detailModal.classList.add('hidden');
      detailModal.classList.remove('flex');
      document.body.style.overflow = '';
    });
  }

  if (detailModal) {
    detailModal.addEventListener('click', (e) => {
      if (e.target === detailModal) {
        detailModal.classList.add('hidden');
        detailModal.classList.remove('flex');
        document.body.style.overflow = '';
      }
    });
  }
}

/* ==========================================================================
   7. Galerie Photos & Visionneuse Lightbox
   ========================================================================== */
function initGallery() {
  const filterBtns = document.querySelectorAll('.gallery-filter-btn');
  const items = document.querySelectorAll('.gallery-item');
  const lightbox = document.getElementById('gallery-lightbox');
  const lightboxImg = document.getElementById('lightbox-image');
  const lightboxCaption = document.getElementById('lightbox-caption');
  const closeBtn = document.getElementById('lightbox-close');
  const prevBtn = document.getElementById('lightbox-prev');
  const nextBtn = document.getElementById('lightbox-next');

  let currentGalleryList = [];
  let currentIdx = 0;

  // Filtrage
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active', 'bg-slate-900', 'text-white'));
      btn.classList.add('active', 'bg-slate-900', 'text-white');

      const filter = btn.getAttribute('data-filter');

      items.forEach(item => {
        const cat = item.getAttribute('data-category');
        if (filter === 'all' || cat === filter) {
          item.style.display = 'block';
          item.classList.add('scale-100', 'opacity-100');
        } else {
          item.style.display = 'none';
        }
      });
    });
  });

  function updateGalleryList() {
    currentGalleryList = Array.from(document.querySelectorAll('.gallery-item')).filter(el => el.style.display !== 'none');
  }

  function showLightboxIndex(idx) {
    if (!currentGalleryList.length) return;
    currentIdx = (idx + currentGalleryList.length) % currentGalleryList.length;
    const item = currentGalleryList[currentIdx];
    const img = item.querySelector('img');
    const caption = item.getAttribute('data-caption') || img.getAttribute('alt') || 'EST Fquih Ben Salah';

    lightboxImg.src = img.src;
    lightboxCaption.textContent = caption;
    lightbox.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  items.forEach(item => {
    item.addEventListener('click', () => {
      updateGalleryList();
      const index = currentGalleryList.indexOf(item);
      showLightboxIndex(index !== -1 ? index : 0);
    });
  });

  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      lightbox.classList.remove('active');
      document.body.style.overflow = '';
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      showLightboxIndex(currentIdx - 1);
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      showLightboxIndex(currentIdx + 1);
    });
  }

  if (lightbox) {
    lightbox.addEventListener('click', (e) => {
      if (e.target === lightbox || e.target.classList.contains('lightbox-backdrop')) {
        lightbox.classList.remove('active');
        document.body.style.overflow = '';
      }
    });
  }

  document.addEventListener('keydown', (e) => {
    if (!lightbox || !lightbox.classList.contains('active')) return;
    if (e.key === 'Escape') {
      lightbox.classList.remove('active');
      document.body.style.overflow = '';
    } else if (e.key === 'ArrowLeft') {
      showLightboxIndex(currentIdx - 1);
    } else if (e.key === 'ArrowRight') {
      showLightboxIndex(currentIdx + 1);
    }
  });
}

/* ==========================================================================
   8. E-Services Demandes & Sauvegarde dans la Base de Données MySQL (PHP)
   ========================================================================== */
function initEServices() {
  const form = document.getElementById('form-eservice-etudiant');
  const modal = document.getElementById('eservice-success-modal');
  const closeBtn = document.getElementById('close-eservice-modal');

  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const submitBtn = form.querySelector('button[type="submit"]');
    const originalBtnContent = submitBtn ? submitBtn.innerHTML : '';
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Enregistrement en cours…';
    }

    const nom = form.querySelector('[name="nom"]').value.trim();
    const cne = form.querySelector('[name="cne"]').value.trim();
    const cin = form.querySelector('[name="cin"]').value.trim();
    const filiere = form.querySelector('[name="filiere"]').value;
    const doc = form.querySelector('[name="document"]').value;
    const email = form.querySelector('[name="email"]').value.trim();

    let refNumber = null;
    let dateNow = new Date().toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' });

    try {
      const response = await fetch('/backend/api/submit_etudiant.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nom, cne, cin, filiere, document: doc, email })
      });

      const resData = await response.json();
      if (!response.ok || !resData.success || !resData.data) throw new Error(resData.message || 'Enregistrement impossible.');
      if (resData.success && resData.data) {
        refNumber = resData.data.code_suivi;
      }
    } catch (err) {
      alert(err.message || 'La demande n’a pas été enregistrée. Réessayez.');
      return;
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnContent;
      }
    }

    document.getElementById('eservice-receipt-ref').textContent = refNumber;
    document.getElementById('eservice-receipt-name').textContent = nom;
    document.getElementById('eservice-receipt-cne').textContent = cne;
    document.getElementById('eservice-receipt-filiere').textContent = filiere;
    document.getElementById('eservice-receipt-doc').textContent = doc;
    document.getElementById('eservice-receipt-date').textContent = dateNow;

    const trackBtn = document.getElementById('eservice-receipt-track-btn');
    if (trackBtn) {
      trackBtn.href = `suivi.php?code=${encodeURIComponent(refNumber)}`;
    }

    if (modal) {
      modal.classList.remove('hidden');
      modal.classList.add('flex');
    }

    form.reset();
  });

  if (closeBtn && modal) {
    closeBtn.addEventListener('click', () => {
      modal.classList.add('hidden');
      modal.classList.remove('flex');
    });
  }
}

/* ==========================================================================
   Formulaire de contact avec contrôle du numéro Apogée par Django
   ========================================================================== */
function initContactForm() {
  const form = document.getElementById('form-contact');
  const statusMsg = document.getElementById('contact-status-msg');
  const submitBtn = document.getElementById('btn-submit-contact');

  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const originalBtn = submitBtn ? submitBtn.innerHTML : '';
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Envoi du message...';
    }

    const apogee = form.querySelector('[name="apogee"]').value.trim();
    const nom = form.querySelector('[name="nom"]').value.trim();
    const email = form.querySelector('[name="email"]').value.trim();
    const sujet = form.querySelector('[name="sujet"]').value.trim();
    const message = form.querySelector('[name="message"]').value.trim();

    try {
      const res = await fetch('/backend/api/submit_contact.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nom, email, apogee, sujet, message })
      });

      const data = await res.json();
      if (statusMsg) {
        statusMsg.classList.remove('hidden');
        if (data.success) {
          statusMsg.className = 'p-3 rounded-xl text-xs bg-emerald-100 text-emerald-800 border border-emerald-300';
          statusMsg.textContent = data.message;
          form.reset();
        } else {
          statusMsg.className = 'p-3 rounded-xl text-xs bg-red-100 text-red-800 border border-red-300';
          statusMsg.textContent = Object.values(data.errors || {}).flat().map(error => error.message || error).join(' ') || data.message || 'Erreur lors de l’envoi.';
          if (data.errors && data.errors.apogee) form.querySelector('[name="apogee"]').focus();
        }
      }
    } catch (err) {
      if (statusMsg) {
        statusMsg.classList.remove('hidden');
        statusMsg.className = 'p-3 rounded-xl text-xs bg-red-100 text-red-800 border border-red-300';
        statusMsg.textContent = 'Le message n’a pas pu être enregistré. Vérifiez votre connexion et réessayez.';
      }
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtn;
      }
    }
  });
}

/* ==========================================================================
   9. Modale Mot du Directeur
   ========================================================================== */
function initDirectorModal() {
  const openBtns = document.querySelectorAll('#open-director-speech, .open-director-modal-btn');
  const modal = document.getElementById('director-speech-modal');
  const closeBtn = document.getElementById('close-director-modal');

  if (!modal) return;

  openBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      modal.classList.remove('hidden');
      modal.classList.add('flex');
      document.body.style.overflow = 'hidden';
    });
  });

  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      modal.classList.add('hidden');
      modal.classList.remove('flex');
      document.body.style.overflow = '';
    });
  }

  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.classList.add('hidden');
      modal.classList.remove('flex');
      document.body.style.overflow = '';
    }
  });
}

/* ==========================================================================
   10. Bouton Retour en Haut avec Progression Circulaire
   ========================================================================== */
function initScrollTopProgress() {
  const btn = document.getElementById('back-to-top');
  const circle = document.getElementById('progress-circle');
  if (!btn || !circle) return;

  const radius = circle.r.baseVal.value;
  const circumference = 2 * Math.PI * radius;
  circle.style.strokeDasharray = `${circumference} ${circumference}`;
  circle.style.strokeDashoffset = circumference;

  function updateProgress() {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = docHeight > 0 ? scrollTop / docHeight : 0;
    const offset = circumference - (progress * circumference);
    circle.style.strokeDashoffset = offset;

    if (scrollTop > 400) {
      btn.classList.remove('opacity-0', 'pointer-events-none');
      btn.classList.add('opacity-100');
    } else {
      btn.classList.add('opacity-0', 'pointer-events-none');
      btn.classList.remove('opacity-100');
    }
  }

  window.addEventListener('scroll', updateProgress);
  btn.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
}

/* ==========================================================================
   11. Assistant Virtuel IA (EST-Bot)
   ========================================================================== */
function initChatbot() {
  const triggerBtn = document.getElementById('chatbot-toggle-btn');
  const windowEl = document.getElementById('chatbot-window');
  const closeBtn = document.getElementById('close-chatbot');
  const form = document.getElementById('chatbot-form');
  const input = document.getElementById('chatbot-input');
  const messagesList = document.getElementById('chatbot-messages');

  if (!triggerBtn || !windowEl) return;

  triggerBtn.addEventListener('click', () => {
    windowEl.classList.toggle('hidden-chat');
    windowEl.classList.toggle('visible-chat');
    if (windowEl.classList.contains('visible-chat') && input) {
      input.focus();
    }
  });

  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      windowEl.classList.add('hidden-chat');
      windowEl.classList.remove('visible-chat');
    });
  }

  // Chips questions rapides
  document.querySelectorAll('.chatbot-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.getAttribute('data-question');
      appendUserMessage(q);
      handleBotAnswer(q);
    });
  });

  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const val = input.value.trim();
      if (!val) return;
      appendUserMessage(val);
      input.value = '';
      handleBotAnswer(val);
    });
  }

  function appendUserMessage(text) {
    const el = document.createElement('div');
    el.className = 'flex justify-end mb-3';
    el.innerHTML = `
      <div class="bg-slate-900 text-white text-xs px-4 py-2.5 rounded-2xl rounded-tr-none max-w-[80%] shadow">
        ${escapeHtml(text)}
      </div>
    `;
    messagesList.appendChild(el);
    messagesList.scrollTop = messagesList.scrollHeight;
  }

  function appendBotMessage(html) {
    const typing = document.createElement('div');
    typing.className = 'flex items-start gap-2 mb-3';
    typing.innerHTML = `
      <div class="w-7 h-7 rounded-full bg-amber-500 text-slate-950 flex items-center justify-center text-xs font-bold shrink-0">
        <i class="fas fa-robot"></i>
      </div>
      <div class="bg-slate-100 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-xs px-4 py-2.5 rounded-2xl rounded-tl-none max-w-[85%] shadow-sm">
        <div class="flex items-center gap-1.5 py-1">
          <span class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"></span>
          <span class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
          <span class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:0.4s]"></span>
        </div>
      </div>
    `;
    messagesList.appendChild(typing);
    messagesList.scrollTop = messagesList.scrollHeight;

    setTimeout(() => {
      typing.remove();
      const msg = document.createElement('div');
      msg.className = 'flex items-start gap-2 mb-3';
      msg.innerHTML = `
        <div class="w-7 h-7 rounded-full bg-amber-500 text-slate-950 flex items-center justify-center text-xs font-bold shrink-0">
          <i class="fas fa-robot"></i>
        </div>
        <div class="bg-slate-100 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-xs px-4 py-2.5 rounded-2xl rounded-tl-none max-w-[85%] shadow-sm leading-relaxed">
          ${html}
        </div>
      `;
      messagesList.appendChild(msg);
      messagesList.scrollTop = messagesList.scrollHeight;
    }, 600);
  }

  function handleBotAnswer(q) {
    const query = q.toLowerCase();
    let reply = '';

    if (query.includes('dut') || query.includes('filiere') || query.includes('filières') || query.includes('formation')) {
      reply = `L'EST de Fquih Ben Salah propose plusieurs filières d'excellence :<br><br>
      • <strong>DUT Génie Informatique (GI)</strong><br>
      • <strong>DUT Génie Civil (GC)</strong><br>
      • <strong>DUT Industries Agroalimentaires (IAA)</strong><br>
      • <strong>DUT Génie Biologique (GB)</strong><br>
      • <strong>DUT Chimie & Techniques d'Analyses</strong><br>
      • <strong>Bachelor Big Data & IA</strong><br>
      • <strong>Bachelor Génie Civil</strong><br><br>
      Consultez le volet <a href="#formations" class="text-amber-600 dark:text-amber-400 font-bold underline">Formations</a> pour les détails.`;
    } else if (query.includes('emploi') || query.includes('temps') || query.includes('horaire')) {
      reply = `Les emplois du temps des filières DUT et Licences Pro sont consultables et téléchargeables en ligne :<br><br>
      Consultez la page <a href="${document.body.dataset.emploisUrl || '/emplois-du-temps'}" class="text-amber-600 dark:text-amber-400 font-bold underline">Emplois du temps</a>.`;
    } else if (query.includes('elogha') || query.includes('langue')) {
      reply = `La plateforme nationale <strong>ELOGHA-SUP</strong> (Français, Anglais, Espagnol) est accessible aux étudiants avec leur e-mail institutionnel <code class="text-orange-600">@usms.ac.ma</code>.<br><br>
      Consultez la sous-section <a href="#elogha" class="text-amber-600 dark:text-amber-400 font-bold underline">Elogha</a> pour voir les tutoriels vidéos et liens de connexion.`;
    } else if (query.includes('certification') || query.includes('certif') || query.includes('coursera') || query.includes('cisco')) {
      reply = `L'EST-FBS offre un accès gratuit à +4 000 cours certifiants sur <strong>Coursera for Campus</strong>, ainsi qu'aux certifications Cisco CCNA, Python PCAP, AWS Cloud et normes industrielles.<br><br>
      Détails dans la sous-section <a href="#certification" class="text-amber-600 dark:text-amber-400 font-bold underline">Certification</a>.`;
    } else if (query.includes('ecoute') || query.includes('écoute') || query.includes('psycholog') || query.includes('stress')) {
      reply = `La <strong>Cellule d'écoute</strong> vous offre un espace bienveillant et 100% confidentiel sur le campus et à distance.<br><br>
      Contact : <em>cellule.ecoute.est@usms.ac.ma</em> ou via la sous-section <a href="#cellule-ecoute" class="text-amber-600 dark:text-amber-400 font-bold underline">Cellule d'écoute</a>.`;
    } else if (query.includes('amoe') || query.includes('assurance') || query.includes('maladie') || query.includes('cme') || query.includes('santé') || query.includes('sante')) {
      reply = `L'<strong>AMOE (Assurance Maladie Obligatoire des Étudiants)</strong> offre une couverture médicale gratuite à 100% via la CNSS et l'ONOUSC (Loi 116-12).<br><br>
      Démarches et portail sur <a href="#amoe" class="text-amber-600 dark:text-amber-400 font-bold underline">AMOE</a>.`;
    } else if (query.includes('bourse') || query.includes('bourses') || query.includes('minhaty')) {
      reply = `Les bourses d'études sont versées en 3 tranches par l'ONOUSC. Retrait des cartes bancaires Minhaty au campus.<br><br>
      Consultez le calendrier sur <a href="#bourses" class="text-amber-600 dark:text-amber-400 font-bold underline">Bourses</a>.`;
    } else if (query.includes('annuel') || query.includes('calendrier') || query.includes('vacance') || query.includes('rattrapage')) {
      reply = `Le calendrier universitaire 2026/2027 détaille les dates des cours, sessions d'examens (ordinaire et rattrapage), stages PFE et vacances.<br><br>
      Téléchargez le PDF sur <a href="#planning-annuel" class="text-amber-600 dark:text-amber-400 font-bold underline">Planning annuel</a>.`;
    } else if (query.includes('attestation') || query.includes('relevé') || query.includes('service') || query.includes('document')) {
      reply = `Vous pouvez demander vos documents en ligne directement via notre plateforme <a href="https://cursus-estfbs.usms.ac.ma/documents" target="_blank" rel="noopener noreferrer" class="text-amber-600 dark:text-amber-400 font-bold underline">Demandes d'Attestations en Ligne</a> :<br>
      1. Attestation de scolarité<br>
      2. Relevé de notes officiel<br>
      3. Convention de stage<br>
      4. Attestation de réussite. Le délai de traitement moyen est de 48 heures.`;
    } else if (query.includes('labo') || query.includes('laboratoire') || query.includes('limos') || query.includes('lipaem') || query.includes('lgc-gem')) {
      reply = `L'EST-FBS héberge 3 laboratoires et équipes de recherche d'excellence :<br><br>
      • <strong>Labo LIMOS :</strong> Informatique, IA, IoT & Smart Agriculture<br>
      • <strong>Labo LIPAEM :</strong> Procédés Agroalimentaires & Traitement des Eaux<br>
      • <strong>Labo LGC-GEM :</strong> Génie Civil, Géopolymères & Exploitation Minière.<br><br>
      Consultez la sous-section <a href="#labo" class="text-amber-600 dark:text-amber-400 font-bold underline">Labo</a>.`;
    } else if (query.includes('soutenance') && (query.includes('these') || query.includes('thèse') || query.includes('doctorat') || query.includes('cedoc'))) {
      reply = `Consultez les avis officiels de soutenances de thèses de doctorat (CEDoc USMS), les jurys et dates dans la sous-section <a href="#soutenances" class="text-amber-600 dark:text-amber-400 font-bold underline">Soutenances</a>.`;
    } else if (query.includes('manifestation') || query.includes('colloque') || query.includes('congres') || query.includes('congrès') || query.includes('citite')) {
      reply = `L'EST-FBS organise plusieurs évènements scientifiques majeurs dont le congrès international <strong>CITITE'2026</strong> et la journée <strong>JNA-2026</strong>.<br><br>
      Détails et programmes dans <a href="#manifestations-scientifiques" class="text-amber-600 dark:text-amber-400 font-bold underline">Manifestations scientifiques</a>.`;
    } else if (query.includes('habilitation') || query.includes('hdr')) {
      reply = `Les avis de soutenances d'<strong>Habilitation Universitaire (HDR)</strong> des enseignants-chercheurs de l'EST-FBS ainsi que le canevas de dossier sont accessibles dans <a href="#soutenance-habilitation" class="text-amber-600 dark:text-amber-400 font-bold underline">Soutenance dHabilitation Univer</a>.`;
    } else if (query.includes('soutenance')) {
      reply = `Pour les soutenances de thèses doctorales, consultez <a href="#soutenances" class="text-amber-600 dark:text-amber-400 font-bold underline">Soutenances</a>. Pour l'habilitation universitaire, consultez <a href="#soutenance-habilitation" class="text-amber-600 dark:text-amber-400 font-bold underline">Soutenance dHabilitation Univer</a>.`;
    } else if (query.includes('professeur') || query.includes('professeurs') || query.includes('enseignant') || query.includes('corps professoral')) {
      reply = `L'EST-FBS compte <strong>48 enseignants-chercheurs permanents</strong> (PES, PH et PA) répartis sur 3 départements : Génie Informatique, Génie Civil & Mines, et Agrochimie.<br><br>
      Consultez la sous-section <a href="#nos-professeurs" class="text-amber-600 dark:text-amber-400 font-bold underline">Nos professeurs</a>.`;
    } else if (query.includes('harakiya') || query.includes('mobilité') || query.includes('mobilite')) {
      reply = `Le programme national <strong>Mobilité (Harakiya — حركية)</strong> du MESRSI / CNRST prend en charge les séjours de recherche internationaux et la participation aux congrès mondiaux indexés.<br><br>
      Détails et plateforme dans <a href="https://recherche.usms.ac.ma/harakiya" target="_blank" rel="noopener noreferrer" class="text-amber-600 dark:text-amber-400 font-bold underline">Mobilité (Harakiya)</a>.`;
    } else if (query.includes('nadwa') || query.includes('manifestation scientifique') || (query.includes('organisation') && query.includes('colloque'))) {
      reply = `Le programme <strong>Nadwa (ندوة)</strong> du CNRST et de l'USMS accorde des subventions aux enseignants pour l'organisation de colloques, conférences et séminaires à l'EST-FBS.<br><br>
      Consultez <a href="https://recherche.usms.ac.ma/nadwa" target="_blank" rel="noopener noreferrer" class="text-amber-600 dark:text-amber-400 font-bold underline">Organisations des Manifestations Scientifiques (Nadwa)</a>.`;
    } else if (query.includes('ichaa') || query.includes('ichâaê') || query.includes('revue') || query.includes('ouvrage') || query.includes('livre') || query.includes('manuel')) {
      reply = `Le programme <strong>Ichâaê (إشعاع)</strong> finance l'édition, la publication et l'indexation d'ouvrages scientifiques, polycopiés de cours et revues académiques pour les enseignants-chercheurs.<br><br>
      Consultez <a href="https://recherche.usms.ac.ma/ichaae" target="_blank" rel="noopener noreferrer" class="text-amber-600 dark:text-amber-400 font-bold underline">Editions d'ouvrages et revues scientifiques (Ichâaê)</a>.`;
    } else if (query.includes('organigramme') || query.includes('gouvernance') || query.includes('structure')) {
      reply = `L'organisation de l'<strong>EST-FBS</strong> est structurée autour de la Direction (Prof. Dr. El Mostapha RAKIB), du Secrétariat Général, de la Direction Adjointe et de 3 départements pédagogiques.<br><br>
      Consultez la section <a href="#organigramme" class="text-amber-600 dark:text-amber-400 font-bold underline">Organigramme de EST-FBS</a> pour voir l'arborescence complète.`;
    } else if (query.includes('departement') || query.includes('département') || query.includes('pôle')) {
      reply = `L'EST-FBS compte <strong>3 départements d'enseignement et de recherche</strong> :<br>
      1. <strong>Génie Informatique & Décisionnel</strong><br>
      2. <strong>Génie Civil, Mines & Énergies</strong><br>
      3. <strong>Génie Biologique, Agroalimentaire & Chimie</strong><br><br>
      Détails complets dans la section <a href="#departements" class="text-amber-600 dark:text-amber-400 font-bold underline">Départements</a>.`;
    } else if (query.includes('locaux') || query.includes('amphi') || query.includes('administration') || query.includes('campus') || query.includes('equipement') || query.includes('équipement')) {
      reply = `Le campus de l'<strong>EST-FBS</strong> s'étend sur 10 000 m² et comprend 3 pôles majeurs :<br><br>
      • <strong>Administrations :</strong> Direction, Secrétariat Général, Guichet Scolarité (8h30-16h30) et E-Services (<a href="administrations.html" class="text-amber-600 dark:text-amber-400 font-bold underline">Administrations</a>)<br>
      • <strong>Amphis :</strong> Amphi A & Amphi B (500+ places au total, Full HD, climatisés) (<a href="amphis.html" class="text-amber-600 dark:text-amber-400 font-bold underline">Amphis</a>)<br>
      • <strong>Laboratoire :</strong> 8 ateliers de TP spécialisés (Informatique 120+ PC, Génie Civil presse 3000 kN, Agrochimie & Bio HPLC) (<a href="laboratoire.html" class="text-amber-600 dark:text-amber-400 font-bold underline">Laboratoire</a>).<br><br>
      Consultez la section <a href="index.html#nos-locaux" class="text-amber-600 dark:text-amber-400 font-bold underline">Nos locaux</a> pour explorer l'ensemble des infrastructures.`;
    } else if (query.includes('inscription') || query.includes('concours') || query.includes('admission') || query.includes('bac')) {
      reply = `Les préinscriptions pour les nouveaux bacheliers se font via la plateforme nationale <strong>Tawjihi</strong> ou le portail officiel de l'USMS. La sélection se fait selon les notes du Baccalauréat (National et Régional).`;
    } else if (query.includes('directeur') || query.includes('mot')) {
      reply = `L'EST-FBS est un établissement public d'enseignement supérieur affilié à l'<strong>Université Sultan Moulay Slimane</strong>. Le mot du Directeur met l'accent sur l'excellence, l'innovation technologique et l'insertion professionnelle.`;
    } else if (query.includes('contact') || query.includes('adresse') || query.includes('téléphone') || query.includes('email')) {
      reply = `📍 <strong>Adresse :</strong> Route de Oued Zem, Fquih Ben Salah, Maroc<br>
      📞 <strong>Tél :</strong> +212 523 48 51 12<br>
      ✉️ <strong>Email :</strong> estfbs@usms.ac.ma<br>
      🕒 <strong>Horaires :</strong> Du Lundi au Vendredi, 8h30 - 16h30.`;
    } else {
      reply = `Merci pour votre question ! Je suis l'assistant officiel de l'<strong>EST-FBS</strong>. Vous pouvez consulter les rubriques Accueil, EST-FBS, Formations, Recherche, Évènements, Espace Étudiants ou Galerie pour plus de détails.`;
    }

    appendBotMessage(reply);
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

/* ==========================================================================
   12. Recherche Globale (Ctrl + K)
   ========================================================================== */
function initGlobalSearch() {
  const triggers = document.querySelectorAll('.search-trigger-btn');
  const modal = document.getElementById('search-modal');
  const input = document.getElementById('search-input');
  const results = document.getElementById('search-results');
  const close = document.getElementById('search-close');
  if (!modal || !input || !results) return;
  let controller, debounce, origin;

  function message(text) {
    const p = document.createElement('p');
    p.className = 'py-8 text-center text-slate-500 text-sm';
    p.textContent = text;
    results.replaceChildren(p);
  }
  function closeSearch() {
    clearTimeout(debounce);
    controller?.abort();
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    origin?.focus();
  }
  function render(rows) {
    if (!rows.length) message('Aucune publication trouvée pour cette recherche.');
    else results.replaceChildren();
    for (const item of rows) {
      if (!/^\/publications\/\d+$/.test(item.url || '')) continue;
      const link = document.createElement('a');
      link.href = item.url;
      link.className = 'search-result-item block p-3 rounded-xl hover:bg-amber-50 dark:hover:bg-slate-700/60 transition';
      const title = document.createElement('strong');
      title.className = 'block text-sm text-blue-900';
      title.textContent = item.titre;
      const category = document.createElement('span');
      category.className = 'text-xs text-amber-700';
      category.textContent = [item.type, item.categorie].filter(Boolean).join(' · ');
      const excerpt = document.createElement('p');
      excerpt.className = 'text-xs text-slate-500 line-clamp-2';
      excerpt.textContent = item.resume || '';
      link.append(title, category, excerpt);
      link.addEventListener('click', closeSearch);
      results.appendChild(link);
    }
    const archive = document.createElement('a');
    archive.className = 'block p-3 font-bold text-sm text-blue-900 underline';
    archive.href = '/actualites' + (input.value.trim() ? '?q=' + encodeURIComponent(input.value.trim()) : '');
    archive.textContent = 'Voir les résultats dans les actualités et événements →';
    results.appendChild(archive);
  }
  async function search() {
    controller?.abort();
    controller = new AbortController();
    message('Recherche en cours…');
    try {
      const response = await fetch('/backend/api/publications.php?q=' + encodeURIComponent(input.value.trim()), {
        signal: controller.signal, headers: { Accept: 'application/json' }, credentials: 'same-origin'
      });
      if (!response.ok) throw new Error('Recherche indisponible.');
      const data = await response.json();
      render(Array.isArray(data.data) ? data.data : []);
    } catch (error) {
      if (error.name !== 'AbortError') {
        message('La recherche est momentanément indisponible.');
        const link = document.createElement('a');
        link.href = '/actualites?q=' + encodeURIComponent(input.value.trim());
        link.textContent = 'Consulter les actualités';
        link.className = 'block text-center underline';
        results.appendChild(link);
      }
    }
  }
  function openSearch() {
    origin = document.activeElement;
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    input.value = '';
    input.focus();
    search();
  }
  triggers.forEach(button => button.addEventListener('click', openSearch));
  close?.addEventListener('click', closeSearch);
  input.addEventListener('input', () => {
    clearTimeout(debounce);
    controller?.abort();
    debounce = setTimeout(search, 200);
  });
  modal.addEventListener('click', event => { if (event.target === modal) closeSearch(); });
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      modal.classList.contains('hidden') ? openSearch() : closeSearch();
      return;
    }
    if (modal.classList.contains('hidden')) return;
    if (event.key === 'Escape') { event.preventDefault(); closeSearch(); }
    const items = [...results.querySelectorAll('a')];
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const index = items.indexOf(document.activeElement);
      const next = event.key === 'ArrowDown' ? (index + 1) % items.length : (index <= 0 ? items.length - 1 : index - 1);
      items[next]?.focus();
    }
    if (event.key === 'Tab') {
      const focusable = [...modal.querySelectorAll('button, input, a[href]')];
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  });
}
