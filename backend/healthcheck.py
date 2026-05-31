"""Container HEALTHCHECK probe for the FastAPI app.

Exits 0 when GET /api/health returns HTTP 200, non-zero otherwise.

`urllib.request.urlopen` raises HTTPError/URLError on any non-2xx response or
connection failure rather than returning, so we catch everything and map it to
exit 1. This keeps Docker's health status correct while avoiding the noisy
uncaught traceback the previous inline one-liner produced on every transient
startup probe.
"""

import sys
import urllib.request

try:
    with urllib.request.urlopen(
        "http://127.0.0.1:8000/api/health", timeout=2
    ) as resp:
        sys.exit(0 if resp.status == 200 else 1)
except Exception:
    sys.exit(1)
