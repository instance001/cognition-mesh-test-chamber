$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$serverExe = Join-Path $repoRoot "runtime\\llama-server.exe"
$modelPath = Join-Path $repoRoot "model_under_test\\Qwen3-8B-abliterated-q8_0.gguf"

if (-not (Test-Path $serverExe)) {
    throw "Missing runtime executable: $serverExe"
}

if (-not (Test-Path $modelPath)) {
    throw "Missing model file: $modelPath"
}

& $serverExe `
  -m $modelPath `
  --host 127.0.0.1 `
  --port 8080 `
  -ngl 999 `
  -c 8192
