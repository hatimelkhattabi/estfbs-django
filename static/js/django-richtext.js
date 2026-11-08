document.addEventListener('DOMContentLoaded',()=>{
  const area=document.querySelector('textarea.est-rich-editor');
  if(!area)return;
  const delta=document.getElementById('id_contenu_delta');
  if(!window.Quill){
    const notice=document.createElement('p');notice.textContent='Mode HTML : l’éditeur visuel est indisponible. Vous pouvez modifier le contenu ci-dessous.';
    area.insertAdjacentElement('beforebegin',notice);
    area.addEventListener('input',()=>{if(delta)delta.value='';});
    return;
  }
  const shell=document.createElement('div');shell.className='est-quill-shell';
  const editor=document.createElement('div');editor.className='est-quill-editor';shell.appendChild(editor);
  area.insertAdjacentElement('afterend',shell);area.classList.add('enhanced');
  const quill=new Quill(editor,{theme:'snow',modules:{toolbar:[[{header:[1,2,3,false]}],['bold','italic','underline','strike'],[{list:'ordered'},{list:'bullet'}],[{align:[]},{direction:'rtl'}],[{color:[]},{background:[]}],['link','blockquote','clean']]}});
  let initial=null;try{initial=JSON.parse(delta?.value||'null');if(typeof initial==='string')initial=JSON.parse(initial);}catch{}
  if(initial?.ops)quill.setContents(initial);else quill.clipboard.dangerouslyPasteHTML(area.value||'');
  function sync(){area.value=quill.root.innerHTML;if(delta)delta.value=JSON.stringify(quill.getContents());}
  quill.on('text-change',sync);area.form?.addEventListener('submit',sync);sync();
  const extra=document.createElement('div');extra.className='est-editor-extra';
  const status=document.createElement('span');status.className='est-upload-status';status.setAttribute('role','status');
  for(const [label,kind,accept] of [['Insérer une image','image','image/jpeg,image/png,image/webp'],['Ajouter un PDF ou un document','document','.pdf,.jpg,.jpeg,.png,.webp']]){
    const button=document.createElement('button');button.type='button';button.textContent=label;
    button.addEventListener('click',()=>{const input=document.createElement('input');input.type='file';input.accept=accept;input.onchange=async()=>{
      if(!input.files[0])return;button.disabled=true;status.textContent='Envoi en cours…';
      try{const data=new FormData();data.append('fichier',input.files[0]);const token=document.querySelector('[name=csrfmiddlewaretoken]')?.value;
      const response=await fetch('/admin/documents',{method:'POST',body:data,headers:{'X-CSRF-TOKEN':token||'','Accept':'application/json'},credentials:'same-origin'});
      const result=await response.json();if(!response.ok)throw new Error(result.message||'Envoi impossible.');
      const range=quill.getSelection(true)||{index:quill.getLength()-1};
      if(kind==='image')quill.insertEmbed(range.index,'image',result.url,'user');
      else quill.insertText(range.index,result.nom||'Consulter le document',{link:result.url},'user');
      sync();status.textContent='Fichier ajouté.';}catch(e){status.textContent=e.message;}finally{button.disabled=false;}
    };input.click();});extra.appendChild(button);
  }extra.appendChild(status);shell.appendChild(extra);
});
