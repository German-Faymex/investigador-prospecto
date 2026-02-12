"""Investigador de Prospectos - Entrypoint."""
import uvicorn
import os

from webapp.app import app  # noqa: F401 - used by Procfile

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "webapp.app:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("APP_MODE", "development") == "development",
    )
