#!/usr/bin/env python3
"""从 t3 CLI 的 stdout 里取 JSON 载荷，按模式返回字段（无第三方依赖）。

t3 CLI 与服务端版本不一致时会把 WARN/ERROR 日志混进 stdout（如
`Database migration history diverges`），JSON 总是最后一整行。这里跳过日志行，
只解析能解析的 JSON，以最后一个载荷为准。

用法（stdin 接 t3 的 stdout）：
  t3-json.py thread-id                 # thread start 的 JSON → threadId
  t3-json.py project-id                # thread show 的 JSON → thread.projectId
  t3-json.py list-status <threadId>    # thread list 的 JSON → 该线程 status
  t3-json.py thread-id-prefix <前缀>    # thread list 的 JSON → 唯一匹配的 threadId
  t3-json.py last-assistant            # thread show 的 JSON → 最后一条 assistant 正文，输出到 stdout
"""
import json, sys


def die(msg):
    sys.exit("错误：" + msg)


def payloads():
    for line in sys.stdin:
        s = line.strip()
        if not s.startswith(("{", "[")):
            continue
        try:
            yield json.loads(s)
        except json.JSONDecodeError:
            continue


def last_payload():
    data = None
    for item in payloads():
        data = item
    return data


def threads(data):
    if isinstance(data, list):
        return data
    return (data.get("threads") if isinstance(data, dict) else None) or []


def find_thread_id(data):
    if isinstance(data, dict):
        tid = data.get("threadId")
        if isinstance(tid, str) and tid:
            return tid
        for value in data.values():
            found = find_thread_id(value)
            if found:
                return found
    elif isinstance(data, list):
        for value in data:
            found = find_thread_id(value)
            if found:
                return found
    return ""


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    arg = sys.argv[2] if len(sys.argv) > 2 else ""
    data = last_payload()
    if data is None:
        die("t3 输出里没有可解析的 JSON。确认项目已登记（t3 project add）、T3 服务端在运行。")
    thread = data.get("thread") if isinstance(data, dict) else None
    if mode == "thread-id":
        tid = find_thread_id(data)
        if not tid:
            die("t3 输出里没有 threadId。")
        print(tid)
    elif mode == "project-id":
        pid = (thread or {}).get("projectId") or ""
        if not pid:
            die("thread show 的 JSON 里没有 projectId。")
        print(pid)
    elif mode == "list-status":
        for item in threads(data):
            if item.get("threadId") == arg:
                print(item.get("status") or "")
                return
        die("项目下找不到线程 %s。用 --project 指定该线程所属项目。" % arg)
    elif mode == "thread-id-prefix":
        hits = [str(i.get("threadId") or "") for i in threads(data) if str(i.get("threadId") or "").startswith(arg)]
        if not hits:
            die("项目下没有以 %s 开头的线程。" % arg)
        if len(hits) > 1:
            die("前缀匹配到多个线程：" + "、".join(hits))
        print(hits[0])
    elif mode == "last-assistant":
        texts = [m.get("text") or "" for m in (data.get("messages") or [])
                 if m.get("role") == "assistant" and (m.get("text") or "").strip()]
        if not texts:
            die("该线程没有 assistant 回复正文。")
        if (thread or {}).get("status") == "running":
            print("注意：线程仍在 running，以下是当前最后一条，不是最终回复。", file=sys.stderr)
        print(texts[-1].rstrip())
    else:
        die("用法：t3-json.py <thread-id|project-id|list-status <threadId>|thread-id-prefix <前缀>|last-assistant>")


if __name__ == "__main__":
    main()
