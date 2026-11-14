#!/usr/bin/env bash
# 列出 T3 Code 已配置的 provider 实例，以及历史会话里每个实例用过的模型串。
# `t3 thread start --provider <id> --model <模型串>` 两个参数都要从这里取。
set -euo pipefail
home="${T3CODE_HOME:-$HOME/.t3}/userdata"
if [ ! -f "$home/settings.json" ]; then
  echo "错误：未找到 $home/settings.json。" >&2
  echo "请确认已安装 T3 Code，或设置数据目录：export T3CODE_HOME=\"<T3 数据目录>\"" >&2
  exit 1
fi
python3 -I - "$home" <<'PY'
import json, sqlite3, sys, pathlib
home = pathlib.Path(sys.argv[1])
inst = json.loads((home / "settings.json").read_text()).get("providerInstances", {})
print("== provider 实例（settings.json 中自定义的；内置 provider 不在此列）")
for k, v in inst.items():
    print(f"{k}\tdriver={v.get('driver')}\tname={v.get('displayName', '-')}\tenabled={v.get('enabled')}")
db = home / "statev2.sqlite"
print("== 历史会话用过的模型串（--model 原样使用，含引号与方括号）")
if not db.exists():
    print("（无 statev2.sqlite）"); sys.exit(0)
try:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute(
        "select json_extract(payload_json,'$.modelSelection.instanceId') i,"
        " json_extract(payload_json,'$.modelSelection.model') m, count(*)"
        " from orchestration_v2_projection_threads group by i, m order by i").fetchall()
except sqlite3.Error as e:
    print(f"（读取失败：{e}。T3 版本变化可能改了表结构）"); sys.exit(0)
if not rows:
    print("（暂无。先在 T3 界面用该 provider 开一个会话，再重跑本脚本）")
for i, m, n in rows:
    if i:
        print(f"{i}\t{m}\t({n} 个会话)")
PY
