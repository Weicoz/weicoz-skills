import {shell} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,options);
  const grid=element.querySelector('.file-grid');
  const icons={doc:'<path d="M7 3h13l6 6v21H7Z M20 3v7h6 M12 16h9 M12 21h9"/>',image:'<rect x="3" y="5" width="28" height="24" rx="3"/><circle cx="12" cy="13" r="3"/><path d="m5 26 8-8 5 4 5-7 7 9"/>',video:'<rect x="3" y="7" width="20" height="21" rx="3"/><path d="m23 13 8-4v17l-8-4"/>',code:'<path d="m11 10-8 7 8 7 M23 10l8 7-8 7 M19 5l-5 24"/>'};
  const fallback=[['image','cover.png'],['color','palette.fig'],['doc','brief.pdf'],['video','intro.mp4'],['code','tokens.json'],['audio','theme.wav'],['image','texture.jpg'],['doc','notes.md'],['image','poster.png'],['video','reel.mov'],['doc','license.txt'],['code','theme.css'],['image','scene.webp'],['audio','voice.wav'],['doc','guide.pdf']].map(([type,name])=>({type,name}));
  const files=Array.isArray(options.content?.files)?options.content.files:fallback;
  grid.replaceChildren();
  for(const file of files){
    const type=file.type || 'doc',tile=document.createElement('div'),art=document.createElement('div'),label=document.createElement('span');
    tile.className='file-tile';art.className='file-art';
    art.innerHTML=type==='color'?'<div class="file-thumbnail"><i></i><i></i><i></i><i></i></div>':type==='audio'?'<div class="file-wave">'+[12,23,32,17,27,35,22,13,24].map(h=>`<i style="--h:${h}px"></i>`).join('')+'</div>':`<svg viewBox="0 0 34 34">${icons[type] || icons.doc}</svg>`;
    label.textContent=String(file.name ?? '');label.title=label.textContent;tile.append(art,label);grid.append(tile);
  }
  if(!files.length){const empty=document.createElement('p');empty.className='file-empty';empty.textContent=options.content?.emptyText ?? '还没有文件';grid.append(empty);}
  
  element.querySelector('.file-collection i').hidden=!files.length;
  if(!files.length && options.content?.status===undefined)element.querySelector('[data-text="status"]').textContent='暂无文件';
  return{destroy(){clean();grid.replaceChildren();}};
}
