#!/usr/bin/env bash
# 只读检查 DSH 本体与两个预设仓库，并按实装状态输出信号灯。
# 只 fetch 对比仓库的远端引用，核对实装文件哈希，
# 绝不 checkout/reset/pull/clean，不修改任何工作区、不卸载插件、不改 ~/.dsh。
#
# 信号灯语义（关键）：
#   🟢 绿灯 = 实装与上游一致 / 无需任何同步操作
#   🔴 红灯 = 实装与上游不一致，需评估同步
#   ⚪ 无法对比 / 实装未能检测 = 如实说明，不断言
#
# 注意：/tmp/dsh-compare 下的 clone 只是"对比镜像"，落后不代表实装(DSH)落后。
#   信号灯一律以实装(~/.dsh)为准，不以缓存 clone 落后就报红。
#
# 路径可用环境变量覆盖：
#   DSH_REPOS_XIAOBRIGHT  DSH_REPOS_ROUTING   (缓存 clone)
#   DSH_INSTALLED_ANCHORED                     (anchored 实装目录，默认 ~/.dsh/.agent-presets/anchored-standard)
# 远端可用：
#   DSH_REMOTE_XIAOBRIGHT  DSH_REMOTE_ROUTING
set -u

REMOTE_XIAOBRIGHT="${DSH_REMOTE_XIAOBRIGHT:-https://github.com/xiaobright/dsh-anchored-standard.git}"
REMOTE_ROUTING="${DSH_REMOTE_ROUTING:-https://github.com/yjh051108/dsh-routing-suite.git}"
LOCAL_XIAOBRIGHT="${DSH_REPOS_XIAOBRIGHT:-$HOME/File/git/dsh-anchored-standard}"
LOCAL_ROUTING="${DSH_REPOS_ROUTING:-$HOME/File/git/dsh-routing-suite}"
INSTALLED_ANCHORED="${DSH_INSTALLED_ANCHORED:-$HOME/.dsh/.agent-presets/anchored-standard}"
DSH_HOME_DIR="${DSH_HOME:-$HOME/.dsh}"

remote_head() { git ls-remote "$1" HEAD 2>/dev/null | awk '{print $1}'; }

check_dsh() {
  echo "===== deepseek-ai/dsh ====="
  if ! command -v dsh >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
    echo "信号灯: ⚪ 无法对比（缺少 dsh/npm/jq）"; echo; return
  fi
  local installed tags latest next newest
  installed="$(dsh --version 2>/dev/null)"
  tags="$(npm view @deepseek-ai/dsh dist-tags --json 2>/dev/null)"
  latest="$(printf '%s' "$tags" | jq -r '.latest // empty' 2>/dev/null)"
  next="$(printf '%s' "$tags" | jq -r '.next // empty' 2>/dev/null)"
  echo "本机版本: ${installed:-<未知>}"
  echo "npm latest: ${latest:-<未知>}"
  echo "npm next: ${next:-<未知>}"
  if [ -z "$installed" ] || [ -z "$latest" ]; then
    echo "信号灯: ⚪ 无法对比（npm 查询失败）"
  else
    newest="$(printf '%s\n' "$latest" "$next" | sed '/^$/d' | sort -V | tail -1)"
    if [ "$installed" = "$newest" ]; then
      echo "信号灯: 🟢 绿灯（与 npm 最高发布标签一致）"
    elif [ "$(printf '%s\n' "$installed" "$newest" | sort -V | tail -1)" = "$newest" ]; then
      echo "信号灯: 🔴 红灯（有较新发布版本 ${newest}；未安装）"
    else
      echo "信号灯: ⚪ 本机版本高于发布标签，需人工核对"
    fi
  fi
  echo
}

