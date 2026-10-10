# 添加一台机器

## 1. 本机能免密登录

```bash
ssh -o BatchMode=yes <用户>@<地址> true
```

不通就先配好 SSH 密钥。`rd` 不处理密码和交互式登录。

## 2. 写进机器清单

在 `~/.config/remote-dispatch/config.ini` 加一节，字段说明见 `assets/config.example.ini`：

```ini
[host:box2]
ssh = user@10.0.0.12
sync = direct
max_sessions = 2
max_heavy = 1
```

并发怎么定：`max_sessions` 是同时运行的任务数，`max_heavy` 是同时运行的重命令数（经 `rd-heavy` 或 `--heavy` 排队的那些）。先看项目一个测试进程占多少内存，乘以并发数，不能超过机器的空闲内存。16 GB 的机器一般是会话 2、重命令 1。

## 3. 远端装好要用的东西

- `git`。
- 要派的代理命令行，并且已经登录。登录是交互步骤，需要机器的主人自己在那台机器上完成。
- 项目自己的工具链（包管理器、运行时、Docker 等）。

非交互的 SSH 会话不读 `.zshrc`、`.bashrc`，装在用户目录下的命令往往找不到。把这些目录写进该机器的 `path`。默认已包含 `~/.local/bin`、`~/.kimi-code/bin`、`/opt/homebrew/bin`、`/usr/local/bin`。需要的环境变量（例如接口密钥）写进远端的一个文件，用 `env_file` 指过去，任务启动前会被加载。

## 4. 仓库访问（只在 `sync = origin` 时需要）

远端要能读写 `origin`。几种做法，按你对这台机器的信任程度选：

- 在远端生成 SSH 密钥，作为只对这一个仓库有写权限的部署密钥加到仓库上。权限最小，推荐。此时远端要用 SSH 地址，在项目小节里写 `origin_url = git@github.com:<所有者>/<仓库>.git`。
- 在远端登录 `gh auth login`，或配置带令牌的凭据助手。权限是整个账号的，只适合完全属于自己的机器。

不想在远端放任何仓库凭据，就用 `sync = direct`。

## 5. 项目配置

```ini
[project:myrepo]
setup = <在新 worktree 里装依赖的命令>
test = <完整测试命令>
```

小节名是 `origin` 地址的仓库名（没有 `origin` 时是目录名）。

- `setup` 在每个任务第一次启动前执行一次，失败则任务以 97 结束。新 worktree 没有依赖环境，不配这一项的话，代理第一件事就是自己摸索怎么装，既慢又不稳定。
- `test` 是 `rd run --test` 跑的命令，默认按重命令排队。不需要排队时加 `test_heavy = false`。
- `origin_url` 只在远端访问仓库的地址和本机不同时才写。

## 6. 体检

在项目目录里执行：

```bash
rd doctor box2
rd run --cmd 'git log -1 --oneline' --host box2 --name smoke
```

第二条跑通（`rd wait` 返回 0，`rd logs` 能看到提交）说明同步、启动、日志都正常。跑完 `rd clean <job> --delete-branch`。

## 远端目录结构

都在该机器的 `workdir` 下（默认 `~/remote-dispatch`），整个目录可以随时删掉重来，前提是没有未取回的任务：

```
repos/<项目>.git    裸仓库
wt/<job>/           每个任务的 worktree
jobs/<job>/         提示词、运行脚本、输出、退出码
locks/              重命令的排队锁
bin/rd-heavy        排队命令
```
