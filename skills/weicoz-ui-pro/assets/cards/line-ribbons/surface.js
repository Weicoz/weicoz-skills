import {fitCanvas,glProgram,glColor,watchColors} from '../shared/runtime.js';

// Fixed camera, three translucent ruled surfaces. Thread coverage is filtered in
// screen space; below one pixel it converges to a film instead of a moire pattern.
export function createSurface(element, ribbons, invalidate, variant='webgl') {
  const canvas=document.createElement('canvas');canvas.className='ribbon-surface';canvas.setAttribute('aria-hidden','true');
  element.querySelector('.card-stage').append(canvas);
  const vertex=`attribute vec3 a_position;attribute float a_thread,a_along;
    uniform vec2 u_size;uniform vec4 u_view;uniform float u_time,u_dpr;varying vec3 v_position;varying float v_thread,v_along;
    void main(){vec3 p=a_position;float wave=sin(p.x*.004-u_time*.11);
      p.y+=wave*3.*sin(a_thread*3.14159265);p.z+=wave*12.;
      v_position=p;v_thread=a_thread;v_along=a_along;float scale=max(u_size.x/u_view.z,u_size.y/u_view.w);
      vec2 xy=(p.xy-u_view.xy-u_view.zw*.5)*scale/(u_size*.5);
      gl_Position=vec4(xy.x,-xy.y,0.,1.);gl_PointSize=(1.+.65*sin(a_thread*3.14159265))*u_dpr;}`;
  const fragment=`#extension GL_OES_standard_derivatives : enable
    precision highp float;varying vec3 v_position;varying float v_thread,v_along;
    uniform vec3 u_a,u_b;uniform float u_dark,u_style;${glColor}
    float wire(float phase){
      float footprint=max(fwidth(phase),.001),distance=abs(fract(phase+.5)-.5);
      float line=1.-smoothstep(footprint*.18,footprint*.9,distance);
      return line*(1.-smoothstep(.28,.85,footprint));
    }
    void main(){vec3 n=normalize(cross(dFdx(v_position),dFdy(v_position)));
      float grazing=1.-abs(n.z);float light=abs(dot(n,normalize(vec3(-.35,-.45,1.))));
      float phase=v_thread*128.;float footprint=max(fwidth(phase),.001);
      float distance=abs(fract(phase)-.5);
      float thread=1.-smoothstep(.18-footprint*.5,.18+footprint*.5,distance);
      thread=mix(thread,.36,smoothstep(.45,1.15,footprint));
      float edge=exp(-min(v_thread,1.-v_thread)*40.);
      float hue=smoothstep(360.,1350.,v_position.x)*.92;
      vec3 c=pigment(u_b,u_a,hue);vec3 l=lab(c);
      l.x+=.05*light-.08*grazing;c=srgb(l);
      float alpha=.15+thread*.39+grazing*.28+edge*.10+u_dark*.08;
      alpha*=smoothstep(0.,max(fwidth(v_thread)*1.1,.0001),min(v_thread,1.-v_thread));
      if(u_style>1.5){
        float grid=max(wire(v_thread*22.),wire(v_along*88.));
        alpha=grid*(.40+.24*light)+edge*.055;
      }else if(u_style>.5){
        float point=1.-smoothstep(.22,.50,length(gl_PointCoord-.5));
        alpha=point*(.55+.30*sin(v_thread*3.14159265));c=pigment(u_b,u_a,hue);
      }
      gl_FragColor=vec4(c*alpha,alpha);}`;
  const gpu=glProgram(canvas,vertex,fragment);
  if(!gpu){canvas.remove();return null;}
  const positions=[],threads=[],alongs=[];
  const bezier=(a,t)=>{const q=1-t;return [0,1].map(k=>q*q*q*a[k]+3*q*q*t*a[k+2]+3*q*t*t*a[k+4]+t*t*t*a[k+6]);};
  const point=(r,u,v)=>{
    const [a,b]=ribbons[r],A=bezier(a,u),B=bezier(b,u),s=variant==='dots'?v:(1-Math.cos(v*Math.PI))/2;
    positions.push(A[0]+(B[0]-A[0])*s,A[1]+(B[1]-A[1])*s,Math.sin(v*Math.PI*2+u*3+r)*22);
    threads.push(v);alongs.push(u);
  };
  const U=128,V=40;
  if(variant==='dots'){
    for(let r=0;r<ribbons.length;r++)for(let u=0;u<=128;u++)for(let v=0;v<=24;v++)point(r,u/128,v/24);
  }else for(let r=0;r<ribbons.length;r++)for(let u=0;u<U;u++)for(let v=0;v<V;v++){
    for(const [du,dv]of [[0,0],[1,0],[0,1],[1,0],[1,1],[0,1]])point(r,(u+du)/U,(v+dv)/V);
  }
  gpu.attribute('a_position',positions,3);gpu.attribute('a_thread',threads,1);gpu.attribute('a_along',alongs,1);
  let palette,lost=false;
  const off=watchColors(element,p=>{palette=p;invalidate();});
  const ro=new ResizeObserver(invalidate);ro.observe(canvas);
  const lostContext=e=>{e.preventDefault();lost=true;canvas.hidden=true;element.dataset.surfaceReady='false';};
  canvas.addEventListener('webglcontextlost',lostContext);
  element.dataset.surfaceReady='true';
  return {
    draw(time){
      if(!palette||lost)return;
      const {w,h,dpr}=fitCanvas(canvas,1);const {gl}=gpu;
      gl.useProgram(gpu.program);gl.viewport(0,0,canvas.width,canvas.height);
      gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);
      gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
      gl.uniform2f(gpu.uniform('u_size'),w,h);gl.uniform1f(gpu.uniform('u_time'),time);
      gl.uniform1f(gpu.uniform('u_dpr'),dpr);gl.uniform1f(gpu.uniform('u_style'),variant==='dots'?1:variant==='grid'?2:0);
      gl.uniform4fv(gpu.uniform('u_view'),element.clientWidth<=650?[100,60,560,474]:[0,0,1280,474]);
      gl.uniform3fv(gpu.uniform('u_a'),palette.a);gl.uniform3fv(gpu.uniform('u_b'),palette.b);
      gl.uniform1f(gpu.uniform('u_dark'),palette.dark?1:0);
      gl.drawArrays(variant==='dots'?gl.POINTS:gl.TRIANGLES,0,threads.length);
    },
    destroy(){off();ro.disconnect();canvas.removeEventListener('webglcontextlost',lostContext);gpu.destroy();canvas.remove();delete element.dataset.surfaceReady;}
  };
}
