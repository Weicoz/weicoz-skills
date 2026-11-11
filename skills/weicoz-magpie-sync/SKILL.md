---
name: weicoz-magpie-sync
version: 1.0.0
description: >
  在多台机器之间同步 Magpie 的 provider、设置、登录态与额度配置，并用同一个
  WebDAV 账号下的独立目录做加密备份。API key 只从本机密钥文件
  ~/.zsh_secrets 读取，不写入仓库、README、日志或对话。用户说“同步 Magpie
  配置”“线上 Magpie 和本地一样”“配置 WebDAV 备份”“不要同步
  remote-magpie”“把 key 放本地密钥库”时使用。不代登录、扫码、验证码、实名或付款。
---

# Magpie 多机同步与 WebDAV 备份

## 先记住三件事

1. Magpie 的 WebDAV 同步没有“按 provider 排除”的开关。两台机器共用同一个
   WebDAV 目录时，本地专用的 `remote-magpie` 会被同步到远端，远端也可能把
   自己的 provider 写回本地。必须使用同一账号下的不同目录。
2. `remote-magpie` 是回指本机的 provider，只留在本机。远端不应有它。
3. API key 只放在本机 `~/.zsh_secrets`（权限 600）或 Magpie 自己的
   `providers.json`（权限 600）。任何 key、WebDAV 密码、passphrase 都不得
   出现在 skill、README、Git、日志、截图或对话里。

## 变量

```bash
export MAGPIE_HOME="${MAGPIE_HOME:-$HOME/.config/magpie}"
export MAGPIE_REMOTE_SSH="${WEICOZ_MAGPIE_REMOTE_SSH:?请先配置 SSH 别名}"
export MAGPIE_REMOTE_CONTAINER="${WEICOZ_MAGPIE_REMOTE_CONTAINER:-magpie}"
export MAGPIE_REMOTE_CONFIG="${WEICOZ_MAGPIE_REMOTE_CONFIG:-/opt/docker/magpie/config/magpie}"
export MAGPIE_LOCAL_ONLY="${WEICOZ_MAGPIE_LOCAL_ONLY_PROVIDERS:-remote-magpie}"
```

`MAGPIE_REMOTE_SSH` 应是 `~/.ssh/config` 里的别名，优先走 EasyTier、WireGuard
或内网跳板。不要在公网用 FRP 暴露 SSH；若机器上仍有 `frps`/`frpc`，先确认
没有其他依赖，再停用或删除，并保留备份。

## 1. 只读核对

```bash
magpie providers
magpie webdav
jq '{url,user,keys,agents,library,usage,signIns}' "$MAGPIE_HOME/sync.json"

ssh "$MAGPIE_REMOTE_SSH" \
  "docker exec $MAGPIE_REMOTE_CONTAINER magpie webdav"
ssh "$MAGPIE_REMOTE_SSH" \
  "docker exec $MAGPIE_REMOTE_CONTAINER magpie providers"
```

只打印 `sync.json` 的 `url`、`user` 和开关；不要打印 `password`、`passphrase`。

## 2. 选择独立目录

```bash
local_url="$(jq -r .url "$MAGPIE_HOME/sync.json")"
webdav_user="$(jq -r .user "$MAGPIE_HOME/sync.json")"

# 把 magpie-remote 换成目标机器名；不要与本地目录相同
remote_url="${local_url%/}/magpie-remote"
printf 'local=%s\nremote=%s\n' "$local_url" "$remote_url"
```

Magpie 会在给定地址下再建一个 `magpie` 子目录。例如
`https://webdav.example.com/magpie-remote` 最终备份是
`/magpie-remote/magpie/magpie.magpie-backup`。

目录不存在时，优先用 WebDAV 网页或已登录客户端创建。需要命令行创建时，
从 `sync.json` 读取密码并写入临时 netrc，避免把密码放进命令参数：

