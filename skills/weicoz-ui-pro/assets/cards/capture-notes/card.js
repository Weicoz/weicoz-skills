import {shell,loop,staticMotion,clamp} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,options),content=options.content || {},rows=element.querySelector('.capture-rows'),now=element.querySelector('.capture-now'),bars=[...element.querySelectorAll('.capture-wave i')],button=element.querySelector('.capture-pause');
  const defaults=[{title:'首页设计评审',team:'设计'},{title:'内容与视觉方向',team:'创作'},{title:'本周项目同步',team:'产品'},{title:'新想法的第一轮讨论',team:'团队'},{title:'发布前的最后一次检查',team:'工程'}];
  const records=(Array.isArray(content.records)?content.records:defaults).filter(record=>record && typeof record==='object');
  const still=staticMotion(element,options),events=new AbortController(),tones=['indigo','teal','amber','rose','slate'];let clock,paused=false,phase=0,selected=0;
  rows.replaceChildren();
  const select=index=>{selected=index;now.textContent=String(records[index]?.title ?? content.emptyText ?? '还没有讨论记录');now.title=String(records[index]?.detail ?? now.textContent);[...rows.children].forEach((r,i)=>r.setAttribute('aria-pressed',String(i===index)));clock?.invalidate();};
  records.forEach((record,index)=>{
    const row=document.createElement('button'),name=document.createElement('span'),tags=document.createElement('span');row.type='button';row.className='capture-row';tags.className='capture-tags';name.textContent=String(record.title ?? '');
    const values=Array.isArray(record.tags)?record.tags:[{label:record.team ?? '',tone:record.tone}];
    values.forEach((value,i)=>{const tag=document.createElement('small'),label=typeof value==='object'?value?.label:value,tone=typeof value==='object'?value?.tone:undefined;tag.textContent=String(label ?? '');tag.dataset.tone=tones.includes(tone)?tone:tones[(index+i)%tones.length];tags.append(tag);});
    row.append(name,tags);row.addEventListener('click',()=>select(index),{signal:events.signal});rows.append(row);
  });select(0);
  const start=()=>{clock?.destroy();clock=loop(element,(time,dt)=>{
    if(!paused)phase+=dt;
    const waveform=records[selected]?.waveform;
    bars.forEach((b,i)=>{const sample=Array.isArray(waveform)&&waveform.length?waveform[i%waveform.length]:undefined,base=typeof sample==='number'&&Number.isFinite(sample)?clamp(sample):undefined;
      const value=base!==undefined?clamp(base*(still()?1:.8+.2*Math.sin(phase*3.2+i*.85)),.08,1):still()?.25+.5*Math.abs(Math.sin(i*1.8)):.2+.8*Math.abs(Math.sin(phase*3.2+i*.85)*Math.cos(phase*1.4-i*.32));b.style.transform=`scaleY(${value})`;
    });
  },{...options,continuous:!paused&&records.length>0});};
  const syncButton=()=>{button.setAttribute('aria-label',paused?'播放波形动画':'暂停波形动画');button.setAttribute('aria-pressed',String(paused));button.querySelector('path').setAttribute('d',paused?'m7 4 8 6-8 6Z':'M7 5v10M13 5v10');};
  button.disabled=!records.length;syncButton();button.addEventListener('click',()=>{paused=!paused;syncButton();start();},{signal:events.signal});start();
  return {destroy(){clock.destroy();events.abort();clean();rows.replaceChildren();bars.forEach(bar=>bar.style.removeProperty('transform'));}};
}
