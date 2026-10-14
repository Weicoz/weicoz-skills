# Remote Dispatch

把编码任务、测试和构建交给公司共享机器执行。员工共用一台机器，但各自使用固定 ID、独立配置、代码目录和任务会话。本版员工代理配置支持 **Codex**。

目标机可以是 **macOS、Linux 或 Windows**。管理员按机器配置平台；员工不用维护三份个人规范。Windows 使用原生 PowerShell worker，机器配置与验收见 [Platforms](references/platforms.md)。

验证范围：macOS 和 Linux 容器的本地回归已通过；M4 已完成真实 Codex 写文件、验证、提交、同一会话续跑及 SSH 取回验收。原生 Windows 尚未设备实跑，首次使用必须完成平台验收。回归中的假 Codex 与真实设备验收分别记录。

## 首次使用

### 1. 设置你的固定 ID

选择公司内唯一的工号或英文名，例如 `zhangsan`。使用 1–64 位小写英文、数字、下划线或连字符；统一小写，避免 macOS 把仅大小写不同的 ID 当作同一个目录。不是随机 UUID，也不是 API token。

```bash
export RD_USER_ID=zhangsan
```

Windows 派单端用 PowerShell 设置当前进程和自己的用户环境变量：

```powershell
$env:RD_USER_ID = 'zhangsan'
[Environment]::SetEnvironmentVariable('RD_USER_ID', 'zhangsan', 'User')
```

把这行写进你实际使用的启动环境，使启动 Codex/终端的进程能够继承它。终端用户可放进自己的 shell 配置；GUI 启动的代理还需确认其进程实际能读取该变量。不要修改其他员工的启动文件。

同一个人在另一台电脑设置相同 ID。其他人选择自己的 ID。ID 缺失时，工具停止派单并询问；不会根据机器用户名猜 ID。ID 重复会选择同一套配置，所以必须保持唯一。

### 2. 准备自己的配置包

可以直接告诉代理：

> 使用 $weicoz-remote-dispatch。我的 ID 是 zhangsan，请先准备公司规范和我选定的 Codex 配置，展示同步清单，问我是否同步到 mini。

自己准备时，在 skill 安装目录执行：

```bash
export RD_PROFILE_DIR="$HOME/.config/remote-dispatch/profiles/$RD_USER_ID"
mkdir -p "$RD_PROFILE_DIR"
cp assets/profile.example/config.toml "$RD_PROFILE_DIR/config.toml"
cp assets/profile.example/AGENTS.md "$RD_PROFILE_DIR/AGENTS.md"
RD_BIN="$PWD/scripts/rd"
```

模板用于起步；首次准备后编辑公司规范、模型、接口和个人差异。不要用这些 `cp` 命令覆盖已有配置包。只有配置包不在默认路径时才需要长期设置 `RD_PROFILE_DIR`。

包内可放 `skills/`、`agents/`、`rules/` 和配套 `tools/`。个人 skills 需要复制选定实体资源，不保留指向本机的软链接。不要整份复制 `.codex`，不要放凭据、历史或个人记忆。

资源路径写成包内相对路径，或使用 `@RD_PROFILE@` 占位符。执行时映射到当前任务目录。详情见 [Employee Profiles](references/user-profiles.md)。

### 3. 确认后同步

机器清单来自管理员，位于 `~/.config/remote-dispatch/config.ini`。管理员还负责目标机 Python 3.11+、Codex 和认证来源；员工不需要在聊天里提供 API key。

```bash
"$RD_BIN" profile check mini
```

代理向你展示 **ID、目标机、目标目录、文件清单、变化、更新时间和配置版本**，再询问是否同步。即使你已提出同步请求，新用户登记仍保留这次明确确认。

你同意后，代理使用检查结果里的完整指纹：

```bash
# 将检查输出中的完整指纹填入此变量；它只确认本次同步版本
RD_CONFIRMED_VERSION='填入已审阅的完整指纹'
"$RD_BIN" profile sync mini --confirm-user-id "$RD_USER_ID" --confirm-version "$RD_CONFIRMED_VERSION"
```

配置包改变、ID 不一致或远端版本已变化时，工具拒绝同步，重新检查和确认。旧版本保留，新配置只影响之后的任务。

## 日常派单

可以直接告诉代理：

> 使用 $weicoz-remote-dispatch，把这个任务派到 mini，使用我的 RD_USER_ID 对应配置。

代理检查负载和配置。已有配置时不重复初始化，不自动同步个人环境。没有配置时先问是否同步，并展示或询问你的 ID。

手工执行时，进入需要处理的 Git 仓库：

```bash
"$RD_BIN" hosts
"$RD_BIN" run --agent codex --host mini --prompt-file /path/to/task.md --name fix-login
```

保留输出的 job id，随后用 `status`、`logs`、`wait` 和 `fetch` 查看、取回结果。代理提交到任务分支，脚本负责回传；本机审查后再合并。

```bash
"$RD_BIN" status
"$RD_BIN" logs <job>
"$RD_BIN" wait <job>
"$RD_BIN" fetch <job>
```

新任务可以绑定当前发起会话，执行方完成本轮工作后回传结果，后续修复或复检由发起方决定并续派到原会话：

```bash
"$RD_BIN" run --agent codex --host mini --prompt-file task.md --initiator-session <当前会话ID>
"$RD_BIN" status <job> --details --initiator-session <当前会话ID>
"$RD_BIN" result <job> --initiator-session <当前会话ID>
"$RD_BIN" ack <job> --round 1 --receipt-id <回执ID> --initiator-session <当前会话ID>
"$RD_BIN" inbox --initiator-session <当前会话ID>
# 发起方确认下一轮指令后再续派，接收方不会自动追加工作。
"$RD_BIN" resume <job> --prompt-file followup.md --initiator-session <当前会话ID>
```

