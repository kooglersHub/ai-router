[CmdletBinding()]
param(
    [ValidateRange(1024,65535)]
    [int]$Port = 4321,
    [switch]$NoOpen,
    [switch]$Kit
)

$ErrorActionPreference = 'Stop'
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (!$pythonCommand) { throw 'Python 3.12 oder neuer installieren und dem Suchpfad hinzufuegen.' }
& $pythonCommand.Source -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 oder neuer wird benoetigt.' }

$stateDirectory = Join-Path $PSScriptRoot '.local/router'
New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
$healthUrl = "http://127.0.0.1:$Port/api/state"
try {
    $existing = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($existing.version -eq '0.1.0' -and $null -ne $existing.agents) {
        if ($Kit -and !($existing.agents | Where-Object { $_.id -eq 'kit' -and $_.installed })) {
            Write-Host 'Beende die laufende Instanz mit .\stop-router.ps1 und starte erneut mit -Kit.'
            return
        }
        Write-Host "AI Router laeuft bereits: http://127.0.0.1:$Port"
        if (!$NoOpen) { Start-Process "http://127.0.0.1:$Port" }
        return
    }
} catch [System.Net.Http.HttpRequestException] {
    # No listener is normal before the first start.
} catch [System.Threading.Tasks.TaskCanceledException] {
    # A slow unrelated listener will cause the actual bind to fail visibly below.
} catch {
    Write-Verbose $_.Exception.Message
}

$previousKitKey = $env:KIT_TOOLBOX_API_KEY
try {
    if ($Kit -and !$previousKitKey) {
        $kitSecret = Read-Host 'KIT-API-Key' -AsSecureString
        $env:KIT_TOOLBOX_API_KEY = [System.Net.NetworkCredential]::new('', $kitSecret).Password
    }
    $server = Start-Process -FilePath $pythonCommand.Source -ArgumentList @('-m','router.server','--port',"$Port") -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $stateDirectory 'stdout.log') -RedirectStandardError (Join-Path $stateDirectory 'stderr.log') -PassThru
} finally {
    $env:KIT_TOOLBOX_API_KEY = $previousKitKey
}
$ready = $false
for ($attempt=0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 250
    $server.Refresh()
    if ($server.HasExited) {
        $serverError = Get-Content (Join-Path $stateDirectory 'stderr.log') -Raw
        throw "Router konnte nicht gestartet werden: $serverError"
    }
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 1
        if ($health.version -eq '0.1.0') { $ready=$true; break }
    } catch { Write-Verbose $_.Exception.Message }
}
if (!$ready) { throw 'Router antwortet noch nicht. Siehe .local/router/stderr.log.' }
$server.Id | Set-Content (Join-Path $stateDirectory 'server.pid')
Write-Host "AI Router gestartet: http://127.0.0.1:$Port"
if (!$NoOpen) { Start-Process "http://127.0.0.1:$Port" }
