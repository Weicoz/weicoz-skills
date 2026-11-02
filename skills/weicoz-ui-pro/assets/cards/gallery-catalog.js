export function createCatalog(query) {
  const descriptions={
    all:'',
    visual:'用光场、曲面和影像建立品牌印象。先选视觉语言，再替换品牌与内容。',
    product:'把真实产品的一小段体验放大呈现：任务、文件、运行输出与内容就绪。',
    data:'表达数量、范围和连接关系。数据可以替换，图形应保持清楚的阅读顺序。',
    action:'引导一个清楚的下一步：快捷操作、资源入口或推广行动。'
  };
  const items=[...document.querySelectorAll('main [data-family]')],buttons=[...document.querySelectorAll('[data-family-filter]')],summary=document.querySelector('.category-summary');
  const groups=[...document.querySelectorAll('.signature-grid,.exploration-grid,.utility-grid,.peer-grid')];
  const controller=new AbortController();
  buttons.forEach(button=>{const family=button.dataset.familyFilter;button.querySelector('span').textContent=String(items.filter(item=>family==='all'||item.dataset.family===family).length);});
  function select(family){
    document.querySelector('main').dataset.category=family;
    items.forEach(item=>{item.hidden=family!=='all'&&item.dataset.family!==family;});
    groups.forEach(group=>{group.hidden=![...group.querySelectorAll('[data-family]')].some(item=>!item.hidden);});
    document.querySelector('.peer-intro').hidden=document.querySelector('.peer-grid').hidden;
    document.querySelector('.showcase-intro').hidden=document.querySelector('.showcase-section').hidden;
    buttons.forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.familyFilter===family)));
    summary.textContent=descriptions[family];summary.hidden=!summary.textContent;
  }
  buttons.forEach(button=>button.addEventListener('click',()=>select(button.dataset.familyFilter),{signal:controller.signal}));
  const requested=query.get('category');select(!query.has('focus')&&Object.hasOwn(descriptions,requested)?requested:'all');
  return {destroy(){controller.abort();}};
}
