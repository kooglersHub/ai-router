# This launcher deliberately has no live-agent mode.
[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 4321,
    [switch]$NoOpen
)

$ErrorActionPreference = 'Stop'
$entryPoint = Join-Path $PSScriptRoot '.local/cezar/node_modules/cezar-run/bin.js'
$demoRepository = Join-Path $PSScriptRoot '.local/demo'
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$nodeExecutable = if ($nodeCommand) { $nodeCommand.Source } else {
    Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
}

if (!(Test-Path -LiteralPath $nodeExecutable)) {
    throw 'Node.js 20 oder neuer wird benoetigt.'
}
if (!(Test-Path -LiteralPath $entryPoint) -or !(Test-Path -LiteralPath $demoRepository)) {
    throw 'Die lokale Demo-Installation fehlt. Siehe README.md.'
}

$demoEnvironment = @{
    CEZ_DRY_RUN = '1'
    CEZ_HOME = (Join-Path $PSScriptRoot '.local/cezar-home')
    CEZ_AUTONAME = '0'
    CEZ_DISPATCH = '0'
    CEZ_REVIEW_GATE = '1'
    CEZ_NO_BANNER = '1'
}
$previousEnvironment = @{}
foreach ($name in $demoEnvironment.Keys) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    [Environment]::SetEnvironmentVariable($name, $demoEnvironment[$name], 'Process')
}

try {
    $cezarArguments = @($entryPoint, '--repo', $demoRepository, '--bind-host', '127.0.0.1', '--port', "$Port")
    if ($NoOpen) { $cezarArguments += '--no-open' }
    Write-Host "Cezar DEMO: simulierte Agenten, lokales Test-Repository. http://127.0.0.1:$Port"
    & $nodeExecutable @cezarArguments
    if ($LASTEXITCODE -ne 0) { throw "Cezar wurde mit Exitcode $LASTEXITCODE beendet." }
}
finally {
    foreach ($name in $previousEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
}
