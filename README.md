# SRE Incident Response — OpenEnv

An [OpenEnv](https://openenv.dev)-compatible reinforcement learning environment that
simulates an SRE engineer handling production incidents on a mock Linux server.

## Environment Description

The agent acts as an on-call SRE. It receives PagerDuty-style alerts and must
diagnose and resolve three progressively harder failures by issuing shell commands.

## Action Space

| Field     | Type   | Description                              |
|-----------|--------|------------------------------------------|
| `command` | string | A shell command (max 512 chars)          |

Supported commands: `ls`, `cat`, `df`, `du`, `ps`, `top`, `free`, `kill`,
`systemctl`, `>` (truncate), `rm`, `echo`, `sed`

## Observation Space

| Field           | Type          | Description                                  |
|-----------------|---------------|----------------------------------------------|
| `stdout`        | string        | Command output                               |
| `stderr`        | string        | Error output                                 |
| `pwd`           | string        | Current directory                            |
| `active_alerts` | list[string]  | Unresolved PagerDuty alerts                  |
| `step_count`    | integer       | Steps taken this episode                     |

## Tasks

| # | Name                          | Difficulty | Max Steps |
|---|-------------------------------|------------|-----------|
| 1 | Crashed Web Server            | Easy       | 30        |
| 2 | OOM Database                  | Medium     | 30        |
| 3 | Disk Exhaustion + Bad Config  | Hard       | 30        |

## Baseline Scores (Gemini 1.5 Flash)

| Task | Reward | Solved |
|------|--------|--------|
| 1    | 1.00   | ✅     |
| 2    | 0.70   | ❌     |
| 3    | 0.60   | ❌     |

*(Run `python baseline.py` to reproduce)*

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/sre-openenv
cd sre-openenv
pip install -r requirements.txt
uvicorn app.main:app --reload --port 7860
```

## Docker

```bash
docker build -t sre-openenv .
docker run -p 7860:7860 sre-openenv
```

## Baseline

```bash
export GEMINI_API_KEY="your-key"
python baseline.py
```

## API

- `POST /reset?task_id=1`  — start episode
- `POST /step`             — `{"command": "systemctl status nginx"}`
- `GET  /state`            — full internal state
- `GET  /docs`             — Swagger UI