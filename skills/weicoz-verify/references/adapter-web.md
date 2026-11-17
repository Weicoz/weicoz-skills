# Web 适配器

怎么为项目选流程、写流程、证明它能抓错，见 `e2e-authoring.md`。本文只讲网页脚本的用法和格式。

脚本：`scripts/web-verify.mjs`（只用 Node 内置模块）。输出遵守 `SKILL.md` 第 2 节：最后一行是结论行，退出码 0 通过、1 不通过、3 未验证。

```bash
node ~/.agents/skills/weicoz-verify/scripts/web-verify.mjs --project <目录> [--quick] [--base-url <URL>] [--script <流程名或路径> ...] [--no-start] [--no-checks] [--env-file <路径>] [--base <ref>]
```

| 参数 | 作用 |
| --- | --- |
| `--quick` | 快检：只跑 `checks.quick` 与 `quickFlows` |
| `--base-url` | 覆盖配置里的 baseUrl |
| `--script` | 只跑指定流程（可重复），写流程名（`smoke`）或路径均可，忽略 glob 与 quick 过滤 |
| `--no-start` | 不拉起服务；服务没起来时相关项记“未验证” |
| `--no-checks` | 跳过命令检查，只跑流程；写流程时反复试跑用 |
| `--base` | 评分配置（`web-verify.config.json`、`AGENTS.md`、`CLAUDE.md`、`package.json` 的 `verify:*` 脚本）相对 `<ref>` 有改动时，打印改动并记“未验证（缺：评分配置改动待用户确认）”；验收时带上 |
| `--env-file` | 读入 env 文件（只进内存，不打印），传给被拉起的服务和流程；也可用环境变量 `WEB_VERIFY_ENV_FILE` |

## 配置

文件：`<项目>/tests/e2e/web-verify.config.json`，字段全部可选。

```json
{
  "baseUrl": "http://127.0.0.1:3000",
  "start": { "command": "pnpm dev", "readyPath": "/", "timeoutSec": 120 },
  "checks": {
    "quick": [{ "name": "类型检查", "cmd": "pnpm typecheck" }],
    "full":  [{ "name": "类型检查", "cmd": "pnpm typecheck" }, { "name": "单测", "cmd": "pnpm test", "timeoutSec": 900 }]
  },
  "viewports": [{ "name": "mobile", "width": 390, "height": 844 }, { "name": "desktop", "width": 1440, "height": 900 }],
  "flows": "tests/e2e/*.flow.mjs",
  "quickFlows": ["smoke"],
  "ignore": { "console": ["regex"], "pageerror": [], "requests": ["favicon\\.ico"] }
}
```

- `start`：端口已有服务时直接用，不管理它，并在明细里提示“复用已运行的服务，未确认是本次代码构建”；没有才拉起，结束时只关自己起的进程组。`readyPath` 返回 5xx 以下状态算就绪。
- `checks.<档>`：按顺序跑，失败附输出末 5 行。`timeoutSec` 默认 600。
- `flows`：只支持文件名里的 `*`。`quickFlows` 写流程名（去掉 `.flow.mjs`）。
- `flowTimeoutSec`：单个流程的整体超时，默认 180，超时记失败。
- `ignore`：正则字符串（非法正则按子串）。`console` 和 `pageerror` 匹配消息文本，`requests` 匹配 `METHOD 状态码 URL`（请求失败为 `METHOD 失败 URL 原因`）。只放确认无害的噪声，不得用它掩盖真错误。每类被忽略的条数大于 0 时会打印；`.`、`.*` 这类吞掉一切的模式视为配置错误，结论记“未验证（缺：有效 ignore 配置）”。

## 流程脚本

每个 `*.flow.mjs` 默认导出一个函数，每个视口各跑一遍。

```js
export default async ({ page, baseUrl, step, shot, viewport, unverified }) => {
  await step('打开首页', async () => {
    await page.goto(baseUrl + '/');
    await page.getByRole('heading', { level: 1 }).waitFor();
  });
  await shot('home'); // 存到 <项目>/temp/web-verify/<流程>-<视口>-home.png
};
```

- `step(名称, fn)`：记一行结果；失败时中止本流程。
- `shot(名称)`：截图并加入联系图。运行器会在流程结束时自动补一张 `end`。
- `unverified(缺什么)`：前置条件不具备（缺凭据、后端起不来）时调用，该流程记“未验证”；此前已有失败步骤或 problems 时仍记失败。
- 流程没有任何 `step` 记失败（“流程没有任何 step 断言”）。每个流程整体受 `flowTimeoutSec` 限制。
- 运行器自动收集：控制台 error、未捕获异常、同源 4xx/5xx、同源请求失败（requestfailed）。出现任何一条，该流程记失败。
- 凭据只从环境变量读，不打印、不提交。流程只做只读浏览；不得点会触发外部写操作的按钮。
- 共用辅助文件不要命名成 `*.flow.mjs`（如 `_login.mjs`）。

## 联系图

全部截图按文件名排序，拼成 `temp/web-verify/contact.png`，脚本打印一行路径。看图按 `visual-checklist.md`。`temp/` 不入库：项目 `.gitignore` 没有时补一行。

## 接进项目 AGENTS.md

按 `project-section.md` 写 `## 验证约定`：适配器填 `web`；快检填 `pnpm verify:web:quick`，全检填 `pnpm verify:web`。`package.json` 里写：

```json
"verify:web": "node ${WEB_VERIFY_SCRIPT:-$HOME/.agents/skills/weicoz-verify/scripts/web-verify.mjs} --project .",
"verify:web:quick": "node ${WEB_VERIFY_SCRIPT:-$HOME/.agents/skills/weicoz-verify/scripts/web-verify.mjs} --project . --quick"
```

skill 装在别处时，设环境变量 `WEB_VERIFY_SCRIPT` 指向脚本。

## 找 Playwright 与浏览器

顺序：项目 `node_modules`（`playwright`、`@playwright/test`、`playwright-core`）→ `npm root -g` 下同名包及 `@playwright/*/node_modules`。都没有：输出指引，`结论：未验证（缺：playwright）`，退出码 3。自带 chromium 缺失时退到本机 Chrome；都没有则 `未验证（缺：chromium 浏览器）`，执行 `npx playwright install chromium`。

## 常见坑

- 服务没起来：看失败时打印的服务日志末尾。数据库、端口占用等依赖起不来时记“未验证”，不得为过关改库或改环境。
- 登录页面：用项目的开发登录或测试账号，在流程开头调用；凭据缺失就 `unverified(...)`。
- 控制台报错来自第三方脚本：先确认无害，再加进 `ignore`，并写明原因。
- 流程不稳：用 `waitFor`、`expect` 类断言等待元素，不用固定 sleep。
- 只看到“结论：通过”不等于画面没问题：还要看联系图。
- 用了 `--no-checks` 或 `--script` 就是部分验证：档位行写“部分（<开关>）”，全部通过时结论也只是“未验证（缺：完整快检/全检，本次用了 <开关>）”，退出码 3。`--base-url`、`--no-start` 不降级（对部署环境跑是正当全检）。
- 命令检查输出上限 64MB；运行器自身异常时末行为“结论：未验证（缺：运行器异常 <首行>）”，退出码 3，并清理自己拉起的服务。
