---
name: weicoz-pinky-phone
version: 1.0.0
description: >
  用 Pinky 操作真实手机（Android / iPhone）：打开 App、点按、输入、读屏、截图排障、
  转账前填单；经 Magpie MCP hub 调用 pinky__* 工具。适用于“用 Pinky 操作手机”
  “打开某个 App”“帮我在手机上点”“读一下手机屏幕”“转账填单”等场景。
  不负责安装 Pinky、配 adb 或 EasyTier；支付提交、密码、验证码、Key宝由用户完成。
whenToUse: 用户要求用 Pinky 或手机自动化操作 App，或需要读手机屏幕、截图、填表、导航到某个页面时。
---

# Pinky 手机操作

入口脚本 `scripts/pinky_call.py`，只用 Python 标准库。不要手写 curl 和 session 头。

```bash
python3 scripts/pinky_call.py doctor
python3 scripts/pinky_call.py pick
python3 scripts/pinky_call.py connect "打开农行并准备转账"
python3 scripts/pinky_call.py call phone_connect '{"task":"打开农行并准备转账"}'
python3 scripts/pinky_call.py call phone_launch '{"app":"com.android.corpormbank"}'
python3 scripts/pinky_call.py call phone_observe '{}'
python3 scripts/pinky_call.py call phone_release '{}'
```

`call` 默认只打印屏幕文本。加 `--wait-approval` 自动处理 `approval_pending`。

## 通道选择

新建任务优先用 `connect`：它先选路，再调用 `phone_connect`。顺序是
USB → 同网 Wi-Fi → EasyTier。内网 IP 从手机 `wlan0` 实时读取；只有 Mac 到该地址的
路由不是 `utun`、且 `ro.serialno` 匹配时才使用。不要写死内网 IP。

每次新建任务调用一次，进程处理完即退出，不常驻。已有任务继续用 `call`，
不要在中途切换通道，避免 lease 断开。`pick` 只做选路并打印结果，便于诊断。

## 标准循环

1. 预检：`doctor` 必须退出码 0。它检查 hub、pinky 工具、adb 在线设备、前台 App、金融类包名。
2. 连接：`connect "<任务名>"` 带一句任务名，用户会在 Pinky 里看到。首次连接可能返回
   `approval_pending`，用 `--wait-approval` 重试。
3. 打开：`phone_launch` 用包名，不要靠 `phone_apps` 猜。金融类 App 默认被隐藏，
   且启动会要求用户批准。
4. 读屏：动作本身返回新屏幕；需要等待或截图时用 `phone_observe`。
5. 释放：任务结束调用 `phone_release`。完成判据是手机已释放。

## 审批与接管

- 任何动作都可能返回 `approval_pending` 和 `approval_id`。用同一参数加 `approval_id`
  重试，不要改参数。
- `phone_handoff` 阻塞 45 秒后返回 `approval_pending`，审批窗口约 14 分钟。
- 返回 `user_took_over`、`paused` 时先 `phone_handoff`，不要重试原动作。
- `lease_held` 表示另一会话占着手机。先释放自己的旧任务，或请用户在 Pinky 里结束它。

## 副屏与主屏

- 默认在手机的 background display 上操作：起始为空，没有桌面，只能 `phone_launch`。
- 报 `observing a virtual display needs the companion app` 时，重连并加 `"own_screen": true`。
- 用户刚用过手机时任务会 `paused`，需 `phone_handoff`。
- 银行类 App 需要主屏时，用 `own_screen: true` 重连；表单可能因 App 退到后台而清空。

## 输入与键盘

- 金额、密码类安全键盘：`phone_type` 会拒绝按钮字段。先按坐标点中输入区，再逐个点数字 ref。
- 聚焦后布局会重排，旧 ref 可能 `not_found`。此时直接 `phone_type '{"text":"..."}'`
  不带 ref，输入到当前焦点。
- BACK 可能退出整个录入页并丢表单。要收起键盘，优先把表单向上滑，让提交按钮露出键盘区域。

## 转账与支付边界

- 可以填收款人、账号、金额、用途，并逐项核对户名和账号。
- `提交`、`确认` 只在用户明确要求点击时才点；Pinky 的审批卡就是用户的确认。
- 密码、短信验证码、2FA、Key宝 PIN 一律不代输；到这些页面就 `phone_handoff`。
- 完成后重开 App 查“转账记录”或“交易查询”，核对金额、收款人、状态。
  读不到成功页就向用户要回单，并明确标“未验证”。

## 读屏兜底

- `no UI hierarchy in uiautomator output` 时改用截图：
  `adb -s <serial> exec-out screencap -p > /tmp/pinky.png`，再读图。
- 确认前台：`adb -s <serial> shell dumpsys window | grep mCurrentFocus`。
- 安全页、成功页可能读不到也截不到，不要反复重试，直接交接给用户。

## 故障表

| 现象 | 处理 |
| --- | --- |
| `No installed app matches` | 包名错。`pm list packages -3 \| rg -i 'bank\|pay'` 找真实包名 |
| `phone_apps` 不显示银行 | 正常，金融类默认隐藏；直接用包名 launch |
| `blocked_by_policy` | 让用户在 Pinky 里允许，或 `phone_handoff`；不得绕过 |
| `lease_held` | 释放自己的旧任务，或请用户结束其他会话 |
| `device_needs_setup` | `phone_handoff`，让用户完成信任电脑/无线调试 |
| `device_offline` | 先 `pick` 重新选路；仍失败则重启 adb server 后重试 |
| `No route to host` | 内网 Wi-Fi 路由或 adb server 缓存失效；`pick` 会回退 EasyTier |
| `invalid_argument` 且提到 ref | ref 必须是整数，不是字符串 |
| ref `not_found` | 页面已重排，先 `phone_observe` 取新 ref |
| `approval_pending` | 同参数加 `approval_id` 重试，或用 `--wait-approval` |

## 环境变量

- `MAGPIE_HUB_URL`：默认 `http://127.0.0.1:3425/mcp/magpie/hub/codex`。
- `PINKY_ADB`：默认 `/Applications/Pinky.app/Contents/Helpers/adb`。
- `PINKY_EASYTIER_ADB`：EasyTier 回退地址，默认 `10.144.144.10:5555`。
  这是 EasyTier 虚拟地址，不随物理网段变化；内网地址不配置。
