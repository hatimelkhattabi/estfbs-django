'use strict';
document.addEventListener('DOMContentLoaded',()=>{
 document.querySelectorAll('[data-gallery]').forEach(gallery=>{
  const entries=[...gallery.querySelectorAll('[data-gallery-entry]')];const empty=gallery.querySelector('[data-gallery-empty]');
  gallery.querySelectorAll('[data-gallery-filter]').forEach(button=>button.addEventListener('click',()=>{
   const type=button.dataset.galleryFilter;let count=0;
   entries.forEach(entry=>{entry.hidden=type!=='all'&&entry.dataset.kind!==type;if(!entry.hidden)count++;else entry.querySelectorAll('video').forEach(video=>video.pause());});
   gallery.querySelectorAll('[data-gallery-filter]').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',String(b===button));});
   if(empty)empty.hidden=count!==0;
  }));
  const dialog=gallery.querySelector('[data-gallery-dialog]');if(!dialog)return;
  gallery.querySelectorAll('[data-gallery-image]').forEach(button=>button.addEventListener('click',()=>{
   dialog.querySelector('[data-gallery-large]').src=button.dataset.galleryImage;dialog.querySelector('[data-gallery-large]').alt=button.dataset.caption||'';dialog.querySelector('[data-gallery-caption]').textContent=button.dataset.caption||'';
   if(typeof dialog.showModal==='function')dialog.showModal();else window.open(button.dataset.galleryImage,'_blank','noopener');
  }));
  gallery.querySelector('[data-gallery-close]')?.addEventListener('click',()=>dialog.close());
  dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});
 });
 const type=document.querySelector('[data-media-type]'),file=document.querySelector('[data-media-file]'),hint=document.querySelector('[data-media-hint]');
 function updateAccept(){if(!type||!file)return;const video=type.value==='video';file.accept=video?'video/mp4,video/webm':'image/jpeg,image/png,image/webp';if(hint)hint.textContent=video?'MP4 / WebM · 100 Mo maximum.':'JPG / PNG / WebP · 5 Mo maximum.';}
 type?.addEventListener('change',()=>{if(file)file.value='';updateAccept();});updateAccept();
});
