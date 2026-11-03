# -*- coding: utf-8 -*-
"""音色试听页常驻服务：只读音色库和样板声，不加载模型、不占显存（内存约几十 MB）。

和 Qwen 合成服务分开，所以 Qwen 空闲退出、或 GPT-SoVITS 占着 9880 时，试听页照常能开。
管理与重建接口需要合成队列，仍在 Qwen 服务（9880）上。
"""
import os

import uvicorn
from fastapi import FastAPI

import voices_site

PORT = int(os.environ.get("VOICES_PAGE_PORT", "9881"))
app = FastAPI(title="zero-tts-voices")
voices_site.register(app, submit=None, touch=lambda: None)


@app.get("/health")
def health():
    return {"engine": "voices-page", "ready": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
