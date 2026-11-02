import {shell,loop,svgStops} from '../shared/runtime.js';
import {createSurface} from './surface.js';
export function mount(element, options = {}) {
  const clean=shell(element,options);
  const svg=element.querySelector('.ribbon-art'),ns='http://www.w3.org/2000/svg';
  // Unique IDs per instance, no shared counters or page-singleton assumptions.
  const id='ribbon-'+crypto.randomUUID();
  svg.innerHTML=`<defs><linearGradient id="${id}" x1="0" y1="1" x2="1" y2="0">${svgStops([[0.0,"var(--_card-accent-2)",1.0],[0.5,"var(--_card-accent-2)",1.0],[1.0,"var(--card-accent)",1.0]])}</linearGradient></defs>`;
  const ribbons=[
    [[-160,390,210,285,850,410,1350,-170],[-160,460,430,465,775,250,1390,-50]],
    [[-170,455,400,540,800,50,1120,-210],[-170,310,490,640,855,250,1300,-40]],
    [[280,650,650,180,1110,500,1420,60],[480,680,730,420,1150,80,1450,320]]
  ];
  for(let r=0;r<ribbons.length;r++)for(let i=0;i<128;i++){
    const t=(1-Math.cos(Math.PI*i/127))/2,[a,b]=ribbons[r],p=a.map((n,j)=>n+(b[j]-n)*t);
    const path=document.createElementNS(ns,'path');path.setAttribute('d',`M${p[0]} ${p[1]}C${p.slice(2).join(' ')}`);path.setAttribute('fill','none');path.setAttribute('stroke',`url(#${id})`);path.setAttribute('stroke-width','.8');path.setAttribute('opacity',String(r===1?.64:.46));svg.append(path);
  }
  let surface=null,destroyed=false;
  const frame=()=>svg.setAttribute('viewBox',element.clientWidth<=650?'100 60 560 474':'0 0 1280 474');
  const framing=new ResizeObserver(frame);framing.observe(element);frame();
  const clock=loop(element,t=>{if(surface)surface.draw(t);svg.style.transform=`translate(${Math.sin(t/17)*5}px,${Math.sin(t/19)*3}px)`;},options);
  const setRenderer=value=>{if(destroyed)return null;surface?.destroy();surface=null;if(['webgl','dots','grid'].includes(value))surface=createSurface(element,ribbons,()=>clock.invalidate(),value);const actual=surface?value:'svg';element.dataset.renderer=actual;clock.invalidate();return actual;};
  if(['webgl','dots','grid'].includes(element.dataset.renderer))setRenderer(element.dataset.renderer);
  
  return {setRenderer,destroy(){if(destroyed)return;destroyed=true;clock.destroy();surface?.destroy();surface=null;framing.disconnect();clean();svg.replaceChildren();svg.style.removeProperty('transform');}};
}
