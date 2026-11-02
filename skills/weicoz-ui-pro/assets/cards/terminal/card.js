import {loop,shell,smooth,staticMotion} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,options);
  const content=options.content || {};
  if(Array.isArray(content.lines)){
    const container=element.querySelector('.terminal-lines');container.replaceChildren();
    const lines=content.lines.length?content.lines:[{text:content.emptyText || '等待运行'}];
    for(const item of lines){
      const line=typeof item==='string'?{text:item}:item,row=document.createElement('p');
      if(['highlight','result','address'].includes(line.tone))row.className='terminal-'+line.tone;
      row.append(document.createTextNode(String(line.text ?? '')));
      if(line.detail){const detail=document.createElement('span');detail.className='terminal-dim';detail.textContent=' '+line.detail;row.append(detail);}
      container.append(row);
    }
    const cursor=document.createElement('span');cursor.className='terminal-cursor';cursor.textContent=' ▎';container.lastElementChild.append(cursor);
  }
  const rows=[...element.querySelectorAll('.terminal-lines p')],cursor=element.querySelector('.terminal-cursor'),still=staticMotion(element,options);
  const clock=loop(element,time=>{
    const staticState=still();
    rows.forEach((r,i)=>r.style.setProperty('--line-visible',staticState?1:smooth((time-.12-i*.42)/.52)));
    cursor.style.setProperty('--cursor-on',staticState?1:.35+.65*(.5+.5*Math.cos(time*5)));
  },{...options,duration:Math.max(1,rows.length*.42+.78)});
  return {replay:()=>clock.restart(),destroy(){clock.destroy();clean();rows.forEach(r=>r.style.removeProperty('--line-visible'));cursor.style.removeProperty('--cursor-on');}};
}
