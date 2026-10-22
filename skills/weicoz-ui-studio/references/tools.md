# 工具与运行

## 默认完整能力

先用 [完整继承工具](free/tools.md)：`build_explorer.py` 生成完整对比页，`curate-media.mjs` 完成多信源搜索/预览/下载与 PBR/视频，`shoot.mjs` 完成默认取证。下面的 studio.py 和 capture.py 是兼容或补充入口，不能替代完整方法。

截图默认可见窗口，所有 Free 取证选项保留；仅用户明确要求时使用 `--headless`。评审和交付用 `shoot.mjs --evidence`，包含遮字、并排、2 倍图、动效探测和录屏；精确动作清单或宿主浏览器场景再用 capture.py 补充。录屏需要 ffmpeg，缺少时按真实输出标未完成。

素材服务可通过可选 `UI_STUDIO_MEDIA_ORIGINS` JSON 对象覆盖 origin，未配置时保持原有公开端点。可用 `CHROME_PATH` 指定本机浏览器。变量示例在主仓库 `.env.example`；无需 LLM API 凭据。

## 兼容与补充工具

Python 3.10+；组件馆无构建、无网络依赖，直接打开 HTML。`studio.py` 不调用模型、登录服务或外部 API。

```sh
python3 <skill>/scripts/studio.py gallery --output <新目录>
python3 <skill>/scripts/studio.py compare <候选清单.json> --output <新目录>
python3 <skill>/scripts/studio.py sheet <素材清单.json> --output <新目录>
python3 <skill>/scripts/studio.py review --output <新账本.json>
python3 <skill>/scripts/studio.py parity <一致性清单.json> --output <新报告.json>
```

同名输出默认拒绝覆盖；`--force` 允许替换本工具管理的输出。组件馆导出到新目录，后续自行编辑；`gallery` 不替换既有目录，即使传了 `--force`。

## 轻量兼容对比页

新的多方向任务默认用 build_explorer.py，支持完整方向字段、baseline、nativeViewport、interactive、离线资源内嵌、轮次与实际尺寸。以下仅说明旧版 studio.py compare 的兼容输入。

清单相对路径以清单所在目录为根。每个候选使用独立 HTML、图片或 HTTP(S) 页面；本地 HTML 资源目录整体复制，目录与清单同级或在其下。避免把含凭据、仓库根或无关用户数据的目录作为素材树。输出目录必须在这些候选树之外。

```json
{"title":"课程预约方向","candidates":[
  {"name":"安静阅读","path":"quiet/index.html","note":"内容先行、衬线标题、纸面色"},
  {"name":"现场海报","path":"poster/index.html","note":"大图与窄字，行动贴近内容"},
  {"name":"精准工具","url":"https://example.com/demo","note":"直接展示可操作内容"}
]}
```

对比页有桌面/手机预览、方向键翻页、全尺寸入口、选择及复制反馈。外部页面受其 CSP/X-Frame-Options 限制时用全尺寸入口，不能把空白 iframe 当成成功渲染。

## 截图、交互与录屏

优先使用宿主当前浏览器；本地确定性回归使用已装 `playwright-cli`，默认可见窗口。

```sh
playwright-cli -s=ui-studio open <页面http地址> --headed
playwright-cli -s=ui-studio resize 1440 1000
playwright-cli -s=ui-studio screenshot --filename=<证据目录>/desktop.png
playwright-cli -s=ui-studio resize 390 844
playwright-cli -s=ui-studio screenshot --filename=<证据目录>/mobile.png
playwright-cli -s=ui-studio video-start <证据目录>/walkthrough.webm
playwright-cli -s=ui-studio video-stop
playwright-cli -s=ui-studio close
```

工具语法先核对当前 `--help`。不要关闭用户已有窗口；只清理本次测试会话。动作、局部截图、DOM 读取、状态切换、逐帧测量由 run-code 实现；示例测试在 `tests/browser.js`。普通浏览器可以直接打开 HTML；当前 playwright-cli 阻止 file:// 时，通过一次性测试服务运行：

