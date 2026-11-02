import {shell,loop,staticMotion,smooth} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,options),still=staticMotion(element,options),button=element.querySelector('.size-toggle');let value=0,target=1,clock,destroyed=false;
  const animate=next=>{const from=value;target=next;clock?.destroy();button.setAttribute('aria-pressed',String(!!target));button.firstChild.textContent=target?'收起尺寸 ':'比较尺寸 ';clock=loop(element,time=>{value=still()?target:from+(target-from)*smooth(time/.9);element.style.setProperty('--spread',value);},{...options,duration:.9});};
  const toggle=()=>animate(target?0:1);button.addEventListener('click',toggle);animate(1);
  return{replay(){if(!destroyed){value=0;animate(1);}},destroy(){if(destroyed)return;destroyed=true;clock.destroy();button.removeEventListener('click',toggle);clean();element.style.removeProperty('--spread');}};
}
