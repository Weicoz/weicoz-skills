---
name: weicoz-skill-tiers
version: 1.0.0
description: 管理 skill 三层分级与领域 Hub，减少常驻上下文的 skill 描述量：L1 常驻、L2 同名短描述桩、L3 由领域 Hub 索引按需加载。只改各 harness 发现目录的软链、生成桩与 Hub，不改原 skill 内容，Claude Code/Codex/DSH/Kimi/Grok/Antigravity 通用。用于“skill 太多占上下文”“调整 skill 分层”“新装 skill 后重新分层”“恢复 skill 分层前状态”。
---

# weicoz-skill-tiers

## 机制

- **L1 常驻**：发现目录中保留原软链，完整描述常驻。
- **L2 短描述桩**：发现目录中的同名软链改指向生成的桩。桩只含短描述，正文要求先读原 SKILL.md。仍可自动触发和 `/name` 调用。
- **L3 Hub 收纳**：从发现目录移除软链。领域 Hub（`weicoz-hub-*`）的索引表列出该 skill 的用途与 SKILL.md 路径，按需读取。
- manifest 未列出的 skill 保持原样，不受影响。

原 skill 目录不改动。工具不删除任何 skill 源，只增删软链；每次 apply 前写快照。

## 目录

数据根目录默认 `~/.agents/skill-tiers/`，可用环境变量 `SKILL_TIERS_HOME` 覆盖：

| 路径 | 用途 |
| --- | --- |
| `manifest.json` | 分层定义（用户维护） |
| `library/<name>` | 指向原 skill 的稳定软链，供桩与 Hub 引用；不在任何 harness 的扫描范围内 |
| `generated/<name>` | 生成的桩与 Hub |
| `backups/baseline.json` | 首次 apply 前的原始状态，之后不再覆盖；`restore` 它即完全撤销分层 |
| `backups/snapshot-*.json` | 每次 apply 前的发现目录软链快照 |
| `installed.json` | 各发现目录原本安装过的 skill，用于调层后按原范围恢复 |

manifest 格式见 [references/manifest.example.json](references/manifest.example.json)。`discovery_dirs` 省略时使用脚本内置的默认列表。

## 操作

```bash
T="<skill_dir>/scripts/skill_tiers.py"
python3 "$T" status            # 分层状态、各目录描述体量、漂移、未分层清单
python3 "$T" plan              # 预演，不改动
python3 "$T" apply             # 写快照 → 建 library → 生成桩与 Hub → 改链
python3 "$T" restore <快照路径> [--dry-run]   # 精确恢复到快照时的软链
```

## 维护规则

1. 改 manifest 后先 `plan` 核对动作数，再 `apply`。
2. 新装 skill 默认不分层；`status` 列出未分层项，按需写入 manifest 后再 `apply`。
3. 安装器或同步工具重建软链后，`status` 会报告漂移；重新 `apply` 即可。
4. 依赖 `context: fork`、`allowed-tools` 等 frontmatter 的 skill 必须放 L1，桩和 Hub 读取方式下这些字段不生效。
5. 名称在 L1、L2、Hub 中只能出现一次，脚本会校验。
6. 发现目录中的真实目录（非软链）一律不处理。
