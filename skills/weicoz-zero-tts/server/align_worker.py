"""字级时间与识别回读的工作进程，由 voices_site.py 按需启动，一次处理一批句子后退出（不常驻、不长期占显存）。

用法：python align_worker.py para|fa <job.json> <out.json> [cpu|cuda]
  para：funasr paraformer-zh 识别，输出识别出的字及其时间（需要 GPT-SoVITS venv 里的 funasr，模型从 MODELSCOPE_CACHE 读取）。
  fa：Qwen3-ForcedAligner-0.6B 强制对齐，按给定文字输出每个字的时间（需要 aligner venv 里的 qwen-asr，模型路径 ALIGNER_MODEL）。
job.json：[{"id", "wav", "text"}]，wav 为 16kHz 单声道。
out.json：{id: [[文字, 开始秒, 结束秒], ...]}；para 另含 {"_heard": {id: 识别全文}}。
"""
import json
import os
import sys


def run_para(job, device):
    from funasr import AutoModel
    m = AutoModel(model="paraformer-zh", disable_update=True, device=device)
    out, heard = {}, {}
    for it in job:
        r = m.generate(input=it["wav"])[0]
        toks = r.get("text", "").split()
        ts = r.get("timestamp") or []
        out[it["id"]] = [[t, a / 1000, b / 1000] for t, (a, b) in zip(toks, ts)]
        heard[it["id"]] = "".join(toks)
    out["_heard"] = heard
    return out


def run_fa(job, device):
    import torch
    from qwen_asr import Qwen3ForcedAligner
    path = os.environ.get("ALIGNER_MODEL", r"D:\TTS_Services\aligner\model\Qwen3-ForcedAligner-0.6B")
    m = Qwen3ForcedAligner.from_pretrained(path, dtype=torch.bfloat16 if device == "cuda" else torch.float32,
                                           device_map="cuda:0" if device == "cuda" else "cpu")
    out = {}
    for it in job:
        res = m.align(audio=it["wav"], text=it["text"], language="Chinese")
        out[it["id"]] = [[x.text, float(x.start_time), float(x.end_time)] for x in res[0]]
    return out


def main():
    mode, job_path, out_path = sys.argv[1:4]
    device = sys.argv[4] if len(sys.argv) > 4 else "cpu"
    job = json.load(open(job_path, encoding="utf-8"))
    out = run_para(job, device) if mode == "para" else run_fa(job, device)
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
