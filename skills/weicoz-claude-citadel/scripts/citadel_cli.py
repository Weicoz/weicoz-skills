#!/usr/bin/env python3
"""Claude Citadel 配置与同步 CLI 工具。

支持安全从剪贴板 (pbpaste) 或环境变量读取机场订阅与 Claude 节点，
生成/更新 profile.yaml 并一键编译发布到 6 大主流代理客户端。
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import yaml

DEFAULT_REPO_DIR = Path("/Users/weicoz/File/git/claude-citadel")


def get_clipboard_text():
    """安全读取 macOS 剪贴板内容，避免将凭据作为命令行参数留下 shell 历史记录。"""
    try:
        res = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception as e:
        print(f"[ERROR] 无法从剪贴板读取数据: {e}")
        return ""


def parse_proxy_url(proxy_url):
    """解析代理 URL (socks5://user:pass@host:port, ss://..., vmess://..., http://...)。"""
    parsed = urllib.parse.urlparse(proxy_url.strip())
    scheme = parsed.scheme.lower()

    if scheme in ["socks5", "socks", "http", "https"]:
        node = {
            "name": "Claude专用出口",
            "type": "socks5" if "socks" in scheme else "http",
            "server": parsed.hostname or "127.0.0.1",
            "port": parsed.port or (1080 if "socks" in scheme else 8080)
        }
        if parsed.username:
            node["username"] = urllib.parse.unquote(parsed.username)
        if parsed.password:
            node["password"] = urllib.parse.unquote(parsed.password)
        return node
    elif scheme == "ss":
        # ss://base64(method:password@host:port)#tag or simple
        return {
            "name": urllib.parse.unquote(parsed.fragment) if parsed.fragment else "Claude专用出口",
            "type": "ss",
            "server": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 8388
        }
    else:
        # Fallback generic
        return {
            "name": "Claude专用出口",
            "type": scheme,
            "server": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 1080
        }


def load_or_init_profile(profile_path):
    """加载已有 profile.yaml 或从 example 初始化。"""
    path = Path(profile_path)
    if path.is_file():
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            print(f"[WARN] 读取现有配置失败: {e}，将初始化全新模板。")

    return {
        "claude_exits": {
            "use_relay_chain": True,
            "custom_proxies": [],
            "subscriptions": []
        },
        "relays": {
            "subscriptions": [],
            "custom_proxies": []
        },
        "custom_rules": {
            "direct": {"remote_rulesets": [], "rules": []},
            "relay": {"remote_rulesets": [], "rules": []},
            "claude_exit": {"remote_rulesets": [], "rules": []}
        }
    }


def save_profile(profile_path, data):
    """保存配置到文件。"""
    path = Path(profile_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    print(f"[OK] ✅ 配置已更新至: {path}")


def main():
    parser = argparse.ArgumentParser(description="Claude Citadel 自动化配置助手")
    parser.add_argument("--repo-dir", default=str(DEFAULT_REPO_DIR), help="claude-citadel 本地仓库目录")
    parser.add_argument("--profile", help="指定 profile.yaml 路径 (默认使用 repo-dir 下的 profile.yaml)")
    parser.add_argument("--from-clipboard", action="store_true", help="从剪贴板读取订阅链接或节点 URL 安全导入")
    parser.add_argument("--type", choices=["claude-node", "claude-sub", "relay-sub", "relay-node"], default="relay-sub",
                        help="导入的内容类型 (默认: relay-sub 通用中转机场订阅)")
    parser.add_argument("--name", default="", help="为添加的节点或订阅指定别名")
    parser.add_argument("--use-relay-chain", choices=["true", "false"], help="设置 Claude 出口是否走中转代理链")
    parser.add_argument("--build", action="store_true", help="配置完成后立即执行 6 大客户端全量本地编译与校验")
    parser.add_argument("--gist-id", help="指定 GitHub Secret Gist ID")
    parser.add_argument("--sync-gist", action="store_true", help="从指定 Gist 拉取并编译，或推送回 Gist")

    args = parser.parse_args()

    repo_dir = Path(args.repo_dir)
    profile_path = Path(args.profile) if args.profile else (repo_dir / "profile.yaml")

    data = load_or_init_profile(profile_path)

    # 1. 设置代理链开关
    if args.use_relay_chain:
        is_chain = args.use_relay_chain.lower() == "true"
        data.setdefault("claude_exits", {})["use_relay_chain"] = is_chain
        print(f"[INFO] Claude 专用出口代理链已设置为: {'开启' if is_chain else '关闭'}")

    # 2. 从剪贴板或环境变量导入
    if args.from_clipboard:
        clip_content = get_clipboard_text()
        if not clip_content:
            print("[ERROR] 剪贴板为空，未读取到任何有效内容。")
            sys.exit(1)

        name = args.name or "已导入项目"

        if args.type == "relay-sub":
            # 机场订阅链接
            subs = data.setdefault("relays", {}).setdefault("subscriptions", [])
            subs.append({
                "name": name,
                "emoji": "✈️",
                "url": clip_content
            })
            print(f"[OK] ✅ 成功添加中转机场订阅: {name} (URL 字符数: {len(clip_content)})")

        elif args.type == "claude-sub":
            subs = data.setdefault("claude_exits", {}).setdefault("subscriptions", [])
            subs.append({
                "name": name,
                "emoji": "🛡️",
                "url": clip_content
            })
            print(f"[OK] ✅ 成功添加 Claude 专属订阅: {name}")

        elif args.type == "claude-node":
            node = parse_proxy_url(clip_content)
            if args.name:
                node["name"] = args.name
            proxies = data.setdefault("claude_exits", {}).setdefault("custom_proxies", [])
            proxies.append(node)
            print(f"[OK] ✅ 成功添加 Claude 专用节点: {node['name']} ({node['type']} -> {node['server']}:{node['port']})")

        elif args.type == "relay-node":
            node = parse_proxy_url(clip_content)
            if args.name:
                node["name"] = args.name
            proxies = data.setdefault("relays", {}).setdefault("custom_proxies", [])
            proxies.append(node)
            print(f"[OK] ✅ 成功添加中转自定义节点: {node['name']}")

        save_profile(profile_path, data)

    # 3. 执行编译校验
    if args.build or (not args.from_clipboard and not args.use_relay_chain):
        build_script = repo_dir / "build.py"
        if not build_script.is_file():
            print(f"[ERROR] 未找到编译脚本: {build_script}")
            sys.exit(1)

        cmd = [sys.executable, str(build_script), "--profile", str(profile_path)]
        if args.gist_id and args.sync_gist:
            cmd.extend(["--publish-gist", args.gist_id])

        print(f"[INFO] 正在调用编译引擎生成 6 大客户端配置...")
        res = subprocess.run(cmd)
        if res.returncode == 0:
            print("[OK] 🎉 全客户端编译与离线内核校验全部通过！")
        else:
            print("[ERROR] ❌ 编译或静态内核校验失败，请检查配置。")
            sys.exit(res.returncode)


if __name__ == "__main__":
    main()
