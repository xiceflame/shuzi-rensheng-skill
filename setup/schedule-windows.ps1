# Windows：按任务名生成计划任务（PowerShell，管理员运行；与 schedule-macos/linux 同一任务目录）
# 用法： powershell -File setup\schedule-windows.ps1            # 推荐集
#        powershell -File setup\schedule-windows.ps1 -Tasks qkb-follow,lint
param([string]$Tasks = "")
$Engine = if ($env:SHUZI_ENGINE) { $env:SHUZI_ENGINE } else { "$env:USERPROFILE\shuzi-rensheng-skill\engine" }
$Bash = "C:\Program Files\Git\bin\bash.exe"   # 或 WSL: wsl.exe bash
$Recommended = @("chat-ingest","finance-ingest","rebuild","transcribe","lint","idea-review","rollup","qkb-follow")
if ($Tasks -eq "" -or $Tasks -eq "all") {
  $list = if ($Tasks -eq "all") { $Recommended + @("collector-refresh") } else { $Recommended }
} else { $list = $Tasks -split "," | ForEach-Object { $_.Trim() } }

foreach ($t in $list) {
  switch ($t) {
    "chat-ingest" {
      schtasks /create /f /tn "数字人生-chat-ingest-am" /tr "`"$Bash`" `"$Engine/run.sh`" chat-ingest" /sc daily /st 08:07
      schtasks /create /f /tn "数字人生-chat-ingest-pm" /tr "`"$Bash`" `"$Engine/run.sh`" chat-ingest" /sc daily /st 21:07
      Write-Host "  ✓ chat-ingest 08:07/21:07" }
    "finance-ingest" {
      schtasks /create /f /tn "数字人生-finance-ingest" /tr "`"$Bash`" `"$Engine/run.sh`" finance-ingest" /sc hourly /mo 4
      Write-Host "  ✓ finance-ingest 每 4 小时" }
    "rebuild" {
      schtasks /create /f /tn "数字人生-rebuild" /tr "`"$Bash`" `"$Engine/scripts-extra.sh`" rebuild" /sc hourly /mo 4
      Write-Host "  ✓ rebuild 每 4 小时" }
    "transcribe" {
      schtasks /create /f /tn "数字人生-transcribe" /tr "`"$Bash`" `"$Engine/scripts-extra.sh`" transcribe" /sc hourly /mo 4
      Write-Host "  ✓ transcribe 每 4 小时" }
    "lint" {
      schtasks /create /f /tn "数字人生-lint" /tr "`"$Bash`" `"$Engine/run.sh`" lint" /sc weekly /d SUN /st 21:07
      Write-Host "  ✓ lint 每周日" }
    "idea-review" {
      schtasks /create /f /tn "数字人生-idea-review" /tr "`"$Bash`" `"$Engine/run.sh`" idea-review" /sc weekly /d MON /st 10:07
      Write-Host "  ✓ idea-review 每周一" }
    "rollup" {
      schtasks /create /f /tn "数字人生-rollup" /tr "`"$Bash`" `"$Engine/run.sh`" rollup" /sc monthly /d 1 /st 09:07
      Write-Host "  ✓ rollup 每月 1 日" }
    "qkb-follow" {
      schtasks /create /f /tn "数字人生-qkb-follow" /tr "`"$Bash`" -c 'python3 ~/.config/qkb/qkb-follow.py --once'" /sc minute /mo 5
      Write-Host "  ✓ qkb-follow 每 5 分钟（计划任务版；常驻更佳）" }
    "collector-refresh" {
      Write-Host "  [跳过] Windows 采集端走 windows-collector.md 的机制，不用本项" }
    default { Write-Host "  [跳过] 未知任务: $t（目录见 setup/schedule.sh）" }
  }
}
