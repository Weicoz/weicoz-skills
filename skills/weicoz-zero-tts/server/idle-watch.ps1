param([Parameter(Mandatory)][string]$LogFile, [Parameter(Mandatory)][string]$Match, [double]$Minutes = 10)
# 看门狗：日志文件超过 N 分钟没有新写入（即没有请求）就结束命令行匹配 $Match 的进程，释放显存后自己退出。
while($true){
  Start-Sleep 30
  $procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match $Match -and $_.Name -match 'python' }
  if(-not $procs){ break }
  if(((Get-Date) - (Get-Item $LogFile).LastWriteTime).TotalMinutes -gt $Minutes){ $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA 0 }; break }
}