```bash
umask 077
netrc="$(mktemp)"
trap 'rm -f "$netrc"' EXIT
jq -r '
  "machine \(.url | sub("^https?://"; "") | sub("/.*$"; ""))" +
  "\nlogin \(.user)\npassword \(.password)"
' "$MAGPIE_HOME/sync.json" > "$netrc"

curl --netrc-file "$netrc" -sS -L -X PROPFIND \
  -H 'Depth: 0' -o /dev/null -w '%{http_code}\n' "$remote_url"

# 404 时创建
curl --netrc-file "$netrc" -sS -L -X MKCOL "$remote_url"
```

密码含空格或特殊字符导致 netrc 失败时，改用 WebDAV 客户端创建目录，不要
把密码写进命令行或聊天。

## 3. 清理远端 provider

先停容器，备份 `providers.json`，再删除本地专用 id。下面的脚本会同时清理
`.providers`、`.order` 和路由组的 `members`/`seen`。

```bash
ssh "$MAGPIE_REMOTE_SSH" \
  "docker stop $MAGPIE_REMOTE_CONTAINER >/dev/null 2>&1 || true"

ssh "$MAGPIE_REMOTE_SSH" \
  "MAGPIE_REMOTE_CONFIG='$MAGPIE_REMOTE_CONFIG' MAGPIE_LOCAL_ONLY='$MAGPIE_LOCAL_ONLY' bash -s" <<'REMOTE'
set -euo pipefail
cd "$MAGPIE_REMOTE_CONFIG"
ts="$(date +%Y%m%d-%H%M%S)"
mkdir -p ../backups
cp -a providers.json "../backups/providers-pre-clean-$ts.json"

ids="$(printf '%s\n' "$MAGPIE_LOCAL_ONLY" | tr ' ' '\n' | jq -R . | jq -s .)"
jq --argjson ids "$ids" '
  .providers |= map(select(.id as $id | $ids | index($id) | not))
  | .order |= map(select(. as $id | $ids | index($id) | not))
  | .groups |= map(
      (if (.members | type) == "array"
       then .members |= map(select(. as $id | $ids | index($id) | not))
       else . end)
      | (if (.seen | type) == "array"
         then .seen |= map(select(. as $id | $ids | index($id) | not))
         else . end)
    )
' providers.json > providers.json.tmp

jq empty providers.json.tmp
owner="$(stat -c '%u:%g' providers.json)"
chown "$owner" providers.json.tmp
chmod 600 providers.json.tmp
mv providers.json.tmp providers.json

if jq -r '.providers[].id' providers.json |
  grep -Fxf <(printf '%s\n' "$MAGPIE_LOCAL_ONLY" | tr ' ' '\n'); then
  echo "error: excluded provider still present" >&2
  exit 1
fi
REMOTE

ssh "$MAGPIE_REMOTE_SSH" \
  "docker start $MAGPIE_REMOTE_CONTAINER >/dev/null; sleep 3; docker exec $MAGPIE_REMOTE_CONTAINER magpie healthcheck"
```

如果远端不是 Docker，把 `docker exec ... magpie` 换成远端宿主机的
`magpie` 命令。不要删除备份；回滚时用它恢复。

## 4. 切到独立目录

密码和 passphrase 由 Magpie 管理，按“第一行密码、第二行 passphrase”从 stdin
传入，不落命令行、不回显：

```bash
{
  jq -r .password "$MAGPIE_HOME/sync.json"
  jq -r .passphrase "$MAGPIE_HOME/sync.json"
} | ssh "$MAGPIE_REMOTE_SSH" \
  "docker exec -i $MAGPIE_REMOTE_CONTAINER magpie webdav on '$remote_url' user='$webdav_user'"

ssh "$MAGPIE_REMOTE_SSH" \
  "docker exec $MAGPIE_REMOTE_CONTAINER magpie webdav auto 3"
ssh "$MAGPIE_REMOTE_SSH" \
  "docker exec $MAGPIE_REMOTE_CONTAINER magpie webdav now"
ssh "$MAGPIE_REMOTE_SSH" \
  "docker exec $MAGPIE_REMOTE_CONTAINER magpie webdav"
```

首次同步到空目录时，Magpie 会把当前机器的配置上传成服务器文件，不会反向
覆盖本机。需要从服务器恢复本机时，先读 `magpie webdav help`，再用
`restore`/`undo`，不要凭印象操作。

