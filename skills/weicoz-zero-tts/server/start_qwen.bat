@echo off
cd /d D:\TTS_Services\qwen3tts
set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8
set HF_HUB_OFFLINE=1
set TEMP=D:\TTS_Services\cache\tmp
set TMP=D:\TTS_Services\cache\tmp
D:\TTS_Services\qwen3tts\venv\Scripts\python.exe D:\TTS_Services\qwen3tts\server\qwen_server.py > D:\TTS_Services\qwen3tts\logs\server.log 2>&1
