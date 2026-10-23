// run-code 将此文件作为函数表达式，末尾不能有分号。
// prettier-ignore
async (page) => {
  const base = await page.evaluate(() => new URL(".", location.href).href);
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const assert = (condition, message) => {
    if (!condition) throw new Error(message);
  };
  const text = (selector) => page.locator(selector).textContent();
  const noOverflow = async (label) =>
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
      label + ": 页面横向溢出",
    );
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  assert((await page.locator(".specimen").count()) === 19, "应有 19 个原型");
  await page.locator("[data-action=bookmark]").click();
  assert((await text("[data-action=bookmark]")) === "已收藏", "收藏未切换");
  await page.locator("#more").click();
  assert((await text("#add")) === "加入 · ¥256", "数量与总额不同步");
  for (let i = 0; i < 10; i++)
    if (!(await page.locator("#more").isDisabled()))
      await page.locator("#more").click();
  assert(await page.locator("#more").isDisabled(), "数量上界未限制");
  await page.locator("#add").click();
  assert((await text("#cart-result")).includes("9 张"), "加入结果错误");
  await page.locator("#period").selectOption("month");
  assert((await text("#metric-value")).includes("92"), "指标周期未切换");
  await page.locator("#follow").click();
  assert((await text("#followers")).includes("129"), "关注数未更新");
  await page.locator("#annual").check();
  assert((await text("#price")) === "¥288", "年度价格错误");
  await page.locator("#plan").click();
  assert((await text("#plan-result")).includes("年付"), "套餐结果错误");
  for (const input of await page.locator(".task-check").all())
    await input.check();
  assert((await text("#task-result")).includes("全部完成"), "任务进度错误");
  for (let i = 0; i < 3; i++) await page.locator("#next-step").click();
  assert(await page.locator("#next-step").isDisabled(), "过程终态错误");
  await page.locator("#reset-step").click();
  assert(!(await page.locator("#next-step").isDisabled()), "过程不可重置");
  const download = page.waitForEvent("download");
  await page.locator("#file a").click();
  const file = await download;
  assert(file.suggestedFilename().endsWith(".csv"), "下载文件无效");
  await page.locator("#rsvp").click();
  assert((await text("#seats")).includes("7"), "报名名额错误");
  await page.locator("#rsvp").click();
  assert((await text("#seats")).includes("8"), "取消未归还名额");
  await page.locator("#audio").evaluate(
    (audio) =>
      new Promise((resolve, reject) => {
        if (audio.readyState >= 1) resolve();
        else {
          audio.addEventListener("loadedmetadata", resolve, { once: true });
          audio.addEventListener("error", reject, { once: true });
        }
      }),
  );
  assert(
    await page.locator("#audio").evaluate((audio) => audio.duration > 0),
    "音频未解码",
  );
  await page.locator("#play").click();
  await page.waitForFunction(() => !document.querySelector("#audio").paused);
  await page.locator("#play").click();
  await page.locator("#quote-next").click();
  assert((await text("#quote-page")) === "2 / 3", "证言未翻页");
  await page.locator("[data-choice=竹纸]").click();
  assert((await text("#trip-result")).includes("竹纸"), "选择结果错误");
  for (const button of await page.locator(".read").all()) await button.click();
  assert((await text("#unread")) === "0 条未读", "通知状态错误");
  await page.locator("#project-name").fill("本地项目");
  await page.locator("#inline-form button").click();
  await page.waitForFunction(() =>
    document.querySelector("#inline-result").textContent.includes("已保存"),
  );
  await page.locator("#create-note").click();
  assert((await page.locator("#notes li").count()) === 1, "空状态未创建内容");
  await page.locator("#advance").click();
  assert((await text("#kanban-state")) === "进行中", "看板未推进");
  await page.locator("#fold-toggle").click();
  assert(await page.locator("#fold-body").isVisible(), "折展未展开");
  await page.locator("#drawer-toggle").click();
  await page.locator("#drawer-text").fill("新的计划介绍");
  await page.locator("#drawer-form button[type=submit]").click();
  assert((await text("#drawer-summary")) === "新的计划介绍", "微抽屉未保存");
  assert(
    await page
      .locator("#drawer-toggle")
      .evaluate((el) => el === document.activeElement),
    "微抽屉未恢复焦点",
  );
  await page.locator("#focus-start").click();
  assert((await text("#focus-result")).includes("眼前"), "聚光主操作未响应");
  await page.locator("#filter").fill("不存在");
  assert(await page.locator("#no-matches").isVisible(), "搜索空态缺失");
  await page.locator("#filter").fill("");
  await noOverflow("组件桌面");
  await page.screenshot({ path: "cards-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await noOverflow("组件手机");
  await page.screenshot({ path: "cards-mobile.png", fullPage: true });
  await page.locator("#theme").selectOption("night");
  await page.screenshot({ path: "cards-night.png", fullPage: true });
  await page.goto(base + "workspace.html");
  await page.locator("#search").fill("雪中");
  assert((await page.locator("#items button").count()) === 1, "工作区搜索错误");
  await page.locator("#items button").click();
  assert(await page.locator("#inspector").isVisible(), "手机详情不可达");
  // 一次只套一块版：雪中椿已套 2 块，再套两次才完成；完成后主按钮停用，可撤销。
  await page.locator("#move").click();
  assert((await text("#detail-state")).includes("进行中"), "套版跳步");
  await page.locator("#move").click();
  assert((await text("#detail-state")).includes("已完成"), "工作区状态未推进");
  assert(await page.locator("#move").isDisabled(), "完成后仍可推进");
  await page.locator("#undo").click();
  assert((await text("#detail-state")).includes("进行中"), "撤销未恢复");
  await page.locator("#move").click();
  await page.locator("#back-list").click();
  await page.locator("#search").fill("");
  await page.locator("#layout").selectOption("board");
  assert((await page.locator(".column").count()) === 3, "看板布局缺失");
  await page.locator("#layout").selectOption("table");
  assert((await page.locator("tbody tr").count()) === 6, "表格布局缺失");
  await noOverflow("工作区手机");
  await page.screenshot({ path: "workspace-mobile.png", fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.locator("#layout").selectOption("list");
  await page.screenshot({ path: "workspace-desktop.png", fullPage: true });
  await page.goto(base + "interaction.html");
  await page.locator("#reset").evaluate((button) => button.click());
  for (const state of [
    "loading",
    "empty",
    "error",
    "offline",
    "denied",
    "ready",
  ]) {
    await page.locator("#view-state").selectOption(state);
    assert((await text("#state-panel")).trim().length > 0, "缺少状态 " + state);
  }
  await page.locator("#fail-save").check();
  await page.locator("#open-dialog").click();
  assert(
    await page
      .locator("#title")
      .evaluate((el) => el === document.activeElement),
    "弹窗初始焦点错误",
  );
  await page.locator("#title").fill("恢复后的计划");
  await page.locator("#email").fill("not-an-email");
  await page.locator("#save").click();
  assert(
    !(await page.locator("#email").evaluate((el) => el.validity.valid)),
    "邮件格式未校验",
  );
  await page.locator("#email").fill("reader@example.com");
  await page.locator("#save").click();
  await page.locator("#form-error").waitFor({ state: "visible" });
  assert(
    (await page.locator("#title").inputValue()) === "恢复后的计划",
    "失败丢失输入",
  );
  await page.screenshot({ path: "form-error-desktop.png" });
  await page.locator("#cancel").click();
  assert(
    await page
      .locator("#open-dialog")
      .evaluate((el) => el === document.activeElement),
    "弹窗未恢复焦点",
  );
  assert(!(await page.locator("#fail-save").isChecked()), "失败开关未在一次失败后关闭");
  await page.locator("#open-dialog").click();
  await page.locator("#title").fill("恢复后的计划");
  await page.locator("#save").click();
  await page.locator("#editor").waitFor({ state: "hidden" });
  assert((await text("#state-panel")).includes("恢复后的计划"), "重试未保存");
  await page.reload();
  assert(
    (await text("#state-panel")).includes("恢复后的计划"),
    "本地存储未恢复",
  );
  await page.locator("#open-dialog").click();
  await page.locator("#title").fill("不得迟到的保存");
  await page.locator("#save").click();
  await page.locator("#cancel").click();
  await page.waitForTimeout(450);
  assert(
    !(await text("#state-panel")).includes("不得迟到"),
    "取消未终止旧提交",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#open-dialog").click();
  await noOverflow("表单手机");
  await page.screenshot({ path: "form-mobile.png" });
  await page.keyboard.press("Escape");
  assert(!(await page.locator("#editor").isVisible()), "Escape 未关闭弹窗");
  await page.goto(base + "effects.html");
  assert((await text("#motion-status")).includes("静态"), "减少动态效果未响应");
  for (let i = 0; i < 5; i++) await page.locator("#target").click();
  assert((await text("#game-status")).includes("完成"), "小游戏未完成");
  await page.locator("#game-reset").click();
  await page.locator("#game-pause").click();
  assert(await page.locator("#target").isDisabled(), "暂停仍可输入");
  await page.locator("#game-pause").click();
  await page.locator("#target").focus();
  await page.keyboard.press("Enter");
  assert(
    (await text("#game-status")).startsWith("1 / 5"),
    "小游戏键盘输入失败",
  );
  await noOverflow("动效手机");
  await page.screenshot({ path: "effects-mobile.png", fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.locator("#motion-toggle").click();
  assert((await text("#motion-status")).includes("暂停"), "动态暂停失效");
  await page.screenshot({ path: "effects-desktop.png", fullPage: true });
  assert(errors.length === 0, "浏览器脚本错误：" + errors.join("; "));
  const single = await page.context().newPage();
  single.on("pageerror", (error) => errors.push(error.message));
  await single.goto(base + "index.html");
  const snippets = await single
    .locator(".card")
    .evaluateAll((cards) => cards.map((card) => card.outerHTML));
  for (let i = 0; i < snippets.length; i++) {
    await single.goto(base + "index.html");
    await single.setContent(
      '<html lang="zh-CN"><head><base href="' +
        base +
        '"></head><body>' +
        snippets[i] +
        "</body></html>",
    );
    await single.addScriptTag({ url: base + "cards.js" });
    const button = single.locator("button").first();
    if ((await button.count()) && !(await button.isDisabled()))
      await button.click();
  }
  await single.close();
  assert(errors.length === 0, "单卡初始化错误：" + errors.join("; "));
  return {
    passed: true,
    prototypes: 19,
    viewports: ["1440x1000", "390x844"],
    pages: 4,
    shader: await text("#shader-status"),
    reference_parity: "未验证：没有第三方原版基线",
  };
}
