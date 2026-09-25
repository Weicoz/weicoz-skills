---
name: weicoz-semrush-ego-browser
description: >
  Use when the user wants to operate a configured Semrush proxy through a real browser,
  especially Keyword Magic Tool, Keyword Overview, Keyword Strategy Builder, or filters
  using KD, Volume, and CPC thresholds. Use this skill for repeatable Semrush
  extraction and CSV/JSON output. Browser priority is ego-browser, then browser-skill,
  then @Chrome; never invent metrics or treat shell HTML as a successful table.
allowed-tools: Bash(ego-browser:*), Bash(bsk:*), Bash(node:*), Bash(mkdir:*), Bash(date:*), Bash(test:*)
---

# Semrush via Ego Browser

通过真实渲染页面读取 Semrush 数据。默认浏览器优先级严格为：`ego-browser` -> `browser-skill` -> `@Chrome`。只有当前工具不可用，或已确认无法完成当前页面能力时，才进入下一层；每次 fallback 记录页面、失败信号和尝试次数。

## 配置

- `WEICOZ_SEMRUSH_PROXY_HOST`：代理域名，不在 skill 中硬编码。
- `WEICOZ_SEMRUSH_FID`：可选项目/文件夹 id。
- URL 中的登录参数（例如 `__gmitm`）只从用户已打开的当前结果页继承，不复制到报告或日志。

## ego-browser 主路径

通过 `ego-browser nodejs <<'EOF' ... EOF` 执行，并在每个 heredoc 开头调用 `useOrCreateTaskSpace('semrush keyword research')` 复用同一 task space。

1. 用 `openOrReuseTab` 打开 `https://${WEICOZ_SEMRUSH_PROXY_HOST}/analytics/keywordmagic/`，只改变 `q`、`db`、`fid` 参数。
2. 用 `pageInfo()` 和 `snapshotText()` 核对标题、URL、查询词和登录状态。
3. 等待真实表格渲染；需要精确字段时，用一个 `js()` IIFE 提取 `.sm-kmt-table__table`，必要时兼容 AG Grid 和标准 table。
4. 应用页面筛选：`Volume > minVolume`、`KD < maxKd`、`CPC > minCpc`。必须读取筛选控件的可见标签并验证每一行满足阈值；不接受只在本地数组过滤后冒充页面筛选。
5. 输出 `keyword / intent / volume / kd / cpc_usd / sf / updated / _raw`，并保存 CSV/JSON。
6. 只在结果已保存、标题/URL/行数均验证后，使用独立最终 heredoc 调用 `completeTaskSpace(taskId, { keep: false })`。

### Keyword Magic 质量闸门

以下任一项不成立，运行失败，不得返回“成功”：

- 页面标题包含 `Keyword Magic Tool`；
- URL 的 `q`、`db`、`fid` 与本次请求一致；
- 页面筛选控件显示预期范围；
- 真实渲染表格存在表头或行，且行数大于 0；
- 抽取行没有违反 `volume > minVolume`、`kd < maxKd`、`cpc > minCpc`。

shell HTML、登录页、builder 起始页、旧 query 的残留 tab 都属于失败。报告实际失败原因，不补造数据。

### Keyword Overview

打开 `/analytics/keywordoverview/` 的真实结果页，读取 summary、countries、keyword variations、questions、clusters。前端渲染结果优先从当前 tab DOM 提取；服务端 HTML 只有在字段完整且标题/URL 已核对时才可接受。

### Keyword Manager

支持 builder/list URL 构造和当前 builder 状态读取。`keywordmanager/list` 若回退到 builder，明确报告回退，不声称拿到了稳定列表。

## browser-skill fallback

仅 ego-browser 不可用或无法完成当前能力时使用。严格执行：

```text
bsk session start
bsk navigate/snapshot/evaluate ... --session <id>
bsk session stop <id>
```

每条命令传同一个 session id；成功和异常路径都必须 stop。先 `bsk snapshot`，再根据最新引用操作；不使用旧 ref。

## @Chrome fallback

仅前两层都不可用或无法完成当前能力时使用。加载 `chrome:control-chrome`，通过绝对路径的 `browser-client.mjs` 建立浏览器 binding，读取完整 documentation 后再操作；复用现有登录态和 tab binding，不读取 cookies、localStorage、token 或密码。任务完成后关闭临时 tab。

## 可复用脚本

脚本也必须走上述浏览器优先级，不再依赖旧 CLI adapter：

```bash
node scripts/keywordmagic-filter-runner.mjs \
  --query <query> --db us --fid "$WEICOZ_SEMRUSH_FID" \
  --seed-url <verified-filter-url> --maxKd 30 --minCpc 0.1 --limit 20
```

脚本默认调用 `ego-browser nodejs`，验证失败退出非零；若 ego-browser 不可用，停止并按本 skill 的 browser-skill / @Chrome fallback 手工完成，不得静默切换。

西语批量脚本 `scripts/spanish-tool-roots-batch.mjs` 同样要求 `--seed-url`，每个市场和词根保存 checkpoint；单个查询失败继续其他查询，最终报告成功/失败数。

## 失败与安全边界

- 403/429、验证码、登录过期：记录失败信号，必要时交给用户完成认证，再从原 task space 继续。
- 没有真实 SEO KD：可改用 Ads-KDRoi proxy，但输出必须标注 `proxy`，不能判定为标准 SEO KD。
- 临时 tab 只由当前运行创建和关闭；不关闭用户既有 tab。
- 只读页面和数据，不执行加词、建列表、导出账户私密数据或任何写操作。
