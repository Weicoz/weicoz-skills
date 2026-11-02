const query=new URLSearchParams(location.search);
let theme=query.get('theme')==='dark'||query.get('state')==='dark'?'dark':'light';
const cards=[...document.querySelectorAll('[data-card]')];
const title=['top','bottom'].includes(query.get('title'))?query.get('title'):'default',motion=query.get('motion')||'auto';
function setAttribute(attribute,value){if(attribute==='material')document.documentElement.dataset.material=value;for(const card of cards){if(attribute==='title'&&value==='default')delete card.dataset.title;else card.dataset[attribute]=value;}}
setAttribute('title',title);setAttribute('motion',motion);
const effects=['none','tilt','glow','tilt glow'].includes(query.get('effects'))?query.get('effects'):'none';
setAttribute('effects',effects);
const finishChoices={shadow:['auto','none','contact','lifted'],material:['plain','metal','glass','solid']},finishKey='oil.cards.finish.v2';
let savedFinish={};try{savedFinish=JSON.parse(localStorage.getItem(finishKey)) || {};}catch{}
const requestedMaterial=finishChoices.material.includes(query.get('material'))?query.get('material'):null;
const finish={
  material:requestedMaterial || (finishChoices.material.includes(savedFinish.material)?savedFinish.material:'plain'),
  shadow:finishChoices.shadow.includes(query.get('shadow'))?query.get('shadow'):requestedMaterial?'auto':finishChoices.shadow.includes(savedFinish.shadow)?savedFinish.shadow:'auto'
};
for(const [key,value] of Object.entries(finish))setAttribute(key,value);
for(const control of document.querySelectorAll('[data-attribute]')){
  control.value=({title,motion,effects,...finish})[control.dataset.attribute];
  control.addEventListener('change',()=>{
    const key=control.dataset.attribute;setAttribute(key,control.value);
    if(Object.hasOwn(finishChoices,key)){
      finish[key]=control.value;
      if(key==='material'){finish.shadow='auto';setAttribute('shadow','auto');document.querySelector('[data-attribute=shadow]').value='auto';}
      try{localStorage.setItem(finishKey,JSON.stringify(finish));}catch{}
    }
  });
}
function appearance(){
  document.documentElement.dataset.theme=theme;
  const [a,b,c]=paletteEditor.colors;
  document.documentElement.style.setProperty('--gallery-accent',a);
  for(const card of cards){card.style.setProperty('--card-accent',a);card.style.setProperty('--card-accent-2',b);card.style.setProperty('--card-accent-3',c);card.style.setProperty('--card-radius',document.querySelector('#radius').value+'px');card.dispatchEvent(new Event('card-theme-change'));}
  for(const button of document.querySelectorAll('[data-theme-choice]')){const active=button.dataset.themeChoice===theme;button.classList.toggle('selected',active);button.setAttribute('aria-pressed',active);}
}
const paletteEditor=modules['gallery-palette.js'].createPaletteEditor({query,onChange:appearance});
const catalog=modules['gallery-catalog.js'].createCatalog(query);
appearance();
const focus=query.get('focus');
if(focus){document.body.classList.add('focus-only');if(['line-ribbons','metric','promo-band','showcase','explorations','peer-cards'].includes(focus))document.body.classList.add('focus-wide');document.querySelector(`[data-template="${CSS.escape(focus)}"]`)?.classList.add('focused');}
const original=cards.map(card=>card.innerHTML);
function flowVariant(value){document.querySelector('.flow-object').dataset.variant=value;for(const b of document.querySelectorAll('[data-flow-variant]'))b.setAttribute('aria-pressed',String(b.dataset.flowVariant===value));}
function globeMode(value){document.querySelector('.dot-globe').dataset.mode=value;for(const b of document.querySelectorAll('[data-globe-mode]'))b.setAttribute('aria-pressed',String(b.dataset.globeMode===value));}
flowVariant(query.get('variant')==='card'?'card':'token');globeMode(query.get('mode')==='mesh'?'mesh':'globe');
for(const b of document.querySelectorAll('[data-flow-variant]'))b.addEventListener('click',()=>flowVariant(b.dataset.flowVariant));
for(const b of document.querySelectorAll('[data-globe-mode]'))b.addEventListener('click',()=>globeMode(b.dataset.globeMode));
let scene=Object.hasOwn(contentScenes,query.get('content'))?query.get('content'):'studio',mounts=[];
function mountScene(){
  mounts.forEach(instance=>instance.destroy());
  cards.forEach((card,i)=>{card.innerHTML=original[i];});
  mounts=cards.map(card=>modules[card.dataset.card+'/card.js'].mount(card,{speed:Number(query.get('speed')??1),content:contentScenes[scene][card.dataset.example || card.dataset.card] || {}}));
  ribbonRenderer(selectedRenderer);
}
let selectedRenderer=['webgl','dots','grid'].includes(query.get('ribbons'))?query.get('ribbons'):'svg';
mountScene();
const sceneControl=document.querySelector('#content-scene');sceneControl.value=scene;
sceneControl.addEventListener('change',()=>{scene=sceneControl.value;mountScene();});
for(const button of document.querySelectorAll('[data-replay]'))button.addEventListener('click',()=>{
  mounts.forEach((instance,i)=>{if(button.dataset.replay==='all' || cards[i].dataset.card===button.dataset.replay)instance.replay?.();});
});
function ribbonRenderer(value){const ribbon=mounts[cards.findIndex(card=>card.dataset.card==='line-ribbons')];const actual=ribbon.setRenderer(value);selectedRenderer=actual;for(const b of document.querySelectorAll('[data-ribbon-renderer]'))b.setAttribute('aria-pressed',String(b.dataset.ribbonRenderer===actual));}
for(const b of document.querySelectorAll('[data-ribbon-renderer]'))b.addEventListener('click',()=>ribbonRenderer(b.dataset.ribbonRenderer));
for(const button of document.querySelectorAll('[data-theme-choice]'))button.addEventListener('click',()=>{theme=button.dataset.themeChoice;appearance();});
document.querySelector('#radius').addEventListener('input',e=>{document.querySelector('.radius-control output').value=e.target.value;appearance();});
for(const button of document.querySelectorAll('[data-slide]'))button.addEventListener('click',()=>document.querySelector('.showcase-row').scrollBy({left:Number(button.dataset.slide)*348,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'}));
window.addEventListener('pagehide',event=>{if(!event.persisted){mounts.forEach(instance=>instance.destroy());paletteEditor.destroy();catalog.destroy();}});
