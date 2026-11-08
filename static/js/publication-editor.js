'use strict';

(() => {
    // Optional centered button: these settings work independently of the editor.
    const toggle = document.getElementById('publication-button-enabled');
    const options = document.getElementById('publication-button-options');
    const buttonLabel = document.getElementById('publication-button-label');
    const buttonUrl = document.getElementById('publication-button-url');
    const buttonFile = document.getElementById('publication-button-file');
    const buttonPreview = document.getElementById('publication-button-preview');

    function updateButton() {
        if (!toggle || !options || !buttonLabel || !buttonUrl || !buttonPreview) return;
        options.hidden = !toggle.checked;
        toggle.setAttribute('aria-expanded', String(toggle.checked));
        buttonLabel.required = toggle.checked;
        buttonUrl.required = toggle.checked && !buttonFile?.files?.length;
        if (buttonFile) buttonFile.disabled = !toggle.checked;
        buttonPreview.textContent = (buttonLabel.value.trim() || 'Consulter le document') + ' ↗';
    }

    toggle?.addEventListener('change', updateButton);
    buttonLabel?.addEventListener('input', updateButton);
    buttonFile?.addEventListener('change', updateButton);
    updateButton();

    const source = document.getElementById('publication-contenu');
    const deltaField = document.getElementById('publication-delta');
    const visualTools = document.getElementById('publication-visual-tools');
    const message = document.getElementById('publication-editor-message');
    const form = source?.closest('form');
    if (!source || !deltaField || !visualTools || !form) return;

    // Keep a usable plain-text form if the editor asset cannot load.
    if (typeof window.Quill !== 'function') {
        message.textContent = 'Mode texte actif. Rechargez la page pour retrouver les outils de mise en forme.';
        return;
    }

    const dialog = document.getElementById('publication-link-dialog');
    const linkText = document.getElementById('publication-link-text');
    const linkAddress = document.getElementById('publication-link-address');
    const linkError = document.getElementById('publication-link-error');
    const linkFile = document.getElementById('publication-link-file');
    const uploadButton = document.getElementById('publication-upload-link');
    const uploadStatus = document.getElementById('publication-upload-status');
    const linkSubmit = document.querySelector('#publication-link-form button[type="submit"]');
    const preview = document.getElementById('publication-content-preview');
    const previewBody = document.getElementById('publication-preview-body');
    const previewToggle = document.getElementById('publication-preview-toggle');
    let linkRange = null;
    let editor;
    let uploadController = null;
    let uploadPending = false;

    function normaliseLink(value) {
        const input = value.trim();
        if (!input || input.length > 2000 || /[\u0000-\u0020\u007f\\]/.test(input)) throw new Error('invalid');
        if (input.startsWith('/') && !input.startsWith('//')) return input;
        const url = new URL(input);
        if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('invalid');
        return url.href;
    }

    function uploadBusy(busy) {
        uploadPending = busy;
        if (uploadButton) uploadButton.disabled = busy;
        if (linkFile) linkFile.disabled = busy;
        if (linkSubmit) linkSubmit.disabled = busy;
    }

    function openLinkDialog() {
        if (!editor || !dialog) return;
        linkRange = editor.getSelection(true) || { index: editor.getLength() - 1, length: 0 };
        const currentLink = editor.getFormat(linkRange).link;

        // Clicking inside an existing link edits its full label and address.
        if (!linkRange.length && currentLink) {
            let [blot] = editor.getLeaf(linkRange.index);
            while (blot && blot.statics.blotName !== 'link') blot = blot.parent;
            if (blot) linkRange = { index: editor.getIndex(blot), length: blot.length() };
        }

        linkText.value = editor.getText(linkRange.index, linkRange.length).replace(/[\r\n]+/g, ' ') || 'Via ce lien';
        linkAddress.value = typeof currentLink === 'string' ? currentLink : '';
        linkError.textContent = '';
        uploadController?.abort();
        uploadController = null;
        uploadBusy(false);
        if (linkFile) linkFile.value = '';
        if (uploadStatus) uploadStatus.textContent = '';
        dialog.showModal();
        linkAddress.focus();
    }

    try {
        visualTools.hidden = false;
        editor = new window.Quill('#publication-rich-editor', {
            theme: 'snow',
            placeholder: 'Rédigez votre annonce, les pièces à fournir et les informations utiles…',
            formats: [
                'direction', 'image', 'header', 'font', 'size', 'bold', 'italic', 'underline', 'strike',
                'color', 'background', 'list', 'align', 'blockquote', 'script', 'link',
            ],
            modules: {
                toolbar: { container: '#publication-rich-toolbar', handlers: { link: openLinkDialog } },
                history: { delay: 700, maxStack: 100, userOnly: true },
                keyboard: {
                    bindings: {
                        // Indentation is intentionally not enabled in this editor.
                        tab: { key: 'Tab', handler() { return true; } },
                    },
                },
            },
        });

        let restored = false;
        if (deltaField.value.trim()) {
            try {
                const delta = JSON.parse(deltaField.value);
                if (Array.isArray(delta.ops)) {
                    editor.setContents(delta, 'silent');
                    restored = true;
                }
            } catch { /* Fall back to the original article content below. */ }
        }
        if (!restored) {
            const html = document.getElementById('publication-initial-html').value;
            editor.setContents(editor.clipboard.convert({ html }), 'silent');
        }

        editor.history.clear();
        editor.root.setAttribute('aria-label', 'Contenu complet');
        editor.root.setAttribute('aria-multiline', 'true');
        source.hidden = true;
        source.required = false;
        deltaField.disabled = false;
        message.textContent = 'Les liens, couleurs, listes et alignements seront conservés sur le site.';
    } catch {
        visualTools.hidden = true;
        message.textContent = 'Mode texte actif. Rechargez la page pour retrouver les outils de mise en forme.';
        return;
    }

    function syncContent() {
        source.value = editor.getSemanticHTML();
        const plainText = editor.getText().trim();
        deltaField.value = JSON.stringify(editor.getContents());
        const count = Array.from(plainText).length;
        const words = plainText ? plainText.split(/\s+/u).length : 0;
        document.getElementById('publication-word-count').textContent =
            `${words.toLocaleString('fr-MA')} mots · ${count.toLocaleString('fr-MA')} / 50 000 caractères`;

        const tooLong = count > 50000 || deltaField.value.length > 200000;
        message.classList.toggle('pub-rich-error', tooLong);
        message.textContent = tooLong
            ? 'Le contenu dépasse la limite autorisée. Raccourcissez le texte ou simplifiez sa mise en forme.'
            : 'Les liens, couleurs, listes et alignements seront conservés sur le site.';
        if (!preview.hidden) previewBody.innerHTML = editor.getSemanticHTML();
        return !tooLong;
    }

    editor.on('text-change', syncContent);
    syncContent();

    document.getElementById('publication-undo').addEventListener('click', () => editor.history.undo());
    document.getElementById('publication-redo').addEventListener('click', () => editor.history.redo());

    document.getElementById('publication-remove-link').addEventListener('mousedown', event => event.preventDefault());
    document.getElementById('publication-remove-link').addEventListener('click', () => {
        editor.focus();
        editor.format('link', false, 'user');
    });

    previewToggle.addEventListener('click', () => {
        preview.hidden = !preview.hidden;
        previewToggle.setAttribute('aria-expanded', String(!preview.hidden));
        previewToggle.textContent = preview.hidden ? 'Aperçu' : 'Masquer l’aperçu';
        if (!preview.hidden) {
            syncContent();
            preview.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    });

    document.getElementById('publication-link-cancel').addEventListener('click', () => {
        dialog.close();
        editor.focus();
        if (linkRange) editor.setSelection(linkRange.index, linkRange.length, 'silent');
    });

    document.getElementById('publication-link-form').addEventListener('submit', event => {
        event.preventDefault();
        if (uploadPending) return;
        let url;
        try {
            url = normaliseLink(linkAddress.value);
        } catch {
            linkError.textContent = 'Utilisez une adresse HTTP, HTTPS ou un chemin local commençant par /.';
            linkAddress.focus();
            return;
        }
        const label = linkText.value.trim().replace(/[\r\n]+/g, ' ');
        if (!label || !linkRange) return;

        const selectionFormats = editor.getFormat(linkRange);
        const formats = { link: url };
        for (const key of ['bold', 'italic', 'underline', 'strike', 'font', 'size', 'color', 'background', 'script']) {
            if (selectionFormats[key] !== undefined && !Array.isArray(selectionFormats[key])) formats[key] = selectionFormats[key];
        }
        const Delta = window.Quill.import('delta');
        editor.history.cutoff();
        editor.updateContents(new Delta().retain(linkRange.index).delete(linkRange.length).insert(label, formats), 'user');
        editor.history.cutoff();
        dialog.close();
        editor.focus();
        editor.setSelection(linkRange.index + label.length, 0, 'silent');
    });

    uploadButton?.addEventListener('click', async () => {
        const file = linkFile?.files?.[0];
        linkError.textContent = '';
        if (!file) {
            linkError.textContent = 'Choisissez d’abord un PDF ou une image.';
            return;
        }
        if (file.size > 20 * 1024 * 1024) {
            linkError.textContent = 'Le document doit peser au maximum 20 Mo.';
            return;
        }
        const data = new FormData();
        data.append('fichier', file);
        const controller = new AbortController();
        uploadController = controller;
        uploadBusy(true);
        uploadStatus.textContent = 'Téléversement en cours…';
        try {
            const response = await fetch(dialog.dataset.uploadUrl, {
                method: 'POST', body: data, credentials: 'same-origin', signal: controller.signal,
                headers: {'Accept': 'application/json', 'X-CSRF-TOKEN': document.querySelector('meta[name="csrf-token"]')?.content || ''},
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(result.message || 'Le téléversement a échoué. Vérifiez le format, la taille et la configuration du serveur.');
            if (controller !== uploadController || !dialog.open) return;
            linkAddress.value = normaliseLink(result.url);
            if (!linkRange?.length && linkText.value === 'Via ce lien') linkText.value = result.nom;
            uploadStatus.textContent = 'Fichier prêt. Cliquez sur Insérer le lien puis enregistrez la publication.';
        } catch (error) {
            if (error.name !== 'AbortError') {
                uploadStatus.textContent = '';
                linkError.textContent = error.message || 'Le téléversement a échoué.';
            }
        } finally {
            if (uploadController === controller) {
                uploadController = null;
                uploadBusy(false);
            }
        }
    });

    dialog?.addEventListener('close', () => {
        uploadController?.abort();
        uploadController = null;
        uploadBusy(false);
    });

    form.addEventListener('submit', event => {
        if (uploadPending) {
            event.preventDefault();
            message.textContent = 'Attendez la fin du téléversement avant d’enregistrer.';
            return;
        }
        if (!syncContent() || !editor.getText().trim()) {
            event.preventDefault();
            if (!editor.getText().trim()) message.textContent = 'Saisissez le contenu de votre publication avant d’enregistrer.';
            message.classList.add('pub-rich-error');
            editor.focus();
        }
    });
})();
