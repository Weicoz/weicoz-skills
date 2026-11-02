import {loop,shell,smooth,staticMotion} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,options);
  const value=element.querySelector('.metric-value'),chart=element.querySelector('.metric-bars');
  const content=options.content || {};
  if(content.value!==undefined)value.textContent=typeof content.value==='number' && Number.isFinite(content.value)?content.value.toLocaleString('en-US',{maximumFractionDigits:2}):String(content.value);
  if(Array.isArray(content.series)){
    const series=content.series.filter(n=>typeof n==='number' && Number.isFinite(n) && n>=0),max=Math.max(1,...series);
    chart.replaceChildren(...series.map((n,i)=>{const bar=document.createElement('i');bar.style.setProperty('--height',`${n/max*96}%`);if(i===series.length-1)bar.className='current';else if(i>=series.length-6)bar.className='recent';return bar;}));
  }
  const bars=[...chart.querySelectorAll('i')];
  const formatted=value.textContent.trim(),still=staticMotion(element,options);
  const digits=[];
  value.replaceChildren();
  const readable=document.createElement('span');readable.className='metric-readable';readable.textContent=formatted;value.append(readable);
  for(const char of formatted){
    const slot=document.createElement('span');slot.setAttribute('aria-hidden','true');
    if(!/\d/.test(char)){slot.className='metric-separator';slot.textContent=char;value.append(slot);continue;}
    slot.className='metric-digit';
    const strip=document.createElement('span');strip.className='metric-reel';
    const end=Number(char);
    for(let i=0;i<=end;i++){const n=document.createElement('span');n.textContent=String(i%10);strip.append(n);}
    slot.append(strip);value.append(slot);digits.push({strip,end});
  }
  const clock=loop(element,time=>{
    const staticState=still();
    digits.forEach(({strip,end},i)=>{
      const p=staticState?1:smooth((time-.12-i*.065)/2.05);
      strip.style.transform=`translateY(${-end*p}em)`;
    });
    bars.forEach((bar,i)=>{
      const p=staticState?1:smooth((time-.10-i*.018)/1.85);
      bar.style.setProperty('--bar-growth',Math.max(.008,p));
    });
    element.style.setProperty('--metric-settled',staticState?1:smooth((time-1.70)/.70));
  },{...options,duration:Math.max(2.65,bars.length*.018+1.95,digits.length*.065+2.17)});
  return {replay:()=>clock.restart(),destroy(){clock.destroy();clean();value.textContent=formatted;element.style.removeProperty('--metric-settled');bars.forEach(b=>b.style.removeProperty('--bar-growth'));}};
}
