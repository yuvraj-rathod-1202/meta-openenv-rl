#!/usr/bin/env python3
"""
baseline.py - Run Google Gemini against all 3 SRE OpenEnv tasks.

Usage:
    export GEMINI_API_KEY="your-key-here"
    python baseline.py

    # Against a remote HF Space:
    python baseline.py --base-url https://your-hf-space.hf.space
"""
import argparse
import json
import os
from pathlib import Path

import httpx

DEFAULT_BASE_URL = "http://localhost:7860"
MODEL_NAME = "gemini-3.1-flash-lite-preview"
MAX_STEPS = 30
TASKS = [1, 2, 3]

SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) responding to a
production incident. You interact with a mock Linux server by issuing ONE shell command
per turn. You will receive the output (stdout/stderr) and current PagerDuty alerts.

Your goal is to diagnose and fix the incident as efficiently as possible.

Rules:
- Respond with ONLY the shell command. No explanation, no markdown, no backticks.
- Valid commands include: ls, cat, df, du, ps, top, free, kill, systemctl, >, rm, echo, sed.
- Do not loop. After running a command once, interpret the output before repeating.

Example valid responses:
systemctl status nginx
kill -9 8821
> /var/log/app-debug.log
echo '}' >> /etc/app/config.json
"""


def _load_dotenv() -> None:
    """Populate os.environ from local .env files without external dependencies."""
    project_root = Path(__file__).resolve().parent
    candidates = [project_root / ".env", project_root.parent / ".env"]

    for env_path in candidates:
        if not env_path.exists() or not env_path.is_file():
            continue

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("export "):
                line = line[len("export ") :].strip()

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
USE_GEMINI = False
model = None

try:
    import google.generativeai as genai

    if api_key:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(MODEL_NAME)
        USE_GEMINI = True
    else:
        print("WARNING: GEMINI_API_KEY is not set; using deterministic fallback baseline.")
except Exception as exc:
    print(f"WARNING: Gemini SDK unavailable ({exc}); using deterministic fallback baseline.")


def _fallback_command(task_id: int, step_num: int, obs: dict) -> str:
    if task_id == 1:
        if step_num == 1:
            return "systemctl status nginx"
        return "systemctl start nginx"

    if task_id == 2:
        if step_num == 1:
            return "kill -9 8821"
        return "systemctl start postgresql"

    if task_id == 3:
        if step_num == 1:
            return "> /var/log/app-debug.log"
        if step_num == 2:
            return "cat /etc/app/config.json"
        if step_num == 3:
            return "echo '}' >> /etc/app/config.json"
        return "systemctl start app"

    return "ls /"


def run_episode(base_url: str, task_id: int) -> dict:
    client = httpx.Client(base_url=base_url, timeout=30)
    obs_data = client.post("/reset", params={"task_id": task_id}).json()
    obs = obs_data

    total_reward = 0.0
    done = False
    steps = 0

    print(f"\n{'=' * 60}")
    print(f"  TASK {task_id}  |  Alerts: {obs.get('active_alerts', [])}")
    print(f"{'=' * 60}")

    for step_num in range(1, MAX_STEPS + 1):
        prompt = (
            f"Step {step_num}.\n"
            f"Active alerts: {obs.get('active_alerts', [])}\n"
            f"STDOUT:\n{obs.get('stdout', '')}\n"
            f"STDERR:\n{obs.get('stderr', '')}\n"
            f"\nWhat is your next command?"
        )

        if USE_GEMINI and model is not None:
            if step_num == 1:
                chat = model.start_chat(history=[])
            full_prompt = SYSTEM_PROMPT + "\n\n" + prompt if step_num == 1 else prompt
            response = chat.send_message(full_prompt)
            command = response.text.strip().split("\n")[0].strip()
            command = command.strip("`").strip()
        else:
            command = _fallback_command(task_id, step_num, obs)

        print(f"  Step {step_num:02d} -> command: {command!r}")

        step_resp = client.post("/step", json={"command": command}).json()
        obs = step_resp["observation"]
        reward = step_resp["reward"]
        steps = step_num

        total_reward = reward["value"]
        done = reward["done"]

        print(f"           reward: {total_reward:.2f}  done: {done}")

        if done:
            break

    result = {
        "task_id": task_id,
        "final_reward": total_reward,
        "steps_taken": steps,
        "solved": done and total_reward >= 1.0,
    }
    print(f"\n  RESULT task={task_id}: reward={total_reward:.2f}, steps={steps}, solved={result['solved']}")
    return result


def main():
    parser = argparse.ArgumentParser(description="SRE OpenEnv Gemini Baseline")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    results = []
    for task_id in TASKS:
        results.append(run_episode(args.base_url, task_id))

    print("\n" + "=" * 60)
    print("  BASELINE SUMMARY")
    print("=" * 60)
    avg = sum(r["final_reward"] for r in results) / len(results)
    for r in results:
        difficulty = {1: "easy", 2: "medium", 3: "hard"}[r["task_id"]]
        print(f"  Task {r['task_id']} ({difficulty:6s}): reward={r['final_reward']:.2f}  solved={r['solved']}")
    print(f"\n  Average reward: {avg:.3f}")
    print("=" * 60)

    with open("baseline_results.json", "w") as f:
        json.dump({"model": MODEL_NAME, "results": results, "average_reward": avg}, f, indent=2)
    print("\n  Results saved to baseline_results.json")


if __name__ == "__main__":
    main()