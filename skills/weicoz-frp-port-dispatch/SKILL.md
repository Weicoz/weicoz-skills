---
name: weicoz-frp-port-dispatch
description: Use when user wants to configure, migrate, verify, or troubleshoot FRP frps/frpc port dispatch, reverse access, or startup services on a server or local machine, especially when a configured public relay is used. Always ask user to confirm ports, token, target host, service names, and any sudo-required step instead of deciding them.
---

# Weicoz FRP Port Dispatch

## 适用场景
- 用户要把某台公网机配置成 `frps` 服务端。
- 用户要把某台本地机配置成 `frpc` 客户端，并映射 SSH / Web / 其他 TCP 服务。
- 用户要把旧 FRP 方案迁移到新端口，或从 SSH tunnel 方案改成直连 `frps`。
- 用户要验证 FRP 是否连上、端口是否打开、systemd 是否开机自启。
- 用户明确说以后想复用同一套 FRP 配置流程。

## 硬规则
1. 不替用户决定关键参数。以下信息必须先问清或让用户确认：
   - `frps` 入口端口
   - `auth.token`（只从环境变量或用户确认值读取）
   - 每个 `remotePort`
   - 要暴露的本地服务与端口
   - 是否停用旧 `frp-tunnel` / 旧 `frpc` / 旧代理规则
   - 是否需要 systemd 开机自启
   - 是否有 `sudo` 权限与密码
2. 不把“已监听”当成“已可用”。必须做真实连通验证。
3. 改端口后，必须提醒用户所有客户端同步改 `serverPort`。
4. 若涉及 systemd、`/etc`、防火墙、云安全组，先说明哪一步需要用户确认或凭据。
5. 若缺 `sudo`，先完成用户态可运行版本，再明确告诉用户“自动启动未完成”。
6. 若用户要求“外网必须密钥、内网可密码”，不要把同一个 SSH 监听口同时给内外网共用。默认改为双端口方案：
   - 内网直连端口：保留密码策略
   - 外网经 FRP 端口：单独本地 SSH 监听口，仅允许公钥
7. 涉及 SSH 认证策略时，必须先向用户确认：
   - 外网入口映射到本地哪个 SSH 端口
   - 哪个用户允许外网登录
   - 外网使用哪把公钥/现有 `authorized_keys` 是否沿用
   - 是否允许 root 外网登录
8. 如果这次任务中新建、替换、追加了任何 SSH key，最终必须把可供登录使用的私钥与公钥内容、落点文件、对应用户、登录命令一并输出给用户；否则不算完成。

## 默认输出协议
- Goal
- Verify
- Next
- Blocker

## 优先流程

## 标准执行顺序
以后遇到同类任务，严格按这个顺序，避免乱序出错：

1. 先确认参数
   - `frps` 入口端口
   - `auth.token`
   - `remotePort`
   - 外网专用本地 SSH 端口
   - 外网登录用户
   - 是否沿用旧 key 还是新生成 key
   - 是否要求 systemd 开机自启
   - 是否有可用 `sudo`
2. 再查真实现状
   - `frps/frpc` 服务状态
   - 配置文件当前位置与内容
   - 旧 `frp-tunnel` / 旧依赖是否存在
   - `sshd` 当前监听端口与认证策略
3. 先改服务端，再改客户端
   - 服务端先保证入口端口与 `allowPorts` 正确
   - 客户端再改 `serverAddr/serverPort/token`
4. 若要求“外网仅密钥，内网可密码”，先完成 SSH 双端口
   - 内网口保留密码
   - 外网专用口改成仅公钥
   - 先验证本地专用口成立，再挂到 FRP
5. 若要新 key，先生成 key，再装公钥，再做登录验证
   - 不要先说“已经可以 key 登录”
   - 必须拿新私钥实测一次
6. 若要自启，最后再做 systemd 落地
   - 配置文件先稳定
   - 旧依赖先去掉
   - `daemon-reload`
   - `enable --now`
   - `restart` 复验
7. 最后统一做验证与交付
   - 内网
   - 外网
   - 密码成功/失败
   - 公钥成功
   - service restart 后恢复
   - key 全文交付

