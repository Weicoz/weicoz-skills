import {loop,shell,smooth,staticMotion} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,options);
  const chunks=[...element.querySelectorAll('.stream-chunk')],count=element.querySelector('.stream-count'),status=element.querySelector('.stream-status > span'),still=staticMotion(element,options);
  const total=chunks.length,pending=options.content?.pendingStatus ?? '内容陆续就绪',complete=options.content?.completeStatus ?? '全部内容已就绪';
  let previous=-1;
  const clock=loop(element,time=>{
    const staticState=still();let ready=0;
    chunks.forEach((chunk,i)=>{
      const v=staticState?1:smooth((time-.15-i*.65)/.72);
      chunk.style.setProperty('--ready',v);
      chunk.style.setProperty('--skeleton-opacity',1-smooth(v/.38));
      chunk.style.setProperty('--content-opacity',smooth((v-.42)/.58));
      if(v===1)ready++;
    });
    if(ready!==previous){count.textContent=`${ready} / ${total}`;status.textContent=ready===total?complete:pending;previous=ready;}
  },{...options,duration:2.35});
  return{replay:()=>clock.restart(),destroy(){clock.destroy();clean();chunks.forEach(c=>{for(const p of ['--ready','--skeleton-opacity','--content-opacity'])c.style.removeProperty(p);});count.textContent=`${total} / ${total}`;status.textContent=complete;}};
}
