@echo off
cd /d D:\TTS_Services\qwen3tts
set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8
D:\TTS_Services\qwen3tts\venv\Scripts\python.exe D:\TTS_Services\qwen3tts\server\voices_server.py > D:\TTS_Services\qwen3tts\logs\voices_page.log 2>&1
