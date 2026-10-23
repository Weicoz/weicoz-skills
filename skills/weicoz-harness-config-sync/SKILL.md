---
name: weicoz-harness-config-sync
version: 1.1.0
description: 将 Codex、DSH、Antigravity CLI（agy）和 Shell 配置同步到用户指定机器，并安装对应平台的 CLI、插件及运行依赖。适用于换机、员工设备初始化、Linux 或 Windows 测试机配置迁移；保留模型、Hooks、MCP、插件，按用户要求迁移登录，排除个人会话和记忆。
---

# Harness 配置同步

交付可运行的目标环境：配置与入口关系完整，CLI 和原生依赖符合目标平台，个人历史未导入。当前同步要求决定范围；安装包、配置哈希与真实请求分别验证。

## 确定范围

- 从当前上下文、SSH 配置或 Herdr 保存机器中确认目标、用户、系统及实际数据根目录。用户已指定机器时直接核实连接，不再索要已有信息。
- 模型配置、Hooks、MCP、插件源码、Skills、共用 AGENTS 和 Shell 配置属于可迁移层。登录文件及模型凭据仅在用户要求同步账号或已明确授权同一范围时加入。
- Antigravity CLI 的实际入口是 `.gemini/config/{config.json,hooks.json,mcp_config.json,hooks,plugins,skills}`、`.gemini/antigravity-cli/settings.json` 和 `.gemini/AGENTS.md`；`.gemini/settings.json` 属于旧版 Gemini CLI，agy 不读它。`.gemini/` 下的 brain、conversations、history.jsonl、log、cache、antigravity-browser-profile 以及 google_accounts.json、oauth_creds.json、`antigravity-cli/antigravity-oauth-token` 属于排除层。
- 会话、记忆、历史数据库、生成图片、附件、日志、定时任务、缓存、设备配对和 SSH 私钥属于排除层。目标已有工作保留；不把“不要同步历史”解释为“删除目标历史”。
- 源和目标使用自定义数据根目录时，先核对真实入口。本脚本处理标准用户目录；其他根目录按实际布局适配暂存包及入口，避免生成第二套配置。

## 生成与安装

1. 盘点源版本、各 DSH profile、链接插件、MCP 可执行文件及 Hook 命令；盘点目标现有数据、空间、Node、Shell 和联网路径。只操作用户指定机器。
2. 按源版本安装目标平台 CLI。macOS 二进制、`.venv` 和 `node_modules` 不跨平台复制。长期安装放入已核实的 Herdr pane；普通 SSH 用于本次盘点和文件传输。
3. 用 [scripts/package.py](scripts/package.py) 生成私有暂存包。该脚本按白名单复制配置和源码、改写用户目录、记录 SHA-256，将各 Harness Skills/AGENTS 入口映射到同源。`--extra SOURCE=HOME_RELATIVE_DEST` 仅补充已盘点的插件代码或配置；运行数据不加入。

```bash
python3 "$skill_dir/scripts/package.py" \
  --source-home "$sync_source_home" \
  --target-home "$sync_target_home" \
  --platform "$sync_target_platform" \
  --output "$sync_private_run/package"
```

平台值为 `linux`、`darwin`、`win32`。用户要求 Shell 时加 `--shell`；仅 Shell 用 `--shell-only`。已授权账号迁移时加 `--include-auth`。目标机已有独立技能库（其 `~/.agents/skills/<name>` 本身是指向他处技能仓的软链）时加 `--skip-skills`：只同步配置，技能入口全部指向 `.agents/skills/<name>`，避免安装穿过目标软链改写其技能仓；缺失技能用 `--extra` 补。Shell 过滤凭据导出和凭据加载器，但仍需检查函数及语法；目标原有代理、PATH 和凭据导出按差异保留。

4. 修改暂存包中的调用路径，完成 [跨平台适配](references/platforms.md)。改变包内容后重新计算 manifest 与压缩包。保留不可用组件定义，明确停用原因；不把停用解释为迁移成功。
5. 将 `payload.tgz`、`manifest.json`、`install.mjs` 传到目标私有目录，解包到同目录。执行 `node install.mjs <目录>`。安装器先核对所有文件哈希，再逐项备份被覆盖的配置、写入文件和恢复链接。它不清理目标历史或旧备份。
6. 同步 agy 时在目标执行 `node fixup-agy.mjs [报告路径]`。它按目标实际存在的命令停用缺命令的 MCP 与 Hook，删除目标不存在的 `trustedWorkspaces` 条目，并核对 `.gemini` 下的入口链接；报告 JSON 列出每项停用原因。停用项必须写入交付说明，不当作迁移成功。
7. 在目标安装 DSH 各 profile 依赖及 MCP 命令。链接插件保留已构建源码及来源，核对其运行依赖。CLI 管理的核心包使用目标 DSH 安装，不复制源宿主的原生依赖。

## 本机入口漂移检查

改共用 AGENTS 后、迁移前后，以及怀疑某个 Harness 读到旧规则时，运行 `python3 scripts/check_links.py`。它只读核对各 Harness 的 `AGENTS.md` 入口与唯一维护源是否为同一文件（硬链接或软链接），分叉时退出码 1。常见成因是编辑器整文件替换保存，给维护源换了 inode。修复：备份旧入口后以 `ln -f <维护源> <入口>` 重新硬链接，再运行一次确认。维护源与入口清单可用 `HARNESS_AGENTS_SOURCE`、`HARNESS_AGENTS_ENTRIES`（以 `:` 分隔、相对 `HOME`）覆盖。

## 验证与收尾

- 对安装报告、模型/协议、MCP 名称与启用状态、插件清单、Shell 语法、Skills/AGENTS 链接逐项核对差异。默认源版本与目标版本匹配；偏差写明原因。
- 用 Codex app-server 的 `hooks/list`、`skills/list` 检查实际注册与解析错误。路径或命令变更会改变 Hook 哈希；只迁移已授权且源端可信的相应 Hook 信任，不给未知新命令批量授权。
- agy 用 `agy --version`、`agy mcp list`、`agy plugin list` 核对二进制哈希、MCP 启用状态与插件解析。`agy install` 只在目标 PATH 不含 `~/.local/bin` 时执行：它会改写 Shell 启动文件并清理别名。
- 登录身份用脱敏布尔比较或实际请求验证，令牌与账号标识不回显。DSH 的各 profile `--dump-config` 验证解析；TUI 或 Web 的真实启动另验。
- 用最小真实请求验证 Codex 和 DSH 的模型链路。测试时隔离通知及自动记忆写入，保持目标保存配置原样；测试结果不代表全部 MCP 和插件功能验收。
- 验证本次包没有个人会话、记忆、图片或 SSH 私钥；保留目标已有数据。清理本次无用暂存包，保留用户要求的配置恢复点。用户明确取消本次备份时按其范围处理。
- 交付每台机器的已完成项、已验证项、停用项与未验证项，并给私有报告路径。无需把机器地址、端口、凭据或迁移产物写入公开 Skill 仓库。