```sh
python3 <skill>/tests/run_browser.py --output <新的证据目录>
```

运行器使用回环地址和系统分配端口，仅在本次测试期间提供组件馆，结束自动关闭；浏览器可见。无须新建常驻服务。

截图时等待字体和关键图片，记录 CSS 视口、DPR、浏览器版本、缩放与动态效果。需要逐帧比较时保存具体时间点，不把视频截图和终态 PNG 混比。状态可用真实操作进入；测试参数只能用于确定性范例，不绕开产品权限。

## 按状态清单截图与录屏

```sh
python3 <skill>/scripts/capture.py <截图清单.json> --output <新证据目录>
python3 <skill>/scripts/capture.py <截图清单.json> --output <新证据目录> --record
```

使用当前安装的 playwright-cli。录屏额外需要该 Playwright 版本的 FFmpeg 运行件；缺少时会报错，不冒充已录制。每次创建独立可见会话；本地文件通过临时回环服务，结束关闭。清单与截图留在本机。

```json
{"root":"./site","cases":[
  {"id":"desktop-idle","path":"index.html","viewport":{"width":1440,"height":1000}},
  {"id":"mobile-error","url":"https://example.com/demo","viewport":{"width":390,"height":844},"selector":".form","actions":[
    {"type":"fill","selector":"#email","value":"reader@example.com"},
    {"type":"click","selector":"button[type=submit]"},
    {"type":"wait","ms":300}
  ]}
]}
```

动作还支持 select（selector/value）、press（key）、scroll（x/y）、drag（selector/to）。`mark` 数组可标出选择器区域和编号。每项可用 `selector` 局部截图、`full_page:false` 只截视口、`reduced_motion:false` 保留动态效果。默认减少动态效果，环境写入 capture.json。记录的字体上下文为 FontFace 列表与测量样本，不等同所有操作系统字体文件的哈希；严格跨机一致性还需核实字体文件。

## 素材联系表与来源

先用宿主搜索/图片能力找真实来源，再把选定素材写进清单。`sheet` 解码图片、校正 EXIF 方向、保留透明度、输出编号 PNG 和联系表；远端每项最多 20 MB。Pillow 按需使用，不需要 API 凭据。

```json
{"sources":[
  {"title":"局部材质","path":"assets/texture.png","source_url":"原始来源页","license":"CC0","usage":"page"},
  {"title":"版式参考","url":"https://example.com/reference.jpg","source_url":"https://example.com/","license":"unknown","usage":"reference"}
]}
```

`usage` 是 page/check/reference；未知许可不能声明 page。SOURCES.md 保留来源、许可、用途与原尺寸；声明不能替代真实许可核对。视频、PBR 多通道贴图与生成图片沿项目现有工具处理，按视觉素材文档核对后归档。

## 一致性清单

每个图像路径相对清单目录，环境字段两边都填真实值。`scope` 声明是否为自回归或经授权参考；所有 expected_states 必须恰好有一项，且任务结果均为 true。

```json
{
  "scope":"self-regression",
  "reference_source":"自己的上一版，不能证明第三方原版一致",
  "expected_states":["desktop-idle","mobile-error"],
  "cases":[{
    "id":"desktop-idle","reference":"baseline/desktop.png","candidate":"current/desktop.png",
    "reference_environment":{"browser":"实际版本","os":"实际系统","fonts":"字体指纹","dpr":1,"zoom":1,"reduced_motion":true},
    "candidate_environment":{"browser":"实际版本","os":"实际系统","fonts":"字体指纹","dpr":1,"zoom":1,"reduced_motion":true},
    "reference_task_passed":true,"candidate_task_passed":true
  }]
}
```

图像对比需 Pillow，可用已有 Python 环境或 `uv run --with pillow ...`；无需写入全局解释器。不同参考来源分别建清单。报告非零退出表示未通过，不能把命令运行成功当一致性通过。