# 比对远端目录的直接文件与平铺实装目录；不把上游文档/测试算作预设文件。
compare_flat_files() {
  local local_dir="$1" remote_ref="$2" source_dir="$3" installed_dir="$4"
  local count=0 mismatch=0 f rel upstream local_hash
  if [ ! -d "$installed_dir" ]; then
    echo "实装核对: 未找到 $installed_dir"; return 2
  fi
  while IFS= read -r f; do
    case "${f#"$source_dir"/}" in */*) continue ;; esac
    rel="${f#"$source_dir"/}"
    upstream="$(git -C "$local_dir" rev-parse "$remote_ref:$f" 2>/dev/null)"
    local_hash=""
    [ ! -f "$installed_dir/$rel" ] || local_hash="$(git hash-object "$installed_dir/$rel" 2>/dev/null)"
    count=$((count + 1))
    if [ "$upstream" != "$local_hash" ]; then
      mismatch=$((mismatch + 1))
      echo "  不一致: $installed_dir/$rel"
    fi
  done < <(git -C "$local_dir" ls-tree -r --name-only "$remote_ref" -- "$source_dir")
  echo "实装核对: $installed_dir 与上游 ${source_dir}：$count 个文件，$mismatch 个不一致"
  [ "$count" -eq 0 ] && return 2
  [ "$mismatch" -eq 0 ]
}

check_anchored_installed() {
  local local_dir="$1" remote_ref="$2"
  compare_flat_files "$local_dir" "$remote_ref" preset "$INSTALLED_ANCHORED"
}

# routing-suite 的两个已装预设和 injector 链接都要核对。
check_routing_installed() {
  local local_dir="$1" remote_ref="$2"
  local rc=0 part link f upstream local_hash refs junction
  for part in router-standard router-spec; do
    compare_flat_files "$local_dir" "$remote_ref" "preset/$part" "$DSH_HOME_DIR/.agent-presets/$part" || rc=1
  done
  link="$(jq -r '.dependencies["@dsh-external/dsh-super-injector"] // empty' "$DSH_HOME_DIR/profiles/web/package.json" 2>/dev/null)"
  if [[ "$link" == link:* ]]; then
    link="${link#link:}"
    for f in package.json src/index.ts scripts/build.sh; do
      upstream="$(git -C "$local_dir" rev-parse "$remote_ref:injector/$f" 2>/dev/null)"
      local_hash=""
      [ ! -f "$link/$f" ] || local_hash="$(git hash-object "$link/$f" 2>/dev/null)"
      if [ "$upstream" != "$local_hash" ]; then
        echo "  injector 链接与套装上游不一致: $link/$f"
        rc=1
      fi
    done
  else
    echo "实装核对: injector 未见明确 link 来源，无法自动核对"
    rc=2
  fi
  refs="$(grep -rl 'mode-boost' "$DSH_HOME_DIR"/profiles/*/package.json 2>/dev/null | head -1)"
  junction="$(find "$DSH_HOME_DIR/profiles"/*/node_modules -maxdepth 1 -iname '*mode-boost*' ! -iname '*.bak*' 2>/dev/null | head -1)"
  if ! git -C "$local_dir" ls-tree "$remote_ref" -- mode-boost 2>/dev/null | grep -q mode-boost && { [ -n "$refs" ] || [ -n "$junction" ]; }; then
    echo "实装核对: 上游已移除 mode-boost，本机仍有真实引用，需处理断 link 风险"
    rc=1
  fi
  return "$rc"
}

check_repo() {
  name="$1"
  local_dir="$2"
  remote_url="$3"
  echo "===== $name ====="

  if ! git -C "$local_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "local clone 缺失: $local_dir"
    rh="$(remote_head "$remote_url")"
    if [ -n "$rh" ]; then
      echo "remote HEAD (仅远端): $rh"
      echo "状态: ⚪ 无法对比（无本地基线）"
    else
      echo "无法访问远端（网络/权限）。"
      echo "状态: ⚪ 无法对比"
    fi
    echo ""
    return
  fi

  if ! git -C "$local_dir" fetch origin >/dev/null 2>&1; then
    echo "fetch 失败（网络/权限）；旧远端引用不能证明当前状态"
    echo "信号灯: ⚪ 无法对比"
    echo; return
  fi

  local local_head remote_head
  local_head="$(git -C "$local_dir" rev-parse HEAD 2>/dev/null || true)"
  remote_head="$(git -C "$local_dir" rev-parse origin/HEAD 2>/dev/null || remote_head "$remote_url")"
  echo "local HEAD : ${local_head:-<未知>}"
  echo "remote HEAD: ${remote_head:-<未知>}"

  if [ -z "$local_head" ] || [ -z "$remote_head" ]; then
    echo "状态: ⚪ 无法完整对比"
    echo ""
    return
  fi

  if [ "$local_head" = "$remote_head" ]; then
    echo "状态: NO update（对比 clone 本地=远端）"
  else
    echo "状态: HAS update（对比 clone 落后，下详）"
  fi
  local rc=2
  case "$name" in
    *anchored-standard*) check_anchored_installed "$local_dir" "$remote_head"; rc=$? ;;
    *routing-suite*) check_routing_installed "$local_dir" "$remote_head"; rc=$? ;;
  esac
  if [ "$rc" = "0" ]; then
    echo "信号灯: 🟢 绿灯 - 实装已与上游一致"
  elif [ "$rc" = "1" ]; then
    echo "信号灯: 🔴 红灯 - 实装与上游不一致，需评估同步"
  else
    echo "信号灯: ⚪ 实装未能完整检测"
  fi
  if [ "$local_head" != "$remote_head" ]; then
    echo "-- 新提交（local->remote）--"
    git -C "$local_dir" log --format='%h | %ci | %s' "$local_head..$remote_head" 2>/dev/null \
      | sed 's/^/    /' || echo "    (无法列出)"
    echo "-- 改动文件按需用 git diff --name-only $local_head..$remote_head 查看 --"
  fi
  echo ""
}

check_dsh
check_repo "xiaobright/dsh-anchored-standard" "$LOCAL_XIAOBRIGHT" "$REMOTE_XIAOBRIGHT"
check_repo "yjh051108/dsh-routing-suite"   "$LOCAL_ROUTING"   "$REMOTE_ROUTING"
