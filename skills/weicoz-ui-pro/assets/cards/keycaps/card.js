import {loop,shell,smooth,staticMotion} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,options);
  const keys=[...element.querySelectorAll('.keycap')],stage=element.querySelector('.card-stage'),still=staticMotion(element,options);
  const clock=loop(element,time=>{
    const staticState=still();
    keys.forEach((key,i)=>{
      const down=smooth((time-.7-i*.085)/.23),up=smooth((time-1.12-i*.045)/.46);
      key.style.setProperty('--key-press',staticState?0:down*(1-up));
    });
    stage.style.setProperty('--command-visible',staticState?1:smooth((time-.98)/.48));
  },{...options,duration:1.85});
  return {replay:()=>clock.restart(),destroy(){clock.destroy();clean();keys.forEach(k=>k.style.removeProperty('--key-press'));stage.style.removeProperty('--command-visible');}};
}