不要跳步。尤其不要：
- 没确认参数就改
- 没验证 SSH 专用口就挂 FRP
- 没去掉旧依赖就启新 `frpc.service`
- 没拿新私钥实测就把 key 交付给用户
- 没做 restart 复验就说“自启已完成”

### 1. 先识别角色
先问清这是哪一类：
- `frps` 服务端
- `frpc` 客户端
- 两边都要
- 迁移/排障

若用户没说清，至少确认：
- 目标机器
- 机器登录方式
- 目标服务
- 需要对外暴露哪些端口

### 2. 服务端 `frps` 流程
先查真实现状：
- `systemctl status frps --no-pager -l`
- `ss -lntp | grep frps`
- `sed -n '1,220p' /etc/frp/frps.toml`

要确认用户这些参数：
- `bindPort`
- `auth.token`
- `allowPorts` 范围
- 是否还要保留旧入口端口

标准配置骨架：

```toml
bindPort = 47000
auth.method = "token"
auth.token = "REPLACE_ME"
allowPorts = [
  { start = 50000, end = 59000 }
]
```

改完后必须验证：
- `systemctl restart frps`
- `systemctl status frps --no-pager -l`
- `ss -lntp | grep frps`
- `journalctl -u frps -n 50 --no-pager -l`

还要提醒用户检查两层放行：
- 云安全组
- 服务器本机防火墙

至少确认：
- `bindPort/tcp`
- 实际要用的 `remotePort/tcp` 或整个允许范围

### 3. 客户端 `frpc` 流程
先查真实现状：
- `systemctl status frpc --no-pager -l`
- `systemctl status frp-tunnel --no-pager -l`
- `ps -ef | grep '[f]rpc'`
- `sed -n '1,220p' <frpc 配置文件>`

必须先问用户确认：
- 这台客户端要映射哪些服务
- 每个服务对应哪个 `remotePort`
- 是否保留旧代理
- 是否停用旧 `frp-tunnel`
- 是否需要 systemd 开机自启

客户端配置骨架：

```toml
serverAddr = "<FRP_SERVER_ADDR>"
serverPort = 47000
auth.method = "token"
auth.token = "REPLACE_ME"

[[proxies]]
name = "client-ssh"
type = "tcp"
localIP = "127.0.0.1"
localPort = 22
remotePort = 50022
```

多服务时重复 `[[proxies]]`，但不要替用户自动分配端口。先让用户确认端口表。

### 4. systemd 落地流程
若用户要开机自启，且有 `sudo`：
- 写配置文件
- 写或更新 `frpc.service` / `frps.service`
- `systemctl daemon-reload`
- `systemctl enable --now <service>`
- `systemctl is-enabled <service>`
- `systemctl status <service> --no-pager -l`

若没有 `sudo`：
- 先做用户态启动验证
- 明确告诉用户：配置已通，但自动启动未完成
- 列出需要用户自己执行或提供凭据的命令

典型 `frpc.service`：

```ini
[Unit]
Description=frp client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=jy
WorkingDirectory=/home/jy/frp
ExecStart=/opt/frp/frpc -c /home/jy/frp/frpc.toml
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
```

### 4.1 SSH 外网仅密钥 / 内网可密码
若用户要求：
- 外网连接必须密钥
- 内网连接可以密码

默认采用双端口，不要尝试在同一 SSH 端口里区分“内外网来源”。

推荐结构：
- `22`：内网直连，允许密码
- `2222`：给 FRP 外网入口用，只允许公钥

FRP 代理示例：

```toml
[[proxies]]
name = "client-ssh-external"
type = "tcp"
localIP = "127.0.0.1"
localPort = 2222
remotePort = 50022
```

`sshd_config` 或 drop-in 要点：
- 让 `22` 保留内网密码策略
- 让 `2222` 仅允许 `PubkeyAuthentication yes`
- `PasswordAuthentication no`
- `KbdInteractiveAuthentication no`
- 需要时用 `Match LocalPort 2222` 收紧到指定用户

不要替用户决定：
- 外网专用端口是 `2222` 还是别的值
- 外网专用用户是否还是 `jy`
- 外网是否禁用 root
- 若新配了 key，不要只说“已配置完成”，必须把 key 相关交付物直接给用户

改完必须验证两条链路：
- 内网：`ssh user@内网IP`
- 外网：`ssh -p <remotePort> user@<FRP_SERVER_ADDR>`

