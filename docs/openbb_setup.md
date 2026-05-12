# OpenBB Setup

OpenBB is the preferred local data and research layer. The app works without
OpenBB, but enrichment quality improves when a local OpenBB API is running.

## Local Ports

| Service | URL |
| --- | --- |
| OpenBB API | `http://127.0.0.1:6900` |
| Optional OpenBB MCP | `http://127.0.0.1:8001` |
| ISA Portfolio Intelligence API | `http://127.0.0.1:8002` |

## Checks

```powershell
python scripts/check_openbb.py
```

The check reads:

- `http://127.0.0.1:6900/openapi.json`
- `http://127.0.0.1:6900/widgets.json`

No API keys are required. If OpenBB is unavailable, the app still starts and
marks enrichment sections missing rather than failing the run.

## Route Safety

OpenBB route paths are centralized in
`src/isa_system/enrichment/openbb_endpoints.py` because paths may vary by local
OpenBB version and provider installation.
