# Free 基线复查

版本：1.1.0。日期：2026-10-22。结论分为能力继承、运行验证、质量目标和原版效果一致性。

## 原版 1.0.0 的退化与修复

| 范围 | 原有缺口 | 当前修复 |
| --- | --- | --- |
| 方向与视觉方法 | 短摘要遗漏调性刻度、生成引擎、色彩推导、完整方向卡、差异盲看 | 默认读取 references/free 的完整方法，短文档只作增强 |
| 真实素材 | 只有手工素材清单与图片联系表 | 默认 curate-media.mjs 多信源搜索、编号缓存、用途与许可、look、预览和下载 |
| PBR 与视频 | 依赖项目另找工具 | 恢复完整贴图/MD5、视频下载、poster、SOURCES 与解码校验 |
| 对比页 | 简版 name/path/url/note | 默认 build_explorer.py：方向字段、baseline、nativeViewport、interactive、轮次、离线内嵌、单张和实际尺寸 |
| 截图取证 | capture.py 仅截图与脚本错误 | 默认 shoot.mjs：遮字、并排、2x、动作组、动效、录屏、序列帧、对比热图、控制台/图片/溢出/可读性检查 |
| 评审 | 泛化七维，缺具体评分门槛 | 完整手册保留三秒遮字、真实标杆、锚线、密度、构图节奏、评分锚点与保留项，再加任务闭环 |
| 动效与游玩 | 摘要遗漏弹簧、共享元素、滚动分镜、倒放/跳中段等 | 对应任务默认读取 Free 完整章节，再加场景、状态和失败恢复 |
| 内置资源 | 缺完整模板、Alpine、字体及许可 | 完整随运行层保留，并逐文件比对 |

不能把“新增 19 套组件”当作原版方法与工具的替代。旧的 studio.py compare/sheet 和 capture.py 保留兼容，不再承担默认完整流程。

## 基线与修改范围

- 官方发布包：Oil UI Free 0.23.9，SHA-256 `66b97458ef31fc5ec363cdfcf6a9f2b5e3beca17998d0fdd04fde47bf0eff3a1`。
- 39 个原包文件完整保留并逐文件锁定。上游入口仅改名为 ENTRYPOINT.source.md，原字节不变，锁文件记录路径映射；防止递归发现成第二个 Skill。
- build_explorer.py、运行模板、Alpine、字体和 Free 参考文档保留原字节。原始 MIT 与 OFL 见 THIRD_PARTY.md。
- shoot.mjs 增加可见窗口默认、显式 --headless、完整评审交接路径；临时浏览器固定 sRGB，避免 Mac 广色域屏把原色转成不同截图像素。取证逻辑不删减。
- curate-media.mjs 增加可选 origin 环境覆盖，未配置时保持公开端点和原有行为；不加 LLM 调用或付费服务。
- 上游完整设计流程移除推广、购买和自动更新提示，再与增强入口整合；不执行原始上游 Skill 入口。

## 验证方式

```sh
uv run --no-project --with pillow python -m unittest discover -s skills/weicoz-ui-studio/tests -p 'test_*.py' -v
python3 skills/weicoz-ui-studio/tests/run_free.py --suite build
python3 skills/weicoz-ui-studio/tests/run_free.py --suite media
python3 skills/weicoz-ui-studio/tests/run_free.py --suite shoot
```

Free 的原有测试直接指向当前运行层。对比页浏览器探针用可见 Playwright 执行相同 DOM 查询与原始断言，保留减少动态效果条件；只替换原 headless pipe 启动层，不删断言、不降低尺寸或像素容差。Windows 专用测试在 macOS 跳过；最终结果见实现状态记录。

已验证真实 Poly Haven 检索与一套 1K Diffuse/Roughness/Normal 下载，三张均 full-decode、无错误，生成联系表与来源。真实科学素材检索返回 Wellcome 结果，NASA 当次 fetch failed，不能写成所有公开服务均可用。视频/poster 与异常处理由本地真实 HTTP、文件和 FFmpeg 回归覆盖，不冒充 NASA 视频在线下载成功。

## 实际回归结果

- 本地防退化与原有增强自测：11 项通过。
- 完整对比页：57 项，0 失败、0 错误；1 项 Windows 专用测试在 macOS 跳过。
- 素材：20 项，0 失败、0 错误、0 跳过。
- 截图：102 项完整执行。初跑 6 个方法、14 个子断言失败；其中局部裁切、批量拼图和短反馈颜色受 Mac 广色域影响，已固定 sRGB。浏览器/编码中断用例在高并发下超出原有 10 秒断言，单独复核已通过，未修改时间断言。
- 对比页初版测试适配的 pipe 启动、减少动态效果和 DOM 查询差异已修正；保留全部原始断言后的最终对比页回归通过。

截图失败方法的逐项复核：

| 原方法 | 修复与复核 |
| --- | --- |
| browser_disconnect_interrupts_steps_and_cleans_frames | 低并发定向通过，6.783 秒 |
| disconnect_during_encoding_exits_without_waiting_for_encoder | 低并发定向通过，6.045 秒 |
| selector_crops_first_visible_element_and_scrolls | sRGB 后三组原断言通过，11.958 秒 |
| multi_target_shared_server_browser_and_auto_sheet | sRGB 后原断言通过，11.816 秒 |
| mark_accepts_explicit_numbers | sRGB 后原断言通过，13.474 秒 |
| record_frames_follow_last_action_and_capture_short_feedback | sRGB 后七种动作的原断言通过，43.517 秒 |

6 个原失败方法现均定向通过，覆盖原 14 个失败子断言。这不是“102 项初跑一次全绿”。未降低像素和时间断言，未用跳过短反馈测试掩盖差异。

整合走查：使用默认 shoot 对本地交互示例的 ready/error 两状态生成普通、遮字及两种并排图，无控制台错误、横向溢出或失败图片。有 1 类非阻塞的眉标提示；示例馆用于状态章节讲解而保留，不据此宣称视觉评分达到 9 分。

## 增强与仍需证据的目标

保留交互/表单/弹窗/响应式、后台布局、存量改造、19 套可运行卡片、折展/微抽屉、SVG/点阵/渐变/WebGL、真实任务走查、≥9 分修订目标与严格参考一致性检查。

Pro 的公开功能类别已有实现入口。私有原型清单、原始规范、同任务输出与评分基线未取得；现有 19 套为独立原型，不声称等于原版那 19 套。真实项目效果仍按完整手册与任务验收，原版效果完全一致仍未验证。

来源：[Free 开源功能与 Pro 公开差异](https://github.com/oil-oil/oil-ui/blob/main/README.zh-CN.md)、upstream.lock.json、upstream/oil-ui/ENTRYPOINT.source.md、各命令实际回执。
