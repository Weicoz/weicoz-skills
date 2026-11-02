import {loop, shell, svgStops} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,{...options,trigger:options.content?.href!==undefined?null:element.querySelector('.showcase-link')});
  const art=element.querySelector('.showcase-art'),type=element.dataset.background||'glow-shapes',id='s'+crypto.randomUUID();
  const defs=`<defs>
  <filter id="${id}-grain"><feTurbulence type="fractalNoise" baseFrequency=".72" numOctaves="2" seed="8" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter>
  <filter id="${id}-edge" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
  <filter id="${id}-fog" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="16"/></filter>
  <radialGradient id="${id}-heart" cx="50%" cy="49%" r="63%">${svgStops([[0.0,"var(--_card-accent-3)",1.0],[0.3,"var(--_card-accent-3)",1.0],[0.56,"var(--_card-accent-2)",1.0],[0.88,"var(--card-accent)",1.0],[1.0,"var(--card-accent)",0.0]])}</radialGradient>
  <linearGradient id="${id}-back" x1="0" y1="0" x2="1" y2="1">${svgStops([[0.0,"var(--card-accent)",1.0],[1.0,"color-mix(in oklab,var(--card-accent) 48%,#10121b)",1.0]])}</linearGradient>
  <pattern id="${id}-grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="white" stroke-opacity=".14" stroke-width=".7"/></pattern>
  <radialGradient id="${id}-fade">${svgStops([[0.0,"white",1.0],[0.62,"white",1.0],[1.0,"black",1.0]])}</radialGradient><mask id="${id}-mask"><rect width="332" height="448" fill="url(#${id}-fade)"/></mask>
  <linearGradient id="${id}-memA" x1="0" y1="0" x2=".4" y2="1">${svgStops([[0.0,"var(--_card-accent-2)",0.04],[0.44,"var(--_card-accent-2)",0.55],[0.51,"white",0.35],[0.62,"var(--card-accent)",0.4],[1.0,"var(--card-accent)",0.04]])}</linearGradient>
  <linearGradient id="${id}-memB" x1="0" y1="0" x2="1" y2="1">${svgStops([[0.0,"var(--_card-accent-3)",0.03],[0.45,"var(--_card-accent-3)",0.46],[0.52,"white",0.32],[0.7,"var(--_card-accent-2)",0.26],[1.0,"var(--card-accent)",0.04]])}</linearGradient>
  </defs>`;
  let content='';
  if(type==='glow-shapes'){
    const paths={heart:'M0 31C-51 0-38-39-15-29Q0-25 0-13Q0-25 15-29C38-39 51 0 0 31Z',circle:'M32 0A32 32 0 1 0-32 0A32 32 0 1 0 32 0',star:'M0-33 9-10 33-10 14 5 21 30 0 15-21 30-14 5-33-10-9-10Z',petal:'M0-36C21-35 35-21 28-4L9 34Q-24 24-24 1Q-19-31 0-36Z'};
    const shape=paths[options.shape||element.dataset.shape]||paths.heart;
    for(let i=0;i<5;i++){const a=-Math.PI/2+i*Math.PI*2/5,x=166+75*Math.cos(a),y=170+75*Math.sin(a),rotation=[-5,14,-9,10,-13][i];content+=`<g transform="translate(${x} ${y}) rotate(${rotation})"><path d="${shape}" fill="var(--card-accent)" opacity=".48" filter="url(#${id}-fog)"/><path d="${shape}" fill="url(#${id}-heart)" filter="url(#${id}-edge)"/><path d="${shape}" transform="scale(.88)" fill="url(#${id}-heart)" opacity=".8"/></g>`;}
  }else if(type==='grid-solid'){
    content=`<rect width="332" height="448" fill="url(#${id}-grid)" mask="url(#${id}-mask)"/><path d="M244 130 70 256 96 303 270 177Z" fill="url(#${id}-back)"/><path d="M70 124 244 130 270 177 96 171Z" fill="var(--card-accent)"/><path d="M70 256 244 262 270 309 96 303Z" fill="var(--card-accent)"/><path d="M244 130 270 177M70 256 96 303" fill="none" stroke="color-mix(in oklab,var(--card-accent) 65%,white)" stroke-width="1"/>`;
  }else if(type==='iso-object'){
    content=`<path d="M156 252 216 216 276 252 216 288Z" fill="#14101c"/><g stroke="#2b1b38" stroke-width=".85" stroke-linejoin="round"><path d="M108 130 168 94 228 130 168 166Z" fill="var(--_card-accent-2)"/><path d="M108 130 168 166 168 246 108 210Z" fill="var(--_card-accent-3)"/><path d="M168 166 228 130 228 210 168 246Z" fill="var(--card-accent)"/></g>`;
  }else if(type==='membrane'){
    content=`<g class="membrane-folds"><path d="M-90 392C26 172 164 433 400-80L455 207C270 357 100 453-90 392Z" fill="url(#${id}-memA)"/><path d="M-69 279C124 418 157-2 399 72L392 436C235 376 110 555-69 279Z" fill="url(#${id}-memB)"/><path d="M-25 364C129 166 211 324 373 91L425 271C266 237 166 424-25 364Z" fill="url(#${id}-memA)" opacity=".7"/><g fill="none" stroke="white" stroke-opacity=".75" stroke-width=".8"><path d="M-90 392C26 172 164 433 400-80"/><path d="M-69 279C124 418 157-2 399 72"/><path d="M-25 364C129 166 211 324 373 91"/></g><g fill="none" stroke="white" stroke-opacity=".18" stroke-width=".4"><path d="M-68 401C51 225 174 426 405-56"/><path d="M-53 409C66 258 201 425 414-32"/><path d="M-48 296C133 412 179 22 405 88"/></g></g>`;
  }
  const hasImage=type==='image'||type==='editorial';
  if(!hasImage)art.innerHTML=`<svg viewBox="0 0 332 448" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">${defs}<g class="showcase-subject">${content}</g><rect width="332" height="448" filter="url(#${id}-grain)" opacity=".06"/></svg>`;
  const fold=art.querySelector('.membrane-folds'),subject=art.querySelector('.showcase-subject');
  const clock=loop(element,t=>{if(fold)fold.setAttribute('transform',`translate(${Math.sin(t/15)*3} ${Math.cos(t/17)*4})`);else if(subject&&type==='glow-shapes')subject.setAttribute('transform',`translate(0 ${Math.sin(t/12)*2})`);},{...options,continuous:!!fold||type==='glow-shapes'});
  
  return {destroy(){clock.destroy();clean();if(!hasImage)art.replaceChildren();}};
}
