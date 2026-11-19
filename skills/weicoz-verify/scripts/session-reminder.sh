#!/bin/bash
# SessionStart 钩子：仓库 AGENTS.md 有“## 验证约定”才注入两条流程硬门提醒；其他仓库不输出。
root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
grep -q '^## 验证约定' "$root/AGENTS.md" 2>/dev/null || exit 0
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cat <<EOT
本仓库有验证约定（AGENTS.md「## 验证约定」），两条硬门：
1. 合并到主分支和任何上传之前：主会话亲自对最终提交跑全检，再运行 node $here/verify-gate.mjs --project . [--build <产物目录>]，结论“通过”才继续；子代理自述不算。
2. 对抗式审查只在这些情形做：触及高风险目录或存档、鉴权、支付、并发、对外接口契约；发版或上传前（每批一次）；改验证或门本身；用户要求。文档、文案、调参、样式和小修不做。做时只派 1 个上下文干净的审查者（weicoz-code-review），先说明命中哪一条。派实现子代理时用 weicoz-implement-verified 的派单模板。
EOT
