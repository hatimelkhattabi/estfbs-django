'use strict';
document.querySelectorAll('form[data-confirm]').forEach(form => form.addEventListener('submit', event => {
  if (!window.confirm(form.dataset.confirm)) event.preventDefault();
}));
let previewUrl;
document.querySelector('#pub-image-file')?.addEventListener('change', event => {
  const file = event.target.files[0];
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) { alert('L’image doit peser au maximum 5 Mo.'); event.target.value = ''; return; }
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  document.querySelector('#pub-image-preview').src = previewUrl;
});
