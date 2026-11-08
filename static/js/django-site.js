document.addEventListener('DOMContentLoaded',()=>{
 for(const form of document.querySelectorAll('[data-est-api-form]'))form.addEventListener('submit',async event=>{
  event.preventDefault();const output=form.querySelector('[data-api-result]');const button=form.querySelector('button[type=submit],button');if(button)button.disabled=true;
  try{const response=await fetch(form.action,{method:'POST',body:new FormData(form),credentials:'same-origin',headers:{Accept:'application/json'}});const data=await response.json();
   if(!response.ok)throw new Error(Object.values(data.errors||{}).flat().map(x=>x.message||x).join(' ')||data.message||'Envoi impossible.');
   output.textContent=data.message+(data.code_suivi?' Code de suivi : '+data.code_suivi:'');form.reset();
   if(data.code_suivi){const link=document.createElement('a');link.href='/suivi.php?code='+encodeURIComponent(data.code_suivi);link.textContent=' Suivre ma demande →';output.appendChild(link);}
  }catch(e){output.textContent=e.message;}finally{if(button)button.disabled=false;}
 });
});
