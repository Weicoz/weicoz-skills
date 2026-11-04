---
name: weicoz-claude-citadel
version: 1.0.0
description: 一键配置与更新 Claude 专属节点与多机场分流订阅（支持 Surge / Loon / Shadowrocket / Quantumult X / Clash / Stash 6 大客户端）。可从剪贴板（pbpaste）或环境变量安全读取订阅链接与住宅 IP 节点，避免敏感凭据外泄；一键更新 GitHub Secret Gist 并触发全格式编译。
---

# Claude Citadel 一键配置与订阅管理

为用户或好友一键配置全平台 6 大主流客户端（Surge、Loon、Shadowrocket、Quantumult X、Clash/Mihomo、Stash）的规则与订阅，支持 Claude 专属独立出口（如波特兰/洛杉矶/日本等原生住宅 IP 或自建 VPS）与多家机场中转池物理分流，并支持分层规则扩展与代理链动态切换。

## 核心设计与安全规范

1. **绝对凭据隔离**：
   - 严禁在对话或终端命令行参数中明文回显机场订阅 Token 或代理服务器账密。
   - 优先通过 macOS 剪贴板（`pbpaste`）或本地环境变量（`~/.zsh_secrets`）读取敏感链接。
2. **私有与公共解耦**：
   - 公共规则采用权威社区规则源（Loyalsoldier / blackmatrix7）与项目专属补充集（`rules/claude.yaml`、`rules/public_direct_supplement.yaml`）。
   - 个人私有服务器、内网网段、自建 NAS 等私密规则，仅存放在用户私有的 GitHub Secret Gist 或本地 `profile.yaml` 的 `custom_rules` 中，绝不提交至公共代码库。
3. **6 大主流客户端全兼容**：
   - 一套统一的 `profile.yaml`，一键编译输出：
     - `clash.yaml` (Mihomo 21-策略组、TUN、严格进程匹配)
     - `stash.yaml` (Stash 移动端精细分流)
     - `surge.conf` (Surge `[Proxy Group]`, `underlying-proxy`, `policy-path`)
     - `loon.conf` (Loon `[Remote Proxy]`, `[Proxy Chain]`, `[Remote Rule]`)
     - `shadowrocket.conf` (Shadowrocket `chain`, `[Proxy Group]`, `RULE-SET`)
     - `qx.conf` (Quantumult X `[policy]`, `[filter_remote]`, `[server_remote]`)

---

## 常用操作工作流

### 1. 从剪贴板安全导入中转机场订阅
用户复制好机场的 Clash / 通用订阅链接后：
```bash
python3 /Users/weicoz/File/git/weicoz-skills/skills/weicoz-claude-citadel/scripts/citadel_cli.py \
  --from-clipboard \
  --type relay-sub \
  --name "猫咪云"
```

### 2. 从剪贴板安全导入 Claude 专用住宅 IP / VPS 节点
用户复制好专用出口链接（如 `socks5://user:pass@198.51.100.1:1080`）：
```bash
python3 /Users/weicoz/File/git/weicoz-skills/skills/weicoz-claude-citadel/scripts/citadel_cli.py \
  --from-clipboard \
  --type claude-node \
  --name "🇺🇸 专属出口"
```

### 3. 动态切换 Claude 代理链模式
- 若住宅 IP 在国内无法直连，开启代理链（经由中转节点转发拨号）：
  ```bash
  python3 /Users/weicoz/File/git/weicoz-skills/skills/weicoz-claude-citadel/scripts/citadel_cli.py --use-relay-chain true
  ```
- 若使用原生可直连的住宅 IP 或专线，关闭代理链（直接出海）：
  ```bash
  python3 /Users/weicoz/File/git/weicoz-skills/skills/weicoz-claude-citadel/scripts/citadel_cli.py --use-relay-chain false
  ```

### 4. 一键全量编译与离线内核校验
```bash
python3 /Users/weicoz/File/git/weicoz-skills/skills/weicoz-claude-citadel/scripts/citadel_cli.py --build
```
编译后将自动调用本地内置的 Mihomo 内核执行 `-t` 静态语法校验。全部通过后产出到 `output/` 目录。

### 5. 同步至 GitHub Secret Gist
如果用户在 Gist 维护配置：
```bash
python3 /Users/weicoz/File/git/claude-citadel/build.py \
  --gist-id "<GIST_ID>" \
  --publish-gist "<GIST_ID>"
```

---

## 统一配置文件结构参考 (`profile.yaml`)

```yaml
# Claude 专用出口
claude_exits:
  use_relay_chain: true
  custom_proxies:
    - name: "🇺🇸 专属出口"
      type: socks5
      server: 198.51.100.1
      port: 1080
      # dialer-proxy: "🔀 中转节点"

# 通用中转节点 (支持 1~4+ 机场订阅)
relays:
  subscriptions:
    - name: "主干专线"
      emoji: "✈️"
      url: "https://sub.airport1.com/api/v1/client/subscribe?token=xxx"
  custom_proxies: []

# 独立组网节点 (可选，如 EasyTier / Tailscale，分配至「🕸️ 组网访问」，不污染常规中转池)
mesh_proxies:
  - name: "EasyTier SOCKS5"
    type: socks5
    server: 127.0.0.1
    port: 15555

# 分层自定义规则 (最高优先级置顶)
custom_rules:
  direct:
    remote_rulesets: []
    rules:
      - "DOMAIN-SUFFIX,my-private-server.com"
      - "IP-CIDR,10.0.0.0/8,no-resolve"
  relay:
    remote_rulesets: []
    rules:
      - "DOMAIN-SUFFIX,custom-blocked.com"
  claude_exit:
    remote_rulesets: []
    rules:
      - "DOMAIN-SUFFIX,my-claude-mirror.com"
  mesh:
    remote_rulesets: []
    rules:
      - "IP-CIDR,10.144.0.0/16,no-resolve"
      - "IP-CIDR,10.126.0.0/16,no-resolve"
      - "PROCESS-NAME,easytier-core"
```
