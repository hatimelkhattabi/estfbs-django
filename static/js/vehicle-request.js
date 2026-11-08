document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('vehicule-form');
  if (!form) return;
  const submitBtn = document.getElementById('submit-btn');
  const effectifInput = document.getElementById('effectif_etudiants');
  const capacityText = document.getElementById('capacity-text');
  const jsErrorAlert = document.getElementById('js-error-alert');
  const jsErrorText = document.getElementById('js-error-text');

  const successCard = document.getElementById('success-confirmation');
  const formContainer = document.getElementById('form-container');
  const confRef = document.getElementById('conf-reference');
  const confPdfBtn = document.getElementById('conf-pdf-btn');
  const confStatusBtn = document.getElementById('conf-status-btn');
  const sumProf = document.getElementById('sum-prof');
  const sumDest = document.getElementById('sum-dest');
  const sumDate = document.getElementById('sum-date');
  const sumEffectif = document.getElementById('sum-effectif');
  const btnNewDemande = document.getElementById('btn-new-demande');

  // Ajustement dynamique du type de véhicule suggéré selon l'effectif
  function updateVehicleSuggestion() {
    if (!effectifInput || !capacityText) return;
    const val = parseInt(effectifInput.value, 10);
    if (!val || val <= 0) return;

    if (val <= 6) {
      capacityText.textContent = "Adapté pour un Véhicule de liaison / service (5 à 7 places)";
    } else if (val <= 25) {
      capacityText.textContent = "Adapté pour un Minibus Universitaire (25 places)";
    } else if (val <= 50) {
      capacityText.textContent = "Adapté pour un Grand Bus Universitaire (50 places)";
    } else {
      capacityText.textContent = "Effectif important (" + val + " étudiants) : attribution autocar ou 2 bus";
    }
  }

  if (effectifInput) {
    effectifInput.addEventListener('input', updateVehicleSuggestion);
    updateVehicleSuggestion();
  }

  // Soumission AJAX du formulaire
  form.addEventListener('submit', async function (e) {
    e.preventDefault();

    // Reset alert
    jsErrorAlert.classList.add('hidden');

    // Validation basique côté client
    const nom = document.getElementById('nom_professeur').value.trim();
    const dest = document.getElementById('destination').value.trim();
    const dateV = document.getElementById('date_visite').value;
    const eff = parseInt(effectifInput.value, 10);
    const duree = document.getElementById('duree_visite').value;

    if (!nom || nom.length < 3) {
      showError("Veuillez saisir le nom complet du professeur (au moins 3 caractères).");
      return;
    }
    if (!dest || dest.length < 2) {
      showError("Veuillez indiquer la destination de la visite.");
      return;
    }
    if (!dateV) {
      showError("Veuillez choisir la date de la visite.");
      return;
    }
    if (!eff || eff < 1) {
      showError("Veuillez spécifier l'effectif des étudiants (au moins 1).");
      return;
    }
    if (!duree) {
      showError("Veuillez choisir la durée de la visite.");
      return;
    }

    // État de chargement du bouton
    const originalBtnContent = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin text-base"></i><span>Enregistrement de la demande...</span>';

    try {
      const formData = new FormData(form);
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

      const response = await fetch(form.action, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json',
          ...(csrfToken ? { 'X-CSRF-TOKEN': csrfToken } : {})
        },
        body: formData
      });

      const result = await response.json();

      if (!response.ok || !result.success) {
        let msg = result.message || "Une erreur est survenue lors de l'enregistrement.";
        if (result.errors) {
          msg = Object.values(result.errors).flat().map(error => error.message || error).join('\n');
        }
        showError(msg);
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnContent;
        return;
      }

      // Succès : remplissage du bloc confirmation
      confRef.textContent = result.code_suivi;

      confPdfBtn.href = result.pdf_download_url;
      confStatusBtn.href = result.status_url;

      if (result.data) {
        sumProf.textContent = result.data.nom_professeur;
        sumDest.textContent = result.data.destination;
        sumDate.textContent = result.data.date_visite;
        sumEffectif.textContent = result.data.effectif_etudiants + " étudiants";
      }

      // Transition visuelle
      successCard.classList.remove('hidden');
      formContainer.classList.add('opacity-40', 'pointer-events-none');
      successCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
      console.error(err);
      showError("Impossible de joindre le serveur. Veuillez vérifier votre connexion et réessayer.");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalBtnContent;
    }
  });

  function showError(msg) {
    jsErrorText.textContent = msg;
    jsErrorText.style.whiteSpace = "pre-line";
    jsErrorAlert.classList.remove('hidden');
    jsErrorAlert.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  // Bouton pour faire une nouvelle demande
  btnNewDemande.addEventListener('click', function () {
    form.reset();
    updateVehicleSuggestion();
    successCard.classList.add('hidden');
    formContainer.classList.remove('opacity-40', 'pointer-events-none');
    formContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});
