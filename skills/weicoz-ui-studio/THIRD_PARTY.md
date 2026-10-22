# 第三方许可与基线

本 Skill 1.1.0 在 Oil UI Free 0.23.9 的 MIT 开源版基础上二次开发。官方包 SHA-256：`66b97458ef31fc5ec363cdfcf6a9f2b5e3beca17998d0fdd04fde47bf0eff3a1`。完整原包文件和逐文件摘要见 `upstream/oil-ui/`、`upstream.lock.json`。

上游 SKILL.md 原字节存为 ENTRYPOINT.source.md，锁文件 archive_paths 记录映射，防止宿主递归发现第二个自动入口；其余原包路径不变。

- 来源：[oil-oil/oil-ui](https://github.com/oil-oil/oil-ui)，发布地址见锁文件。
- 原始 MIT 版权和许可完整保留在 `upstream/oil-ui/LICENSE`。
- 三个继承工具 build_explorer、shoot、curate-media、完整 explorer 模板、logo、`references/free/` 源于基线；原始标记和出处保留，不声称为原创。修改见复查报告。
- `assets/vendor/alpine.min.js` 为上游附带 Alpine.js 3.17.4 发行件；对应官方标签的完整 MIT 版权与许可另保留于 `assets/vendor/ALPINE-LICENSE.md`。
- Instrument Serif 字体和 SIL Open Font License 见 `assets/fonts/instrument-serif/OFL.txt`。
- 新增组件、示例、工具与说明采用本目录 LICENSE。未取得、未分发 Pro 付费代码或私有文档。

上游品牌、推广、购买和更新服务不代表本项目提供或代办。原包仅为源码溯源和回归，不自动执行其 Skill 入口。
