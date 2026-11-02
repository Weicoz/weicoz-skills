import {random, simplex, loop, fitCanvas, glProgram, glNoise, glColor, watchColors, shell, clamp, mix, mixColor, rgb, TAU,staticMotion} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const cleanShell=shell(element,options);
  const garmentGradient=element.querySelector('linearGradient');
  if(garmentGradient){const old=garmentGradient.id,id='garment-'+crypto.randomUUID();garmentGradient.id=id;for(const path of element.querySelectorAll('svg [fill]'))if(path.getAttribute('fill')===`url(#${old})`)path.setAttribute('fill',`url(#${id})`);}
  let canvas = element.querySelector('canvas'), palette, w = 1, h = 1, dpr = 1;
  const rng=random(91), count=matchMedia('(max-width: 650px)').matches?8000:16000;
  const data=Array.from({length:count},()=>[rng()*TAU,rng(),.6+Math.pow(rng(),3)*3.4,.25+.75*Math.pow(rng(),1.3)]);
  const vertex=`precision highp float;attribute vec4 a_seed;uniform vec2 u_size,u_mouse;uniform float u_time,u_dpr,u_active;varying float v_alpha;varying float v_y;${glNoise}
    void main(){vec2 unit=vec2(cos(a_seed.x),sin(a_seed.x));float r=u_size.x*.59;
      float fine=simplex(unit*45.+a_seed.y*15.+u_time*.075),coarse=simplex(unit*8.+a_seed.y*4.+u_time*.035);
      float coreWidth=mix(.008,.030,smoothstep(-.6,.6,simplex(unit*2.2+vec2(u_time*.14,-u_time*.10))));
      float scatter=a_seed.y<.6?(fine*.75+coarse*.25)*coreWidth*r:(fine*150.+coarse*45.)*pow((a_seed.y-.6)/.4,2.4);
      vec2 base=vec2(u_size.x*.5,u_size.y*.43)+unit*r;
      float recover=(1.-smoothstep(0.,u_size.x*.29,distance(base,u_mouse)))*u_active;
      vec2 p=base+unit*scatter*(1.-recover);
      gl_Position=vec4(p.x/u_size.x*2.-1.,1.-p.y/u_size.y*2.,0.,1.);gl_PointSize=a_seed.z*u_dpr;v_alpha=a_seed.w;v_y=clamp(p.y/u_size.y,0.,1.);
    }`;
  const fragment=`precision mediump float;uniform vec3 u_a,u_b;varying float v_alpha,v_y;${glColor} void main(){float r=length(gl_PointCoord-.5);float alpha=(1.-smoothstep(.15,.5,r))*v_alpha;gl_FragColor=vec4(pigment(u_b,u_a,v_y),alpha);}`;
  let gpu=glProgram(canvas,vertex,fragment),ctx=null;
  if(!gpu){ const replacement=canvas.cloneNode();canvas.replaceWith(replacement);canvas=replacement;ctx=canvas.getContext('2d'); }
  else gpu.attribute('a_seed',data.flat(),4);
  let mouse=[-1000,-1000],target=[-1000,-1000],active=0,targetActive=0;
  const still=staticMotion(element,options);
  const noise=simplex(77);
  const draw=(time,dt)=>{
    if(!palette)return;
    if(still())active=targetActive=0;
    if(dt){mouse=mouse.map((n,i)=>mix(n,target[i],1-Math.exp(-dt*5.6)));active=mix(active,targetActive,1-Math.exp(-dt*3.2));}
    ({w,h,dpr}=fitCanvas(canvas));
    if(gpu){const {gl}=gpu;gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);gl.useProgram(gpu.program);gl.enable(gl.BLEND);gl.blendFuncSeparate(gl.SRC_ALPHA,palette.dark?gl.ONE:gl.ONE_MINUS_SRC_ALPHA,gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
      gl.uniform2f(gpu.uniform('u_size'),w,h);gl.uniform2f(gpu.uniform('u_mouse'),...mouse);gl.uniform1f(gpu.uniform('u_active'),active);gl.uniform1f(gpu.uniform('u_time'),time+12);gl.uniform1f(gpu.uniform('u_dpr'),dpr);gl.uniform3fv(gpu.uniform('u_a'),palette.a);gl.uniform3fv(gpu.uniform('u_b'),palette.b);gl.drawArrays(gl.POINTS,0,count);
    }else{ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);for(const [a,s,size,alpha]of data){const x=Math.cos(a),y=Math.sin(a),base=w*.59,f=noise(x*45+s*15+1,y*45+s*15+1),c=noise(x*8+s*4,y*8+s*4),n=clamp((noise(x*2.2+1.68,y*2.2-1.2)+.6)/1.2),width=mix(.008,.030,n*n*(3-2*n)),r=base+(s<.6?(f*.75+c*.25)*width*base:(f*150+c*45)*((s-.6)/.4)**2.4);const px=w*.5+x*r,py=h*.43+y*r;ctx.fillStyle=rgb(mixColor(palette.b,palette.a,clamp(py/h)),alpha);ctx.beginPath();ctx.arc(px,py,size*.5,0,TAU);ctx.fill();}}
  };
  const clock=loop(element,draw,{...options,continuous:!!gpu,settled:()=>Math.abs(active-targetActive)<.001});
  const off=watchColors(element,p=>{palette=p;clock.invalidate();});
  const ro=new ResizeObserver(()=>clock.invalidate());ro.observe(element.querySelector('.card-stage')); 
  const move=e=>{if(e.pointerType==='touch' || still())return;const r=canvas.getBoundingClientRect();target=[e.clientX-r.left,e.clientY-r.top];targetActive=1;};
  const leave=()=>targetActive=0;element.addEventListener('pointermove',move);element.addEventListener('pointerleave',leave);element.addEventListener('pointercancel',leave);
  
  return {destroy(){clock.destroy();off();ro.disconnect();gpu?.destroy();cleanShell();element.removeEventListener('pointermove',move);element.removeEventListener('pointerleave',leave);element.removeEventListener('pointercancel',leave);}};
}
