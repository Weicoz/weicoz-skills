import {loop, watchColors, shell, mix, clamp, staticMotion} from '../shared/runtime.js';
import {coatedSurface} from './material.js';

export function mount(element, options = {}) {
  const variant=options.variant ?? element.dataset.variant ?? 'token';
  const cleanShell=shell(element,{...options,variant:variant==='card'?'card':'token'});
  const surface=coatedSurface(element.querySelector('.flow-surface'));
  const card=element.querySelector('.physical-card');
  let palette,x=0,y=0,tx=0,ty=0;
  const still=staticMotion(element,options);
  const draw=(time,dt)=>{
    if(still())x=y=tx=ty=0;
    if(dt || still()){
      const ease=1-Math.exp(-dt*7);x=mix(x,tx,ease);y=mix(y,ty,ease);
      card.style.transform=`rotateX(${-y*5}deg) rotateY(${x*7}deg)`;
    }
    surface.draw(time,palette,[x,y]);
    element.style.setProperty('--token-pulse',still()?.8:.65+.35*(.5+.5*Math.sin(time*2.2)));
  };
  const clock=loop(element,draw,{...options,settled:()=>Math.abs(x-tx)+Math.abs(y-ty)<.001});
  const off=watchColors(element,p=>{palette=p;clock.invalidate();});
  const ro=new ResizeObserver(()=>{surface.resize();clock.invalidate();});ro.observe(card);
  const move=e=>{if(e.pointerType==='touch' || still())return;const r=element.getBoundingClientRect();tx=clamp((e.clientX-r.left)/r.width*2-1,-1,1);ty=clamp((e.clientY-r.top)/r.height*2-1,-1,1);};
  const leave=()=>{tx=ty=0;};
  element.addEventListener('pointermove',move);element.addEventListener('pointerleave',leave);element.addEventListener('pointercancel',leave);
  return {destroy(){clock.destroy();off();ro.disconnect();surface.destroy();cleanShell();element.removeEventListener('pointermove',move);element.removeEventListener('pointerleave',leave);element.removeEventListener('pointercancel',leave);card.style.removeProperty('transform');element.style.removeProperty('--token-pulse');}};
}
