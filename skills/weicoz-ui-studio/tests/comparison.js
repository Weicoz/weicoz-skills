// run-code 读取函数表达式，末尾不加分号。
async page => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const assert = (value, message) => { if (!value) throw Error(message); };
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.reload();
  await page.setViewportSize({width:1440,height:1000});
  assert(await page.locator('#grid .card').count() === 3, '缺少候选');
  await page.locator('#grid [data-pick="workspace"]').click();
  await page.waitForFunction(() => document.querySelector('#toast').classList.contains('show'));
  assert(await page.locator('#toast').evaluate(el => !el.hasAttribute('data-fail')), '选择复制未成功');
  await page.screenshot({path:'comparison-desktop.png',fullPage:true});
  await page.locator('#grid .card[data-id="components"] .hit').click();
  await page.locator('#loupe').waitFor({state:'visible'});
  assert(!(await page.locator('#film').textContent()).includes('null'), '缺省色板显示空节点');
  const iframe = page.locator('#track .slide.is-current iframe');
  const frame = page.frameLocator('#track .slide.is-current iframe');
  // 目标可能在候选首屏以下：先在 iframe 内滚到可视区，再按渲染比例换算真实鼠标坐标。
  await frame.locator('#more').evaluate(el => el.scrollIntoView({block:'center'}));
  const target = await frame.locator('#more').evaluate(el => el.getBoundingClientRect().toJSON());
  const box = await iframe.boundingBox();
  const logical = await iframe.evaluate(el => ({width:el.clientWidth,height:el.clientHeight}));
  // 缩放预览用真实屏幕坐标点击，避免测试驱动把 iframe 的 CSS 比例漏算。
  await page.mouse.click(box.x+(target.x+target.width/2)*box.width/logical.width,
                        box.y+(target.y+target.height/2)*box.height/logical.height);
  await frame.getByRole('button',{name:'加入 · ¥256',exact:true}).waitFor();
  await page.locator('#zoom').click();
  assert(await page.locator('#zoom').getAttribute('aria-pressed')==='true', '实际尺寸无效');
  await frame.locator('#more').click();
  await frame.getByRole('button',{name:'加入 · ¥384',exact:true}).waitFor();
  await page.locator('#next').click();
  const workspace = page.frameLocator('#track .slide.is-current iframe');
  await workspace.locator('#search').fill('铜瓶');
  assert(await workspace.locator('#items button').count()===1, '内嵌工作区筛选失败');
  // 沙箱只放行 data: 图片；脚本引用的图版也必须被内嵌，不能是坏图。
  assert(await workspace.locator('img:not([hidden] img)').evaluateAll(imgs => imgs.length > 0 && imgs.every(i => i.complete && i.naturalWidth > 0)), '内嵌工作区图片未加载');
  await page.locator('button[data-layout="compare"]').click();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'comparison-mobile.png',fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'窄屏溢出');
  assert(errors.length===0,errors.join(';'));
  return {passed:true,candidates:3,copy_feedback:true,scaled_pointer:true,actual_size_pointer:true,
    sandbox_workspace:true,optional_metadata:true,mobile:true,page_errors:errors};
}
