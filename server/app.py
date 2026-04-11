"""
Server application entry point for SRE OpenEnv.
Re-exports the FastAPI app from app.main for server deployment.
"""

from app.main import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
