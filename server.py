"""Entrypoint for Zoho Catalyst AppSail (Catalyst-managed Python runtime).

Catalyst injects the port to bind via an env var and does not reliably shell-expand
${...} inside the configured start command, so we read the port in Python instead.
"""
import os

import uvicorn

if __name__ == "__main__":
    port = int(
        os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT")
        or os.environ.get("PORT")
        or "9000"
    )
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
