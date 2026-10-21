---
name: weicoz-mac-procmon
version: 1.0.0
description: >
  用 mac-procmon（procmon）查本机 CPU / 内存 / 磁盘占用异常，做异常进程深度归因、
  告警排查与数据库体积维护。适用于"谁在吃 CPU""内存不够""电脑卡""哪个进程失控"
  "资源占用高""监控停了没""procmon 数据库越来越大"等场景，并规定
  list_incidents / scan_anomalies / diagnose_process / terminate_process 四个 MCP 工具的选择顺序。
  不负责安装或编译二进制；终止进程、清空数据库必须取得用户明确授权。
---

# mac-procmon 本机资源监控

## 判定顺序

先查状态，再取证据，最后才动进程。

1. 采集是否在跑：`procmon status` 看 `Daemon State`。STOPPED 时任何"没有异常"的结论都无效。
2. 有无异常：MCP `procmon_list_incidents` 取已确诊事件，`procmon_scan_anomalies` 取当前高负载候选。
3. 单进程归因：MCP `procmon_diagnose_process`，它返回命令行、工作区、活跃文件、网络和指标波形。
4. 处置：只有用户明确要求时才 `procmon_terminate_process` 或 `procmon stop`。

命令与 MCP 工具读同一份数据库，结论必须来自实际输出，不得凭经验编造 PID 或数值。

## 入口

- CLI：`procmon`（PATH 内，可用 `PROCMON_BIN` 覆盖）。无参数启动 TUI。
- MCP：DSH 与 Codex 已各配一份 stdio server（`procmon mcp`），工具名带 `procmon_` 前缀。
- 数据：`$HOME/.local/state/mac-procmon/`（`procmon.db`、`incidents/`、`procmon.log`）。
- 仓库：mac-procmon 源码，Rust 实现；`engine/*.py` 只是旧版契约，不再执行。

## 常用命令

| 目的 | 命令 |
| --- | --- |
| 守护状态 / 最新快照 | `procmon status` |
| 当前占用排行 | `procmon top` |
| 单进程详情 | `procmon inspect <PID>` |
| 深度诊断报告 | `procmon diagnose <PID>` |
| 告警事件列表 | `procmon incidents` |
| 时间序列导出 | `procmon export <PID> --hours 6 --format csv` |
| 曲线图 | `procmon plot <PID> --hours 6` |
| 七项自检 | `procmon check`（失败退出码 1） |
| 启动 / 重启 / 停止 | `procmon start [-i 秒]`、`procmon restart`、`procmon stop` |
| 清空历史库 | `procmon clean`（破坏性，先授权） |

## 采集模型（回答"是不是定时监控"）

不是 cron、不是 launchd、没有系统定时任务。守护进程是常驻后台，内部固定节拍循环：
默认 `-i 1.0` 秒，每轮采样全进程、跑检测器，再 sleep 到下一拍。所以是持续轮询，不是定点触发。

推论：

- 关机或停止守护 = 停止采集，历史数据不会补。`status` 的 `Last Snapshot` 是最早证据。
- 默认无开机自启（无 LaunchAgent）。重启电脑后必须手动 `procmon start`，否则长期静默。
- 告警双通道：osascript 桌面横幅，加 harness-notify（Bark / ntfy）只在 CRITICAL 时推送。
- 检测阈值在 `detector.rs`：CPU 70% 进、45% 退；持续写盘 30MB/s 起警；同进程 900 秒冷却。

## 数据库体积

保留策略：每 300 秒删除 24 小时前的 `proc_samples` / `sys_snapshot`，随后
`PRAGMA incremental_vacuum(512)`；连接打开时若 `freelist_count > 500` 执行一次 `VACUUM`，
同时把 `auto_vacuum` 切成 INCREMENTAL。

样本节流：同一 PID 最小间隔 5 秒（`storage.rs` 的 `DEFAULT_SAMPLE_MIN_INTERVAL_SECS`，
环境变量 `PROCMON_SAMPLE_MIN_SECS` 可覆盖，0 关闭）。忙时不再逐秒落盘；
异常检测走每轮实时指标与最近 60 分钟时间线，5 秒粒度不影响判定。

稳态体积由 24 小时窗口决定，不是无限膨胀；但库文件是**高水位**，删行不自动缩文件。
两个前提缺一个就会"只增不减"：

- `PRAGMA auto_vacuum` 必须是 2（INCREMENTAL）。为 0 时 `incremental_vacuum` 是空操作。
- 剪枝只有守护在跑才会触发。停跑期间积累的旧行，要等重启后下一个五分钟窗口才删。

实测（有一个 2.3 天未采集的库）：192.6 MB、`freelist=44275`、`auto_vacuum=0`。
`procmon restart` 触发打开时的 `VACUUM` 后降到 18.3 MB，`auto_vacuum=2`、`freelist=0`。

处理顺序：

1. 先跑 `bash scripts/db-health.sh` 看体积、行数、保留窗、`auto_vacuum`、`freelist`、快照新鲜度。
2. 体积偏高且 `freelist` 大：`procmon restart`（停一拍再起，触发一次性 VACUUM）。不丢数据。
3. 只要恢复空间又不想重启：先 `procmon stop`，再 `sqlite3 "$DB" 'VACUUM;'`，再 `procmon start`。
4. 只想保留最近几小时：`sqlite3 "$DB" "DELETE FROM proc_samples WHERE ts < strftime('%s','now')-3600*6;"` 后再 VACUUM。
5. `procmon clean` 清空全部历史，含取证目录，破坏性，必须先授权。

稳态体积 = 24 小时窗口 × 采样密度。实测（2026-10-20，659 进程）：节流前忙时 4,816 行/分，
节流后 2,086 行/分（降 57%）；轻载约 940 行/分。24 小时对应约 200 MB（轻载）至 400 MB（忙时）。
行数下限由空闲抽样决定：约 2 行/分钟/进程。还要更小就改空闲抽样（`now_int % 30`）或窗口（`86400`），
两者都在 `storage.rs`；不要在运行中的库上手工反复 VACUUM 抵消设计窗口。

## 故障对照

| 现象 | 判断 | 处理 |
| --- | --- | --- |
| `Daemon State: STOPPED` | 采集停，非故障 | `procmon start` |
| `Last Snapshot` 是几小时前 | 守护中途退出 | 看 `$HOME/.local/state/mac-procmon/procmon.log` 末尾 |
| `pgrep -fl procmon` 多个 `mcp` | 各 Agent 会话的 MCP 子进程，不是采集 | 不影响；无需清理 |
| 库大、行数少 | 高水位未回收 | `procmon restart` |
| `incremental_vacuum` 无效 | `auto_vacuum=0` | 走一次 VACUUM 转 INCREMENTAL |
| MCP 工具报错但 CLI 正常 | 旧 MCP 子进程持有旧二进制 | 重启对应 Agent 会话 |
| `procmon check` 退出码 1 | 七项运行时自检有失败项 | 按输出逐项处理 |

## 边界

- 终止进程是破坏性动作，必须用户点名 PID 或明确说"杀掉"，不得凭告警自行处置。
- `clean`、批量删除样本、改保留窗口都算删数据，需单独授权；VACUUM 只回收空闲页，不删有效数据。
- 报告定位到 `路径:行号` 与完整命令；未实际执行的检查标"未验证"。
