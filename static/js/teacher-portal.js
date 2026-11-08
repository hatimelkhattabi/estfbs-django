(() => {
  "use strict";
  document.body.classList.add("tp-js");
  const menu = document.querySelector(".tp-menu-toggle");
  if (menu) menu.addEventListener("click", () => {
    const open = document.querySelector(".tp-sidebar").classList.toggle("is-open");
    menu.setAttribute("aria-expanded", String(open));
  });
  const documentType = document.querySelector('[name="type_document"]');
  const precision = document.querySelector('[data-document-precision]');
  if (documentType && precision) {
    const updatePrecision = () => {
      const other = documentType.value === "Autre document";
      precision.hidden = !other;
      precision.querySelector("input").required = other;
    };
    documentType.addEventListener("change", updatePrecision); updatePrecision();
  }
  const attendance = document.querySelector("[data-attendance-form]");
  if (attendance) {
    const course = attendance.querySelector('[name="filiere"]');
    const year = attendance.querySelector('[name="niveau"]');
    const help = attendance.querySelector("[data-dbt-year-help]");
    let wasDbt = false;
    const updateYear = () => {
      const dbt = /^DBT\b/i.test(course.value);
      // Keep the select enabled so its value is included in the GET request.
      for (const option of year.options) option.disabled = dbt && option.value !== "3";
      if (dbt) year.value = "3";
      else if (wasDbt) year.value = "";
      help.hidden = !dbt;
      wasDbt = dbt;
    };
    course.addEventListener("change", updateYear);
    window.addEventListener("pageshow", updateYear);
    updateYear();
  }
  const form = document.querySelector("[data-print-form]");
  if (!form) return;
  const list = form.querySelector("[data-document-list]");
  const template = form.querySelector("[data-document-template]");
  const total = form.querySelector('[name="documents-TOTAL_FORMS"]');
  const add = form.querySelector("[data-add-document]");
  const visibleRows = () => [...list.querySelectorAll("[data-document-row]")].filter(row => !row.hidden);
  function updateRows() {
    const rows = visibleRows();
    rows.forEach((row, index) => {
      row.querySelector("[data-document-number]").textContent = index + 1;
      row.querySelector("[data-remove-document]").disabled = rows.length === 1;
      // Django formsets defer required fields to server validation. Enable the
      // browser check for active rows so a missing PDF/date is caught early.
      row.querySelectorAll('input[type="file"],input[type="date"],input[name$="-exemplaires"],input[name$="-type_travail"],select').forEach(input => {
        input.required = !(input.type === "file" && row.dataset.hasFile === "true");
      });
      supplies(row);
    });
    add.disabled = rows.length >= 10;
    add.textContent = add.disabled ? "10 documents maximum" : "＋ Ajouter un autre document";
  }
  add.addEventListener("click", () => {
    if (visibleRows().length >= 10) return;
    const reusable = list.querySelector("[data-document-row][hidden]");
    const index = reusable ? reusable.dataset.index : Number(total.value);
    const html = template.innerHTML.replace(/__prefix__/g, String(index));
    if (reusable) reusable.outerHTML = html;
    else { list.insertAdjacentHTML("beforeend", html); total.value = Number(index) + 1; }
    updateRows();
    const row = list.querySelector(`[data-index="${index}"]`);
    row.querySelector('input[type="file"]').focus();
  });
  list.addEventListener("click", event => {
    const button = event.target.closest("[data-remove-document]");
    if (!button || visibleRows().length <= 1) return;
    const row = button.closest("[data-document-row]");
    row.querySelector('[name$="-DELETE"]').checked = true;
    row.hidden = true;
    row.querySelectorAll("input,select").forEach(input => {
      if (!input.name.endsWith("-DELETE")) input.disabled = true;
    });
    updateRows(); add.focus();
  });
  // Keep rows deleted before a validation error hidden on redisplay.
  list.querySelectorAll('[name$="-DELETE"]:checked').forEach(input => {
    const row = input.closest("[data-document-row]");
    row.hidden = true;
    row.querySelectorAll("input,select").forEach(field => {
      if (!field.name.endsWith("-DELETE")) field.disabled = true;
    });
  });
  function supplies(row) {
    const exam = row.querySelector('[name$="-type_travail"]:checked')?.value === "examen";
    row.querySelector("[data-exam-options]").hidden = !exam;
    for (const name of ["feuilles_reponse", "papier_brouillon"]) {
      const check = row.querySelector(`[name$="-avec_${name}"]`);
      const container = row.querySelector(`[data-supply-count="${name}"]`);
      const input = container.querySelector("input");
      check.disabled = !exam;
      container.hidden = !exam || !check.checked;
      input.disabled = !exam || !check.checked;
      input.required = exam && check.checked;
      if (exam && check.checked && !input.value) {
        input.value = row.querySelector('[name$="-exemplaires"]')?.value || 1;
      }
    }
  }
  form.addEventListener("change", event => {
    const row = event.target.closest("[data-document-row]");
    if (row && (event.target.name?.endsWith("-type_travail") || event.target.name?.includes("-avec_"))) supplies(row);
  });
  updateRows();
})();
