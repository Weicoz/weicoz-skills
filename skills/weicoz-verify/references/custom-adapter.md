# 自建验证命令（“其他”项目）

后端、命令行、脚本类项目没有现成适配器时，自建一条命令，满足 `SKILL.md` 第 2 节。骨架：

```bash
#!/usr/bin/env bash
# scripts/verify.sh：逐项检查，末行结论，退出码 0 通过 / 1 不通过 / 3 未验证
set -o pipefail
fails=(); missing=()
STAMP=<weicoz-verify 目录>/scripts/stamp.mjs
node "$STAMP" start   # 记开始状态，删旧戳记

check() { # check <名称> <命令...>
  local name=$1; shift
  if out=$("$@" 2>&1); then echo "✅ $name"
  else echo "❌ $name"; echo "$out" | tail -5 | sed 's/^/    /'; fails+=("$name"); fi
}
need() { # need <名称> <命令>：缺工具时记未验证，不当通过
  command -v "$2" >/dev/null || { echo "⚠️ $1：缺 $2"; missing+=("$2"); return 1; }
}

need 类型检查 tsc && check 类型检查 npx tsc --noEmit
check 单测 npm test
check 构建 npm run build
# 健康检查、关键接口真实调用：check 健康检查 curl -fsS http://127.0.0.1:3000/health

if [ ${#fails[@]} -gt 0 ]; then
  node "$STAMP" finish --tier "${VERIFY_TIER:-full}" --code 1 --base "${BASE:-main}"
  echo "结论：不通过（失败：$(IFS=、; echo "${fails[*]}")）"; exit 1
elif [ ${#missing[@]} -gt 0 ]; then
  node "$STAMP" finish --tier "${VERIFY_TIER:-full}" --code 3 --base "${BASE:-main}"
  echo "结论：未验证（缺：$(IFS=、; echo "${missing[*]}")）"; exit 3
fi
node "$STAMP" finish --tier "${VERIFY_TIER:-full}" --code 0 --base "${BASE:-main}"   # 全检通过才写戳记
echo "结论：通过"
```

- 失败优先于未验证：有失败项就退出 1。
- 没跑的检查不得标 ✅。
- 快检与全检用同一脚本的参数区分，或各一条命令；命令检查里读 `VERIFY_TIER`（`quick` 或 `full`）也可以。
- 不引入新依赖；已有的测试、类型检查、构建、健康检查直接串起来。
