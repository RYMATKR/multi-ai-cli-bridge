# Windows installer for Multi-AI CLI Bridge and Orchestrator Skills
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$bridgeDir = Join-Path $env:USERPROFILE ".local\share\multi-ai-bridge"
$claudeSkillDir = Join-Path $env:USERPROFILE ".claude\skills\multi-ai-orchestrator"
$agySkillDir = Join-Path $env:USERPROFILE ".gemini\config\skills\multi-ai-orchestrator"

Write-Host "Installing multi-ai-bridge to $bridgeDir ..."
New-Item -ItemType Directory -Force -Path $bridgeDir | Out-Null
Copy-Item -Force (Join-Path $repoRoot "mcp_bridge\server.py") (Join-Path $bridgeDir "server.py")
Copy-Item -Force (Join-Path $repoRoot "mcp_bridge\test_bridge.py") (Join-Path $bridgeDir "test_bridge.py")

Write-Host "Installing multi-ai-orchestrator skill for Claude Code and Antigravity ..."
New-Item -ItemType Directory -Force -Path (Join-Path $claudeSkillDir "references") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $agySkillDir "references") | Out-Null

Copy-Item -Force (Join-Path $repoRoot ".agents\skills\multi-ai-orchestrator\SKILL.md") (Join-Path $claudeSkillDir "SKILL.md")
Copy-Item -Force (Join-Path $repoRoot ".agents\skills\multi-ai-orchestrator\references\cli-usage.md") (Join-Path $claudeSkillDir "references\cli-usage.md")

Copy-Item -Force (Join-Path $repoRoot ".agents\skills\multi-ai-orchestrator\SKILL.md") (Join-Path $agySkillDir "SKILL.md")
Copy-Item -Force (Join-Path $repoRoot ".agents\skills\multi-ai-orchestrator\references\cli-usage.md") (Join-Path $agySkillDir "references\cli-usage.md")

$serverPathForward = ($bridgeDir -replace "\\", "/") + "/server.py"
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonExe) {
    $pythonExe = "python"
} else {
    $pythonExe = $pythonExe -replace "\\", "/"
}

Write-Host ""
Write-Host "Installation complete!"
Write-Host "Running smoke test..."
& $pythonExe (Join-Path $bridgeDir "test_bridge.py")

Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Register in Claude Code:"
Write-Host "   claude mcp add -s user --transport stdio multi-ai-bridge -- $pythonExe $serverPathForward"
Write-Host "2. Or add the following to ~/.gemini/config/mcp_config.json (Antigravity):"
Write-Host "   command: `"$pythonExe`", args: [`"$serverPathForward`"]"
