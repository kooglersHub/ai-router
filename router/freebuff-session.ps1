param([Parameter(Mandatory=$true)][string]$ConfigPath)
$ErrorActionPreference = 'Stop'
$session = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Host 'AI Router - Freebuff' -ForegroundColor Cyan
Write-Host 'Melde dich bei Bedarf an. Kopiere danach den Auftrag in Freebuff.'
Write-Host ''
Write-Host $session.prompt
Write-Host ''
$executable = $session.command[0]
$arguments = @($session.command | Select-Object -Skip 1)
& $executable @arguments
Write-Host ''
Read-Host 'Freebuff beendet. Enter schliesst dieses Fenster; danach im Router Ergebnis pruefen'
