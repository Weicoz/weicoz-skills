# 自测样片：A1 字雨

本目录不是原作者素材，是本 skill 按 `references/RENDER.md` 跑通流程的产物，留作模板参考。

- 风格：A1 字雨（`references/library/风格提示词/A-G_代码样片/A1_字雨.md`）
- 做法：粘贴 `_公共函数.js` 与 A1 的参考实现，补上 `PARENT` 文案与 `SERIF` 字体栈，套用 `RENDER.md` §3 的确定性外壳
- 参数：6 秒 / 1920×1080 / 30fps / 无音轨
- 已验证：`?t=` 定格正常；同一 t 两次截图哈希一致；`render_mp4.sh` 出片 180 帧、6.000s、H.264

复现：

```bash
./scripts/shot.sh references/examples/自测样片_A1字雨/index.html 2.0 /tmp/a.png
./scripts/render_mp4.sh references/examples/自测样片_A1字雨/index.html /tmp/out.mp4 6 30 1920 1080 6
```
