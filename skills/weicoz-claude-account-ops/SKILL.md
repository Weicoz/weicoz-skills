---
name: weicoz-claude-account-ops
version: 1.0.0
description: Claude Code 多账号切换的运维流程与前置检查：加号、切号、槽位凭据异常修复、macOS 钥匙串限制、cswap 的安全用法。当用户要保存 Claude Code 登录、在多个订阅账号之间切换而不走 /login、或修复"两个槽位同一凭据""re-login needed"时使用。核心是三条不变量和固定顺序，配合 cswap-guard 在改动登录态前做确定性检查。
whenToUse: 用户提到剪藏/切换 Claude Code 账号、cswap、多账号共用 ~/.claude、refresh token 失效、槽位凭据重复，或要在 SSH 里操作 macOS 钥匙串。
---

# Claude Code 账号切换运维（weicoz-claude-account-ops）v1.0.0

目标：在共用 `~/.claude`（settings、CLAUDE.md、skills、MCP、历史都不动）的前提下切换订阅账号，全程不重登。**风险不在读写钥匙串，而在破坏"live 就是活跃槽位"这个假设。**

## 不变量

1. 同一时刻只有一份 live 登录（`Claude Code-credentials`）。
2. 每个槽位的备份必须与 live 隔离；槽位里的凭据只能属于该槽位的账号。
3. cswap 每次写回都以"live == 活跃槽位"为前提。前提破了，它会把 A 的凭据写进 B 的槽位，两份账号互相覆盖，被覆盖的 refresh token 随即轮换作废。

第 3 条在 2026-11-15 真实发生过：登录第二个号时一个 `cswap list` 还在跑，它把新账号凭据回写进旧槽位，旧账号只能重登。

## 固定顺序

1. 登录新账号：`claude` → `/login`（**不要 `/logout`**，会吊销 refresh token）。
2. 立刻登记：`cswap-guard run add`。
3. 之后所有命令都走 guard：`cswap-guard run list`、`cswap-guard run switch 2`。

禁止窗口：登录完成到 `add` 完成之间，不跑 `list`、`status`、`switch`，也不让任何 cswap 进程在后台跑完。

## cswap-guard

同目录 `scripts/cswap-guard`，安装到 PATH 后使用：

| 命令 | 作用 |
|---|---|
| `cswap-guard check` | 只检查：并发进程、身份一致性、槽位备份 |
| `cswap-guard backup` | 把 live 凭据备份到 `~/.claude-accounts/live-<时间>.json`（0600，留 10 份） |
| `cswap-guard run <args…>` | 检查通过后执行 cswap；add/switch/import 前自动备份 |

退出码 `3` 表示钥匙串不可用（SSH、锁屏、无图形会话），必须换到 Mac 本地终端。

身份不一致时只放行 `add`：这正是"刚登录新号"的合法状态；其它命令会被拒绝并给出修复命令。

## macOS 钥匙串

- 凭据存 `Claude Code-credentials`；设了 `CLAUDE_CONFIG_DIR` 则每条目录一个 `-<hash>` 后缀条目。
- Claude Code 用 `security find-generic-password` 读、`security add-generic-password -U` 写。`-U` 是删了重建，会重置条目 ACL，所以"始终允许"不会永久生效，切换后可能再弹一次授权框。
- 钥匙串写入被拒时（SSH、锁屏）官方回退到 `.credentials.json`（0600），别在两个后端之间混用同一账号。

## 故障处理

- **两个槽位同一指纹**：说明有槽位被覆盖。先查 `account-<N>-<email>.prev`，写回后必须验证：请求刷新接口，返回 `invalid_grant` 就是该 lineage 已死，只能重新登录，不要反复重试。
- **`re-login needed — refresh token dead`**：该槽位凭据作废。用该账号登录一次，再 `cswap-guard run add`（原位刷新，不建重复槽位）。
- **切号没立刻生效**：macOS 有约 30 秒钥匙串缓存，下一条消息才走新账号；重开 Claude Code 可立即生效。
- **切换会打断正在跑的会话**：所有在跑的 Claude Code 会话都会转向新账号，Remote Control 会断开。

## 不做的

- 不开 `cswap auto`（自动轮换是最接近"规避限额"定性的用法）。
- 不代理模型请求、不把订阅 OAuth 给第三方客户端用。
- 不把 token 写进日志、导出文件或对话；`cswap export` 是明文 JSON，只在本机用。
- 不并发：同一账号不能一处快照、一处 live 同时刷新。

## 参考

- 官方认证文档（多账号、凭据存储、回退）：https://code.claude.com/docs/en/authentication
- cswap 文档：https://github.com/realiti4/claude-swap
- 相关已知问题：anthropics/claude-code#89985（钥匙串弹窗）、#20131（多账号支持）
