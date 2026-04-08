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
    return {
        "name": "sre-incident-response",
        "version": "1.0.0",
        "tasks": [1, 2, 3],
        "docs": "/docs",
    }


@app.post("/reset", response_model=Observation)
def reset(task_id: int = 1):
    if task_id not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="task_id must be 1, 2, or 3")
    return env.reset(task_id=task_id)


@app.post("/step")
def step(action: Action):
    obs, reward = env.step(action)
    return {"observation": obs.model_dump(), "reward": reward.model_dump()}


@app.get("/state", response_model=EnvironmentState)
def state():
    return env.state()