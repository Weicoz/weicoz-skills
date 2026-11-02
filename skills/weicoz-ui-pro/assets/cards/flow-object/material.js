import {glProgram, glNoise, glColor} from '../shared/runtime.js';

// One coated surface, not a stack of ribbons. Paint stays still; light travels.
const vertex = `attribute vec2 a_position;varying vec2 v_uv;
void main(){v_uv=a_position*.5+.5;gl_Position=vec4(a_position,0.,1.);}`;
const fragment = `precision highp float;
varying vec2 v_uv;uniform vec2 u_resolution,u_pointer;
uniform float u_time;uniform vec3 u_a,u_b,u_c;
${glNoise}
${glColor}
float bell(float d,float w){return exp(-d*d/(w*w));}
void main(){
  // Fit the field to the short side: a wider host reveals more of the material.
  vec2 uv=vec2(v_uv.x,1.-v_uv.y);
  vec2 p=(uv-.5)*u_resolution/min(u_resolution.x,u_resolution.y);
  float grain=hash(gl_FragCoord.xy)-.5;
  float dye=p.y+.42*p.x+.07*sin(p.x*2.1);
  vec3 color=mix(lab(u_b),lab(u_a),smoothstep(-.48,.30,dye));
  // Warm pigment is a broad off-centre pool, not another repeated band.
  float warm=smoothstep(-.01,.43,p.y+.18*p.x-.12*sin(p.x*2.));
  color=mix(color,lab(u_c),warm);
  color=mix(color,lab(vec3(1.)),.18+.09*bell(dye+.52,.40));
  float drift=.055*sin(u_time*.32)+u_pointer.x*.065-u_pointer.y*.035;
  float d=p.y+.43*p.x-.065*p.x*p.x+.10-drift;
  // One narrow glint nested inside an asymmetric, much wider bloom.
  float width=max(1.6/min(u_resolution.x,u_resolution.y),.005);
  float glint=bell(d,width*1.5);
  float shoulder=bell(d-.012,.035)*.20;
  float bloom=bell(d-.055,.14)*.29;
  float envelope=.66+.34*bell(p.x-.10-.22*sin(u_time*.19),.85);
  float brushed=simplex(vec2(p.x*.9,d*220.));
  float echo=bell(d+.038+.008*sin(p.x*4.),.014)*.07;
  float grazing=(glint*.29+shoulder+bloom+echo)*envelope;
  color=mix(color,lab(vec3(1.)),clamp(grazing,0.,.78));
  // A broad reflected softbox moves independently of the pigment boundary.
  float softbox=bell(p.x*.70-p.y*.22+.27*sin(u_time*.25)+u_pointer.x*.14,.52);
  color.x+=softbox*.035;
  color.x+=brushed*.009*bell(d,.14);
  vec3 outcolor=srgb(color)+grain*.020;
  gl_FragColor=vec4(outcolor,1.);
}`;

export function coatedSurface(canvas) {
  let gpu, uniforms, lastFrame=null, disposed=false;
  // Use the untransformed plane, so tilting the host cannot stretch its grain.
  const resize=()=>{
    const dpr=Math.min(devicePixelRatio || 1,2.5);
    const w=Math.max(1,Math.round(canvas.clientWidth*dpr)),h=Math.max(1,Math.round(canvas.clientHeight*dpr));
    if(canvas.width!==w || canvas.height!==h){canvas.width=w;canvas.height=h;}
  };
  const initialize=()=>{
    gpu=glProgram(canvas,vertex,fragment);
    canvas.dataset.renderer=gpu?'webgl':'css';
    if(!gpu)return;
    gpu.attribute('a_position',[-1,-1,1,-1,-1,1,-1,1,1,-1,1,1],2);
    uniforms=Object.fromEntries(['resolution','pointer','time','a','b','c'].map(n=>[n,gpu.uniform('u_'+n)]));
    resize();
  };
  const lost=e=>{if(disposed)return;e.preventDefault();gpu=null;canvas.dataset.renderer='css';};
  const restored=()=>{if(!disposed){initialize();if(lastFrame)draw(...lastFrame);}};
  canvas.addEventListener('webglcontextlost',lost);
  canvas.addEventListener('webglcontextrestored',restored);
  initialize();
  function draw(time,palette,pointer=[0,0]){
      lastFrame=[time,palette,pointer];
      if(!gpu || !palette || disposed)return;
      const {gl}=gpu;gl.useProgram(gpu.program);gl.viewport(0,0,canvas.width,canvas.height);
      gl.uniform2f(uniforms.resolution,canvas.width,canvas.height);
      gl.uniform2f(uniforms.pointer,...pointer);gl.uniform1f(uniforms.time,time);
      for(const n of ['a','b','c'])gl.uniform3fv(uniforms[n],palette[n]);
      gl.drawArrays(gl.TRIANGLES,0,6);
  }
  return {
    resize,draw,
    destroy(){if(disposed)return;disposed=true;canvas.removeEventListener('webglcontextlost',lost);canvas.removeEventListener('webglcontextrestored',restored);gpu?.destroy();gpu=null;lastFrame=null;canvas.width=canvas.height=1;delete canvas.dataset.renderer;}
  };
}
