---
name: weicoz-dsh-repos-update-check
description: >
  只读检查 DeepSeek Harness (DSH) 本体、xiaobright/dsh-anchored-standard、
  yjh051108/dsh-routing-suite 的更新与本机实装差异；用户要求时审计已装 DSH 插件的兼容和可用性。
  适用于“DSH/这两个仓库有没有更新”“所有插件兼容吗/能用吗”。不负责自动升级或同步。
---

# DSH 更新与插件审计

## 更新检查

运行 `bash /Users/weicoz/.agents/skills/weicoz-dsh-repos-update-check/scripts/check_updates.sh`。
脚本从 npm 发布标签核对当前 `dsh --version`，fetch 两个仓库的远端引用，并逐文件对比已装预设及
routing-suite 的 injector 链接。默认使用 `~/File/git/dsh-anchored-standard` 和
`~/File/git/dsh-routing-suite` 作为对比 clone；可用 `DSH_REPOS_XIAOBRIGHT`、
`DSH_REPOS_ROUTING`、`DSH_INSTALLED_ANCHORED` 覆盖路径。

- 🟢 实装与上游一致；🔴 版本更新或实装不一致，需评估同步；⚪ 无法核实。
- clone 的 HEAD 落后只说明对比镜像落后；信号灯以实装核对为准。
- 对 🔴 项，用 `git diff --name-status HEAD..origin/HEAD` 分清功能代码、预设、文档；
  再看实装文件是否是用户有意改动。文件不一致不自动等于应该覆盖。
- 上游删除插件时，只统计当前 `package.json`/`node_modules` 的真实引用；忽略备份、日志、disabled 残留。
- 报告 DSH 当前/发布版本，两个仓库 local/remote SHA、新提交、变化路径、实装差异与影响。

## 插件兼容与可用性审计（用户要求时）

范围以本机 DSH 各 profile 的 `package.json` 直接依赖、有效配置及运行时注入插件为准；
官方内置插件可汇总，第三方插件逐项列出。先查 `dsh --version`、Node 版本、
`pnpm -C ~/.dsh/profiles/<profile> ls --depth 0` 和插件自身 `package.json` 的 `engines`、
`peerDependencies`、实际包路径。GitHub 套装根目录可以没有 `package.json`，不能仅凭此报安装失败。

对每个可用 profile 运行 `dsh --profile <profile> --dump-config`，只提取插件名称、启停状态和错误；
不要回显含密钥的完整配置。Desktop 若由 Electron 独占，标明 CLI 无法检查。区分：

1. **安装**：包和 link 存在，依赖没有明显缺失或版本冲突。
2. **装载**：有效配置启用，运行时插件列表无跳过/报错；主动 disabled 的插件标“未启用”，不判“正常使用”。
3. **功能**：只对已启用插件走安全的实际用户路径，查看结果、console/network/进程日志；
   不能用 `dump-config`、HTTP 200 或启动成功代替功能验收。需要发送、付费、外部写入的功能只检查到授权边界。

逐项输出“已验证可用 / 装载正常但功能未验 / 已禁用 / 不兼容或失败 / 无法判断”，
注明 DSH 版本、证据和失败信息。评估新版 DSH 时，当前版本可用不代表新版兼容；
若未安装新版，标“升级后未验证”。仅检查时不安装、重启、启用或卸载插件。

## 只读边界

不 checkout/reset/pull/clean，不改 `~/.dsh`，不升级 DSH，不重启服务。
`git fetch` 只更新对比 clone 的远端引用；脚本本身只读实装。
用户明确要求修复或升级时，按其授权另行处理，先保留原有配置与运行态证据。
