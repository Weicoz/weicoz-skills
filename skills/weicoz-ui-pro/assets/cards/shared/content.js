// Content values are plain text. A line break is content, not injected markup.
export function contentValue(content, path) {
  return path.split('.').reduce((value,key)=>value!=null && Object.hasOwn(value,key)?value[key]:undefined,content);
}
function url(value, image=false) {
  if(typeof value!=='string' || !value.trim())return null;
  try {
    const protocol=new URL(value,document.baseURI).protocol;
    if(['http:','https:','file:'].includes(protocol) || (!image && ['mailto:','tel:'].includes(protocol)) || (image && (protocol==='blob:' || /^data:image\/(png|jpeg|webp|gif|svg\+xml)[;,]/i.test(value))))return value;
  } catch {}
  return null;
}
export function applyContent(element, content={}) {
  if(!content || typeof content!=='object')return;
  for(const node of element.querySelectorAll('[data-text]')) {
    const value=contentValue(content,node.dataset.text);
    if(value!==undefined && value!==null)node.textContent=Array.isArray(value)?value.join('\n'):String(value);
  }
  for(const node of [element,...element.querySelectorAll('[data-href]')]) {
    if(!node.hasAttribute('data-href'))continue;
    const value=contentValue(content,node.dataset.href);
    if(value===undefined)continue;
    const href=url(value);if(href)node.setAttribute('href',href);else node.removeAttribute('href');
  }
  for(const node of element.querySelectorAll('[data-image]')) {
    const value=contentValue(content,node.dataset.image);
    if(!value)continue;
    const src=url(typeof value==='string'?value:value.src,true);
    if(src){node.src=src;if(typeof value==='object' && value.alt!==undefined)node.alt=String(value.alt);}
  }
}
