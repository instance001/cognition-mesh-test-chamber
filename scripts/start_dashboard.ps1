$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

python -m cm_test_chamber.cli dashboard --host 127.0.0.1 --port 8765
