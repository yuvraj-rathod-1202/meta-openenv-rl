# SRE Incident Response — OpenEnv

An [OpenEnv](https://openenv.dev)-compatible RL environment for evaluating how LLMs handle production incident response on a mock Linux server.

**Use cases**: Benchmark LLM reasoning, test multi-step problem solving, evaluate incident response strategies.

---

## Quick Start

```bash
# 1. Install & setup
pip install -r requirements.txt
export HF_TOKEN="hf_your_token_here"

# 2. Terminal 1: Start environment server
uvicorn app.main:app --port 7860

# 3. Terminal 2: Run baseline agent
python baseline.py
```

Expected output: All 3 tasks solved with reward=1.0

---

## Architecture

**Agent** → **FastAPI Server** → **SREEnvironment** → **Mock Linux System**

```
Agent sends: {"command": "systemctl status nginx"}
         ↓
Environment simulates execution on mock system
         ↓
Returns: {
  "observation": {"stdout": "...", "stderr": "", "active_alerts": [...], ...},
  "reward": {"value": 0.5, "done": false, ...}
}
```

---

## Environment

### Observation Space
- `stdout`: Command output (string)
- `stderr`: Error messages (string)
- `pwd`: Current directory (string)
- `active_alerts`: PagerDuty-style alerts (list)
- `step_count`: Steps taken (int)

### Action Space
Single shell command (string, max 512 chars)

**Supported commands**: `ls, cat, df, du, ps, top, free, kill, systemctl, >, rm, echo, sed`

### Reward
- Range: (0.0, 1.0), implemented as [0.01, 0.99]
- Task-specific grading (see below)
- Breakdown: Detailed sub-rewards for debugging

---

## Tasks

### Task 1: Nginx Down 🟢 Easy
- **Problem**: nginx crashed (port binding error)
- **Alert**: "CRITICAL: 502 Bad Gateway — load balancer reports nginx is down"
- **Solution**: Check status → Start service
- **Reward**: 0.5 for status check, 1.0 for restart

### Task 2: OOM Database 🟡 Medium
- **Problem**: Rogue process consuming 90% memory → PostgreSQL OOM killed
- **Alerts**: High memory usage, DB down
- **Solution**: Kill rogue process → Restart PostgreSQL
- **Tricky**: Restarting before kill fails (reward penalty to 0.2)
- **Reward**: 0.3 for kill, 1.0 for full recovery

### Task 3: Disk Full + Bad Config 🔴 Hard
- **Problem**: /var 100% full (50GB debug log), config.json truncated
- **Alerts**: No space left, app failed
- **Solution**: Clear disk → Fix JSON config → Restart app
- **Partial credit**: 0.3 for disk clear, 0.6 for config fix, 1.0 for restart
- **Reward**: Multi-step with dependency chain

---

## API Reference

### `POST /reset?task_id=1`
Start new episode. Returns initial observation.

### `POST /step`
Execute command.
```json
{"command": "systemctl status nginx"}
```
Returns: `{"observation": {...}, "reward": {...}}`

### `GET /state`
Debug: Full internal state of mock system.

### `GET /docs`
Interactive Swagger UI.

---

## Running Baseline

### With HF Inference API (Recommended)
```bash
export HF_TOKEN="hf_your_token"
python baseline.py
```

**Model options** (edit `baseline.py` line 19):
```python
MODEL_NAME = "google/flan-t5-base"  # Free, reliable
# MODEL_NAME = "gpt2"               # Smaller
# MODEL_NAME = "distilgpt2"         # Tiniest
```

Results saved to `baseline_results.json`

### Using Docker
```bash
docker build -t sre-openenv .
docker run -p 7860:7860 sre-openenv
```

---

## Project Structure

```
app/
├── main.py              # FastAPI routes
├── environment.py       # Core SREEnvironment class
├── models.py            # Pydantic models
└── tasks/
    ├── task1_nginx.py   # Task 1 state
    ├── task2_oom.py     # Task 2 state
    └── task3_disk.py    # Task 3 state
baseline.py             # Agent runner
tests/                  # Pytest suite (18 tests)
Dockerfile
requirements.txt
```

---

## Extending

### Add a New Task
1. Create `app/tasks/task4_name.py` with `build_initial_state()` function
2. Add to `environment.py`:
   - Import state builder
   - Add to `builders` dict in `reset()`
   - Implement `_grade_task4()` method
3. Add tests

### Custom Agent
Simply call the API:
```python
import httpx

client = httpx.Client(base_url="http://localhost:7860")

# Start episode
obs = client.post("/reset", params={"task_id": 1}).json()

# Run step
response = client.post("/step", json={"command": "systemctl status nginx"})
obs, reward = response.json()["observation"], response.json()["reward"]
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Model not supported" | Try `google/flan-t5-base` instead |
| "Connection refused" | Start server: `uvicorn app.main:app --port 7860` |
| Reward stuck at 0.0 | Use `GET /state` to debug mock system state |
| Tests failing | Run `pytest -v tests/` for details |

---

## Testing

```bash
pytest tests/ -v              # Run all tests
pytest tests/test_environment.py::test_task1_solved_on_start  # Specific test
```

---

## License

MIT License
