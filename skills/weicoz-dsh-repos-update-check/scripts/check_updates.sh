#!/usr/bin/env bash
# 只读检查两个 DSH 插件仓库是否有更新，并按"实装(~/.dsh)是否需同步"输出信号灯。
# 只 fetch 远端引用、读本地 HEAD 与远端 HEAD 比对、核对实装关键文件哈希，
# 绝不 checkout/reset/pull/clean，不修改任何工作区、不卸载插件、不改 ~/.dsh。
#
# 信号灯语义（关键）：
#   🟢 绿灯 = 实装与上游一致 / 无需任何同步操作
#   🔴 红灯 = 实装落后于上游，需要 pull / 重新同步预设
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
LOCAL_XIAOBRIGHT="${DSH_REPOS_XIAOBRIGHT:-/tmp/dsh-compare/xiaobright}"
LOCAL_ROUTING="${DSH_REPOS_ROUTING:-/tmp/dsh-compare/routing-suite}"
INSTALLED_ANCHORED="${DSH_INSTALLED_ANCHORED:-$HOME/.dsh/.agent-presets/anchored-standard}"

remote_head() { git ls-remote "$1" HEAD 2>/dev/null | awk '{print $1}'; }

# ---- anchored-standard 实装核对：对比实装目录关键文件与远端 preset/ ----
# 返回 0=已同步 GREEN / 1=落后 RED / 2=未检测 UNKNOWN
check_anchored_installed() {
  local local_dir="$1" remote_ref="$2"
  if [ ! -d "$INSTALLED_ANCHORED" ]; then
    echo "实装核对: 未找到实装目录 $INSTALLED_ANCHORED（未检测）"
    return 2
  fi
  local ok=1 reason=""
  for f in "custom-bash.mjs" "agent.cordis.yml"; do
    # 远端路径在 preset/ 下；实装路径在目录根部
    local rem loc
    rem="$(git -C "$local_dir" show "$remote_ref:preset/$f" 2>/dev/null | shasum | awk '{print $1}')"
    if [ -f "$INSTALLED_ANCHORED/$f" ]; then
      loc="$(shasum "$INSTALLED_ANCHORED/$f" | awk '{print $1}')"
    else
      loc="__missing__"
    fi
    if [ -z "$rem" ] || [ "$rem" != "$loc" ]; then
      ok=0
      reason="$reason [$f 不一致]"
    fi
  done
  if [ "$ok" = "1" ]; then
    echo "实装核对: $INSTALLED_ANCHORED 关键文件与远端 preset/ 一致"
    return 0
  else
    echo "实装核对: 实装与远端 preset/ 不一致$reason"
    return 1
  fi
}

# ---- routing-suite 联动核对：上游若移除 mode-boost，检查本机是否仍引用 ----
# 返回 0=无需操作 GREEN / 1=需注意 RED / 2=未检测 UNKNOWN
check_routing_installed() {
  local local_dir="$1" remote_ref="$2"
  local mb_removed=0
  if ! git -C "$local_dir" ls-tree "$remote_ref" -- mode-boost 2>/dev/null | grep -q "mode-boost"; then
    mb_removed=1
  fi
  if [ "$mb_removed" = "0" ]; then
    echo "实装核对: 上游仍保留 mode-boost 子模块（未触发移除联动）"
    return 0
  fi
  # 上游已移除：检查本机是否还有 link 引用（package.json）或 node_modules junction
  # （只认真实安装痕迹，排除 *.bak 备份、*.jsonl 日志、cached 等）
  local refs junction
  refs="$(grep -rl "mode-boost" "$HOME/.dsh"/profiles/*/package.json 2>/dev/null | head -1)"
  junction="$(find "$HOME/.dsh/profiles"/*/node_modules -maxdepth 1 -iname "*mode-boost*" ! -iname "*.bak*" 2>/dev/null | head -1)"
  if [ -z "$refs" ] && [ -z "$junction" ]; then
    echo "实装核对: 上游已移除 mode-boost，本机无线引用/无 junction，无断 link 风险"
    return 0
  else
    echo "实装核对: 上游已移除 mode-boost，但本机仍有引用(${refs:-无} ${junction:-无})，pull 可能断 link"
    return 1
  fi
}

check_repo() {
  name="$1"
  local_dir="$2"
  remote_url="$3"
  echo "===== $name ====="

  if [ ! -d "$local_dir/.git" ]; then
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
    echo "fetch 失败（网络/权限？）。改用当前本地已有远端引用："
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
    echo "状态: NO update（缓存 clone 本地=远端）"
    echo "信号灯: 🟢 绿灯 - 无需同步"
  else
    echo "状态: HAS update（缓存 clone 落后，下详）"
    # 实装核对决定红/绿
    local rc=2
    case "$name" in
      *anchored-standard*)
        check_anchored_installed "$local_dir" "$remote_head"; rc=$? ;;
      *routing-suite*)
        check_routing_installed "$local_dir" "$remote_head"; rc=$? ;;
    esac
    if [ "$rc" = "0" ]; then
      echo "信号灯: 🟢 绿灯 - 实装已是最新，无需操作"
    elif [ "$rc" = "1" ]; then
      echo "信号灯: 🔴 红灯 - 实装落后，需同步/注意联动"
    else
      echo "信号灯: ⚪ 实装未检测，请人工核对"
    fi
    echo "-- 新提交（local->remote）--"
    git -C "$local_dir" log --format='%h | %ci | %s' "$local_head..$remote_head" 2>/dev/null \
      | sed 's/^/    /' || echo "    (无法列出)"
    echo "-- 改动文件按需用 git diff --name-only $local_head..$remote_head 查看 --"
  fi
  echo ""
}

check_repo "xiaobright/dsh-anchored-standard" "$LOCAL_XIAOBRIGHT" "$REMOTE_XIAOBRIGHT"
check_repo "yjh051108/dsh-routing-suite"   "$LOCAL_ROUTING"   "$REMOTE_ROUTING"
