"""
FastAPI application for SRE Incident Response environment.

Provides HTTP API for agents to interact with the mock Linux server.

Endpoints:
- GET /          : Service info
- POST /reset    : Start new episode
- POST /step     : Execute command
- GET /state     : Debug state
- GET /docs      : Interactive Swagger UI

Example usage:
    # Start episode
    POST /reset?task_id=1

    # Execute command
    POST /step
    {"command": "systemctl status nginx"}

    # Get response with reward
    {
      "observation": {"stdout": "...", "stderr": "", ...},
      "reward": {"value": 0.5, "done": false, ...}
    }
"""

from fastapi import FastAPI, HTTPException

from app.environment import SREEnvironment
from app.models import Action, EnvironmentState, Observation

app = FastAPI(
    title="SRE Incident Response — OpenEnv",
    description="An OpenEnv-compatible RL environment simulating SRE on-call incidents.",
    version="1.0.0",
)

env = SREEnvironment()


@app.get("/")
def root():
    """Service information and available tasks."""
    return {
        "name": "sre-incident-response",
        "version": "1.0.0",
        "tasks": [1, 2, 3],
        "docs": "/docs",
    }


@app.post("/reset", response_model=Observation)
def reset(task_id: int = 1):
    """
    Start a new episode.

    Args:
        task_id: Task to run (1=easy, 2=medium, 3=hard)

    Returns:
        Initial observation for the episode

    Raises:
        HTTPException: If task_id not in (1, 2, 3)
    """
    if task_id not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="task_id must be 1, 2, or 3")
    return env.reset(task_id=task_id)


@app.post("/step")
def step(action: Action):
    """
    Execute a command on the mock server.

    Args:
        action: Action containing shell command to execute

    Returns:
        {
            "observation": Current state observation,
            "reward": Reward signal with value (0-1) and done flag
        }
    """
    obs, reward = env.step(action)
    return {"observation": obs.model_dump(), "reward": reward.model_dump()}


@app.get("/state", response_model=EnvironmentState)
def state():
    """
    Get full internal state (for debugging).

    Returns:
        Complete environment state including filesystem, processes, services, memory.
    """
    return env.state()