param([switch]$BuildPolicyImage)
$ErrorActionPreference = "Stop"

python -m pytest -q
npm --prefix apps/web run build
python scripts/release_check.py
python -m worldsim.cli doctor

$artifactDir = Join-Path (Get-Location) ".worldsim\release"
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
python -m pip wheel . --no-deps --wheel-dir $artifactDir

if ($BuildPolicyImage) {
    docker build -f containers/policy-runner/Dockerfile -t praxis-policy-runner:local .
}

Write-Host "Praxis release readiness passed. Artifacts: $artifactDir"
