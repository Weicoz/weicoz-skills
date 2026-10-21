---
name: weicoz-wechat-save-template-deploy
version: 1.0.0
description: 按本机环境变量配置，将 wechat-save-template 完成本地预检、远端部署和会话存档入库验证。适用于 migration/build、git pull、pnpm install、pm2 restart --update-env 和 HTTP 验证。
allowed-tools: Read, Write, Edit, Bash
---

# WeChat Save Template Deploy

## 适用场景
- 你要把当前工作区和已配置的线上目标部署到远端服务器。
- 你需要先做本地预检，再执行线上拉代码、安装依赖、构建、迁移、重启和验证。
- 你这次改动涉及数据库 migration、`pm2` 环境变量刷新、或 `会话内容存档` 新接口。

## 固定环境
- 本地测试库：由 `WEICOZ_WECHAT_SAVE_LOCAL_DB_URL` 提供
- 本地 PostgreSQL 容器：`local-pgsql-root`
- 线上服务器：由 `WEICOZ_WECHAT_SAVE_SSH_TARGET` 提供
- SSH key：由 `WEICOZ_WECHAT_SAVE_SSH_KEY` 提供
- 线上目录：由 `WEICOZ_WECHAT_SAVE_REMOTE_DIR` 提供
- 线上 PM2 应用：由 `WEICOZ_WECHAT_SAVE_PM2_APP` 提供
- 线上 HTTP 端口：由 `WEICOZ_WECHAT_SAVE_REMOTE_PORT` 提供
- 线上数据库：`pgsql-root` 映射 `127.0.0.1:35432 -> 5432`

## 核心原则
1. 先本地验 migration/build，再推线上。
2. 线上不能只改 `.env.production`，必须 `pm2 restart --update-env`。
3. 线上部署默认走 `git pull`，不要再用 rsync 覆盖线上工作区。
4. 验证至少覆盖：HTTP 200、核心接口 200、数据库真实新增。

## 环境变量

执行脚本前，必须确认本机已加载 `WEICOZ_WECHAT_SAVE_*` 变量；脚本不再提供线上地址、私钥路径或数据库 URL 默认值。

## 标准流程

### 1. 本地预检
执行：

```bash
bash ~/.agents/skills/wechat-save-template-deploy/scripts/local_validate.sh
```

通过标准：
- 本地库 `wechat_save_template_local` 存在
- `pnpm db:migrate` 成功
- `pnpm build` 成功
- callback mock 验证脚本成功写入 `wecom_archive_messages`

### 2. 推送并部署线上
执行：

```bash
bash ~/.agents/skills/wechat-save-template-deploy/scripts/deploy_remote.sh
```

该脚本会：
- 在线上 `git fetch + git pull --ff-only`
- 在线上 `source .env.production`
- 跑 `pnpm install --frozen-lockfile --prod=false`
- 跑 `bash scripts/setup-wecom-sdk.sh`
- 跑 `pnpm build`
- 跑 `pnpm db:migrate`
- 跑 `pm2 restart wechat-save-template --update-env`
- 验证 `http://127.0.0.1:3210`

### 3. 验证会话存档落库
如果这次改动涉及 `/api/wecom/archive/messages`，执行：

```bash
bash ~/.agents/skills/wechat-save-template-deploy/scripts/verify_archive_ingest.sh
```

通过标准：
- `POST /api/wecom/archive/messages` 返回 `200`
- 响应里 `saved >= 1`
- 线上库 `wecom_archive_messages` 有新增测试消息

## 关键坑位
- `.env.local` 当前可能指向远端数据库，不要拿它做“本地验证”的真实依据。
- `pm2 env 0` 和 `.env.production` 可能不一致；如果不加 `--update-env`，进程会继续使用旧 `DATABASE_URL`。
- `GET` 接口可能因为 fallback 看起来没问题，但 `POST` 仍可能因为旧库地址直接 `500`。验证必须看真实写库。
- 如果新增 migration，只做 `git pull` 不够，必须在线上显式跑 `pnpm db:migrate`。
- 如果这次新增了会话存档 SDK 依赖，线上要先跑 `bash scripts/setup-wecom-sdk.sh`。
- 如果 `.env.production` 里带了 `NODE_ENV=production`，安装阶段也必须显式带 `--prod=false`，否则 build 依赖的 devDependencies 会被跳过。

## 输出协议
- Goal：这次部署目标
- Verify：本地预检和线上验证结果
- Next：下一步动作
- Blocker：如果卡住，明确卡在哪一步

## 文件
- 本地预检脚本：`scripts/local_validate.sh`
- 线上部署脚本：`scripts/deploy_remote.sh`
- 会话存档入库验证脚本：`scripts/verify_archive_ingest.sh`