参数优先于 `RD_INITIATOR_SESSION`，其次使用宿主实际提供的 `CODEX_THREAD_ID`。缺少ID时不声称绑定或跨会话送达。`ack` 只确认收取，退出码0与执行方报告的检查通过均不代替发起方验收。详细协议、执行方进度报告和断线缓存见 [会话交付](references/handoff.md)。旧任务原命令保持兼容，不自动改正在执行的任务或配置。

发起方在本机按统一周期检查尚未完成的任务，默认 15 分钟、可以配置，再向当前会话汇报实际进展；远端不承担定时上报责任。后台监控多个 job 可以共用一次有界等待：

```bash
"$RD_BIN" watch <job1> [<job2> ...]
# 单次等待10分钟
"$RD_BIN" watch <job1> [<job2> ...] --timeout 600
# 短期不可达时继续只读观察，保留本次截止时间。
"$RD_BIN" watch <job1> [<job2> ...] --keep-on-disconnect
```

默认周期按环境变量 `RD_REPORT_INTERVAL_SECONDS` → 本机配置 `[monitor] report_interval_seconds` → 900 秒选择，必须为正整数。例如环境变量设为 `600`，或在 `config.ini` 的 `[monitor]` 写 `report_interval_seconds = 600`，表示10分钟。显式 `--timeout` 优先覆盖单次等待，用于本次定时或提前提醒后的剩余时间；不改变登记的基本周期。

退出 2 表示统一巡检到期，0 表示有任务成功结束，1 表示失败或监控连接受阻。发起方读取事件后核对日志、实际源码／检查证据和机器资源，再报告；事件本身不是用户报告。提前结束提醒不重置其余任务的统一截止时间，下一次等待使用剩余秒数。宿主后台唤醒及消息送达必须实际可用；详见 [发起方统一巡检](SKILL.md#3-发起方统一巡检与提醒)。

测试和构建也会带上你的 ID，并使用独立任务目录：

```bash
"$RD_BIN" run --test --host mini
"$RD_BIN" run --cmd 'npm run build' --heavy --host mini
```

机器根目录下的整机排队锁共用，避免员工各自排队却同时耗尽内存。默认分支名带员工 ID，仓库还区分来源，避免同名仓库混用。

## 换电脑与更新

换电脑时设置相同 `RD_USER_ID`，远端已有配置就能使用。没有本地配置包时，工具提示无法比较更新时间；不会根据新电脑环境覆盖旧配置。

员工主动更新时，先修改自己的配置包，再提出同步请求。代理重新展示清单并确认 ID、是否同步。启动时也会检查：

| 状态 | 处理 |
|---|---|
| 配置内容一致 | 不提醒 |
| 内容不同，本地领先远端超过七天 | 提醒是否更新；不自动同步 |
| 内容不同，差距不超过七天 | 使用已有远端配置 |
| 远端配置更新 | 提示差异，不用本地旧版本覆盖 |

比较的是两个配置版本的源更新时间，不是距离上次同步的时间。首次检查用源文件最新修改时间；后续内容变化记录发现时间，删除也能识别。时间是提示依据，内容指纹用来确认具体版本。

任务续跑固定使用原配置、会话和目录，新同步的版本不会改变它。

## 目标机目录

```text
<机器工作根目录>/
├── locks/                     整机重任务排队
└── users/
    ├── zhangsan/
    │   ├── profiles/          张三的配置版本
    │   ├── repos/             张三的仓库
    │   ├── wt/                张三的任务代码
    │   └── jobs/<job>/codex/   此任务的配置、会话和日志
    └── lisi/
        ├── profiles/
        ├── repos/
        ├── wt/
        └── jobs/
```

不会改共享账号的全局 Codex 配置。配置中的本机绝对路径被拒绝；员工资源映射到自己的目标机任务目录。共享账号仍有相同文件访问权限，ID 与目录分开用于防串配置，不提供身份认证。

## 常见问题

- **提示 RD_USER_ID 缺失**：确认启动代理的进程继承了环境变量；设置员工自选 ID，不换随机值。
- **首次派单没有远端配置**：先检查清单，确认 ID 和是否同步，再初始化。
- **同步确认版本错误**：配置包已变化，重新 `profile check`，审阅新版本。
- **认证失败**：由管理员检查目标机 `codex_auth_file` 或 API 环境变量。登录和验证码由用户处理。
- **退出码 98**：员工配置或认证准备失败，查看 `logs <job> err`；不等于业务代码失败。
- **workspace-write 提交失败**：目标 Codex 必须支持命名 permission profiles；运行脚本保留工作区保护，单独开放当前任务的 Git 元数据，详见 [Employee Profiles](references/user-profiles.md)。退出码 0 但无提交仍不能当作任务验收通过。
- **其他代理不能派**：本版只完成 Codex 的员工配置适配，其他代理模板保留但阻止启动，避免串宿主环境。
- **Windows 命令或路径失败**：确认机器配置为 `platform=windows`，Python 路径正确；环境文件用 JSON，任务命令用 PowerShell。不要直接搬 Bash 脚本。
- **Windows 后台启动失败**：查看 OpenSSH 是否支持脱离 Job Object 和 `bootstrap.log`；首次使用必须验 SSH 返回后的任务状态，不能只看启动成功提示。
- **旧任务不能续跑**：旧版任务没有员工配置快照。先取回工作，再用当前 ID 重新派单；查看、取回、停止和清理仍保留。

管理员安装见 [Worker Setup](references/worker-setup.md)，代理模板见 [Agent Adapters](references/agents.md)。
