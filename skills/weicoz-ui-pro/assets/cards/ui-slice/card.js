import {loop,shell,smooth,staticMotion} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,options);
  const row=element.querySelector('.slice-demo'),box=row.querySelector('i'),bar=element.querySelector('.slice-progress i'),count=element.querySelector('.slice-count'),still=staticMotion(element,options);
  box.textContent='✓';
  const clock=loop(element,time=>{
    const staticState=still(),p=staticState?1:smooth((time-1.1)/.32),progress=staticState?1:smooth((time-1.2)/.90);
    row.style.setProperty('--task-done',p);row.classList.toggle('checked',p===1);
    bar.style.transform=`scaleX(${(1+progress)/3})`;count.textContent=progress===1?'2 / 3':'1 / 3';
  },{...options,duration:2.3});
  return {replay:()=>clock.restart(),destroy(){clock.destroy();clean();row.classList.remove('checked');row.style.removeProperty('--task-done');box.textContent='';bar.style.removeProperty('transform');count.textContent='1 / 3';}};
}
