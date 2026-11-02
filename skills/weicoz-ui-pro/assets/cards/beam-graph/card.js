import {loop,shell,smooth} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,options);
  const svg=element.querySelector('svg'),id='beam-'+crypto.randomUUID(),defs=svg.querySelector('defs');
  const source=[...svg.querySelectorAll('.beam-base path')];
  defs.innerHTML=`<filter id="${id}-blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3"/></filter>`;
  const beams=source.map((path,i)=>{const gid=id+'-'+i;defs.insertAdjacentHTML('beforeend',`<linearGradient id="${gid}" gradientUnits="userSpaceOnUse"><stop stop-color="var(--card-accent)" stop-opacity="0"/><stop offset=".55" stop-color="var(--card-accent)"/><stop offset="1" stop-color="color-mix(in oklab,var(--card-accent) 25%,white)"/></linearGradient>`);const copies=['beam-glow','beam-light'].map(cls=>{const n=path.cloneNode();n.setAttribute('stroke',`url(#${gid})`);if(cls==='beam-glow')n.setAttribute('filter',`url(#${id}-blur)`);svg.querySelector('.'+cls).append(n);return n;});return {path,length:path.getTotalLength(),gradient:defs.querySelector('#'+gid),copies};});
  const clock=loop(element,time=>{for(const [i,b]of beams.entries()){const phase=((time+i*.71+1)%4)/4,head=phase*(b.length+72),tail=Math.max(0,head-72),a=b.path.getPointAtLength(tail),z=b.path.getPointAtLength(Math.min(head,b.length));for(const [n,v]of [['x1',a.x],['y1',a.y],['x2',z.x],['y2',z.y]])b.gradient.setAttribute(n,v);for(const p of b.copies){p.style.strokeDashoffset=String(72-head);p.style.opacity=String(smooth(head/28)*(1-smooth((head-b.length)/72)));}}},options);
  return {destroy(){clock.destroy();clean();svg.querySelector('.beam-light').replaceChildren();svg.querySelector('.beam-glow').replaceChildren();defs.replaceChildren();}};
}
