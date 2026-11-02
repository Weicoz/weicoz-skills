import {shell,clamp} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,options),events=new AbortController(),list=element.querySelector('.answer-citations'),excerpt=element.querySelector('.answer-excerpt'),reference=element.querySelector('.answer-reference'),charts=[...element.querySelectorAll('[data-chart]')];
  const defaults=[{label:'项目进度',answer:'核心页面已完成评审，下一步可以集中打磨移动端体验。',citation:'项目记录 · 本周评审'},{label:'内容表现',answer:'实用教程获得了更多收藏，可以继续拓展成一个系列。',citation:'内容记录 · 系列表现'},{label:'用户反馈',answer:'大家最常提到的是查找素材，优先把检索入口做清楚。',citation:'反馈记录 · 需求整理'}];
  const sources=(Array.isArray(options.content?.sources)?options.content.sources:defaults).filter(source=>source && typeof source==='object').slice(0,3);
  const select=index=>{[...list.children].forEach((b,i)=>b.setAttribute('aria-pressed',String(i===index)));charts.forEach((c,i)=>c.dataset.selected=String(i===index));excerpt.textContent=String(sources[index]?.answer ?? options.content?.emptyText ?? '还没有可引用的来源。');reference.textContent=String(sources[index]?.citation ?? '');reference.hidden=!reference.textContent;};
  list.replaceChildren();
  charts.forEach((chart,i)=>{
    chart.hidden=!sources[i];if(!sources[i])return;
    chart.querySelector('[data-text]').textContent=String(sources[i].label ?? '');
    const data=sources[i].chart;if(!data || typeof data!=='object')return;
    if(i===0 && typeof data.value==='number' && Number.isFinite(data.value)){
      const max=typeof data.max==='number' && Number.isFinite(data.max) && data.max>0?data.max:100,ratio=clamp(data.value/max),length=2*Math.PI*48;
      chart.querySelector('.ring-value').style.strokeDasharray=`${length*ratio} ${length*(1-ratio)}`;
    }
    if(i>0 && Array.isArray(data.series)){
      const series=data.series.filter(n=>typeof n==='number' && Number.isFinite(n)).slice(0,32),path=chart.querySelector(i===1?'.chart-bars':'.chart-line');
      const low=Math.min(0,...series),high=Math.max(1,...series),y=value=>115-(value-low)/(high-low)*95;
      if(i===1){path.setAttribute('d',series.map((n,j)=>`M${20+(j+.5)*120/series.length} 115V${y(n)}`).join(' '));path.style.strokeWidth=String(Math.min(15,72/Math.max(1,series.length)));}
      else path.setAttribute('d',series.map((n,j)=>`${j?'L':'M'}${series.length===1?80:15+j*130/(series.length-1)} ${y(n)}`).join(' '));
    }
  });
  sources.forEach((source,index)=>{const b=document.createElement('button');b.type='button';b.textContent=`${index+1} · ${source.label ?? ''}`;b.addEventListener('click',()=>select(index),{signal:events.signal});list.append(b);});select(0);
  return {destroy(){events.abort();clean();list.replaceChildren();charts.forEach(chart=>{delete chart.dataset.selected;chart.querySelector('.ring-value')?.style.removeProperty('stroke-dasharray');chart.querySelector('.chart-bars')?.style.removeProperty('stroke-width');});}};
}
