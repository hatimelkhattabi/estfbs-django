/**
 * EST Fquih Ben Salah - Système de Traduction Automatique Complet (FR / AR / EN)
 * Traduit l'intégralité du site (menus, sections, cartes, formulaires, modales, pied de page)
 */

(function () {
  const STORAGE_KEY = 'estfbs-lang';
  const CACHE_PREFIX = 'estfbs-trans-cache-v1-';

  // Dictionnaire institutionnel prioritaire (traduction instantanée et précise des menus et termes clés)
  const STATIC_DICT = {
    en: {
      'ACCUEIL': 'HOME',
      'EST': 'EST',
      'EST FBS': 'EST FBS',
      'FORMATION': 'PROGRAMS',
      'RECHERCHE': 'RESEARCH',
      'EVENEMENTS': 'EVENTS',
      'Espace Étudiants': 'Student Space',
      'Espace Enseignants': 'Faculty Space',
      'GALERIE': 'GALLERY',
      'Rechercher...': 'Search...',
      'Admin': 'Admin',
      'E-Services': 'E-Services',
      'Présentation': 'Overview',
      'Histoire, vision & missions': 'History, vision & missions',
      'Organigramme de EST-FBS': 'EST-FBS Organization Chart',
      'Direction, services & gouvernance': 'Management, services & governance',
      'Départements': 'Departments',
      'Structures académiques & équipes': 'Academic structures & teams',
      'Nos locaux': 'Our Facilities',
      'Campus, amphis & laboratoires': 'Campus, lecture halls & labs',
      'Infrastructures du Campus': 'Campus Infrastructure',
      'Administrations': 'Administration',
      'Décanat, scolarité & services': 'Dean’s office, student affairs & services',
      'Amphis': 'Lecture Halls',
      'Amphithéâtres & salles de conférences': 'Amphitheaters & conference rooms',
      'Laboratoire': 'Laboratories',
      'Salles TP, Informatique & R&D': 'Practical labs, IT & R&D',
      'Mot du Directeur': 'Director’s Message',
      'Filières Ouvertes': 'Academic Programs',
      'Filières Ouvertes & Stickers': 'Academic Programs & Career Tags',
      'DUT & Licences Pro avec stickers métiers': 'DUT & Bachelor degrees with career tags',
      'EST FBS en chiffres': 'EST FBS in Figures',
      'Chiffres Clés': 'Key Figures',
      'Statistiques & indicateurs clés': 'Statistics & key indicators',
      'Offre Pédagogique': 'Academic Offerings',
      'Filières DUT (Bac+2)': 'DUT Programs (2-Year Degree)',
      'Bachelors & Licences Pro (Bac+3)': 'Bachelors & Professional Licenses (3-Year)',
      'Bachelors & Licences (Bac+3)': 'Bachelors & Licenses (3-Year)',
      'Formation Continue': 'Continuing Education',
      'Certificats & diplômes exécutifs': 'Certificates & executive diplomas',
      'Recherche Scientifique': 'Scientific & Applied Research',
      'Laboratoires de Recherche': 'Research Laboratories',
      'Équipes & axes de recherche': 'Research teams & focus areas',
      'Projets & Publications': 'Projects & Publications',
      'Production scientifique & brevets': 'Scientific output & patents',
      'Partenariats & Coopération': 'Partnerships & Cooperation',
      'Conventions nationales & internationales': 'National & international agreements',
      'Vie Scientifique & Culturelle': 'Scientific & Cultural Life',
      'Actualités & Annonces': 'News & Announcements',
      'Dernières nouvelles du campus': 'Latest campus news',
      'Agenda & Conférences': 'Events & Conferences',
      'Séminaires, workshops & congrès': 'Seminars, workshops & congresses',
      'Activités Parascolaires': 'Extracurricular Activities',
      'Clubs étudiants, sport & culture': 'Student clubs, sports & culture',
      'Portail Étudiant': 'Student Portal',
      'Emplois du Temps & Examens': 'Schedules & Exams',
      'Plannings semestriels & résultats': 'Semester schedules & results',
      'Guichet E-Services Scolarité': 'Student E-Services Desk',
      'Attestations, relevés & stages': 'Certificates, transcripts & internships',
      'Clubs & Vie Estudiantine': 'Clubs & Student Life',
      'Bourses, logement & activités': 'Scholarships, housing & activities',
      'Portail Enseignant & Staff': 'Faculty & Staff Portal',
      'Corps Professoral & Départements': 'Faculty & Departments',
      'Équipes pédagogiques & horaires': 'Teaching teams & schedules',
      'Appels à projets': 'Calls for Projects',
      'Programmes nationaux & internationaux': 'National & international programs',
      'Bourses d\'excellence de recherche': 'Research Excellence Scholarships',
      'Soutien aux doctorants & chercheurs': 'Support for PhD students & researchers',
      'Primes de publication scientifique': 'Scientific Publication Grants',
      'Valorisation des articles indexés': 'Recognition of indexed publications',
      'Editions d\'ouvrages et revues scientifiques (Ichâaê)': 'Scientific Books & Journals Publishing (Ichâaê)',
      'Aide à l\'édition d\'ouvrages & revues indexées': 'Support for book & indexed journal publishing',
      'Étudiants Inscrits': 'Enrolled Students',
      'Filières DUT': 'DUT Programs',
      'Licences & Bachelors': 'Licenses & Bachelors',
      'Corps Enseignant': 'Faculty Members',
      'Équipe Administrative': 'Administrative Staff',
      'Partenaires': 'Partners'
    },
    ar: {
      'ACCUEIL': 'الرئيسية',
      'EST': 'المدرسة',
      'EST FBS': 'المدرسة العليا للتكنولوجيا',
      'FORMATION': 'التكوينات',
      'RECHERCHE': 'البحث العلمي',
      'EVENEMENTS': 'التظاهرات',
      'Espace Étudiants': 'فضاء الطلبة',
      'Espace Enseignants': 'فضاء الأساتذة',
      'GALERIE': 'معرض الصور',
      'Rechercher...': 'بحث...',
      'Admin': 'الإدارة',
      'E-Services': 'الخدمات الرقمية',
      'Présentation': 'تقديم المؤسسة',
      'Histoire, vision & missions': 'التاريخ، الرؤية والمهام',
      'Organigramme de EST-FBS': 'الهيكل التنظيمي للمؤسسة',
      'Direction, services & gouvernance': 'الإدارة، المصالح والحكامة',
      'Départements': 'الشعب والأقسام',
      'Structures académiques & équipes': 'الهياكل الأكاديمية والفرق التربوية',
      'Nos locaux': 'مرافق المؤسسة',
      'Campus, amphis & laboratoires': 'الحرم الجامعي، المدرجات والمختبرات',
      'Infrastructures du Campus': 'البنيات التحتية للحرم الجامعي',
      'Administrations': 'المصالح الإدارية',
      'Décanat, scolarité & services': 'الإدارة، الشؤون الطلابية والمصالح',
      'Amphis': 'المدرجات',
      'Amphithéâtres & salles de conférences': 'المدرجات وقاعات الندوات',
      'Laboratoire': 'المختبرات',
      'Salles TP, Informatique & R&D': 'قاعات الأشغال التطبيقية، المعلوميات والبحث',
      'Mot du Directeur': 'كلمة السيد المدير',
      'Filières Ouvertes': 'المسالك المفتوحة',
      'Filières Ouvertes & Stickers': 'المسالك المفتوحة والآفاق المهنية',
      'DUT & Licences Pro avec stickers métiers': 'الدبلوم الجامعي للتكنولوجيا والإجازة المهنية',
      'EST FBS en chiffres': 'المؤسسة في أرقام',
      'Chiffres Clés': 'أرقام رئيسية',
      'Statistiques & indicateurs clés': 'إحصائيات ومؤشرات أساسية',
      'Offre Pédagogique': 'العرض البيداغوجي',
      'Filières DUT (Bac+2)': 'مسالك الدبلوم الجامعي للتكنولوجيا (سنتان)',
      'Bachelors & Licences Pro (Bac+3)': 'الإجازات المهنية والبكالوريوس (3 سنوات)',
      'Bachelors & Licences (Bac+3)': 'الإجازات المهنية والبكالوريوس (3 سنوات)',
      'Formation Continue': 'التكوين المستمر',
      'Certificats & diplômes exécutifs': 'الشهادات والدبلومات المهنية',
      'Recherche Scientifique': 'البحث العلمي والتطبيقي',
      'Laboratoires de Recherche': 'مختبرات البحث العلمي',
      'Équipes & axes de recherche': 'فرق ومحاور البحث',
      'Projets & Publications': 'المشاريع والمنشورات العلمية',
      'Production scientifique & brevets': 'الإنتاج العلمي وبراءات الاختراع',
      'Partenariats & Coopération': 'الشراكات والتعاون',
      'Conventions nationales & internationales': 'الاتفاقيات الوطنية والدولية',
      'Vie Scientifique & Culturelle': 'الحياة العلمية والثقافية',
      'Actualités & Annonces': 'المستجدات والإعلانات',
      'Dernières nouvelles du campus': 'آخر أخبار المؤسسة',
      'Agenda & Conférences': 'الأجندة والندوات',
      'Séminaires, workshops & congrès': 'الندوات، الورشات والمؤتمرات',
      'Activités Parascolaires': 'الأنشطة الموازية',
      'Clubs étudiants, sport & culture': 'الأندية الطلابية، الرياضة والثقافة',
      'Portail Étudiant': 'بوابة الطالب',
      'Emplois du Temps & Examens': 'استعمالات الزمن والامتحانات',
      'Plannings semestriels & résultats': 'البرمجة الفصلية والنتائج',
      'Guichet E-Services Scolarité': 'شباك الخدمات الطلابية الرقمية',
      'Attestations, relevés & stages': 'الشواهد، بيانات النقط والتداريب',
      'Clubs & Vie Estudiantine': 'الأندية والحياة الطلابية',
      'Bourses, logement & activités': 'المنح، السكن والأنشطة',
      'Portail Enseignant & Staff': 'بوابة الأساتذة والأطر',
      'Corps Professoral & Départements': 'هيئة التدريس والشعب',
      'Équipes pédagogiques & horaires': 'الفرق البيداغوجية والجداول',
      'Appels à projets': 'طلبات عروض المشاريع',
      'Programmes nationaux & internationaux': 'البرامج الوطنية والدولية',
      'Bourses d\'excellence de recherche': 'منح التميز البحثي',
      'Soutien aux doctorants & chercheurs': 'دعم الباحثين وطلبة الدكتوراه',
      'Primes de publication scientifique': 'منح النشر العلمي',
      'Valorisation des articles indexés': 'تثمين المقالات العلمية المفهرسة',
      'Editions d\'ouvrages et revues scientifiques (Ichâaê)': 'إصدار الكتب والمجلات العلمية (إشعاع)',
      'Aide à l\'édition d\'ouvrages & revues indexées': 'دعم نشر المؤلفات والمجلات المفهرسة',
      'Étudiants Inscrits': 'طالب مسجل',
      'Filières DUT': 'مسالك الدبلوم الجامعي',
      'Licences & Bachelors': 'إجازات مهنية',
      'Corps Enseignant': 'أستاذ باحث',
      'Équipe Administrative': 'الطاقم الإداري',
      'Partenaires': 'شريك اقتصادي وأكاديمي'
    }
  };

  let currentLang = localStorage.getItem(STORAGE_KEY) || 'fr';
  let isTranslating = false;

  // Charger le cache depuis localStorage
  function loadCache(lang) {
    try {
      const raw = localStorage.getItem(CACHE_PREFIX + lang);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  }

  function saveCache(lang, cacheObj) {
    try {
      localStorage.setItem(CACHE_PREFIX + lang, JSON.stringify(cacheObj));
    } catch (e) {
      // Ignorer si quota dépassé
    }
  }

  // Notification visuelle (toast)
  function showTranslationToast(message, isLoading = false) {
    let toast = document.getElementById('i18n-status-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'i18n-status-toast';
      toast.className = 'fixed bottom-5 right-24 z-[100] px-4 py-2.5 rounded-xl bg-blue-950 text-white text-xs font-bold shadow-2xl border border-orange-400/50 flex items-center gap-2.5 transition-all duration-300 notranslate';
      toast.setAttribute('translate', 'no');
      document.body.appendChild(toast);
    }
    toast.innerHTML = isLoading
      ? '<i class="fas fa-circle-notch fa-spin text-orange-400"></i><span>' + message + '</span>'
      : '<i class="fas fa-check-circle text-emerald-400"></i><span>' + message + '</span>';
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';

    if (!isLoading) {
      clearTimeout(toast.__hideTimer);
      toast.__hideTimer = setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
      }, 2600);
    }
  }

  // Collecter tous les nœuds texte pertinents du DOM
  function getTranslatableNodes() {
    const nodes = [];
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          const parent = node.parentElement;
          if (!parent) return NodeFilter.FILTER_REJECT;
          const tag = parent.tagName;
          if (
            tag === 'SCRIPT' ||
            tag === 'STYLE' ||
            tag === 'NOSCRIPT' ||
            tag === 'CODE' ||
            tag === 'KBD' ||
            tag === 'SVG' ||
            tag === 'I'
          ) {
            return NodeFilter.FILTER_REJECT;
          }
          if (parent.closest('.notranslate, [translate="no"], #i18n-status-toast')) {
            return NodeFilter.FILTER_REJECT;
          }
          const text = (node.__origText !== undefined ? node.__origText : node.nodeValue) || '';
          const trimmed = text.trim();
          // Ignorer les chaînes vides ou purement numériques / symboles
          if (!trimmed || /^[0-9+\-%.,:/\s•|⌵()]+$/.test(trimmed)) {
            return NodeFilter.FILTER_REJECT;
          }
          return NodeFilter.FILTER_ACCEPT;
        }
      }
    );

    let current;
    while ((current = walker.nextNode())) {
      if (current.__origText === undefined) {
        current.__origText = current.nodeValue;
      }
      nodes.push(current);
    }
    return nodes;
  }

  // Collecter les attributs placeholder et title traduisibles
  function getTranslatableAttributes() {
    const items = [];
    document.querySelectorAll('[placeholder], [title]').forEach((el) => {
      if (el.closest('.notranslate, [translate="no"]')) return;
      if (el.hasAttribute('placeholder')) {
        if (el.__origPlaceholder === undefined) {
          el.__origPlaceholder = el.getAttribute('placeholder');
        }
        if (el.__origPlaceholder && el.__origPlaceholder.trim()) {
          items.push({ el, attr: 'placeholder', orig: el.__origPlaceholder.trim() });
        }
      }
      if (el.hasAttribute('title')) {
        if (el.__origTitle === undefined) {
          el.__origTitle = el.getAttribute('title');
        }
        if (el.__origTitle && el.__origTitle.trim()) {
          items.push({ el, attr: 'title', orig: el.__origTitle.trim() });
        }
      }
    });
    return items;
  }

  // Traduction d'un lot de textes via l'API Google Translate (GTX)
  async function translateBatchAPI(texts, targetLang) {
    const SEP = ' ||| ';
    const joined = texts.join('\n');
    const url =
      'https://translate.googleapis.com/translate_a/single?client=gtx&sl=fr&tl=' +
      encodeURIComponent(targetLang) +
      '&dt=t&q=' +
      encodeURIComponent(joined);

    const response = await fetch(url);
    if (!response.ok) throw new Error('Network error');
    const data = await response.json();
    if (!data || !Array.isArray(data[0])) throw new Error('Invalid format');

    const fullTranslated = data[0].map((part) => (part && part[0]) || '').join('');
    const lines = fullTranslated.split('\n');
    return lines;
  }

  // Appliquer une chaîne traduite en préservant les espaces autour du texte original
  function replacePreservingWhitespace(originalRaw, translatedTrimmed) {
    const leadingMatch = originalRaw.match(/^\s*/);
    const trailingMatch = originalRaw.match(/\s*$/);
    const leading = leadingMatch ? leadingMatch[0] : '';
    const trailing = trailingMatch ? trailingMatch[0] : '';
    return leading + translatedTrimmed + trailing;
  }

  // Mise à jour de l'interface du sélecteur de langue (Desktop & Mobile)
  function updateSelectorUI(lang) {
    const langUpper = lang.toUpperCase();
    document.querySelectorAll('.current-lang-badge').forEach((el) => {
      el.textContent = langUpper;
    });

    document.querySelectorAll('[data-lang-choice]').forEach((btn) => {
      const choice = btn.getAttribute('data-lang-choice');
      const isSelected = choice === lang;
      const checkIcon = btn.querySelector('.lang-check-icon');

      if (btn.classList.contains('mobile-lang-btn')) {
        if (isSelected) {
          btn.className = 'mobile-lang-btn px-3 py-1 rounded-md bg-blue-900 text-white font-bold shadow-sm transition';
        } else {
          btn.className = 'mobile-lang-btn px-3 py-1 rounded-md text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 transition';
        }
      } else {
        if (isSelected) {
          btn.classList.add('font-bold', 'text-orange-600', 'bg-orange-50/70');
          btn.classList.remove('text-slate-700');
        } else {
          btn.classList.remove('font-bold', 'text-orange-600', 'bg-orange-50/70');
          btn.classList.add('text-slate-700');
        }
        if (checkIcon) {
          checkIcon.style.opacity = isSelected ? '1' : '0';
        }
      }
    });

    // Mettre à jour l'attribut lang de la page
    document.documentElement.setAttribute('lang', lang);
  }

  // Fonction principale de changement de langue
  async function applyLanguage(lang) {
    currentLang = lang;
    localStorage.setItem(STORAGE_KEY, lang);
    updateSelectorUI(lang);

    const nodes = getTranslatableNodes();
    const attrs = getTranslatableAttributes();

    // Si retour au Français : restauration immédiate des textes originaux
    if (lang === 'fr') {
      nodes.forEach((node) => {
        if (node.__origText !== undefined) {
          node.nodeValue = node.__origText;
        }
      });
      attrs.forEach((item) => {
        item.el.setAttribute(item.attr, item.orig);
      });
      showTranslationToast('Langue : Français (FR)', false);
      return;
    }

    const dict = STATIC_DICT[lang] || {};
    const cache = loadCache(lang);
    const missingSet = new Set();

    // 1. Appliquer immédiatement le dictionnaire statique + le cache local
    nodes.forEach((node) => {
      const origTrimmed = node.__origText.trim();
      if (dict[origTrimmed]) {
        node.nodeValue = replacePreservingWhitespace(node.__origText, dict[origTrimmed]);
      } else if (cache[origTrimmed]) {
        node.nodeValue = replacePreservingWhitespace(node.__origText, cache[origTrimmed]);
      } else {
        // Ignorer les textes déjà en arabe si la cible est l'arabe
        if (lang === 'ar' && /^[\u0600-\u06FF\s.,،؛:()\-]+$/.test(origTrimmed)) {
          return;
        }
        missingSet.add(origTrimmed);
      }
    });

    attrs.forEach((item) => {
      if (dict[item.orig]) {
        item.el.setAttribute(item.attr, dict[item.orig]);
      } else if (cache[item.orig]) {
        item.el.setAttribute(item.attr, cache[item.orig]);
      } else {
        missingSet.add(item.orig);
      }
    });

    const missingList = Array.from(missingSet);
    if (missingList.length === 0) {
      const msg = lang === 'ar' ? 'تمت ترجمة الموقع إلى العربية (AR)' : 'Site translated to English (EN)';
      showTranslationToast(msg, false);
      return;
    }

    // 2. Traduire automatiquement tous les textes restants par lots (batches)
    const loadingMsg =
      lang === 'ar' ? 'جاري ترجمة الموقع إلى العربية...' : 'Translating entire site to English...';
    showTranslationToast(loadingMsg, true);

    const BATCH_CHAR_LIMIT = 1400;
    const batches = [];
    let currentBatch = [];
    let currentLen = 0;

    missingList.forEach((str) => {
      // Nettoyer les sauts de ligne internes pour préserver l'alignement ligne par ligne
      const cleanStr = str.replace(/\s*\n\s*/g, ' ');
      if (currentLen + cleanStr.length > BATCH_CHAR_LIMIT && currentBatch.length > 0) {
        batches.push(currentBatch);
        currentBatch = [];
        currentLen = 0;
      }
      currentBatch.push({ raw: str, clean: cleanStr });
      currentLen += cleanStr.length + 2;
    });
    if (currentBatch.length > 0) {
      batches.push(currentBatch);
    }

    for (let i = 0; i < batches.length; i++) {
      // Si l'utilisateur a changé de langue entre-temps, interrompre
      if (currentLang !== lang) return;
      const batch = batches[i];
      try {
        const cleanTexts = batch.map((b) => b.clean);
        const translatedLines = await translateBatchAPI(cleanTexts, lang);
        batch.forEach((b, idx) => {
          const translated = (translatedLines[idx] || b.clean).trim();
          if (translated) {
            cache[b.raw] = translated;
          }
        });

        // Mettre à jour le DOM au fur et à mesure de chaque lot
        nodes.forEach((node) => {
          const origTrimmed = node.__origText.trim();
          if (cache[origTrimmed]) {
            node.nodeValue = replacePreservingWhitespace(node.__origText, cache[origTrimmed]);
          }
        });
        attrs.forEach((item) => {
          if (cache[item.orig]) {
            item.el.setAttribute(item.attr, cache[item.orig]);
          }
        });
      } catch (err) {
        console.warn('Batch translation error:', err);
      }
    }

    saveCache(lang, cache);
    const doneMsg = lang === 'ar' ? 'تمت ترجمة الموقع إلى العربية (AR)' : 'Site translated to English (EN)';
    showTranslationToast(doneMsg, false);
  }

  // Initialisation au chargement du DOM
  document.addEventListener('DOMContentLoaded', () => {
    // Gestion de l'ouverture/fermeture au clic ET au survol du menu déroulant de langue
    document.querySelectorAll('.lang-dropdown-btn').forEach((toggleBtn) => {
      const menu = toggleBtn.parentElement ? toggleBtn.parentElement.querySelector('.lang-dropdown-menu') : null;
      if (menu) {
        toggleBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          menu.classList.toggle('lang-open');
        });
      }
    });

    // Fermer le menu si on clique ailleurs sur la page
    document.addEventListener('click', () => {
      document.querySelectorAll('.lang-dropdown-menu').forEach((menu) => {
        menu.classList.remove('lang-open');
      });
    });

    // Attacher les événements sur tous les boutons de choix de langue (FR / AR / EN)
    document.querySelectorAll('[data-lang-choice]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const chosen = btn.getAttribute('data-lang-choice');
        document.querySelectorAll('.lang-dropdown-menu').forEach((menu) => {
          menu.classList.remove('lang-open');
        });
        if (chosen) {
          applyLanguage(chosen);
        }
      });
    });

    // Appliquer la langue mémorisée si différente du français
    updateSelectorUI(currentLang);
    if (currentLang !== 'fr') {
      applyLanguage(currentLang);
    }
  });
})();
