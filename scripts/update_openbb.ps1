param(
    [string]$Ref = "origin/develop",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Vendor = Join-Path $Root "vendor/OpenBB"

if (-not (Test-Path $Vendor)) {
    throw "OpenBB submodule is missing at $Vendor. Run: git submodule update --init --recursive"
}

git -C $Vendor fetch origin
git -C $Vendor checkout $Ref

if (-not $SkipTests) {
    python -m pytest tests/unit/test_openbb_adapter.py tests/integration/test_openbb_routes.py -q
}

python -c "from isa_system.openbb_adapter import OpenBBUpstreamManager; OpenBBUpstreamManager().write_lock(notes='Pinned by scripts/update_openbb.ps1 after compatibility checks')"
