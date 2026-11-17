/* Shared, local-only preference. Run in <head> to avoid a dark flash. */
(()=>{
 const key='cosmokontur-theme';let saved=null;
 try{saved=localStorage.getItem(key);}catch(_){}
 const apply=value=>{
  document.documentElement.dataset.theme=value;
  document.documentElement.style.colorScheme=value;
  const button=document.getElementById('themeToggle');
  if(button){button.textContent=value==='light'?'◐ Тёмная тема':'☼ Светлая тема';button.setAttribute('aria-label',value==='light'?'Включить тёмную тему':'Включить светлую тему');}
 };
 apply(saved==='dark'?'dark':'light');
 addEventListener('DOMContentLoaded',()=>{
  apply(document.documentElement.dataset.theme);
  const button=document.getElementById('themeToggle');
  if(button)button.addEventListener('click',()=>{const value=document.documentElement.dataset.theme==='light'?'dark':'light';apply(value);try{localStorage.setItem(key,value);}catch(_){};});
 });
 addEventListener('storage',event=>{if(event.key===key)apply(event.newValue==='dark'?'dark':'light');});
})();
