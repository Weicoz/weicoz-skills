---
name: weicoz-claude-citadel-routing
version: 1.0.0
description: >
  维护 Claude Citadel 主方案与 subscription-configs 备用方案的分流规则。
  用户报告网站打不开、命中 Fake-IP、代理出口返回 403、要把域名加入
  “不走 fake-IP”或直连、发布订阅、更新 Bettbox/M6，或要求验证浏览器
  是否真的打开时使用。覆盖域名诊断、主备源修改、Gist 发布、客户端热加载
  与实网验收。节点、凭据、Gist ID、profile ID 和 API secret 只在本机读取。
---

# Claude Citadel / Bettbox 域名分流

## 目标

把一个域名从“解析到 Fake-IP 并被代理错误带走”修到“真实解析、按预期
直连或代理、浏览器实际渲染”。同时保持主方案与备用方案一致。

个人主方案是 Claude Citadel 的私有 `profile.yaml`；`subscription-configs`
是备用方案。个人出口、内网、凭据和主备关系只留在私有配置。公域网站的通用
规则可以进入公共模板或规则。

## 先分清四个状态

| 现象 | 含义 | 下一步 |
| --- | --- | --- |
| DNS 返回 `198.18.0.0/15` | Fake-IP 已接管 | 加入 `fake-ip-filter` |
| DNS 是真实 IP，但出口返回 `403 address forbidden` | 路由走错出口 | 加入直连规则 |
| `curl` 200，浏览器仍报错 | 浏览器旧连接或页面资源失败 | 看浏览器错误码并重载 |
| 修完后浏览器报 `ERR_SSL_PROTOCOL_ERROR` | 旧 Fake-IP/TLS 连接残留的常见表现 | 关闭旧标签或重启浏览器 |

Fake-IP 和路由是两层。只做 Fake-IP 过滤时，真实 IP 仍可能因 `GEOIP` 或
`MATCH` 进入海外出口；只做直连规则时，DNS 仍可能返回 Fake-IP。

## 1. 只读复现

先取得浏览器中的真实错误码，再跑命令行对照。`curl` 是链路证据，不能替代
浏览器验收。

```bash
domain=example.com

dig +short "$domain" A
dig +short "$domain" AAAA

curl -sS -o /dev/null \
  -w 'http=%{http_code} remote=%{remote_ip} ssl=%{ssl_verify_result} time=%{time_total}\n' \
  --max-time 20 "https://$domain/"

curl -sS -o /dev/null \
  -w 'direct_http=%{http_code} remote=%{remote_ip}\n' \
  --interface en0 --max-time 20 "https://$domain/" || true
```

`--interface en0` 是绕过 TUN 的对照，不是最终验收。它会掩盖 TUN、规则和
客户端缓存问题。

读取当前 Bettbox 配置，不打印 secret：

```bash
bettbox_home="${BETTBOX_HOME:-$HOME/Library/Application Support/com.appshub.bettbox}"
profile_id="$(jq -r '.currentProfileId // empty' "$bettbox_home/config.json")"
profile="$bettbox_home/profiles/$profile_id.yaml"
runtime="$bettbox_home/config.yaml"

"<skill-dir>/scripts/check-domain.sh" \
  "$domain" "$profile" "$runtime"
```

检查远端来源时，先读私有 Gist 的最新 `profile.yaml`，再核对本地副本。
本地副本是缓存，不是永久事实源。

## 2. 改来源，不先改运行态

为主域名和需要的子域名同时加入过滤与路由：

```yaml
network:
  fake_ip_filter_extra:
    - "example.com"
    - "+.example.com"

custom_rules:
  direct:
    rules:
      - "DOMAIN-SUFFIX,example.com,DIRECT"
```

`example.com` 覆盖裸域，`+.example.com` 覆盖子域；两者都要时分别添加。
域名有 CNAME 时先看真实链路，只在确有需要时补 CNAME 目标。

修改范围：

