$ErrorActionPreference = 'Stop'
$pidFile = Join-Path $PSScriptRoot '.local/router/server.pid'
if (!(Test-Path -LiteralPath $pidFile)) { Write-Host 'Keine gespeicherte Router-Instanz.'; return }
$routerPid = [int](Get-Content -LiteralPath $pidFile)
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $routerPid"
if (!$process) { Write-Host 'Router wurde bereits beendet.'; return }
if ($process.CommandLine -notmatch '\-m\s+router\.server\b') {
    throw 'Die Prozess-ID gehoert nicht mehr zum Router. Es wurde kein Prozess beendet.'
}
Stop-Process -Id $routerPid
Write-Host 'Router beendet. Arbeitskopien und Aufgaben bleiben erhalten.'
