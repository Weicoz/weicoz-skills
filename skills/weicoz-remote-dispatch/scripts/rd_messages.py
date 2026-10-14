"""任务进度与结果回执；只记录本轮工作，不调度下一轮。"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import tempfile

MAX_BYTES = 65536
OUTCOMES = ("completed", "partial", "blocked", "failed")
CHECKS = ("passed", "failed", "partial", "not_run", "not_reported")


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def identifier(value, label):
    if not isinstance(value, str) or not value or len(value) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(label + " 必须是非空、无控制字符的标识。")
    return value


def job_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) or value in (".", ".."):
        raise ValueError("无效的任务 ID。")
    return value


def round_id(value):
    number = int(value)
    if number <= 0:
        raise ValueError("轮次必须是正整数。")
    return number


def atomic_json(path, data, limit=MAX_BYTES):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("回执路径不得是符号链接。")
    body = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if limit is not None and len(body) > limit:
        raise ValueError("回执超过64KiB；正文保存在私有产物中并引用路径。")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, staging = tempfile.mkstemp(prefix=".receipt-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, path)
    finally:
        if os.path.exists(staging):
            os.unlink(staging)


def read_json(path):
    path = Path(path)
    if not path.exists():
        return None
    if any(p.is_symlink() for p in (path, *path.parents)) or path.stat().st_size > MAX_BYTES:
        raise ValueError("回执路径或大小无效。")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError):
        raise ValueError("回执不是有效的UTF-8 JSON。") from None


def validate_report(data, job, number, kind):
    if (not isinstance(data, dict) or type(data.get("schema")) is not int or data.get("schema") != 1
        or type(data.get("round")) is not int or data.get("job") != job or data.get("round") != number or data.get("kind") != kind):
        raise ValueError("回执任务、轮次或格式不匹配。")
    identifier(data.get("updated_at"), "回执时间")
    for field in ("phase", "summary"):
        if not isinstance(data.get(field, ""), str) or len(data.get(field, "")) > 8000:
            raise ValueError("回执阶段或摘要无效。")
    if kind == "result" and (data.get("outcome") not in OUTCOMES or data.get("checks") not in CHECKS):
        raise ValueError("结果或检查状态无效。")
    if not isinstance(data.get("artifacts", []), list) or any(not isinstance(x, str) for x in data.get("artifacts", [])):
        raise ValueError("产物必须是路径列表。")
    return data


def report(directory, job, number, kind, phase="", summary="", outcome="completed", checks="not_reported", artifacts=()):
    job, number = job_id(job), round_id(number)
    if kind not in ("progress", "result"):
        raise ValueError("只支持 progress 或 result。")
    data = dict(schema=1, job=job, round=number, kind=kind, phase=phase, summary=summary,
                artifacts=list(artifacts), updated_at=utc_now())
    if kind == "result":
        data.update(outcome=outcome, checks=checks)
    validate_report(data, job, number, kind)
    atomic_json(Path(directory).resolve() / "reports" / (kind + ".r" + str(number) + ".json"), data)
    return data


def finish(directory, job, number, code):
    directory, job, number = Path(directory).resolve(), job_id(job), round_id(number)
    path = directory / "reports" / ("result.r" + str(number) + ".json")
    data = read_json(path)
    if data is None:
        reply = directory / ("last.r" + str(number) + ".txt")
        summary = ""
        if reply.is_file() and not reply.is_symlink():
            with reply.open("rb") as stream:
                summary = stream.read(MAX_BYTES).decode("utf-8", errors="replace")[:8000]
        data = report(directory, job, number, "result", summary=summary, outcome="completed" if code == 0 else "failed")
    else:
        validate_report(data, job, number, "result")
    data.update(executor_exit=int(code), finished_at=utc_now(),
                reply_file="last.r" + str(number) + ".txt", stdout_file="stdout.r" + str(number) + ".log")
    if code != 0:
        data["outcome"] = "failed"
    atomic_json(path, data)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("progress", "result", "finish"))
    parser.add_argument("--phase", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--outcome", choices=OUTCOMES, default="completed")
    parser.add_argument("--checks", choices=CHECKS, default="not_reported")
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--exit", type=int)
    args = parser.parse_args()
    try:
        directory = os.environ["RD_JOB_DIR"]
        job, number = job_id(os.environ["RD_JOB"]), round_id(os.environ["RD_ROUND"])
        if args.action == "finish":
            if args.exit is None:
                raise ValueError("finish 必须指定 --exit。")
            finish(directory, job, number, args.exit)
        else:
            report(directory, job, number, args.action, args.phase, args.summary, args.outcome, args.checks, args.artifact)
        print("本轮回执已保存；下一步由发起方判断。")
    except (KeyError, ValueError, OSError) as error:
        parser.exit(4, "rd-report: " + ("请在派单任务环境中执行。" if isinstance(error, KeyError) else str(error)) + "\n")


if __name__ == "__main__":
    main()
