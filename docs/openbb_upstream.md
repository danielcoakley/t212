# OpenBB Upstream Workflow

OpenBB is vendored as a Git submodule at `vendor/OpenBB`. Keep it clean:
do not edit tracked files in that directory for ISA-specific features.

All app code that needs OpenBB must go through `isa_system.openbb_adapter`.
The adapter normalises OpenBB output into local schemas before strategy,
risk, execution, or dashboard code sees it.

## ODP Desktop Backend

The default app integration is `ISA_OPENBB_BACKEND=odp_rest`, which calls a
running ODP Desktop/OpenBB API backend instead of importing the full source
checkout into the ISA app process.

In ODP Desktop:

1. Open **Backends**.
2. Start the OpenBB API backend, or create one with executable `openbb-api`.
3. Use the URL shown by ODP Desktop as `ISA_OPENBB_ODP_API_BASE_URL`.

The default ODP API URL is:

```powershell
ISA_OPENBB_ODP_API_BASE_URL=http://127.0.0.1:6900
```

If Basic Auth is enabled on the OpenBB API backend, also set:

```powershell
ISA_OPENBB_ODP_API_USERNAME=...
ISA_OPENBB_ODP_API_PASSWORD=...
```

The vendored `vendor/OpenBB` checkout can remain as an upstream reference and
pinning mechanism, but the local dashboard should not require a full editable
OpenBB repo install when ODP Desktop is running.

## ODP Screening

The broad-market scan defaults to ODP's `/api/v1/equity/screener` route, then
validates any preview candidate against Trading 212 before hand-off:

```powershell
ISA_OPENBB_SCREENER_PROVIDER=yfinance
ISA_OPENBB_SCREENER_COUNTRY=us
ISA_OPENBB_SCREENER_MARKET_CAP_MIN=1000000000
ISA_OPENBB_SCREENER_VOLUME_MIN=100000
```

`yfinance` works without extra ODP credentials. If you prefer FMP or another
provider, configure that provider inside ODP Desktop first, then change
`ISA_OPENBB_SCREENER_PROVIDER`.

## Update

```powershell
git submodule update --init --recursive
.\scripts\update_openbb.ps1
```

The script fetches OpenBB, checks out the requested ref, runs adapter
compatibility tests, and records the accepted revision in
`configs/openbb.lock.json`.

## Rollback

```powershell
$sha = (Get-Content configs/openbb.lock.json | ConvertFrom-Json).revision
git -C vendor/OpenBB checkout $sha
python -m pytest tests/unit/test_openbb_adapter.py tests/integration/test_openbb_routes.py -q
```

If an OpenBB update breaks the app, fix `isa_system.openbb_adapter` rather
than strategy or execution code.
