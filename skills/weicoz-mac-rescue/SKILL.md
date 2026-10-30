---
name: weicoz-mac-rescue
version: 1.0.0
description: >
  macOS 现场急救：机器已经卡顿、CPU 打满、磁盘快满、swap 暴涨、进程上千、风扇狂转，
  或用户怀疑中毒时，按固定顺序取证、归因、分级处置。适用于"电脑特别卡""资源占用超高"
  "磁盘空间严重不足""内存不够一直换页""风扇一直转""是不是病毒""哪个进程失控"
  "要不要重启"等场景。覆盖 swapfile 吃盘闭环、僵尸 launchd 任务无限重启、
  MCP 与子进程泄漏、孤儿进程，以及 WindowServer / coreaudiod 高占用的误判。
  不做长期监控与历史归因（用 weicoz-mac-procmon），不做完整存储盘点（用 storage-analyzer）。
---

# macOS 资源急救

机器还能跑命令时用本流程。顺序不能颠倒：**先磁盘，再内存，再进程，最后才看单个进程的 CPU。**

原因很直接：磁盘或内存耗尽后，几乎所有 CPU 异常都是后果，先去追单个进程的 CPU 会白忙一场，还会把正常进程当成病毒。

## 分诊：什么情况不该用本 Skill

| 用户想要 | 该用的 Skill |
| --- | --- |
| 长期监控、异常告警、历史归因 | `weicoz-mac-procmon` |
| 看清硬盘被什么占满，出可点击清理报告 | `storage-analyzer` |
| 只要清理建议、不诊断卡顿 | `mac-space-cleanup` |

## 四条判读铁律

**1. 磁盘优先。** 可用空间低于总容量 5%，或剩余不足 10 GB，就先按"磁盘满"解释一切。此时内核在反复紧急回收缓存，`df` 会在几分钟内大幅跳动——**跳动本身就是磁盘满的证据**，不是测量误差。

**2. 系统进程的高占用先当症状。** `WindowServer`、`coreaudiod`、`kernel_task` 同时高，先假定是资源饥饿。判定 coreaudiod 是不是被饿死，看它的日志里有没有客户端超时：

```bash
log show --last 2m --predicate 'process == "coreaudiod"' --style compact \
  | grep -c 'Overload possibly due to client timeout'
```

有这条说明音频客户端抢不到时间片，是症状。没有这条、且它独占一个核，才按驱动或客户端死循环去查。

**3. "进程多"和"进程失控"是两件事。** 900 个进程不等于病毒，先找**计数异常**：同一类命令行出现十几次，才是泄漏。判断方法见下文「进程泄漏」。

**4. 中毒判定不看名字，看归属。** 名字像 `com.apple.*` 不代表是 Apple；反过来，Apple 自带组件也可能因为签名格式老化被 `codesign` 拒绝。两种误判都会让你误报。用三样证据交叉确认：代码签名、安装回执、自启动清单对账。

## 第一步：取证（只读）

```bash
bash scripts/snapshot.sh
```

输出覆盖：磁盘、swap、负载、进程与线程数、CPU 排行、内存排行。按下面的阈值判读。

| 指标 | 正常 | 危险信号 |
| --- | --- | --- |
| 磁盘可用 | > 10% | < 5% 或 < 10 GB，且 `df` 短时间大幅跳动 |
| swap 已用 | < 物理内存 30% | > 物理内存 50%，或 `total` 值在增长 |
| swapfile 个数 | < 5 | 10 个以上（每个约 1 GB，直接占盘） |
| load average | < 核数 | > 核数 × 3 |
| CPU 空闲 | > 20% | < 5% 持续 |
| 进程 / 线程 | 300 / 3000 以内 | 800 / 6000 以上 |
| 内核态 CPU 占比 | < 20% | > 40%（换页或 I/O 卡顿的特征） |

## 第二步：按症状分流

