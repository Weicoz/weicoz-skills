param([Parameter(Mandatory)][ValidateSet('qwen','sovits')][string]$Engine)
# 切换 9880 端口的 TTS 引擎：qwen = Qwen3-TTS 加速版（主力），sovits = GPT-SoVITS v2ProPlus（备用）
$pid1 = (Get-NetTCPConnection -LocalPort 9880 -State Listen -EA 0 | Select-Object -First 1).OwningProcess
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'api_v2.py|qwen_server.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA 0 }
Start-Sleep 3
$task = if($Engine -eq 'qwen'){ 'tts_qwen' } else { 'api_main' }
schtasks /run /tn $task | Out-Null
if($Engine -eq 'sovits'){ schtasks /run /tn tts_idle_sovits | Out-Null }  # 备用引擎同样空闲自动关闭
"已切换到 $Engine（任务 $task），等待就绪..."
for($i=0;$i -lt 40;$i++){ Start-Sleep 3; if(Get-NetTCPConnection -LocalPort 9880 -State Listen -EA 0){ "9880 已监听"; break } }
