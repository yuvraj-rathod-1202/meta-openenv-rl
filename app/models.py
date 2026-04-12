from typing import List

from pydantic import BaseModel, ConfigDict, Field


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str = Field(
        ...,
        description=(
            "A single shell command the agent wishes to execute on the mock server. "
            "Examples: 'ls /var/log', 'cat /etc/app/config.json', "
            "'systemctl restart nginx', 'kill -9 1234', 'df -h', 'free -m', "
            "'du -sh /var/log/*', 'ps aux', '> /var/log/app-debug.log', "
            "'sed -i s/old/new/g /etc/app/config.json'."
        ),
        min_length=1,
        max_length=512,
    )


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stdout: str = Field(description="Standard output from the executed command.")
    stderr: str = Field(description="Standard error from the executed command.")
    pwd: str = Field(description="Present working directory after command execution.")
    active_alerts: List[str] = Field(
        description="Current unresolved PagerDuty-style alerts for this incident."
    )
    step_count: int = Field(description="Number of steps taken so far in this episode.")


class Reward(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float = Field(description="Scalar reward in (0.0, 1.0).", gt=0.0, lt=1.0)
    breakdown: dict = Field(description="Named sub-rewards explaining how value was computed.")
    done: bool = Field(description="True when the episode is complete.")
    info: dict = Field(description="Diagnostic info for debugging (not for the agent).")


class EnvironmentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int = Field(description="Active task: 1 (easy), 2 (medium), or 3 (hard).")
    step_count: int
    done: bool
    current_reward: float
    mock_filesystem: dict = Field(description="Snapshot of the mock filesystem.")
    mock_processes: list = Field(description="List of running mock processes.")
    mock_services: dict = Field(description="Service name -> status mapping.")
    mock_memory: dict = Field(description="Simulated memory stats.")
    active_alerts: List[str]