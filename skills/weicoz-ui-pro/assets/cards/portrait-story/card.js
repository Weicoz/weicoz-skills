import {shell} from '../shared/runtime.js';
export function mount(element, options = {}) {
  const clean=shell(element,options);
  return {destroy(){clean();}};
}
