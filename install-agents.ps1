[CmdletBinding()]
param([switch]$WithGemini)
$ErrorActionPreference = 'Stop'
$agentDirectory = Join-Path $PSScriptRoot '.local/agents'
New-Item -ItemType Directory -Path $agentDirectory -Force | Out-Null
$manifest = Join-Path $agentDirectory 'package.json'
if (!(Test-Path -LiteralPath $manifest)) {
    Set-Content -LiteralPath $manifest -Value '{"private":true,"name":"ai-router-agents"}'
}
$packages = @('freebuff@0.2.36')
if ($WithGemini) { $packages += '@google/gemini-cli' }
$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
$pnpmCommand = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
if ($npmCommand) {
    & $npmCommand.Source --prefix $agentDirectory install --save-exact @packages
} elseif ($pnpmCommand) {
    & $pnpmCommand.Source --dir $agentDirectory add --save-exact @packages
} else {
    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    $bundledNode = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    $nodeExecutable = if ($nodeCommand) { $nodeCommand.Source } else { $bundledNode }
    $pnpmScript = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/pnpm/bin/pnpm.cjs'
    if (!(Test-Path -LiteralPath $nodeExecutable) -or !(Test-Path -LiteralPath $pnpmScript)) {
        throw 'Node.js mit npm oder pnpm installieren. Danach dieses Skript erneut starten.'
    }
    & $nodeExecutable $pnpmScript --dir $agentDirectory add --save-exact @packages
}
if ($LASTEXITCODE -ne 0) { throw 'Agenten-Installation fehlgeschlagen.' }
Write-Host 'Agenten lokal installiert. Es wurde kein KI-Auftrag gestartet.'
