import {loop,shell,random,glProgram,fitCanvas,watchColors,mix,staticMotion} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,options);
  const canvas=element.querySelector('canvas');
  const vertex=`attribute vec3 a_position;attribute float a_selected;uniform vec2 u_size,u_rotation;uniform float u_dpr,u_halo;varying float v_selected,v_depth;
    void main(){float c=cos(u_rotation.x),s=sin(u_rotation.x);vec3 p=a_position;p.xz=mat2(c,-s,s,c)*p.xz;c=cos(u_rotation.y);s=sin(u_rotation.y);p.yz=mat2(c,-s,s,c)*p.yz;
      float perspective=1./(1.+p.z*.24);v_depth=perspective;v_selected=a_selected;
      gl_Position=vec4(p.x*perspective*.94/(u_size.x/u_size.y),p.y*perspective*.84-.02,0.,1.);
      gl_PointSize=mix(2.5,7.,a_selected)*u_dpr*perspective+u_halo*a_selected*15.*u_dpr;}`;
  const fragment=`precision highp float;uniform vec3 u_accent,u_ink;uniform float u_points,u_halo,u_lineAlpha;varying float v_selected,v_depth;
    void main(){float a=1.;if(u_points>.5){float r=length(gl_PointCoord-.5)*2.;a=1.-smoothstep(.65,1.,r);if(u_halo>.5){a=exp(-r*r*5.)*.23*v_selected;}}
      vec3 color=mix(u_ink,u_accent,v_selected);a*=u_points>.5?mix(.18,.95,v_selected)*v_depth:u_lineAlpha;
      gl_FragColor=vec4(color*a,a);}`;
  const gpu=glProgram(canvas,vertex,fragment),rng=random(29),positions=[],selected=[];
  const add=(v,s=0)=>{positions.push(...v);selected.push(s);};
  const corners=Array.from({length:8},(_,i)=>[(i&1?.65:-.65),(i&2?.65:-.65),(i&4?.65:-.65)]);
  for(let i=0;i<8;i++)for(const bit of [1,2,4])if(!(i&bit)){add(corners[i]);add(corners[i|bit]);}
  const related=[[-.08,-.06,.28],[.12,.04,.35],[.29,-.12,.23],[.08,-.27,.29]];
  for(let i=0;i<3;i++){add(related[i],1);add(related[i+1],1);}
  for(let i=0;i<140;i++)add([(rng()-.5)*2.1,(rng()-.5)*1.75,(rng()-.5)*1.8]);
  related.forEach(v=>add(v,1));
  if(gpu){gpu.attribute('a_position',positions,3);gpu.attribute('a_selected',selected,1);element.dataset.vectorReady='true';}
  else canvas.hidden=true;
  let palette,tx=0,ty=0,rx=0,ry=0,lost=false;
  const still=staticMotion(element,options);
  const draw=(time,dt)=>{if(!gpu||!palette||lost)return;if(still())rx=ry=tx=ty=0;if(dt){rx=mix(rx,tx,1-Math.exp(-dt*2.5));ry=mix(ry,ty,1-Math.exp(-dt*2.5));}const {w,h,dpr}=fitCanvas(canvas);const {gl}=gpu;
    gl.useProgram(gpu.program);gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
    gl.uniform2f(gpu.uniform('u_size'),w,h);gl.uniform2f(gpu.uniform('u_rotation'),-.62+Math.sin(time*.12)*.06+rx,.35+ry);
    gl.uniform1f(gpu.uniform('u_dpr'),dpr);gl.uniform3fv(gpu.uniform('u_accent'),palette.a);gl.uniform3fv(gpu.uniform('u_ink'),palette.dark?[.8,.84,.9]:[.18,.23,.3]);
    gl.uniform1f(gpu.uniform('u_halo'),0);gl.uniform1f(gpu.uniform('u_points'),0);gl.uniform1f(gpu.uniform('u_lineAlpha'),.21);gl.drawArrays(gl.LINES,0,24);
    gl.uniform1f(gpu.uniform('u_lineAlpha'),.32);gl.drawArrays(gl.LINES,24,6);
    gl.uniform1f(gpu.uniform('u_points'),1);gl.uniform1f(gpu.uniform('u_halo'),1);gl.drawArrays(gl.POINTS,30,144);
    gl.uniform1f(gpu.uniform('u_halo'),0);gl.drawArrays(gl.POINTS,30,144);
  };
  const clock=loop(element,draw,{...options,settled:()=>Math.abs(rx-tx)+Math.abs(ry-ty)<.001}),off=watchColors(element,p=>{palette=p;clock.invalidate();}),ro=new ResizeObserver(()=>clock.invalidate());ro.observe(canvas);
  const move=e=>{if(e.pointerType==='touch' || still())return;const r=element.getBoundingClientRect();tx=((e.clientX-r.left)/r.width-.5)*.25;ty=((e.clientY-r.top)/r.height-.5)*.16;};
  const leave=()=>{tx=ty=0;},loss=e=>{e.preventDefault();lost=true;canvas.hidden=true;delete element.dataset.vectorReady;};
  element.addEventListener('pointermove',move);element.addEventListener('pointerleave',leave);element.addEventListener('pointercancel',leave);canvas.addEventListener('webglcontextlost',loss);
  
  return{destroy(){clean();clock.destroy();off();ro.disconnect();gpu?.destroy();element.removeEventListener('pointermove',move);element.removeEventListener('pointerleave',leave);element.removeEventListener('pointercancel',leave);canvas.removeEventListener('webglcontextlost',loss);delete element.dataset.vectorReady;}};
}
