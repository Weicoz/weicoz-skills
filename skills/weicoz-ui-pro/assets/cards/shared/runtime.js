import {applyContent} from './content.js';
export const TAU = Math.PI * 2;
export const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
export const mix = (a, b, t) => a + (b - a) * t;
export const smooth = t => { t=clamp(t);return t*t*t*(t*(t*6-15)+10); };
export function staticMotion(element, options={}) {
  const media=matchMedia('(prefers-reduced-motion: reduce)');
  return ()=>Number(options.speed)===0 || media.matches || element.closest('[data-motion]')?.dataset.motion==='off';
}
export function random(seed = 17) {
  return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t ^= t + Math.imul(t ^ t >>> 7, 61 | t); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}
/* Original triangular-lattice 2D simplex implementation, deterministic gradients. */
export function simplex(seed = 43) {
  const rng = random(seed), p = Array.from({length: 256}, (_, i) => i);
  for (let i = 255; i; i--) { const j = Math.floor(rng() * (i + 1)); [p[i], p[j]] = [p[j], p[i]]; }
  const perm = [...p, ...p], grads = Array.from({length: 8}, (_, i) => [Math.cos(i * TAU / 8), Math.sin(i * TAU / 8)]);
  return (x, y) => {
    const s = (x + y) * .3660254038, i = Math.floor(x + s), j = Math.floor(y + s), u = (i + j) * .2113248654;
    const x0 = x - i + u, y0 = y - j + u, a = x0 > y0 ? 1 : 0, b = 1 - a;
    const xs = [x0, x0 - a + .2113248654, x0 - .5773502692], ys = [y0, y0 - b + .2113248654, y0 - .5773502692];
    let n = 0;
    for (let k = 0; k < 3; k++) {
      const ii = i + (k === 1 ? a : k), jj = j + (k === 1 ? b : k), g = grads[perm[(ii & 255) + perm[jj & 255]] & 7];
      const h = Math.max(0, .5 - xs[k] * xs[k] - ys[k] * ys[k]);
      n += h ** 4 * (xs[k] * g[0] + ys[k] * g[1]);
    }
    return n * 70;
  };
}
export function colors(element) {
  const cs = getComputedStyle(element), c = document.createElement('canvas'); c.width = c.height = 1;
  const ctx = c.getContext('2d', {willReadFrequently: true});
  const read = name => {
    ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = cs.getPropertyValue(name).trim(); ctx.fillRect(0, 0, 1, 1);
    return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3).map(n => n / 255);
  };
  return {a: read('--card-accent'), b: read('--_card-accent-2'), c: read('--_card-accent-3'), surface: read('--card-surface'), dark: cs.getPropertyValue('--card-surface').trim() === '#14171e'};
}
export const rgb = (c, alpha = 1) => `rgba(${c.map(n => Math.round(n * 255)).join(',')},${alpha})`;
export function mixColor(a, b, t) {
  const linear = c => c.map(n => n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4);
  const lab = c => {const [r,g,b]=linear(c),l=Math.cbrt(.412221*r+.536333*g+.051446*b),m=Math.cbrt(.211903*r+.680700*g+.107397*b),s=Math.cbrt(.088302*r+.281719*g+.629979*b);return [.210454*l+.793618*m-.004072*s,1.977998*l-2.428592*m+.450594*s,.025904*l+.782772*m-.808676*s];};
  const A=lab(a),B=lab(b),[L,x,y]=A.map((n,i)=>mix(n,B[i],t)),l=(L+.396338*x+.215804*y)**3,m=(L-.105561*x-.063854*y)**3,s=(L-.089484*x-1.291486*y)**3;
  return [4.076742*l-3.307711*m+.230970*s,-1.268438*l+2.609757*m-.341319*s,-.004196*l-.703419*m+1.707615*s].map(n=>clamp(n<=.0031308?12.92*n:1.055*Math.max(0,n)**(1/2.4)-.055));
}
/* SVG has no OKLab interpolation mode. Dense OKLab stops preserve the palette. */
export function svgStops(stops) {
  return stops.flatMap(([x,c,a=1],i)=>{
    if(i===stops.length-1)return [`<stop offset="${x}" stop-color="${c}" stop-opacity="${a}"/>`];
    const [nx,nc,na=1]=stops[i+1];
    return Array.from({length:8},(_,j)=>{const t=j/8,color=j?`color-mix(in oklab,${c} ${(1-t)*100}%,${nc})`:c;return `<stop offset="${x+(nx-x)*t}" stop-color="${color}" stop-opacity="${a+(na-a)*t}"/>`;});
  }).join('');
}
export const glColor = `
vec3 lab(vec3 c){c=mix(c/12.92,pow((c+.055)/1.055,vec3(2.4)),step(vec3(.04045),c));vec3 lms=vec3(dot(c,vec3(.412221,.536333,.051446)),dot(c,vec3(.211903,.680700,.107397)),dot(c,vec3(.088302,.281719,.629979)));lms=pow(max(lms,0.),vec3(1./3.));return vec3(dot(lms,vec3(.210454,.793618,-.004072)),dot(lms,vec3(1.977998,-2.428592,.450594)),dot(lms,vec3(.025904,.782772,-.808676)));}
vec3 srgb(vec3 c){float l=c.x+.396338*c.y+.215804*c.z,m=c.x-.105561*c.y-.063854*c.z,s=c.x-.089484*c.y-1.291486*c.z;l=l*l*l;m=m*m*m;s=s*s*s;vec3 v=max(vec3(4.076742*l-3.307711*m+.230970*s,-1.268438*l+2.609757*m-.341319*s,-.004196*l-.703419*m+1.707615*s),0.);return clamp(mix(v*12.92,1.055*pow(v,vec3(1./2.4))-.055,step(vec3(.0031308),v)),0.,1.);}
vec3 pigment(vec3 a,vec3 b,float t){return srgb(mix(lab(a),lab(b),t));}
`;
export function watchColors(element, fn) {
  let signature = '';
  const update = () => {
    const cs = getComputedStyle(element), next = ['--card-accent','--_card-accent-2','--_card-accent-3','--card-surface'].map(n => cs.getPropertyValue(n)).join('|');
    if (next !== signature) { signature = next; fn(colors(element)); }
  };
  const observer = new MutationObserver(update);
  for (let p = element; p; p = p.parentElement) observer.observe(p, {attributes: true, attributeFilter: ['style','data-theme','class']});
  element.addEventListener('card-theme-change', update); update();
  return () => { observer.disconnect(); element.removeEventListener('card-theme-change', update); };
}
/* Timeline motion eases to rest; pointer damping keeps real dt until settled. */
export function loop(element, draw, {continuous = true, speed = 1, duration = Infinity, settled = () => true} = {}) {
  let visible=false,hovered=element.matches(':hover'),id=0,elapsed=0,previous=0,destroyed=false,started=false;
  const rate=Number.isFinite(Number(speed)) && Number(speed)>=0?Number(speed):1;
  const media=matchMedia('(prefers-reduced-motion: reduce)');
  const finite=Number.isFinite(duration),mode=()=>element.closest('[data-motion]')?.dataset.motion || 'auto';
  let activity=mode()==='hover'?0:1;
  const allowed=()=>continuous && rate>0 && visible && !document.hidden && !media.matches && mode()!=='off';
  const running=()=>allowed() && elapsed<duration && (mode()!=='hover' || hovered || (finite && started) || (!finite && (activity>0 || !settled())));
  const stop=()=>{cancelAnimationFrame(id);id=0;previous=0;};
  const tick=now=>{
    id=0;
    if(destroyed || !running()){stop();element.dataset.paused='true';return;}
    const dt=Math.min(now-previous,64)/1000*rate;previous=now;started=true;
    const target=mode()!=='hover' || hovered?1:0,before=activity;
    activity=mix(activity,target,1-Math.exp(-dt*(target?18:10)));
    if(!target && activity<.002)activity=0;
    // A short demonstration finishes once started; continuous art slows to a stop.
    elapsed=Math.min(duration,elapsed+dt*(finite?1:(before+activity)*.5));
    draw(elapsed,dt);
    if(running())id=requestAnimationFrame(tick);else{stop();element.dataset.paused='true';}
  };
  const sync=()=>{
    if(destroyed)return;
    if(finite && (!rate || media.matches || mode()==='off'))elapsed=duration;
    const active=running();element.dataset.paused=String(!active);
    if(active){if(!id){previous=performance.now();id=requestAnimationFrame(tick);}}
    else{stop();draw(elapsed,0);}
  };
  const enter=()=>{hovered=true;sync();},leave=()=>{hovered=false;sync();};
  const io=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();});io.observe(element);
  const observer=new MutationObserver(sync);
  for(let p=element;p;p=p.parentElement)observer.observe(p,{attributes:true,attributeFilter:['data-motion']});
  element.addEventListener('pointerenter',enter);element.addEventListener('pointerleave',leave);element.addEventListener('pointercancel',leave);
  document.addEventListener('visibilitychange',sync);media.addEventListener('change',sync);
  draw(0,0);
  return {invalidate(){if(!destroyed)draw(elapsed,0);},restart(){if(!destroyed){elapsed=0;started=false;sync();}},destroy(){destroyed=true;stop();io.disconnect();observer.disconnect();document.removeEventListener('visibilitychange',sync);media.removeEventListener('change',sync);element.removeEventListener('pointerenter',enter);element.removeEventListener('pointerleave',leave);element.removeEventListener('pointercancel',leave);delete element.dataset.paused;}};
}
export function fitCanvas(canvas, scale = 1) {
  const width=canvas.clientWidth,height=canvas.clientHeight,dpr = Math.min(devicePixelRatio || 1, 2.5) * scale;
  const w = Math.max(1, Math.round(width * dpr)), h = Math.max(1, Math.round(height * dpr));
  if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
  return {w: width, h: height, dpr};
}
export function glProgram(canvas, vertex, fragment) {
  const gl = canvas.getContext('webgl', {alpha: true, antialias: false, premultipliedAlpha: true});
  if (!gl) return null;
  gl.getExtension('OES_standard_derivatives');
  const program = gl.createProgram(), shaders = [];
  try {
    for (const [type, source] of [[gl.VERTEX_SHADER,vertex], [gl.FRAGMENT_SHADER,fragment]]) {
      const s = gl.createShader(type); shaders.push(s); gl.shaderSource(s, source); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      gl.attachShader(program, s);
    }
    gl.linkProgram(program); if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
    gl.useProgram(program);
  } catch (_) { shaders.forEach(s => gl.deleteShader(s)); gl.deleteProgram(program);gl.getExtension('WEBGL_lose_context')?.loseContext();canvas.width=canvas.height=1;return null; }
  const buffers = [];let disposed=false;
  return {gl, program, uniform(name) { return gl.getUniformLocation(program, name); }, attribute(name, data, size) {
    const b = gl.createBuffer(); buffers.push(b); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
    const p = gl.getAttribLocation(program, name); gl.enableVertexAttribArray(p); gl.vertexAttribPointer(p, size, gl.FLOAT, false, 0, 0);
  }, destroy() {
    if(disposed)return;disposed=true;
    buffers.forEach(b => gl.deleteBuffer(b)); shaders.forEach(s => gl.deleteShader(s)); gl.deleteProgram(program);
    gl.getExtension('WEBGL_lose_context')?.loseContext();canvas.width=canvas.height=1;
  }};
}
export const glNoise = `
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
vec2 grad(vec2 p){float a=hash(p)*6.2831853;return vec2(cos(a),sin(a));}
float simplex(vec2 p){
 vec2 i=floor(p+(p.x+p.y)*.3660254); vec2 x=p-i+(i.x+i.y)*.2113249;
 vec2 j=x.x>x.y?vec2(1,0):vec2(0,1);vec2 y=x-j+.2113249,z=x-.5773503;
 vec3 h=max(.5-vec3(dot(x,x),dot(y,y),dot(z,z)),0.);h=h*h*h*h;
 return 70.*dot(h,vec3(dot(grad(i),x),dot(grad(i+j),y),dot(grad(i+1.),z)));
}`;
export function shell(element, options = {}) {
  // Apply the public contract before a component measures, reads colors or draws.
  const attributes=new Map();
  for(const key of ['theme','motion','variant','effects','shadow','material']){
    const value=options[key];
    if(value===undefined || (key==='theme' && !['light','dark'].includes(value)) || (key==='motion' && !['auto','hover','off'].includes(value)))continue;
    attributes.set(key,element.getAttribute('data-'+key));element.dataset[key]=String(value);
  }
  applyContent(element,options.content);
  const button = options.trigger ?? null;
  const rate=Number.isFinite(Number(options.speed ?? 1)) && Number(options.speed ?? 1)>=0?Number(options.speed ?? 1):1;
  const media=matchMedia('(prefers-reduced-motion: reduce)');
  const still=()=>!rate || element.closest('[data-motion]')?.dataset.motion==='off' || media.matches;
  let x=0,y=0,tx=0,ty=0,rx=0,ry=0,trx=0,try_=0,on=false,frame=0,previous=0,destroyed=false,entryRect=null;
  let dialog=null,placeholder=null,animation=null,lightX=0,lightY=0;
  const surface=element.querySelector('.showcase-window') || element;
  // A separate background layer leaves artwork pseudo-elements and text intact.
  const finish=document.createElement('span');finish.className='card-finish';finish.setAttribute('aria-hidden','true');surface.prepend(finish);
  const effects=()=>new Set((element.dataset.effects || '').split(/\s+/));
  const enabled=()=>{const e=effects();return !dialog && !still() && (e.has('glow') || e.has('tilt'));};
  const paint = () => {
    element.style.setProperty('--pointer-x',`${x-lightX}px`);element.style.setProperty('--pointer-y',`${y-lightY}px`);
    element.style.setProperty('--_card-rotate-x',`${rx}deg`);element.style.setProperty('--_card-rotate-y',`${ry}deg`);
  };
  const stop = () => {cancelAnimationFrame(frame);frame=0;previous=0;};
  const reset = () => {on=false;stop();rx=ry=trx=try_=0;entryRect=null;element.style.setProperty('--pointer-on',0);paint();};
  const schedule = () => {if(!frame && !destroyed){previous=performance.now();frame=requestAnimationFrame(follow);}};
  const leave = () => {
    on=false;entryRect=null;trx=try_=0;element.style.setProperty('--pointer-on',0);
    if(document.hidden || !enabled()){reset();return;}
    if(Math.abs(rx)+Math.abs(ry)>.005)schedule();else stop();
  };
  const follow = now => {
    frame=0;
    if(destroyed || document.hidden || !enabled()){reset();return;}
    const dt=Math.min(now-previous,64)/1000*rate;previous=now;
    const ease=1-Math.exp(-dt*(on?18:10));
    if(on){x=mix(x,tx,ease);y=mix(y,ty,ease);}
    rx=mix(rx,trx,ease);ry=mix(ry,try_,ease);
    const positionDone=!on || Math.abs(x-tx)+Math.abs(y-ty)<.1;
    const rotationDone=Math.abs(rx-trx)+Math.abs(ry-try_)<.005;
    if(positionDone && on){x=tx;y=ty;}if(rotationDone){rx=trx;ry=try_;}
    paint();
    if(!positionDone || !rotationDone)frame=requestAnimationFrame(follow);else previous=0;
  };
  const move = e => {
    if(e.pointerType==='touch' || document.hidden || !enabled()){reset();return;}
    // A fixed entry rectangle avoids feeding the tilted bounds back into tilt.
    const r=entryRect || (entryRect=element.getBoundingClientRect());
    tx=e.clientX-r.left-element.clientLeft;ty=e.clientY-r.top-element.clientTop;
    const active=effects();
    trx=active.has('tilt')?-clamp((e.clientY-r.top)/r.height*2-1,-1,1)*2.4:0;
    try_=active.has('tilt')?clamp((e.clientX-r.left)/r.width*2-1,-1,1)*2.4:0;
    if(!on){x=tx;y=ty;on=true;paint();}
    element.style.setProperty('--pointer-on',active.has('glow')?1:0);
    if(Math.abs(x-tx)+Math.abs(y-ty)>=.1 || Math.abs(rx-trx)+Math.abs(ry-try_)>=.005)schedule();
  };
  const sync = () => {element.toggleAttribute('data-static-motion',still());if(document.hidden || !enabled())reset();else if(on){const active=effects();if(!active.has('tilt'))trx=try_=rx=ry=0;element.style.setProperty('--pointer-on',active.has('glow')?1:0);paint();}};
  const observer=new MutationObserver(()=>{measure();sync();});
  for(let p=element;p;p=p.parentElement)observer.observe(p,{attributes:true,attributeFilter:['data-motion','data-effects','data-title']});
  const io=new IntersectionObserver(entries=>{if(!entries[0].isIntersecting)reset();});io.observe(element);
  const heading=element.querySelector(':scope > .card-heading, :scope > .card-caption, :scope > .metric-copy');
  const measure=()=>{if(heading)element.style.setProperty('--_card-heading-height',`${heading.offsetHeight}px`);if(surface!==element){lightX=surface.offsetLeft;lightY=surface.offsetTop;}};
  const ro=new ResizeObserver(()=>{measure();if(on)leave();});ro.observe(element);if(heading)ro.observe(heading);measure();
  element.addEventListener('pointerenter',move);element.addEventListener('pointermove',move);element.addEventListener('pointerleave',leave);element.addEventListener('pointercancel',leave);
  document.addEventListener('visibilitychange',sync);media.addEventListener('change',sync);
  sync();
  window.addEventListener('scroll',leave,{passive:true,capture:true});
  const restore = () => {
    if (!dialog) return; reset(); animation?.cancel(); placeholder.replaceWith(element); dialog.remove(); dialog=null; placeholder=null;
    element.dispatchEvent(new Event('card-theme-change')); button?.focus({preventScroll:true});
  };
  const close = () => {
    if (!dialog) return;
    if (still()) { restore(); return; }
    const from=element.getBoundingClientRect(), to=placeholder.getBoundingClientRect();
    animation=element.animate([{transform:'none'},{transform:`translate(${to.left-from.left}px,${to.top-from.top}px) scale(${to.width/from.width},${to.height/from.height})`}],{duration:450/rate,easing:'cubic-bezier(.165,.84,.44,1)',fill:'forwards'});
    animation.finished.then(restore).catch(()=>{});
  };
  const open = event => {
    if(button?.tagName === 'A') { if(!button.getAttribute('href')?.startsWith('#'))return; event?.preventDefault(); }
    if (dialog) return; reset(); const from=element.getBoundingClientRect();
    placeholder=document.createElement('div');placeholder.style.cssText=`height:${from.height}px;width:100%`;element.before(placeholder);
    dialog=document.createElement('dialog');dialog.className=`card-dialog ${element.classList.contains('showcase-card')?'showcase-dialog':element.classList.contains('banner') || element.classList.contains('strip')?'wide':''}`;
    dialog.setAttribute('aria-label',element.querySelector('h2, .showcase-wordmark')?.textContent || '查看卡片');
    const cs=getComputedStyle(element);
    // The element changes parent; carry its inherited host typography with it.
    dialog.style.font=cs.font;
    for(const n of ['--card-accent','--card-accent-2','--card-accent-3','--card-radius']) {const value=cs.getPropertyValue(n).trim();if(value)dialog.style.setProperty(n,value);}
    dialog.dataset.theme=element.closest('[data-theme]')?.dataset.theme || 'light';
    dialog.dataset.motion=element.closest('[data-motion]')?.dataset.motion || 'auto';
    const exit=document.createElement('button');exit.className='dialog-close';exit.textContent='×';exit.setAttribute('aria-label','关闭');exit.addEventListener('click',close);
    dialog.append(element,exit);document.body.append(dialog);dialog.showModal();
    dialog.addEventListener('cancel',e=>{e.preventDefault();close();});dialog.addEventListener('click',e=>{if(e.target===dialog)close();});
    const to=element.getBoundingClientRect();
    if(!still()) animation=element.animate([{transform:`translate(${from.left-to.left}px,${from.top-to.top}px) scale(${from.width/to.width},${from.height/to.height})`},{transform:'none'}],{duration:700/rate,easing:'cubic-bezier(.165,.84,.44,1)'});
    element.dispatchEvent(new Event('card-theme-change'));
  };
  button?.addEventListener('click',open);
  return () => { if(destroyed)return;destroyed=true;restore();stop();finish.remove();observer.disconnect();io.disconnect();ro.disconnect();window.removeEventListener('scroll',leave,true);media.removeEventListener('change',sync);document.removeEventListener('visibilitychange',sync);element.removeEventListener('pointerenter',move);element.removeEventListener('pointermove',move);element.removeEventListener('pointerleave',leave);element.removeEventListener('pointercancel',leave);button?.removeEventListener('click',open);element.removeAttribute('data-static-motion');element.style.removeProperty('--pointer-on');element.style.removeProperty('--pointer-x');element.style.removeProperty('--pointer-y');element.style.removeProperty('--_card-rotate-x');element.style.removeProperty('--_card-rotate-y');element.style.removeProperty('--_card-heading-height');
    // Keep template canvases for remounting, but release their backing stores.
    for(const canvas of element.querySelectorAll('canvas'))canvas.width=canvas.height=1;
    for(const [key,value] of attributes){if(value===null)element.removeAttribute('data-'+key);else element.setAttribute('data-'+key,value);}
  };
}
