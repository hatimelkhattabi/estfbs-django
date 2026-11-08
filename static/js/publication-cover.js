/* Cover composer: local images, editable text, clean canvas export. No remote service. */
(() => {
    'use strict';

    const root = document.getElementById('cover-designer');
    if (!root) return;
    const find = selector => root.querySelector(selector);
    const all = selector => Array.from(root.querySelectorAll(selector));
    const form = root.closest('form');
    if (!form) return;
    const standalone = root.dataset.mode === 'standalone';
    if (standalone) form.addEventListener('submit', event => event.preventDefault());
    const canvas = find('[data-cover-canvas]');
    const thumbnail = find('[data-cover-thumbnail]');
    const imageInput = document.getElementById('pub-image-file');
    const imagePreview = document.getElementById('pub-image-preview');
    const removeImage = form.querySelector('[name="remove_image"]');
    const configInput = find('[data-cover-config]');
    const backgroundInput = find('[data-cover-background-file]');
    const logoInput = find('[data-cover-logo-file]');
    const applyButton = find('[data-cover-apply]');
    const downloadButton = find('[data-cover-download]');
    const selection = find('[data-cover-selection]');
    const status = find('[data-cover-status]');
    const width = 1600;
    const height = 800;
    const fonts = { outfit: '"Cover Outfit", Arial, sans-serif', sans: 'Arial, sans-serif', serif: 'Georgia, serif' };
    let state;
    try { state = JSON.parse(find('[data-cover-initial]').value); } catch { state = null; }
    const restored = Boolean(state);
    state = state || {
        version: 1, background: 'genie-civil', backgroundColor: '#f5eee3', veil: 0, cropX: 50, cropY: 50,
        logo: { visible: true, source: 'default', x: 50, y: 21, width: 14 },
        texts: [
            { id: 'text-title', text: 'GÉNIE CIVIL', x: 50, y: 53, size: 110, width: 84, font: 'outfit', bold: true, color: '#18202b', align: 'center' },
            { id: 'text-subtitle', text: 'Convocation à l’oral', x: 50, y: 73, size: 64, width: 84, font: 'outfit', bold: true, color: '#18202b', align: 'center' },
        ],
    };
    state.texts.forEach(text => { text.text = text.text || ''; });
    let selected = state.texts[0]?.id || 'logo';
    let started = false;
    let ready = false;
    let busy = false;
    let applying = false;
    let active = restored;
    let dirty = restored && root.dataset.retry === 'true';
    let hasApplied = false;
    let revision = 0;
    let sequence = 0;
    let background = null;
    let logo = null;
    let customBackground = null;
    let customLogo = null;
    const localSequence = { background: 0, logo: 0 };
    let hitboxes = [];
    let fitError = '';
    let drag = null;
    let animation = 0;
    let previewUrl = null;
    let previousFiles = imageInput?.files || [];
    let previousPreview = imagePreview?.src || '';
    const imageCache = new Map();

    function message(text, error = false) {
        status.textContent = text;
        status.dataset.error = String(error);
    }

    function selectedItem() {
        return selected === 'logo' ? state.logo : state.texts.find(text => text.id === selected);
    }

    function configuration() {
        // Asset references are attached by the server, never trusted from the browser.
        return {
            version: 1, background: state.background, backgroundColor: state.backgroundColor,
            veil: state.veil, cropX: state.cropX, cropY: state.cropY, logo: state.logo, texts: state.texts,
        };
    }

    function syncControls() {
        all('[data-cover-control]').forEach(input => { input.value = state[input.dataset.coverControl]; });
        all('[data-cover-logo]').forEach(input => {
            const value = state.logo[input.dataset.coverLogo];
            if (input.type === 'checkbox') input.checked = value;
            else input.value = value;
        });
        const entries = state.texts.map((text, index) => ({ id: text.id, label: text.text.replace(/\s+/g, ' ').slice(0, 32) || `Texte ${index + 1}` }));
        entries.push({ id: 'logo', label: 'Logo' });
        selection.replaceChildren(...entries.map(entry => new Option(entry.label, entry.id)));
        selection.value = selected;
        const item = selectedItem();
        const isText = selected !== 'logo';
        find('[data-cover-text-settings]').hidden = !isText;
        find('[data-cover-remove]').hidden = !isText;
        find('[data-cover-add]').disabled = state.texts.length >= 8;
        if (isText && item) all('[data-cover-text]').forEach(input => {
            const value = item[input.dataset.coverText];
            if (input.type === 'checkbox') input.checked = value;
            else input.value = value;
        });
        all('[data-cover-position]').forEach(input => { input.value = item?.[input.dataset.coverPosition] ?? 50; });
        const outputs = { veil: state.veil, logoWidth: state.logo.width, textWidth: isText ? item?.width : 0, x: item?.x, y: item?.y };
        all('[data-cover-output]').forEach(output => { output.value = `${outputs[output.dataset.coverOutput] ?? 0} %`; });
        find('[data-cover-custom-background]').hidden = state.background !== 'custom';
        find('[data-cover-custom-logo]').hidden = state.logo.source !== 'custom';
        // File choosers stay usable while composing; FormData filters unapplied sources.
        backgroundInput.disabled = false;
        logoInput.disabled = false;
    }

    function buttons() {
        if (applyButton) applyButton.disabled = !ready || busy || Boolean(fitError);
        downloadButton.disabled = !ready || busy || Boolean(fitError);
    }

    function changed() {
        revision++;
        dirty = true;
        configInput.disabled = true;
        syncControls();
        scheduleDraw();
        if (standalone) message('Le visuel a changé. Téléchargez le PNG pour récupérer cette version.');
        else if (active) message('Le visuel a changé. Cliquez sur « Utiliser ce visuel » pour actualiser la couverture.');
    }

    function loadImage(url) {
        if (!url) return Promise.reject(new Error('Choisissez à nouveau votre image personnelle.'));
        if (!imageCache.has(url)) imageCache.set(url, new Promise((resolve, reject) => {
            const image = new Image();
            const timeout = setTimeout(() => reject(new Error('L’image met trop de temps à charger. Réessayez.')), 15000);
            image.onload = () => { clearTimeout(timeout); resolve(image); };
            image.onerror = () => { clearTimeout(timeout); reject(new Error('Impossible de charger une image. Choisissez-la à nouveau.')); };
            image.src = url;
        }));
        return imageCache.get(url);
    }

    async function refreshAssets() {
        const current = ++sequence;
        ready = false;
        buttons();
        try {
            const source = state.background === 'genie-civil' ? root.dataset.backgroundUrl : root.dataset.savedBackgroundUrl;
            const logoSource = state.logo.source === 'default' ? root.dataset.logoUrl : root.dataset.savedLogoUrl;
            const loaded = await Promise.all([
                state.background === 'plain' ? null : state.background === 'custom' && customBackground ? customBackground : loadImage(source),
                !state.logo.visible ? null : state.logo.source === 'custom' && customLogo ? customLogo : loadImage(logoSource),
                document.fonts ? Promise.all([document.fonts.load('700 80px "Cover Outfit"'), document.fonts.load('400 40px "Cover Outfit"')]) : null,
            ]);
            if (current !== sequence) return;
            [background, logo] = loaded;
            ready = true;
            draw();
            if (!fitError) message(standalone ? 'Aperçu prêt. Modifiez les textes, puis cliquez sur « Télécharger en PNG ».' : (active && dirty ? 'Cliquez sur « Utiliser ce visuel » pour actualiser la couverture.' : 'Aperçu prêt. Modifiez les textes, puis cliquez sur « Utiliser ce visuel ».'));
        } catch (error) {
            if (current === sequence) message(error.message, true);
        }
        buttons();
    }

    async function readLocalImage(input, limit) {
        const file = input.files[0];
        if (!file) return null;
        if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > limit * 1024 * 1024) {
            throw new Error(`Choisissez une image JPG, PNG ou WebP de ${limit} Mo maximum.`);
        }
        const url = URL.createObjectURL(file);
        try {
            const image = await loadImage(url);
            if (image.naturalWidth > 8000 || image.naturalHeight > 8000 || image.naturalWidth * image.naturalHeight > 40000000) {
                throw new Error('Cette image est trop grande. Réduisez ses dimensions avant de l’utiliser.');
            }
            return image;
        } finally {
            URL.revokeObjectURL(url);
            imageCache.delete(url);
        }
    }

    function wrapLines(context, text, maxWidth) {
        const lines = [];
        for (const paragraph of text.split('\n')) {
            let line = '';
            for (const word of paragraph.split(/\s+/).filter(Boolean)) {
                const combined = line ? `${line} ${word}` : word;
                if (context.measureText(combined).width <= maxWidth) { line = combined; continue; }
                if (line) lines.push(line);
                line = '';
                for (const character of Array.from(word)) {
                    if (line && context.measureText(line + character).width > maxWidth) { lines.push(line); line = ''; }
                    line += character;
                }
            }
            lines.push(line);
        }
        return lines;
    }

    function textLayout(context, item) {
        const maxWidth = width * item.width / 100;
        let size = item.size;
        let lines;
        do {
            context.font = `${item.bold ? 700 : 400} ${size}px ${fonts[item.font]}`;
            lines = wrapLines(context, item.text, maxWidth);
            if (lines.length * size * 1.16 <= height * .84 || size <= 18) break;
            size--;
        } while (true);
        const blockHeight = lines.length * size * 1.16;
        const left = Math.max(32, Math.min(width - maxWidth - 32, width * item.x / 100 - maxWidth / 2));
        const top = Math.max(24, Math.min(height - blockHeight - 24, height * item.y / 100 - blockHeight / 2));
        return { x: left, y: top, w: maxWidth, h: blockHeight, lines, size, overflow: blockHeight > height - 48 };
    }

    function paint(target, withSelection = false) {
        const context = target.getContext('2d');
        context.clearRect(0, 0, width, height);
        context.fillStyle = state.backgroundColor;
        context.fillRect(0, 0, width, height);
        if (background) {
            const scale = Math.max(width / background.naturalWidth, height / background.naturalHeight);
            const w = background.naturalWidth * scale;
            const h = background.naturalHeight * scale;
            context.drawImage(background, (width - w) * state.cropX / 100, (height - h) * state.cropY / 100, w, h);
        }
        context.fillStyle = state.backgroundColor;
        context.globalAlpha = state.veil / 100;
        context.fillRect(0, 0, width, height);
        context.globalAlpha = 1;
        const boxes = [];
        if (state.logo.visible && logo) {
            const w = width * state.logo.width / 100;
            const h = Math.min(height * .55, w * logo.naturalHeight / logo.naturalWidth);
            const actualWidth = h * logo.naturalWidth / logo.naturalHeight;
            const x = Math.max(24, Math.min(width - actualWidth - 24, width * state.logo.x / 100 - actualWidth / 2));
            const y = Math.max(24, Math.min(height - h - 24, height * state.logo.y / 100 - h / 2));
            context.save();
            // Blend away the white paper of the original school JPEG without altering its identity.
            if (state.logo.source === 'default') context.globalCompositeOperation = 'multiply';
            context.drawImage(logo, x, y, actualWidth, h);
            context.restore();
            boxes.push({ id: 'logo', x, y, w: actualWidth, h });
        }
        let overflow = false;
        for (const item of state.texts) {
            const box = textLayout(context, item);
            if (box.overflow) overflow = true;
            context.fillStyle = item.color;
            context.textAlign = item.align;
            context.textBaseline = 'middle';
            const x = box.x + (item.align === 'center' ? box.w / 2 : item.align === 'right' ? box.w : 0);
            box.lines.forEach((line, index) => context.fillText(line, x, box.y + box.size * 1.16 * (index + .5)));
            boxes.push({ ...box, id: item.id });
        }
        if (withSelection) {
            hitboxes = boxes;
            const box = boxes.find(box => box.id === selected);
            if (box) {
                context.strokeStyle = '#a57b38';
                context.lineWidth = 2;
                context.setLineDash([10, 8]);
                context.strokeRect(box.x - 5, box.y - 5, box.w + 10, box.h + 10);
                context.setLineDash([]);
            }
        }
        return overflow;
    }

    function draw() {
        animation = 0;
        if (!ready) return;
        paint(canvas);
        const context = thumbnail.getContext('2d');
        context.clearRect(0, 0, thumbnail.width, thumbnail.height);
        context.drawImage(canvas, 0, 0, thumbnail.width, thumbnail.height);
        fitError = paint(canvas, true) ? 'Un texte est trop long pour le visuel. Réduisez-le ou augmentez la largeur du bloc.' : '';
        if (fitError) message(fitError, true);
        buttons();
    }

    function scheduleDraw() {
        if (!animation) animation = requestAnimationFrame(draw);
    }

    function start() {
        if (started) return;
        started = true;
        syncControls();
        refreshAssets();
    }

    function exportBlob(type) {
        if (!ready || fitError) return Promise.reject(new Error(fitError || 'Attendez le chargement de l’aperçu.'));
        const output = document.createElement('canvas');
        output.width = width;
        output.height = height;
        if (paint(output)) return Promise.reject(new Error('Un texte est trop long pour être exporté.'));
        return new Promise((resolve, reject) => {
            output.toBlob(blob => blob ? resolve(blob) : reject(new Error('Impossible de créer l’image. Réessayez.')), type, .92);
        });
    }

    async function apply() {
        const current = revision;
        busy = true;
        buttons();
        try {
            const blob = await exportBlob('image/webp');
            if (current !== revision) throw new Error('Les réglages ont changé pendant la création. Cliquez à nouveau sur « Utiliser ce visuel ».');
            if (blob.size > 5 * 1024 * 1024) throw new Error('Le visuel dépasse 5 Mo. Choisissez un fond moins détaillé.');
            const extension = blob.type === 'image/webp' ? 'webp' : 'png';
            const transfer = new DataTransfer();
            transfer.items.add(new File([blob], `couverture-${Date.now()}.${extension}`, { type: blob.type }));
            if (!hasApplied) {
                previousFiles = imageInput.files;
                previousPreview = imagePreview.src;
            }
            applying = true;
            imageInput.files = transfer.files;
            imageInput.dispatchEvent(new Event('change', { bubbles: true }));
            applying = false;
            removeImage.checked = false;
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            previewUrl = URL.createObjectURL(blob);
            imagePreview.src = previewUrl;
            configInput.value = JSON.stringify(configuration());
            configInput.disabled = false;
            active = true;
            hasApplied = true;
            dirty = false;
            message('Visuel prêt comme couverture. Cliquez sur « Enregistrer la publication » pour le sauvegarder.');
        } catch (error) {
            applying = false;
            message(error.message, true);
        } finally {
            busy = false;
            buttons();
        }
    }

    all('[data-cover-control]').forEach(input => input.addEventListener('input', () => {
        state[input.dataset.coverControl] = input.type === 'range' ? Number(input.value) : input.value;
        changed();
        if (input.dataset.coverControl === 'background') refreshAssets();
    }));
    all('[data-cover-logo]').forEach(input => input.addEventListener('input', () => {
        state.logo[input.dataset.coverLogo] = input.type === 'checkbox' ? input.checked : input.type === 'range' ? Number(input.value) : input.value;
        changed();
        if (['source', 'visible'].includes(input.dataset.coverLogo)) refreshAssets();
    }));
    all('[data-cover-text]').forEach(input => input.addEventListener('input', () => {
        const item = selectedItem();
        if (!item || selected === 'logo') return;
        const key = input.dataset.coverText;
        item[key] = input.type === 'checkbox' ? input.checked : ['size', 'width'].includes(key) ? Number(input.value) : input.value;
        if (key === 'size') item.size = Math.max(18, Math.min(140, item.size));
        changed();
    }));
    all('[data-cover-position]').forEach(input => input.addEventListener('input', () => {
        selectedItem()[input.dataset.coverPosition] = Number(input.value);
        changed();
    }));
    selection.addEventListener('change', () => { selected = selection.value; syncControls(); scheduleDraw(); });
    find('[data-cover-add]').addEventListener('click', () => {
        if (state.texts.length >= 8) return;
        selected = `text-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        state.texts.push({ id: selected, text: 'Nouveau texte', x: 50, y: 86, size: 36, width: 80, font: 'outfit', bold: false, color: '#18202b', align: 'center' });
        changed();
        find('[data-cover-text="text"]').focus();
    });
    find('[data-cover-remove]').addEventListener('click', () => {
        if (selected === 'logo') return;
        state.texts = state.texts.filter(text => text.id !== selected);
        selected = state.texts[0]?.id || 'logo';
        changed();
    });
    find('[data-cover-center]').addEventListener('click', () => { selectedItem().x = 50; changed(); });

    for (const [input, limit, kind] of [[backgroundInput, 10, 'background'], [logoInput, 5, 'logo']]) {
        input.addEventListener('change', async () => {
            const token = ++localSequence[kind];
            sequence++;
            ready = false;
            changed();
            buttons();
            try {
                const image = await readLocalImage(input, limit);
                if (token !== localSequence[kind]) return;
                if (!image) { refreshAssets(); return; }
                if (kind === 'background') { customBackground = image; state.background = 'custom'; }
                else { customLogo = image; state.logo.source = 'custom'; state.logo.visible = true; }
                changed();
                await refreshAssets();
            } catch (error) {
                if (token !== localSequence[kind]) return;
                input.value = '';
                if (kind === 'background') customBackground = null;
                else customLogo = null;
                message(error.message, true);
            }
        });
    }

    function pointer(event) {
        const box = canvas.getBoundingClientRect();
        return { x: (event.clientX - box.left) * width / box.width, y: (event.clientY - box.top) * height / box.height };
    }
    canvas.addEventListener('pointerdown', event => {
        if (!ready || busy) return;
        const point = pointer(event);
        const hit = [...hitboxes].reverse().find(box => point.x >= box.x && point.x <= box.x + box.w && point.y >= box.y && point.y <= box.y + box.h);
        if (!hit) return;
        selected = hit.id;
        const item = selectedItem();
        drag = { start: point, x: item.x, y: item.y, pointerId: event.pointerId };
        canvas.setPointerCapture(event.pointerId);
        canvas.focus({ preventScroll: true });
        syncControls();
        scheduleDraw();
    });
    canvas.addEventListener('pointermove', event => {
        if (!drag || drag.pointerId !== event.pointerId) return;
        const point = pointer(event);
        const item = selectedItem();
        item.x = Math.round(Math.max(0, Math.min(100, drag.x + (point.x - drag.start.x) / width * 100)) * 2) / 2;
        item.y = Math.round(Math.max(0, Math.min(100, drag.y + (point.y - drag.start.y) / height * 100)) * 2) / 2;
        changed();
    });
    const endDrag = () => { drag = null; };
    canvas.addEventListener('pointerup', endDrag);
    canvas.addEventListener('pointercancel', endDrag);
    canvas.addEventListener('lostpointercapture', endDrag);
    canvas.addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key) || busy) return;
        event.preventDefault();
        const item = selectedItem();
        const step = event.shiftKey ? 2 : .5;
        const axis = ['ArrowLeft', 'ArrowRight'].includes(event.key) ? 'x' : 'y';
        item[axis] = Math.max(0, Math.min(100, item[axis] + (['ArrowLeft', 'ArrowUp'].includes(event.key) ? -step : step)));
        changed();
    });

    applyButton?.addEventListener('click', apply);
    downloadButton.addEventListener('click', async () => {
        busy = true;
        buttons();
        try {
            const blob = await exportBlob('image/png');
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'couverture-publication.png';
            document.body.appendChild(link);
            link.click();
            link.remove();
            if (standalone) message('Image PNG téléchargée. Choisissez ce fichier dans le champ Image de couverture de votre publication.');
            setTimeout(() => URL.revokeObjectURL(url), 30000);
        } catch (error) { message(error.message, true); }
        busy = false;
        buttons();
    });
    if (!standalone) {
        find('[data-cover-cancel]').addEventListener('click', () => {
            if (hasApplied) {
                imageInput.files = previousFiles;
                if (previousFiles.length) {
                    applying = true;
                    imageInput.dispatchEvent(new Event('change', { bubbles: true }));
                    applying = false;
                } else imagePreview.src = previousPreview;
            }
            configInput.disabled = true;
            active = false;
            hasApplied = false;
            dirty = false;
            message('La couverture actuelle est conservée. Vous pouvez continuer à modifier l’article.');
        });
        imageInput.addEventListener('change', () => {
            if (applying) return;
            configInput.disabled = true;
            active = false;
            hasApplied = false;
            dirty = false;
            previousFiles = imageInput.files;
            message('L’image choisie manuellement sera utilisée comme couverture.');
        });
        removeImage.addEventListener('change', () => {
            if (!removeImage.checked) return;
            imageInput.value = '';
            configInput.disabled = true;
            active = false;
            hasApplied = false;
            dirty = false;
            message('L’image par défaut sera utilisée à l’enregistrement.');
        });
        form.addEventListener('submit', event => {
            if (busy || active && dirty) {
                event.preventDefault();
                root.open = true;
                message('Cliquez sur « Utiliser ce visuel » pour appliquer vos derniers réglages avant d’enregistrer.', true);
                applyButton.focus();
            }
        });
        // Personal source files must not be uploaded while merely experimenting in the creator.
        form.addEventListener('formdata', event => {
            if (configInput.disabled || state.background !== 'custom') event.formData.delete('cover_background');
            if (configInput.disabled || state.logo.source !== 'custom') event.formData.delete('cover_logo');
        });
    }
    root.addEventListener('toggle', () => { if (root.open) start(); });
    document.getElementById('cover-open')?.addEventListener('click', () => {
        root.open = true;
        start();
        root.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    if (root.open) start();
})();