| 症状 | 先查 | 最常见原因 |
| --- | --- | --- |
| 磁盘掉到个位数 GB 且仍在降 | `sysctl vm.swapusage` 的 `total` 是否变大 | swapfile 增生吃盘 |
| 负载高但 CPU 空闲率也低 | `top -l 1` 的内核态占比 | 内存换页 + 磁盘 I/O |
| 某个进程每 10 秒左右出现一次 | `launchctl list` 第二列非 0 | 僵尸 launchd 任务 |
| 同类进程十几个 | 命令行归类计数 | MCP / 子进程泄漏 |
| 单进程吃满一核且久不降 | 该进程日志 | 死循环或客户端超时 |

## 第三步：四个高频杀手

### 1. swapfile 吃盘闭环

链路是：内存不够 → 内核新建 swapfile（每个约 1 GB，放在 `/System/Volumes/VM`）→ 磁盘更满 → 读写更慢 → 进程更拿不到时间片 → 内核继续加。这是正反馈，会自己加速。

确认：

```bash
sysctl vm.swapusage                     # 盯着 total，它变大就是在写盘
ls /System/Volumes/VM/swapfile* | wc -l  # 个数 × 1 GB
du -sh /System/Volumes/VM
```

处置顺序：先退内存占用大的应用降压力，再重启回收。**不要手工 `rm` swapfile**——内核仍持有映射，删了会直接崩。要停 swap 必须走 `sudo launchctl unload` + `dynamic_pager` 那套，属于高风险管理动作，除非用户明确要求否则不碰。

### 2. 僵尸 launchd 任务

脚本被删或 App 卸载，但 plist 还在且 `KeepAlive=true`，launchd 就会按节流间隔（默认 10 秒）无限重拉。单次开销很小，但会持续写日志、持续 fork，在磁盘将满时就是雪上加霜。

```bash
bash scripts/zombie-agents.sh
```

判据三条同时成立才算：`last exit code` 非 0、`runs` 很大、`ProgramArguments` 指向的文件已不存在。

处置（L2，无损可逆）：

```bash
uid=$(id -u)
launchctl bootout "gui/$uid/<label>"
mkdir -p "$HOME/.local/state/mac-rescue-disabled"
mv "$HOME/Library/LaunchAgents/<label>.plist" "$HOME/.local/state/mac-rescue-disabled/"
```

必须移走 plist，否则下次登录会重新加载。**移走而不是删除**，保留可回滚副本。

验收不能只看 `bootout` 返回 0，要看副作用真的停了：对比 plist 里 `StandardErrorPath` 对应日志的字节数，隔 20 秒以上两次取样相等，才算停住。

恢复时把 plist 移回去再 `launchctl bootstrap gui/$uid <plist>`；要先确认脚本已恢复，否则会立刻重新开始失败循环。

### 3. 进程泄漏

同一套 MCP server 被每个 agent 会话各拉一份，会话结束不回收；桌面 App 的操作代理子系统也会留孤儿。

```bash
bash scripts/process-leaks.sh
```

看两个数字：**同一命令行签名的出现次数**（超过 3 次基本就是泄漏），和**单个父进程的子进程数**（几十个说明该守护进程在反复拉起）。

处置要点：
- 主进程已退出、子进程被重挂到别的 daemon 的，属孤儿，可直接 `TERM`（先确认 CPU 为 0）。
- 不要在别的会话正在跑任务时批量杀 `node` / `rustc` / `cargo`，会打断编译和构建。先看 `etime` 和父进程，确认来源。
- 泄漏的根因是配置，不是进程。杀完要回头收敛各 harness 的 MCP 配置，否则下个会话继续漏。

### 4. WindowServer / coreaudiod 高占用

`WindowServer` 超过 50% 且久居不下，常见成因：在线显示器多、有 App 在无限重绘（动画仪表盘、视频、聊天小程序）、或整体 CPU 饥饿。先排除硬件与显示器数量，再看有没有可疑的高频重绘 App。

`coreaudiod` 长期 70% 上下，先按铁律 2 查客户端超时日志。存在多个 `audio-out` 断言（说明多个客户端在持续放音）时，用 `pmset -g assertions | grep -i audio` 看断言归属。卡死的音频会话通常只有重启能清干净。

## 是否中毒的正确判定