## 5. Key 保存与轮换

本机密钥库是 `~/.zsh_secrets`，由 `~/.zshrc` 加载：

```bash
chmod 600 "$HOME/.zsh_secrets"
# 在编辑器中追加，不要把值发到聊天
# export EXAMPLE_API_KEY='...'
# export EXAMPLE_BASE_URL='https://api.example.com/v1'
```

新增 provider 时从密钥库取值，不把值写进命令历史：

```bash
magpie provider add <preset> "$EXAMPLE_API_KEY"
# 自定义供应商的字段名是 key 和 url
magpie provider add <name> key="$EXAMPLE_API_KEY" url="$EXAMPLE_BASE_URL"
magpie provider test <id> <model>
```

Magpie 自己会把 provider key 写进 `providers.json`（600）。WebDAV 同步默认
包含这些 key，并用 passphrase 密封；`keys=no` 时各机器保留自己的 key。
WebDAV 密码和 passphrase 由 Magpie 存在 `sync.json`（600），不要复制进
README、仓库或 skill。需要灾难恢复副本时，放密码管理器，不要放 Git。

轮换 key：先更新 `~/.zsh_secrets`，再执行
`magpie provider key <id> "$EXAMPLE_API_KEY"`，`magpie provider test` 通过后
执行一次 `magpie webdav now`。Magpie 当前 CLI 要求 key 作为参数；用变量至少
避免写入 shell history，操作时确保本机没有不可信进程。

## 6. 验证

```bash
# 本地与远端 provider id 差异；预期只有 MAGPIE_LOCAL_ONLY
jq -r '.providers[].id' "$MAGPIE_HOME/providers.json" | sort -u > /tmp/magpie-local.ids
ssh "$MAGPIE_REMOTE_SSH" \
  "jq -r '.providers[].id' '$MAGPIE_REMOTE_CONFIG/providers.json' | sort -u" \
  > /tmp/magpie-remote.ids
echo '只在本机:'; comm -23 /tmp/magpie-local.ids /tmp/magpie-remote.ids
echo '只在远端:'; comm -13 /tmp/magpie-local.ids /tmp/magpie-remote.ids

ssh "$MAGPIE_REMOTE_SSH" \
  "docker inspect --format '{{.State.Health.Status}}' $MAGPIE_REMOTE_CONTAINER"
ssh "$MAGPIE_REMOTE_SSH" \
  "docker exec $MAGPIE_REMOTE_CONTAINER magpie webdav"

magpie quota <provider-id> --json
```

判定标准：

- 本地比远端多出的 id 只能是 `remote-magpie`（或用户明确指定的本地专用项）。
- 远端多出任何 id 都先停同步，核对路由组和插件来源，不要直接删。
- `magpie webdav` 必须显示新的独立地址、最近同步时间和 `auto 3`。
- `healthcheck` 返回 0，容器状态为 `healthy`。
- 额度只引用 `magpie quota --json` 的实际值；接口报错、无公开额度接口或未登录
  时，记录原始错误和原因，不得写成 0，也不得伪造“已对接”。

## 7. 回滚

```bash
ssh "$MAGPIE_REMOTE_SSH" "docker stop $MAGPIE_REMOTE_CONTAINER"
# 在远端把 ../backups/providers-pre-clean-*.json 复制回 providers.json
# 恢复原属主和 600 权限后：
ssh "$MAGPIE_REMOTE_SSH" \
  "docker start $MAGPIE_REMOTE_CONTAINER; docker exec $MAGPIE_REMOTE_CONTAINER magpie healthcheck"
```

不要删除备份。WebDAV 的 `restore`/`undo` 会改变本机配置，执行前先读帮助并
确认方向。

## 边界

- 不代登录、扫码、验证码、2FA、实名、绑卡或付款；遇到登录墙立即交给用户。
- 不把 `remote-magpie` 同步到它指向的机器，否则会形成回环。
- 不把 WebDAV 密码、passphrase、API key 写入 skill、README、Git、日志或对话。
- `signIns=yes` 会把订阅账号和插件登录态放进密封备份；只有用户接受“持有
  passphrase 即可使用这些账号”时才开启。
