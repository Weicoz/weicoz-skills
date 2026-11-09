---
name: weicoz-harness-config-sync
version: 2.0.3
description: 按单一配置源同步 Codex、DSH、Antigravity CLI（agy）、Kimi Code 与可选 Shell 配置到指定设备，支持差异预览、冲突保护、设备覆盖层、备份回滚与状态核对。用于换机和多设备配置维护；排除个人历史，账号迁移需明确授权。
---

# Harness 配置同步

交付目标设备可运行的配置环境。公共配置版本相同，设备路径、代理和平台组件按设备覆盖；配置安装、CLI 可用性、模型真实请求分别验收。Claude Code 不在当前迁移范围。

## 范围与边界

- 从上下文、SSH 配置或 Herdr 保存机器核实目标、用户、系统及真实数据根目录。只操作指定设备；脚本默认处理标准用户目录，自定义根目录先按实际入口适配。
- 配置层包含模型、Hooks、MCP、插件源码、Skills、共用 AGENTS。Shell 按需同步。个人会话、记忆、日志、数据库、附件、定时任务、设备配对与 SSH 私钥保持隔离；目标已有历史保留。
- 通知渠道沿用目标配置；不默认复制 `harness-notify/config.json` 中的设备配对与收件人设置，账号迁移也不包含它。
- Kimi Code 使用 `.kimi-code/{config.toml,mcp.json,hooks,agents,skills,AGENTS.md}`；`oauth/`、`credentials/` 和个人历史不打包，OAuth 由用户在目标重新登录。旧版 `kimi-cli` 的 `.kimi/` 不作为新 Kimi Code 入口。
- agy 使用 `.gemini/config/{config.json,hooks.json,mcp_config.json,hooks,plugins,skills}`、`.gemini/antigravity-cli/settings.json` 与 `.gemini/AGENTS.md`；旧 `.gemini/settings.json` 不属于 agy。其 OAuth、brain、conversations 与浏览器资料不打包。
- 默认排除独立凭据文件，并拦截配置内嵌的已知凭据字段；发现明文凭据就停止，不回显值。使用无凭据设备覆盖文件、`--keep` 或明确授权后的 `--include-auth`。目标配置含凭据且本次未授权账号迁移时停止覆盖。Shell 保留目标原有 PATH、代理与凭据导出；函数和复杂加载器仍需人工检查。

## 配置基线与设备差异

选择一个配置维护源，用稳定的 `--source-id` 标识。公共配置更新后指定新的 `--revision`，同批设备使用同一版本；每台目标使用唯一的 `--device-id`。版本指公共配置，`payload_id` 指设备安装包的内容摘要。

用重复的 `--overlay` 按“公共补充 → 系统 → 设备”顺序覆盖，后者优先。每层按用户目录相对路径组织文件。覆盖是整文件替换；同文件字段差异用目标专用完整配置，避免不透明合并。`--keep <相对路径>` 保留目标文件或目录，不打包对应源内容。源端撤下的受管路径只报告 `retained`，不自动删除。

目标已有独立技能仓时用 `--skip-skills`；各 Harness 技能入口仍指向 `.agents/skills/<name>`，目标缺失的技能须先补齐。`--extra SOURCE=HOME_RELATIVE_DEST` 只补充已盘点的配置或插件源码，仍接受历史、私钥和凭据检查。

## 打包、预览、安装

1. 盘点源与目标 CLI 版本、DSH profiles、插件、MCP、Hook 命令、空间与网络。源端解析 YAML 需要 [scripts/requirements.txt](scripts/requirements.txt) 中的 PyYAML。按源版本安装目标平台 CLI 及原生依赖；macOS 二进制、`.venv`、`node_modules` 不跨平台复制。长期安装用已核实的 Herdr pane。跨平台细节见 [platforms.md](references/platforms.md)。
2. 将已盘点版本写入私有 JSON（键为 `codex`、`dsh`、`agy`、`kimi`，值为版本号）。不把设备地址、凭据或迁移包写入公开仓库。
3. 生成私有包：

```bash
python3 "$skill_dir/scripts/package.py" \
  --source-home "$sync_source_home" --target-home "$sync_target_home" \
  --platform "$sync_target_platform" --source-id "$sync_source_id" \
  --revision "$sync_config_revision" --device-id "$sync_device_id" \
  --versions "$sync_versions_json" --output "$sync_private_run/package"
```

平台为 `linux`、`darwin`、`win32`。加 `--shell` 同步 Shell；`--shell-only` 只同步 Shell。包包含 `payload.tgz`、manifest、安装与检查脚本；目标必须已安装 Node。

4. 将包传到目标私有目录并解压 `payload.tgz`。运行 `node install.mjs <包目录>`：默认只预览，不创建目标配置、状态或备份。预览列出更改、冲突、保留路径、停用项与 `plan_token`，不输出配置正文。
5. 根据当前授权审查预览。首次覆盖已有配置或目标偏离上次基线时出现冲突；使用覆盖层保留目标差异，或对已明确选择覆盖的单一路径加 `--replace <相对路径>`，重新预览。不要批量接受未知改动；已有同范围授权无需重复询问。
6. 使用相同参数与最新令牌应用：`node install.mjs <包目录> --apply --plan <plan_token>`。有冲突、包哈希错误、预览后目标变化、配置源/设备 ID 不符或父目录链接未核实时停止。安装先备份全部变更对象，再写入并验证；运行错误触发整批回滚。重复应用同一状态报告 `unchanged`。

`schema 1` 旧包不再直接安装；重新生成 `schema 2` 包。命令、冲突判据、恢复与报告约定见 [sync-contract.md](references/sync-contract.md)。

## 验收与恢复

- `node install.mjs --status` 只读核对受管文件与入口，报告配置版本、上次同步时间、漂移及保留项。
- `node install.mjs --verify` 检查状态、CLI 版本和 Kimi `doctor config`。缺 CLI、版本不符或配置检查失败返回非零；未提供版本基准时版本一致性标为未验证。此命令不调用模型，不发送通知。各设备报告保存在私有目录，用 `--collect <报告...>` 汇总，不主动连接其他设备。
- `node fixup-agy.mjs [私有报告路径]` 只读发现缺命令的 MCP、Hook 与失效受信目录；修正写进设备覆盖层后重新打包，不在安装后静默改动受管文件。停用项单列，不当作功能验收成功。
- 实际迁移时继续核对 Codex app-server 的 `hooks/list`、`skills/list`；DSH 各 profile 的依赖与配置解析；agy 的 MCP、插件；Kimi 的配置、MCP 与技能入口。Hook 信任只迁移已授权且源端可信的命令。
- 最小真实请求分别验证四个 Harness 的模型链路，隔离通知和自动记忆写入；只输出脱敏结果。CLI、模型请求和全部插件功能分开报告，不能用其中一项代替其他项。
- 用 `node install.mjs --rollback <恢复点ID>` 恢复当前最新同步。回滚前再次检查目标改动；有新改动则停止保护现场。进程崩溃后保留事务日志和锁，确认没有运行进程后处理锁，再按报告恢复；不自动抢占锁或清理备份。
- 改共用 AGENTS 或怀疑入口漂移时运行 `python3 scripts/check_links.py`。此检查只读，源与入口清单可用原有 `HARNESS_AGENTS_SOURCE`、`HARNESS_AGENTS_ENTRIES` 覆盖。发现分叉后备份旧入口、恢复同源链接并重验。
- 交付每台设备的安装结果、验证范围、停用项、未验证项与私有恢复点。保留已有工作和历史备份；只清理本次无用暂存包。