如果只能验证一条，必须在 `Blocker` 里明说另一条未验证。

### 5. 验证流程
验证必须分两边：

服务端：
- 是否有新登录日志
- 是否有动态代理端口监听

客户端：
- `frpc` 是否登录成功
- 每个代理是否 `start proxy success`

外部真实验证：
- `nc -vz <公网IP> <remotePort>`
- 对 SSH：`ssh -p <remotePort> <user>@<公网IP> 'hostname && whoami'`
- 对 Web：`curl -I` 或直接访问实际 URL

### 6. 排障顺序
遇到不通，按这个顺序查：
1. `frps` 是否在目标端口监听
2. 云安全组是否放行
3. 本机防火墙是否放行
4. `frpc` 是否登录成功
5. `token` 是否一致
6. `remotePort` 是否在 `allowPorts` 范围内
7. `remotePort` 是否冲突
8. 本地服务本身是否在 `localIP:localPort` 监听
9. 是否还残留旧 `frp-tunnel` / 旧 `frpc` 抢配置

## 43 服务器惯例
如果任务明确指向当前这套环境，先向用户确认是否继续使用这些值：
- 公网中转：读取 `WEICOZ_FRP_SERVER_ADDR`
- 当前 `frps` 入口端口：`47000`
- 常用映射范围：`50000-59000`

如果用户说“按 43 这套规则走”，也仍然要确认：
- 这次是否沿用当前 token
- 这次具体要占哪些 `remotePort`

## 常见坑位
- 只开了 `frps` 端口，没开实际 `remotePort`
- 改了 `frps` 入口端口，但客户端还连旧端口
- `frpc` 配置里还是 `127.0.0.1:7000` 这类旧 tunnel 入口
- `systemd` 显示 enabled，但服务本身 failed
- `sudo` 密码不对，导致“配置文件改了但服务没落地”
- 只看 `systemctl active`，没做真实 `ssh` / `nc` 验证

## 交付要求
- 明确列出最终生效的：
  - 服务端入口端口
  - token 是否已确认
  - 每个代理的 `name/localPort/remotePort`
  - systemd 是否已完成
  - 真实验证是否通过
- 若涉及 SSH key，额外列出：
  - 私钥全文
  - 公钥全文
  - 写入到哪台机器、哪个用户、哪个文件
  - 对应登录命令
- 无论是否新配 key，只要本次涉及 SSH 连接配置，最终都必须同时给出：
  - 内网直连命令
  - 外网经 FRP / 公网入口连接命令
- 若有任何未完成项，必须单独列到 `Blocker`，不能包装成完成。

## 强制验证清单
凡是 FRP + SSH 相关任务，结束前至少逐项核对：

### A. 配置验证
- `frps` 配置文件已写入目标值
- `frpc` 配置文件已写入目标值
- 若涉及 SSH 双端口，`sshd` 配置已包含：
  - 内网端口
  - 外网专用端口
  - 外网口仅公钥策略

### B. 进程与自启验证
- `systemctl status <service> --no-pager -l`
- `systemctl is-enabled <service>`
- 至少做 1 次 `systemctl restart` 后复查状态
- 若不能做整机 reboot，必须明确说明“只验证到 service restart，未验证整机重启”

### C. 端口验证
- 服务端入口端口可监听
- FRP 对外 `remotePort` 可监听或可连通
- 本地被代理端口确实在监听

### D. 认证验证
若规则是“内网可密码，外网仅密钥”，必须至少验证：
- 内网密码登录成功
- 外网专用本地 SSH 口密码登录失败
- 外网专用本地 SSH 口密钥登录成功
- 经 FRP 外网入口密钥登录成功
- 若尝试了经 FRP 外网入口密码登录，也要记录结果

### E. Key 交付验证
若新配、替换、追加了 key，必须确认最终答复里已经包含：
 - 私钥全文
 - 公钥全文
 - 机器 / 用户 / 文件路径
 - 登录命令

### F. 结果输出验证
最终答复必须显式区分：
- 已完成
- 已验证
- 未验证
- Blocker

并确认最终答复里已经包含：
- 内网连接命令
- 外网连接命令
- 若外网仅密钥，外网命令必须带正确 `-i <private_key>`

不要把“猜测应该可以”写成“已完成”。
