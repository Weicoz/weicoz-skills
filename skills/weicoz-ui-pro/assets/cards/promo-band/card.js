import {shell} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,options);
  // A real link: content and destination stay in HTML; no extra geometry knobs.
  
  return {destroy(){clean();}};
}
