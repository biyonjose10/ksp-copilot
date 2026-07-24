"""Entrypoint for Zoho Catalyst AppSail (Catalyst-managed Python runtime).

Catalyst injects the port to bind via an env var and does not reliably shell-expand
${...} inside the configured start command, so we read the port in Python instead.
"""
import os
import sys

# Catalyst's managed Python runtime does not install requirements.txt (deploys
# report no build step), so third-party deps are vendored as linux cp311 wheels
# under vendor/ and put on the path before any of them are imported.
_vendor = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if os.path.isdir(_vendor) and _vendor not in sys.path:
    sys.path.insert(0, _vendor)

import uvicorn

if __name__ == "__main__":
    port = int(
        os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT")
        or os.environ.get("PORT")
        or "9000"
    )
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
