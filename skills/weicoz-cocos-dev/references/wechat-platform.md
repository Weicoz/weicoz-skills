# 微信小游戏平台接入

所有 `wx.*` 调用只写在 `assets/scripts/platform/` 里，对外暴露与平台无关的接口（`save/load`、`share`、`showRewarded`）。web-mobile 预览时用同名空实现，让灰盒与试玩脚本不依赖微信。

数值取自微信官方文档（2026-04 版，2026-11 核对）。上线前重新核对，标“未确认”的项不得当成硬规则。

## 判断是否在微信里

```ts
import { WECHAT } from 'cc/env'
const wx = WECHAT ? (globalThis as any).wx : undefined
```

## 存档

- `wx.setStorageSync` / `wx.getStorageSync`：单个 key ≤ 1 MB，总量 ≤ 10 MB。web-mobile 用 `localStorage` 实现同一接口。
- 启动时集中做大量同步读写会拖慢启动：开局读一次存档到内存，变化时节流写回（如关卡结束、切后台 `Game.EVENT_HIDE`）。
- 存档写入带版本号（`{ v: 1, ... }`），读取时迁移旧版本；读不出时回到新档，不抛错。
- 文件系统（`wx.getFileSystemManager`）的本地缓存与用户文件合计 ≤ 200 MB，一般小游戏不需要。

## 分享

- 右上角“转发”默认不可点：启动时调用 `wx.showShareMenu({ menus: ['shareAppMessage', 'shareTimeline'] })`（`shareTimeline` 仅 Android Beta）。
- `wx.onShareAppMessage(() => ({ title, imageUrl, query }))` 设置右上角转发内容；游戏内按钮用 `wx.shareAppMessage({ title, imageUrl, query })`。图片比例 5:4。
- 官方接口没有分享成功回调。不要按“分享成功”发奖励；奖励改用激励视频，或只按“点了分享”给不影响平衡的小奖励。
- 通过 `query` 带关卡号等参数，启动时用 `wx.getLaunchOptionsSync().query` 读取。

## 广告

- 开通流量主才能拉到广告。条件任一：UV > 500 且无刷粉与严重违规；开通游戏圈并有有效活跃且官方帖 5 篇；同主体已有小程序持续一个季度变现。开通前所有广告接口走空实现。
- 激励视频 `wx.createRewardedVideoAd({ adUnitId })` 是全局单例：开局创建一次，之后复用。
  - `onClose(res)` 里 `res.isEnded === true` 才发奖励（看完才算）。
  - `onError` 后用 `load()` 重拉；失败时按钮置灰或给替代路径，不卡住流程。
  - 每日观看次数有限（官方未给数值）。
- 插屏 `wx.createInterstitialAd`：每次调用新建实例；频率受限时 `show()` 返回 rejected Promise，捕获后跳过。只放在关卡间等自然停顿处。
- Banner 自基础库 3.5.5 起停止维护，用原生模板广告 `wx.createCustomAd`，刷新间隔 ≥ 30 秒。
- 广告播放期间暂停计时与音频，与切后台走同一套暂停逻辑。

## 隐私

- 用到个人信息相关接口时（用户信息、位置、录音、相机、写相册、剪贴板、加速度/陀螺仪、好友关系链与云存储等），必须在 MP 后台填写《用户隐私保护指引》，并做隐私授权：后台开启“隐私授权弹窗”，或自定义弹窗。
- 自定义弹窗：`wx.onNeedPrivacyAuthorization((resolve) => ...)`，用户点击后 `resolve({ event: 'agree' })` 或 `'disagree'`；`wx.openPrivacyContract` 打开协议。
- 完全不处理个人信息：后台确认“承诺未处理”即可。
- `__usePrivacyCheck__` 是否适用于小游戏：未确认。

## 性能

- 官方性能评分分启动、运行、网络三类。总启动耗时：优秀 1800 ms，建议 2200 ms，达标 2750 ms。内存、帧率阈值表：未确认。
- 降启动耗时：裁掉未用引擎模块（`weicoz-cocos-run` 的 `cocos-modules.mjs`），主包只留首屏，后续关卡放分包。
- 真机检查：微信开发者工具“真机调试”扫码；构建勾选输出 source map，线上报错看 MP 后台“WE 分析 → 性能质量 → JS 分析”。

## 上线前检查

由用户在 MP 后台和开发者工具里操作，代理只整理清单与材料：

| 项 | 要求 |
| --- | --- |
| 主体与类目 | 个人主体可以发布，但不支持文化互动、角色、牌类类目。二级类目必须与实际玩法一致，否则驳回。 |
| 版号 / 软著 | 只靠广告变现（IAA）不要求版号；名称含英文或“软件”字样、或涉及品牌与公众人物合作时要软著。开虚拟支付（IAP）必须有版号与软著。 |
| 备案 | 完成小程序备案；IAA 小游戏另有“小游戏备案”前置环节（细则未确认）。 |
| 适龄提示 | 必须设置；审核通过后平台在启动页展示。 |
| 防沉迷与实名 | 开虚拟支付才需自行接入；不开时由平台统一处理。 |
| 隐私 | 见上文“隐私”。 |
| 包体 | 主包 ≤ 4 MB，主包加分包 ≤ 30 MB，以 `--release` 构建为准。 |
| 回归 | `weicoz-cocos-run` 第 4 节的发版回归清单全部通过。 |

来源：developers.weixin.qq.com 小游戏开发指南（分包、存储、隐私、分享、广告、性能评分、类目与资质）。
