# 实现与验收边界

本文件记录当前 1.1.0 的实现和验证；不作为商业原版效果等同证明。1.0.0 独立版存在 Free 能力退化，现以完整 Free 0.23.9 为底座，复查修复见 [Free 基线复查](free-audit.md)。验证日期 2026-10-22。

## 能力覆盖

| 能力 | 实现位置 | 验证类型 |
| --- | --- | --- |
| 品类研究、视觉方向、首屏骨架、对比选择 | free/workflow.md、free/design-direction.md、build_explorer.py | 完整基线保留；原有对比页 57 项回归，1 项 Windows 专用跳过 |
| 层级、字体、色彩、空间与素材 | visual.md、studio.css | 规范审查；真实页面截图 |
| 素材检索、联系表、许可与来源 | free/media.md、curate-media.mjs、studio.py sheet | 原有素材回归 20 项通过；真实检索和 PBR 三张 1K 贴图通过 |
| 动效、滚动叙事、减少动态效果 | motion.md、effects.html/js/css | 可见浏览器任务；桌面/手机截图 |
| 截图还原与同条件比较 | capture.py、studio.py parity | 真实截图/录屏；像素、环境、漏状态拒绝测试 |
| 小游戏输入、暂停、胜利、重置 | effects.html/js | 点击与键盘任务通过 |
| 实时 3D、WebGL、SVG 流光、点阵、流动渐变 | effects.html/js/css | WebGL 实际初始化并渲染；暂停与降级逻辑 |
| 独立评审、9 分修订目标、方向碰撞与真实任务 | review.md | 独立代理用真实请求审查并发现缺陷；修复后回归 |
| AI 默认审美自查、精修、减法 | visual.md、components.md、review.md | 规范审查；本轮真实截图人工查看 |
| 表单、状态、弹窗、浮层、响应式 | interaction.md、interaction.html/js/css | 输入校验、失败保留、重试、取消、Escape 与焦点恢复通过 |
| 后台工作区布局与完整页面一致性 | workspace.md、workspace.html/js/css | 搜索、筛选、详情、列表、看板、表格任务通过 |
| 存量 UI 优化、流程改造、新功能 | renovation.md | 两个真实请求的独立前向审查；尚未在真实订单项目试用 |
| 单组件、19 套卡片、折展与微抽屉 | components.md、index.html、cards.js | 整馆任务通过；19 张单卡分别装配，无初始化错误 |
| 候选方向展示、选择复制、大小屏预览 | compare.html/js/css | 路径、转义、资源复制和特殊文件名单元测试；另有运行产物 |
| 完整取证与补充清单截图 | shoot.mjs 默认；capture.py 补充 | Free 取证集合已恢复，原有截图长回归结果见下；补充入口两状态与录屏已验证 |

## 检查记录

- `run_free.py --suite build`：57 项，0 失败、0 错误、1 项 Windows 专用跳过。
- `run_free.py --suite media`：20 项，0 失败、0 错误、0 跳过。
- `run_free.py --suite shoot`：102 项完整执行；初跑有 6 个方法、14 个子断言失败。色彩问题已固定 sRGB；有时限的中断/清理用例在降低并发后定向复核。6 个方法的全部原失败子断言均已定向通过；清单见 Free 基线复查报告，不把初跑写为全绿。

- `uv run --no-project --with pillow python -m unittest discover -s skills/weicoz-ui-studio/tests -p 'test_*.py' -v`：11 项通过，包含原包哈希、单入口、防退化和多个输入/失败分支。
- `python3 skills/weicoz-ui-studio/tests/run_browser.py --output <新的证据目录>`：19 原型、4 页、1440×1000 与 390×844；另由独立评审检查 320 宽度。主路径与单卡装配通过，未捕获页面脚本错误。
- `capture.py`：真实 Chrome 155.0.8059.86、DPR 1、缩放 1、减少动态效果；桌面组件局部截图与手机错误状态截图成功。录屏通过 ffprobe 解码检查。
- 仓库 `scripts/validate-skills.sh --no-links`：64 个 Skill 通过。
- `node --check` 与 `git diff --check` 用于脚本语法与补丁空白检查。
- 系统 skill-creator 的通用 quick_validate 拒绝顶层 version；本仓库规范和检查器要求顶层 version，因此保留项目格式，不把该通用检查写为通过。

独立评审发现并修复：file:// 测试入口、run-code 环境的 URL 构造、工作区选中态、历史导航、单卡初始化与特殊文件名 URL；另扩大导航与播放进度的触控区域。真实截图还发现日期和播放按钮换行、WebGL 深度问题，已修复。

## 不等同声明与剩余工作

用户要求原版效果完整一致；当前没有原版包、截图、评分口径、19 套原型目录或同任务运行结果。因此原版完整一致性未验证，整体目标不能标已完成。这里的 19 套是独立设计的功能原型，不声称是原版那 19 套。

规范文档的覆盖不等于所有未来产品的 UI 都已验收。不同模型、内容、浏览器、系统字体与数据会改变产出。严格一致性需补原版同条件基线并逐状态核对。

未接真实后台、认证、支付、权限或外部保存 API；示例使用本地数据，表单使用明确的可控保存模拟与 localStorage。未在真实手机硬件测帧率、功耗、字体文件一致性或全部浏览器。素材许可由来源声明，工具不自动替用户取得授权。

1.1.0 已经授权复用 Free 的完整代码、方法和资源，版权与锁定信息见 THIRD_PARTY.md；新增增强的需求线索来自公开差异说明：[Oil UI 开源说明](https://github.com/oil-oil/oil-ui/blob/main/README.zh-CN.md)、[Pro 说明页](https://ui.oiloil.org/pro/)。实现没有使用未取得的付费代码、文档或资产；不包含授权绕过或自动更新替换。
