# weicoz-session-recall 开发说明

本文件面向修改本 skill 代码或配套 DSH 插件的人，使用 skill 时不需要读。

## 会话源判定

- 会话源判定集中在 `bin/lib/`，digest 与 recall 共用这一份，不得各自再实现一遍。两边各写一份会因版本优先级不一致（v4 > v3 > 旧版）产生“永久待摘要”的假警报。
- DSH 的版本优先级、项目目录编码与变更判定：`bin/lib/session-source.mjs`。
- 跨 harness 的源注册与统一扫描：`bin/lib/harness.mjs`；各源适配器在 `bin/lib/sources/{dsh,codex,claude,agy,kimi}.mjs`。
- 新增 harness：照现有适配器写一个，并在 `SOURCES` 注册；水位线键用 `<harness>:<id>` 前缀。
- 改完运行：`node --test bin/lib/session-source.test.mjs`。

## DSH 侧栏插件 dsh-session-recall

- 宿主侧路由 `GET /session-recall/summary?sessionId=<id>` 读取同一份 `state.json`。摘要时间取 `detail/<项目>/<日期>-<会话id>.md` 的 mtime，回退 `state.updatedAt`。
- `POST /session-recall/title` 走宿主 `llm` 服务，根据摘要生成标题；模型不可用时前端退回摘要首句。
- 改插件后要重装 bundle 并刷新页面。宿主侧改动还要重启 `dsh web`：宿主半边被 Node 的 ESM 模块缓存持有，停用再启用不会重新读文件。
