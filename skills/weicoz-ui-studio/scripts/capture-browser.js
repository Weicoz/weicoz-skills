// run-code 将此文件作为函数表达式，末尾不能有分号。
// prettier-ignore
async (page) => {
  const spec = /*SPEC*/ null;
  const cases = [];
  for (const item of spec.cases) {
    const errors = [];
    const onError = (error) => errors.push(error.message);
    page.on("pageerror", onError);
    try {
      await page.setViewportSize(item.viewport);
      await page.emulateMedia({
        reducedMotion:
          item.reduced_motion === false ? "no-preference" : "reduce",
      });
      await page.goto(item.url, { waitUntil: "load" });
      await page.evaluate(() => document.fonts.ready);
      for (const action of item.actions || []) {
        const target = action.selector ? page.locator(action.selector) : null;
        if (action.type === "click") await target.click();
        else if (action.type === "fill") await target.fill(action.value);
        else if (action.type === "select")
          await target.selectOption(action.value);
        else if (action.type === "press") await page.keyboard.press(action.key);
        else if (action.type === "scroll")
          await page.mouse.wheel(action.x || 0, action.y || 0);
        else if (action.type === "wait")
          await page.waitForTimeout(
            Math.max(0, Math.min(10000, action.ms || 0)),
          );
        else if (action.type === "drag")
          await target.dragTo(page.locator(action.to));
      }
      if (item.mark)
        for (const [i, selector] of item.mark.entries()) {
          await page.locator(selector).evaluate((node, number) => {
            node.style.outline = "3px solid #b62c1b";
            node.setAttribute("data-ui-mark", number);
            const badge = document.createElement("span");
            badge.textContent = String(number);
            badge.style.cssText =
              "position:absolute;background:#b62c1b;color:white;padding:2px 6px;z-index:2147483647;pointer-events:none";
            node.prepend(badge);
          }, i + 1);
        }
      const environment = await page.evaluate(() => {
        const fontList = [...document.fonts]
          .map((font) =>
            [font.family, font.style, font.weight, font.status].join(":"),
          )
          .sort();
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");
        context.font = getComputedStyle(document.body).font;
        return {
          os: navigator.platform,
          fonts: JSON.stringify({
            loaded: fontList,
            body: context.font,
            width: context.measureText("界面 Aa 0123456789").width,
          }),
          dpr: devicePixelRatio,
          zoom: visualViewport?.scale || 1,
          reduced_motion: matchMedia("(prefers-reduced-motion: reduce)")
            .matches,
        };
      });
      environment.browser = await page.context().browser().version();
      if (item.selector)
        await page.locator(item.selector).screenshot({ path: item.screenshot });
      else
        await page.screenshot({
          path: item.screenshot,
          fullPage: item.full_page !== false,
        });
      cases.push({
        id: item.id,
        screenshot: item.screenshot,
        viewport: item.viewport,
        environment,
        script_errors: errors,
        captured: errors.length === 0,
      });
    } catch (error) {
      cases.push({
        id: item.id,
        captured: false,
        error: error.message,
        script_errors: errors,
      });
    } finally {
      page.removeListener("pageerror", onError);
    }
  }
  return {
    captured: cases.every((item) => item.captured),
    cases,
    reference_parity: "未验证：截图成功不等于与参考一致",
  };
}