按这个顺序，每步都能独立证伪，不要跳步下结论。

**1. 自启动清单对账。**

```bash
ls "$HOME/Library/LaunchAgents" /Library/LaunchAgents /Library/LaunchDaemons
```

逐项对到已安装的软件。全部能对应上（更新器、输入法、远程控制、云盘、驱动），就没有可疑持久化。

**2. 签名与归属。**

```bash
codesign -dv --verbose=4 /path/to/binary 2>&1 | grep -E 'Authority|Identifier|TeamIdentifier'
```

`Authority=Software Signing` + `TeamIdentifier` 有值 = 有开发者身份。`TeamIdentifier=not set` 且顶用 `com.apple.*` 的 bundle id，才需要进一步怀疑。

**3. 安装回执。**

```bash
pkgutil --file-info /path/to/thing
```

有 `pkgid` 和 `install-time` 说明是某个安装包放的。`pkgid` 为 Apple 的系统模板包时，基本可判定为系统组件，即使 `codesign` 因 `resource envelope is obsolete` 拒绝校验也不要误报——苹果自己的老格式组件会这样。

**4. 网络与代理。**

```bash
scutil --proxy | grep -E 'Enable|Proxy'
```

代理全关时，"回连 C2"这条常见叙述就不成立，不要再往这个方向推。

**5. 最后才看资源。** 真正的挖矿或木马会**独占**资源（单进程长期 90%+、CPU 与网络同时满、进程名伪装成内核线程）。而"很多进程各占 20%"是典型的 App 太多，不是病毒。

## 处置分级与授权

| 级别 | 动作 | 授权要求 |
| --- | --- | --- |
| L1 | 全部取证命令、日志读取 | 无需，随时可做 |
| L2 | 退 App、`bootout` 僵尸任务并备份 plist、清缓存 | 声明动作与影响后执行；退出 App 前提示未保存内容风险 |
| L3 | `kill -9`、删数据、`docker system prune`、清历史库 | 必须用户点名对象 |
| L4 | 重启 | 必须用户确认，说明会中断什么 |

退 App 优先用 `osascript -e 'tell application "X" to quit'`，让应用自己保存状态；无响应再升级到 `TERM`。

## 附带脚本

全部只读，可放心先跑。路径相对 skill 目录。

| 脚本 | 作用 | 耗时 |
| --- | --- | --- |
| `scripts/snapshot.sh` | 磁盘、swap、负载、进程线程数、CPU 与内存排行 | 约 2 秒 |
| `scripts/zombie-agents.sh` | 找「程序已删但启动项还在」的 launchd 任务 | 约 5 秒 |
| `scripts/process-leaks.sh` | 命令行归类计数、父进程子进程数、孤儿、僵尸、argv 里的凭据（已打码） | 约 3 秒 |
| `scripts/disk-hogs.sh [秒]` | 定向统计目录大户，每项独立超时 | 慢，默认每目录 20 秒；盘快满时放后台 |

`disk-hogs.sh` 故意不做全盘扫描。盘快满时全盘 `du` 会让 I/O 更糟，宁可分批。

## 汇报格式

按这个结构，不要写成长篇散文。

1. **结论一句**：是资源耗尽、是配置残留，还是无异常。
2. **现象表**：处理前 → 处理后，给出具体数字。
3. **根因排序**：每条附证据（命令输出、日志原文、`路径:行号`）。
4. **已做 / 未做**：未做要写清原因（未授权、需重启、待用户决策）。
5. **决策选项**：编号列表，首项标 `(推荐)`，逐项写动作与后果。

## 边界

- 只读诊断不改系统；任何 L2 以上动作都要有用户授权。
- 不手工删 swapfile、不改 `dynamic_pager`、不动内核参数。
- 不因为"占资源"就自行终止进程；终止必须点名。
- 在快满的盘上避免全盘 `du` / `find` 扫描，会加剧 I/O 拖死机器。用 `scripts/disk-hogs.sh` 的定向统计，必要时放后台。
- 未执行的检查标「未验证」，证据不足标「未确认」并给出确认方法。
