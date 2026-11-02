// The editor owns its committed palette; incomplete HEX input is only a draft.
export function createPaletteEditor({query, onChange}) {
  const root=document.querySelector('.palette-editor'),modeControl=root.querySelector('#palette-mode');
  const slots=[...root.querySelectorAll('[data-color-slot]')],feedback=root.querySelector('.palette-feedback');
  const defaults={mode:'single',colors:['#5865c7','#9aa5e8','#d6c9b7']},key='oil.cards.palette.v1';
  const modes={single:1,duo:2,trio:3};
  const hex=value=>{
    if(typeof value!=='string')return null;
    const raw=value.trim().replace(/^#/,'');
    if(/^[a-f\d]{3}$/i.test(raw))return '#'+[...raw].map(c=>c+c).join('').toLowerCase();
    return /^[a-f\d]{6}$/i.test(raw)?'#'+raw.toLowerCase():null;
  };
  let state={mode:defaults.mode,colors:[...defaults.colors]},frame=0;
  try {const saved=JSON.parse(localStorage.getItem(key));if(Object.hasOwn(modes,saved?.mode)&&Array.isArray(saved.colors)&&saved.colors.length===3&&saved.colors.every(hex))state={mode:saved.mode,colors:saved.colors.map(hex)};}catch{}
  // Existing screenshot URLs remain valid; explicit URL colors override saved input.
  const legacy={dawn:['#7a5cff','#ff4f8b','#ff9a4a'],sage:['#4c9a94','#81bca2','#c7d5aa'],mono:['#44454c','#929399','#dedfe2'],clay:['#ac715d','#cf9d85','#e6caae']};
  const requestedPreset=query.get('preset')||query.get('state');
  if(Object.hasOwn(legacy,requestedPreset))state={mode:'trio',colors:[...legacy[requestedPreset]]};
  const requested=query.get('colors')?.split(',');
  if(requested?.length>=1&&requested.length<=3&&requested.every(hex))state={mode:['single','duo','trio'][requested.length-1],colors:[...requested.map(hex),...defaults.colors.slice(requested.length)]};
  const controller=new AbortController(),listen=(el,event,fn)=>el.addEventListener(event,fn,{signal:controller.signal});
  const save=()=>{try{localStorage.setItem(key,JSON.stringify(state));}catch{}};
  const render=()=>{
    modeControl.value=state.mode;
    slots.forEach((slot,i)=>{slot.hidden=i>=modes[state.mode];slot.querySelector('input[type=color]').value=state.colors[i];const text=slot.querySelector('.palette-hex');text.value=state.colors[i].toUpperCase();text.removeAttribute('aria-invalid');});
    feedback.textContent='';
  };
  const refresh=()=>{save();if(!frame)frame=requestAnimationFrame(()=>{frame=0;onChange();});};
  const showErrors=()=>{
    const invalid=slots.some((slot,i)=>i<modes[state.mode]&&slot.querySelector('.palette-hex').getAttribute('aria-invalid')==='true');
    feedback.textContent=invalid?'请输入 3 或 6 位 HEX 色值。':'';
  };
  slots.forEach((slot,i)=>{
    const color=slot.querySelector('input[type=color]'),text=slot.querySelector('.palette-hex');
    listen(color,'input',()=>{state.colors[i]=color.value;text.value=color.value.toUpperCase();text.removeAttribute('aria-invalid');showErrors();refresh();});
    listen(text,'input',()=>{const value=hex(text.value);text.setAttribute('aria-invalid',String(!value));if(value){state.colors[i]=value;color.value=value;refresh();}showErrors();});
    listen(text,'blur',()=>{const value=hex(text.value);if(value)text.value=value.toUpperCase();});
    listen(text,'keydown',e=>{if(e.key==='Escape'){text.value=state.colors[i].toUpperCase();text.removeAttribute('aria-invalid');showErrors();}if(e.key==='Enter')text.blur();});
  });
  listen(modeControl,'change',()=>{state.mode=modeControl.value;render();refresh();});
  listen(root.querySelector('.palette-reset'),'click',()=>{state={mode:defaults.mode,colors:[...defaults.colors]};render();refresh();});
  render();
  return {
    get colors(){const [a,b,c]=state.colors;return state.mode==='single'?[a,a,a]:state.mode==='duo'?[a,b,b]:[a,b,c];},
    destroy(){controller.abort();cancelAnimationFrame(frame);}
  };
}