1. Claude Citadel 私有 profile 是主来源。用 `network.fake_ip_filter_extra`
   保存个人域名过滤，用 `custom_rules.direct.rules` 保存直连规则。
2. 公域网站的通用规则可以同步到公共模板；个人出口、内网和私密关系不得进入
   公共仓库。
3. `subscription-configs` 必须同步修改所有在用桌面 YAML 和对应规则文件。
   归档配置只在用户明确要求时修改。
4. 页面静态资源域名单独验证。资源域若通过代理正常返回 200，就保持代理，
   不要把 `search*`、`static*` 等后端域名顺手加直连。

## 3. 测试、发布、激活

按仓库现有检查执行，不要另造一套：

```bash
citadel_repo="${CITADEL_REPO:-$HOME/File/git/claude-citadel}"
subscription_repo="${SUBSCRIPTION_REPO:-$HOME/File/git/subscription-configs}"

cd "$citadel_repo"
python3 -m unittest discover -s tests -v
python3 build.py --profile "$HOME/.config/claude-citadel/profile.yaml"

cd "$subscription_repo"
python3 -m unittest discover -s tests -v
python3 scripts/gist_sync.py status
```

发布主 Gist 后，用 revision-pinned raw URL 回读每个改动文件并比较哈希。
稳定 raw URL 可能继续返回旧内容。

发布备用 Gist：

```bash
python3 scripts/gist_sync.py publish
python3 scripts/gist_sync.py status
```

更新 Bettbox 前先备份 profile 和 runtime，并快照 `GET /proxies` 的 selector
状态。热加载使用 `PUT /configs?force=true`；随后清 Fake-IP/DNS 缓存并恢复
被重置的 selector。API secret 只能从本机配置读取，不得回显或写入日志。

订阅自动更新会覆盖本地 profile。只改本地文件而不更新远端来源，下一次更新
就会复发。

## 4. 验收阶梯

逐层报告，前一层通过不能代替后一层：

1. 来源：每个请求域名在主 profile 和所有备用配置中各出现一次。
2. 测试：仓库测试和内核对生成的 YAML 通过。
3. 产物：生成文件只多出预期域名，其他客户端产物不变。
4. 远端：Gist revision、文件哈希和 revision-pinned raw 一致。
5. 运行态：Bettbox 活动 profile 与 runtime 都包含过滤和直连规则。
6. DNS：系统解析返回真实公网 IP，不是 Fake-IP。
7. 命令行：`curl` 返回预期 HTTP 状态和真实远端 IP。
8. 浏览器：实际看到页面标题和正文，并确认页面资源加载成功。

浏览器仍失败时，先记录错误码，再重载或关闭旧标签。不要只看 HTTP 200 就
宣称完成。Computer Use 无法继续时，明确标为“浏览器未验证”，不要改成
“已修复”。

## 交付格式

最终报告按层分开写：

- 根因：Fake-IP、路由、出口拒绝或浏览器缓存。
- 主来源：私有 profile 的字段和规则。
- 备用来源：修改的配置与规则。
- 发布：Gist revision 与回读结果。
- 运行态：Bettbox 热加载与 selector。
- 实网：DNS、curl 和浏览器页面证据。
- 未完成项：git 提交、客户端动作或无法验证的浏览器步骤。

## 常见坑

- 只看 DNS 就停：真实 IP 仍可能走错误出口。
- 只看 `curl` 就停：浏览器可能仍缓存旧 TLS 连接。
- 把上游 403 当网站故障：先看出口返回正文中的 `address forbidden`。
- 把 HTTP 204 当热加载成功：必须回读 profile、runtime 和 live DNS。
- 把 selector 重置当正常：热加载后逐项比较快照并恢复。
- 把稳定 Gist raw 当最新：用 revision-pinned URL 和哈希确认。
- 没获授权就改 TUN、SwitchyOmega、系统代理或重启客户端：这些会中断用户网络。
