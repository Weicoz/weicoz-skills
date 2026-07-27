# weicoz skills

个人维护的 Codex skills 集合。

## 目录约定

- 每个 skill 独立放在 `skills/<skill-name>/`。
- 每个 skill 必须包含 `SKILL.md`，frontmatter 的 `name` 必须与目录名一致。
- 凭据只从环境变量读取，不提交真实值。
- 本机私有变量放在 `~/.zshrc`；变量名示例见 `.env.example`。

## 校验

```bash
./scripts/validate-skills.sh
```

运行环境使用 `$WEICOZ_SKILLS_ROOT` 作为安装根；本仓库作为源码真源，由 Skills Manager 按 `skills/<skill-name>` 子路径管理。
