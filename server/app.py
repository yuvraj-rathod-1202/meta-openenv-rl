"""
Server application entry point for SRE OpenEnv.
Re-exports the FastAPI app from app.main for server deployment.
"""

from app.main import app

__all__ = ["app", "main"]


def main() -> None:
    """Run the SRE OpenEnv server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
