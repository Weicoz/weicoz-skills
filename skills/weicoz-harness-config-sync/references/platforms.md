# 跨平台适配

按本次目标读取对应小节。执行文件、路径和包版本来自现场盘点，不沿用旧机器的值。

## Linux / macOS

- Linux 用原生 Node、Codex 和 DSH。按 Node engines 核对版本；安装 zsh 后验证 OMZ、主题、补全及插件。目标当前使用其他 Shell 时，保留其初始化逻辑；用户要求切换默认 Shell 才切换。
- 路径改写覆盖 TOML、YAML、JSON、Hook 命令、插件依赖、嵌套通知命令和软链。保留 provider、模型、协议、环境变量引用及插件开关。
- 改写只扫描原文本一次。Windows 目标目录可能包含源 macOS 目录后缀；串联替换会把新路径再次改写，产生重复盘符。复查参数与本地 `link:` 路径。
- macOS 桌面应用 MCP 无法在 Linux 上运行。`package.py` 保留定义并将这类服务设为 `enabled = false`；检查实际不可用项和其他本地命令依赖。
- 复制 OMZ 源码时 `.git` 默认排除；验证启动时避免自动更新触发网络或交互。需要可更新安装时，另用公开上游版本恢复 Git 元数据，不复制源 Git 凭据。

## Windows / WSL

- 区分原生 Windows 与 WSL 的用户目录。Herdr pane 的实际 Shell 决定主要 CLI 安装位置；已有 WSL 可以承载 zsh/OMZ。未请求 WSL 时不自动创建发行版或迁移目标工作。
- 原生 Windows 使用满足 engines 的 Node。现有 Node 太旧时可用户级安装新版本，保留系统版本。让当前安装进程与后续 Shell 解析到新 CLI，同时保留目标已有 PowerShell profile。
- 配置路径优先用 `C:/...`，避免 JSON/TOML 反斜杠转义错乱。目录入口用 junction；无文件软链权限时同卷硬链接保持共用 AGENTS。禁止静默复制出独立 AGENTS 正文。
- POSIX Hook 使用 `commandWindows` 调用目标已有 Bash 或经验证的原生实现。保留原 `command`，并检查 app-server 实际选择了 Windows 命令。Mac GUI Hook 在目标明确停用；Windows Python 与 Node 命令分别检查。
- MCP 的 npm `.cmd` shim 不一定能被原生 spawn 启动。可以用目标 Node 加对应 JavaScript 入口，或现场验证的命令包装。所有 `args` 修改保留原参数与凭据。

## DSH 与网络故障

- 每个 profile 分别装依赖、解析配置和检查运行态。`desktop` 由 Electron 宿主管理；同步其配置不等于安装或验证桌面应用。
- 旧插件 peerDependencies 可能引用已撤下的 SDK。先核对源码真正的运行依赖与目标 DSH；需要宿主提供 peer 时可以进程级关闭自动安装 peer。不要为消除报错升级所有插件或绕过兼容检查。
- 改写本地 `link:` 依赖后核对 lockfile 中的相对路径。因路径变化重建锁文件时保留原已锁定版本；检查实际变更。原生模块在目标重建或安装相同平台的可信包。
- Git 锁文件可能保存 SSH URL，即使 package.json 写 HTTPS。公开仓库可在安装进程内将 SSH URL 映射到 HTTPS，保留提交；不复制 SSH 私钥，也不改目标全局 Git 配置。
- npm TLS 失败时检查错误、registry、现有代理与实际监听。可以让安装进程使用现有代理或经验证的包源；不切系统出口、不关闭证书校验。保留 lockfile integrity 验证。
- 离线准备包时，按目标 `os/cpu` 下载对应依赖并校验可信来源和完整性。安装脚本在目标执行或逐项验证；从 macOS 准备 Windows 包不会自动生成 Windows `.cmd` shim。检查目标 CLI、所选原生模块和真实启动，不能只看传输完成。
- Git 下载不可达时，可以迁移源端已安装的同版本插件构建产物，排除其依赖和 Git 元数据，核对哈希与版本并保留原来源。目标用本地 `link:` 引用，再补齐依赖；下载失败时形成的半成品 `node_modules` 不证明插件已经注册。
- 原生 Windows 指定系统自带的 tar 路径，避免 PATH 中 Git/MSYS 的同名程序抢占。导出 Docker 多架构镜像时选择目标平台，并确认保存成功；管道末端成功不能掩盖前端导出失败。
- 通知包装常嵌套旧 GUI 命令。保留通知渠道配置，改成目标可用适配器；验证用 dry-run，避免测试向他人发送消息。只读探针和关闭通知的模型请求不代表通知发送成功。
- Hindsight 配置与历史数据库分开。只有用户要求部署服务时才安装新的空服务；保留 MCP 定义不会使不存在的本地服务自动可用。配置恢复点只保存配置，不把个人记忆或旧数据库带入备份。
