import {random, loop, fitCanvas, glProgram, glColor, watchColors, shell, TAU, mixColor, rgb, clamp, mix, smooth} from '../shared/runtime.js';
import {LAND_WIDTH, LAND_HEIGHT, LAND_BITS} from '../shared/land-mask.js';
export function mount(element, options = {}) {
  const cleanShell=shell(element,options),previousMode=element.getAttribute('data-mode');
  if(options.mode!==undefined)element.dataset.mode=options.mode==='mesh'?'mesh':'globe';
  const isMesh=()=>element.dataset.mode==='mesh';
  const label=element.querySelector('.globe-label'),labelText=label.textContent;
  let canvas=element.querySelector('.globe-points');const backdrop=element.querySelector('.globe-wash'),arcCanvas=element.querySelector('.globe-arcs');
  const wash=backdrop.getContext('2d'),arc=arcCanvas.getContext('2d'),rng=random(301),bits=Uint8Array.from(atob(LAND_BITS),c=>c.charCodeAt(0));
  const count=matchMedia('(max-width: 650px)').matches?55000:110000,points=[];
  const normalize=p=>{const l=Math.hypot(...p);return p.map(n=>n/l);};
  for(let i=0;i<count;i++){
    const latitude=Math.asin(-1+2*(i+.5)/count),longitude=i*2.3999632297;
    let p=[Math.cos(latitude)*Math.sin(longitude),Math.sin(latitude),Math.cos(latitude)*Math.cos(longitude)];
    const v=[rng()-.5,rng()-.5,rng()-.5],dot=v.reduce((s,n,j)=>s+n*p[j],0),t=normalize(v.map((n,j)=>n-dot*p[j]));
    p=normalize(p.map((n,j)=>n+t[j]*.007));
    const lon=Math.atan2(p[0],p[2])*180/Math.PI,lat=Math.asin(p[1])*180/Math.PI;
    const x=Math.min(LAND_WIDTH-1,Math.floor((lon+180)/360*LAND_WIDTH)),y=Math.min(LAND_HEIGHT-1,Math.floor((90-lat)/180*LAND_HEIGHT)),idx=y*LAND_WIDTH+x;
    if(bits[idx>>3]&(1<<(idx&7)))points.push([...p,1.2+Math.pow(rng(),2)*1.4,.35+Math.pow(rng(),.4)*.55]);
  }
  // A second point field shares the renderer, palette and clock with the globe.
  const globeCount=points.length,content=options.content || {};
  const defaults=[[-.98,.64,.18],[-.47,.83,-.32],[.02,.66,.38],[.59,.82,-.18],[1.03,.40,.12],[-1.12,.10,-.4],[-.66,.22,.4],[-.18,.09,-.27],[.36,.29,.24],[.86,-.13,-.18],[-.95,-.46,.21],[-.45,-.28,-.35],[.07,-.39,.38],[.61,-.53,-.25],[-.57,-.85,.1],[.16,-.91,-.18],[1.08,-.70,.25]];
  const nodes=(Array.isArray(content.nodes)?content.nodes.filter(n=>n && typeof n==='object').slice(0,64):defaults.map((position,i)=>({id:String(i),position}))).map((node,i)=>({
    id:String(node.id ?? i),label:String(node.label ?? ''),position:Array.isArray(node.position)&&node.position.length===3&&node.position.every(Number.isFinite)?node.position.map(n=>clamp(n,-1.5,1.5)):defaults[i%defaults.length]
  }));
  const indexes=new Map(nodes.map((node,i)=>[node.id,i]));
  const resolve=value=>indexes.get(String(value)) ?? (Number.isInteger(value)&&value>=0&&value<nodes.length?value:undefined);
  const links=Array.isArray(content.links)?content.links.map(link=>[resolve(link?.from),resolve(link?.to)]).filter(([a,b])=>a!==undefined&&b!==undefined&&a!==b).slice(0,160):nodes.flatMap((node,i)=>nodes.map((other,j)=>({j,d:Math.hypot(...node.position.map((n,k)=>n-other.position[k]))})).filter(({j})=>j!==i).sort((a,b)=>a.d-b.d).slice(0,2).filter(({j})=>j>i).map(({j})=>[i,j]));
  for(let i=0;i<1800;i++)points.push([(rng()-.5)*2.9,(rng()-.5)*2.6,(rng()-.5)*1.4,.7+rng()*1.1,.08+rng()*.22]);
  for(const node of nodes){for(let i=0;i<100;i++){const radius=Math.pow(rng(),.65)*.17,angle=rng()*TAU,z=(rng()-.5)*radius;points.push([node.position[0]+Math.cos(angle)*radius,node.position[1]+Math.sin(angle)*radius,node.position[2]+z,.8+rng()*1.3,.14+rng()*.48]);}points.push([...node.position,4,.95]);}
  const vertex=`precision highp float;attribute vec3 a_position;attribute vec2 a_detail;uniform vec2 u_size;uniform float u_time,u_dpr,u_mode;varying float v_alpha,v_t;
    void main(){float a=-.70+u_time*.069813;vec3 p=vec3(a_position.x*cos(a)+a_position.z*sin(a),a_position.y,-a_position.x*sin(a)+a_position.z*cos(a));
      float tilt=.12;vec2 xy=mat2(cos(tilt),-sin(tilt),sin(tilt),cos(tilt))*p.xy;float r=u_size.x*.76;
      vec2 screen=vec2(u_size.x*.80,u_size.y*.68)+vec2(xy.x,-xy.y)*r;
      v_alpha=a_detail.y*mix(.12,1.,smoothstep(-.1,.35,p.z));if(p.z<0.)v_alpha*=.20+.80*smoothstep(0.,.30,-p.z);
      float size=.82+.18*(p.z+1.)*.5;
      if(u_mode>.5){a=.14+sin(u_time*.07)*.15;p=vec3(a_position.x*cos(a)+a_position.z*sin(a),a_position.y,-a_position.x*sin(a)+a_position.z*cos(a));xy=mat2(cos(tilt),-sin(tilt),sin(tilt),cos(tilt))*p.xy;float perspective=1./(1.+p.z*.24);screen=vec2(u_size.x*.53,u_size.y*.55)+vec2(xy.x,-xy.y)*u_size.x*.43*perspective;size=perspective;v_alpha=a_detail.y*(.85+.15*sin(u_time*.5+a_position.x*7.));}
      gl_Position=vec4(screen.x/u_size.x*2.-1.,1.-screen.y/u_size.y*2.,0.,1.);gl_PointSize=a_detail.x*u_dpr*size;v_t=clamp((xy.x+xy.y+.85)/1.8,0.,1.);}`;
  const fragment=`precision mediump float;varying float v_alpha,v_t;uniform vec3 u_a,u_b,u_c;${glColor} void main(){float r=length(gl_PointCoord-.5),soft=1.-smoothstep(.32,.5,r);vec3 c=v_t<.58?pigment(u_a,u_b,v_t/.58):pigment(u_b,u_c,(v_t-.58)/.42);gl_FragColor=vec4(c,v_alpha*soft);}`;
  let gpu=glProgram(canvas,vertex,fragment),ctx;
  if(gpu){gpu.attribute('a_position',points.flatMap(p=>p.slice(0,3)),3);gpu.attribute('a_detail',points.flatMap(p=>p.slice(3)),2);}
  else{const n=canvas.cloneNode();canvas.replaceWith(n);canvas=n;ctx=canvas.getContext('2d');}
  let palette,washKey="",arcColors=[],fallbackTints=[];const requested=Number(options.arcs??element.dataset.arcs??2),arcs=Number.isFinite(requested)?Math.round(clamp(requested,1,3)):2;
  const rotate=(p,time)=>{const a=-.70+time*TAU/90,x=p[0]*Math.cos(a)+p[2]*Math.sin(a),z=-p[0]*Math.sin(a)+p[2]*Math.cos(a);return [x*Math.cos(.12)+p[1]*Math.sin(.12),-x*Math.sin(.12)+p[1]*Math.cos(.12),z];};
  const project=(p,w,h)=>[w*.80+p[0]*w*.76,h*.68-p[1]*w*.76];
  const meshProject=(p,time,w,h)=>{const a=.14+Math.sin(time*.07)*.15,x=p[0]*Math.cos(a)+p[2]*Math.sin(a),z=-p[0]*Math.sin(a)+p[2]*Math.cos(a),f=1/(1+z*.24);return [w*.53+(x*Math.cos(.12)+p[1]*Math.sin(.12))*w*.43*f,h*.55-(-x*Math.sin(.12)+p[1]*Math.cos(.12))*w*.43*f];};
  const slerp=(a,b,t)=>{const angle=Math.acos(clamp(a.reduce((s,n,i)=>s+n*b[i],0),-1,1)),s=Math.sin(angle);return a.map((n,i)=>(n*Math.sin((1-t)*angle)+b[i]*Math.sin(t*angle))/s);};
  const draw=(time)=>{
    if(!palette)return;const {w,h,dpr}=fitCanvas(canvas);fitCanvas(backdrop);fitCanvas(arcCanvas);
    const mesh=isMesh(),nextWashKey=mesh+":"+canvas.width+":"+canvas.height+":"+JSON.stringify(palette);
    if(nextWashKey!==washKey){
    wash.setTransform(dpr,0,0,dpr,0,0);wash.clearRect(0,0,w,h);const cx=w*.80,cy=h*.68,r=w*.76;
    if(mesh){const g=wash.createRadialGradient(w*.53,h*.55,0,w*.53,h*.55,w*.65);g.addColorStop(0,rgb(palette.b,.10));g.addColorStop(.55,rgb(palette.a,.035));g.addColorStop(1,rgb(palette.a,0));wash.fillStyle=g;wash.fillRect(0,0,w,h);}
    else{const g=wash.createRadialGradient(cx-r*.25,cy-r*.35,r*.1,cx,cy,r);for(let i=0;i<=16;i++){const t=i/16;g.addColorStop(t*.85,rgb(mixColor(palette.surface,palette.a,t),.01+.03*t));}g.addColorStop(1,rgb(palette.a,.05));wash.fillStyle=g;wash.beginPath();wash.arc(cx,cy,r,0,TAU);wash.fill();wash.strokeStyle=rgb(palette.a,.075);wash.lineWidth=.6;wash.stroke();}
      washKey=nextWashKey;arcColors=Array.from({length:201},(_,i)=>mixColor(palette.b,palette.a,i/200));
      if(!gpu)fallbackTints=Array.from({length:129},(_,i)=>{const t=i/128,color=t<.58?mixColor(palette.a,palette.b,t/.58):mixColor(palette.b,palette.c,(t-.58)/.42);return Array.from({length:33},(_,a)=>rgb(color,a/32));});
    }
    if(gpu){const {gl}=gpu;gl.useProgram(gpu.program);gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);gl.enable(gl.BLEND);gl.blendFuncSeparate(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA,gl.ONE,gl.ONE_MINUS_SRC_ALPHA);gl.uniform2f(gpu.uniform('u_size'),w,h);gl.uniform1f(gpu.uniform('u_time'),time);gl.uniform1f(gpu.uniform('u_mode'),mesh?1:0);gl.uniform1f(gpu.uniform('u_dpr'),dpr);for(const [n,c]of [['a',palette.a],['b',palette.b],['c',palette.c]])gl.uniform3fv(gpu.uniform('u_'+n),c);gl.drawArrays(gl.POINTS,mesh?globeCount:0,mesh?points.length-globeCount:globeCount);}
    else{ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);for(let i=mesh?globeCount:0;i<(mesh?points.length:globeCount);i++){const p=points[i],q=rotate(p,time),[x,y]=mesh?meshProject(p,time,w,h):project(q,w,h),t=clamp((q[0]+q[1]+.85)/1.8);const rim=clamp(-q[2]/.30),back=q[2]<0?.20+.80*rim*rim*(3-2*rim):1,alpha=mesh?p[4]:p[4]*(q[2]>.1?1:.12)*back;ctx.fillStyle=fallbackTints[Math.round(t*128)][Math.round(alpha*32)];ctx.beginPath();ctx.arc(x,y,p[3]*.45,0,TAU);ctx.fill();}}
    arc.setTransform(dpr,0,0,dpr,0,0);arc.clearRect(0,0,w,h);
    if(mesh){
      const positions=nodes.map(n=>meshProject(n.position,time,w,h));
      for(const [i,[a,b]] of links.entries()){
        const A=positions[a],B=positions[b],color=mixColor(palette.a,palette.b,(i%7)/6),t=(time*.13+i*.31)%1;
        arc.strokeStyle=rgb(color,.23);arc.lineWidth=.65;arc.beginPath();arc.moveTo(...A);arc.lineTo(...B);arc.stroke();
        const x=mix(A[0],B[0],t),y=mix(A[1],B[1],t),g=arc.createRadialGradient(x,y,0,x,y,7);g.addColorStop(0,rgb(color,.65));g.addColorStop(1,rgb(color,0));arc.fillStyle=g;arc.beginPath();arc.arc(x,y,7,0,TAU);arc.fill();
      }
      for(const [i,[x,y]] of positions.entries()){const pulse=.5+.5*Math.sin(time*1.5+i),g=arc.createRadialGradient(x,y,0,x,y,12+pulse*4);g.addColorStop(0,rgb(palette.a,.28));g.addColorStop(1,rgb(palette.a,0));arc.fillStyle=g;arc.beginPath();arc.arc(x,y,16,0,TAU);arc.fill();arc.strokeStyle=rgb(palette.a,.4+pulse*.3);arc.lineWidth=.7;arc.beginPath();arc.arc(x,y,3+pulse*1.2,0,TAU);arc.stroke();}
      if(label){const i=Math.min(8,nodes.length-1);label.hidden=i<0;if(i>=0){label.style.left=positions[i][0]+'px';label.style.top=positions[i][1]+'px';label.style.opacity='1';label.textContent=String(content.label ?? (nodes[i].label || labelText));}}return;
    }
    if(label){label.hidden=false;label.textContent=labelText;}
    for(let k=0;k<arcs;k++){
      const A=normalize([-.88,.09+k*.17,.42]),B=k===0?normalize([.027,.752,.659]):normalize([.24,.40,.88]);
      const cycle=(time+k*3.1+3)%13,head=smooth(cycle/3),fade=cycle>9?1-smooth((cycle-9)/3):1;
      const tail=cycle>9?smooth((cycle-9)/3)*.85:0;let prev=null,headXY=null;
      for(let i=0;i<=200;i++){
        const t=i/200;if(t>head||t<tail)continue;
        let p=slerp(A,B,t),lift=1+Math.sin(t*Math.PI)*(.38+k*.04);p=rotate(p.map(n=>n*lift),time);
        const xy=project(p,w,h);headXY=xy;
        if(prev){arc.strokeStyle=rgb(arcColors[i],fade*Math.pow(t,1.2)*.9);arc.lineWidth=.7+t*.65;arc.beginPath();arc.moveTo(...prev);arc.lineTo(...xy);arc.stroke();}prev=xy;
      }
      if(headXY&&fade>0){const [x,y]=headXY,g=arc.createRadialGradient(x,y,0,x,y,8);g.addColorStop(0,rgb(palette.a,fade*.7));g.addColorStop(1,rgb(palette.a,0));arc.fillStyle=g;arc.beginPath();arc.arc(x,y,8,0,TAU);arc.fill();arc.fillStyle=rgb(palette.a,fade);arc.beginPath();arc.arc(x,y,1.9,0,TAU);arc.fill();}
      const [x,y]=project(rotate(B,time),w,h),pulse=clamp((cycle-3)/1.15);
      if(head>.99){arc.strokeStyle=rgb(palette.a,fade*.85);arc.lineWidth=1;arc.beginPath();arc.arc(x,y,3.5,0,TAU);arc.stroke();if(pulse<1){arc.strokeStyle=rgb(palette.a,(1-pulse)*.5);arc.beginPath();arc.arc(x,y,4+pulse*14,0,TAU);arc.stroke();}}
      if(k===0&&label){label.style.left=x+'px';label.style.top=y+'px';label.style.opacity=String(smooth((head-.85)/.15)*fade*smooth((x-10)/20)*smooth((w-100-x)/20)*smooth((y-20)/20)*smooth((h-20-y)/20));}
    }

  };
  const clock=loop(element,draw,{...options,continuous:true});const off=watchColors(element,p=>{palette=p;clock.invalidate();});const ro=new ResizeObserver(()=>clock.invalidate());ro.observe(element.querySelector('.card-stage'));
  const modes=new MutationObserver(()=>clock.invalidate());modes.observe(element,{attributes:true,attributeFilter:['data-mode']});
  return {destroy(){clock.destroy();off();ro.disconnect();modes.disconnect();gpu?.destroy();cleanShell();if(options.mode!==undefined){if(previousMode===null)element.removeAttribute('data-mode');else element.setAttribute('data-mode',previousMode);}const label=element.querySelector('.globe-label');label.removeAttribute('style');label.hidden=false;}};
}
