#!/usr/bin/env python3
"""
baseline.py - Run HF models against all 3 SRE OpenEnv tasks.

Usage:
    export HF_TOKEN="hf_your_token_here"
    python baseline.py

    # Against a remote HF Space:
    python baseline.py --base-url https://your-hf-space.hf.space
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

DEFAULT_BASE_URL = "http://localhost:7860"
MODEL_NAME = "google/flan-t5-base"
MAX_STEPS = 30
TASKS = [1, 2, 3]
TASK_NAMES = {1: "crashed-web-server", 2: "oom-database", 3: "disk-exhaustion-corrupted-config"}
API_RETRIES = 3
API_TIMEOUT = 30

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

hf_token = os.environ.get("HF_TOKEN")
USE_HF = False
client = None

try:
    from huggingface_hub import InferenceClient

    if hf_token:
        client = InferenceClient(model=MODEL_NAME, token=hf_token)
        USE_HF = True
        print(f"✓ Connected to Hugging Face Inference API")
        print(f"  Model: {MODEL_NAME}")
    else:
        print("HF_TOKEN not set; using deterministic fallback baseline.")
except Exception as exc:
    print(f"Could not initialize HF ({exc}); using deterministic fallback baseline.")




def _post_with_retry(
    client_http: httpx.Client, endpoint: str, json_data: dict, retries: int = API_RETRIES
) -> dict | None:
    """
    POST request with exponential backoff retry logic.

    Args:
        client_http: httpx Client instance
        endpoint: Endpoint path (e.g., "/step")
        json_data: Request body
        retries: Number of retry attempts

    Returns:
        Response JSON dict, or None if all retries failed
    """
    for attempt in range(retries):
        try:
            response = client_http.post(endpoint, json=json_data)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            if attempt == retries - 1:
                print(f"ERROR: Request timeout after {retries} attempts")
                return None
            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            print(f"Timeout on attempt {attempt + 1}/{retries}, retrying in {wait_time}s...")
            time.sleep(wait_time)
        except httpx.ConnectError as e:
            if attempt == retries - 1:
                print(f"ERROR: Could not connect to server (after {retries} attempts)")
                print(f"Make sure the server is running: uvicorn app.main:app --port 7860")
                return None
            wait_time = 2 ** attempt
            print(f"Connection failed on attempt {attempt + 1}/{retries}, retrying in {wait_time}s...")
            time.sleep(wait_time)
        except httpx.HTTPStatusError as e:
            print(f"ERROR: HTTP {e.response.status_code}: {e.response.text}")
            return None
        except json.JSONDecodeError:
            print(f"ERROR: Invalid JSON response from server")
            return None
        except Exception as e:
            if attempt == retries - 1:
                print(f"ERROR: Unexpected error: {e}")
                return None
            print(f"Error on attempt {attempt + 1}/{retries}: {e}, retrying...")
            time.sleep(1)

    return None


def run_episode(base_url: str, task_id: int) -> dict:
    """
    Run a single episode for the given task.

    Args:
        base_url: Base URL of environment server
        task_id: Task to run (1, 2, or 3)

    Returns:
        Dict with keys: task_id, final_reward, steps_taken, solved
    """
    try:
        client_http = httpx.Client(base_url=base_url, timeout=API_TIMEOUT)
    except Exception as e:
        print(f"ERROR: Failed to create HTTP client: {e}")
        return {
            "task_id": task_id,
            "final_reward": 0.0,
            "steps_taken": 0,
            "solved": False,
        }

    # Reset episode with query parameter, not json body
    obs_data = _post_with_retry(client_http, f"/reset?task_id={task_id}", {})
    if obs_data is None:
        print(f"ERROR: Failed to reset environment for task {task_id}")
        return {
            "task_id": task_id,
            "final_reward": 0.0,
            "steps_taken": 0,
            "solved": False,
        }

    obs = obs_data
    total_reward = 0.0
    done = False
    steps = 0

    task_name = TASK_NAMES[task_id]
    print(f"[START] task={task_name}", flush=True)
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

        command = None

        if USE_HF and client is not None:
            try:
                # Call HF Inference API using CHAT COMPLETION for instruct models like Llama
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
                
                response = client.chat_completion(
                    messages=messages,
                    max_tokens=256,
                    temperature=0.7,
                    top_p=0.9,
                )

                command = response.choices[0].message.content.strip().split("\n")[0].strip()
                command = command.strip("`").strip()

                # Validate command
                if not command or len(command) > 512:
                    raise ValueError(f"Invalid command: {command}")

            except Exception as e:
                print(f"  [DEBUG] LLM Pipeline crashed: {e}")
                command = None

        # Fallback if no command from LLM
        if command is None:
            command = "echo 'LLM failed to generate a command'"

        print(f"  Step {step_num:02d} -> command: {command!r}")

        # Execute step with retry logic
        step_resp = _post_with_retry(client_http, "/step", {"command": command})
        if step_resp is None:
            print(f"ERROR: Failed to execute step {step_num}, aborting task")
            break

        obs = step_resp.get("observation", obs)
        reward = step_resp.get("reward", {})
        steps = step_num

        total_reward = reward.get("value", 0.0)
        done = reward.get("done", False)

        print(f"           reward: {total_reward:.2f}  done: {done}")
        print(f"[STEP] step={step_num} reward={total_reward:.2f}", flush=True)

        if done:
            break

    client_http.close()

    result = {
        "task_id": task_id,
        "final_reward": total_reward,
        "steps_taken": steps,
        "solved": done and total_reward >= 0.99,
    }
    print(f"\n  RESULT task={task_id}: reward={total_reward:.2f}, steps={steps}, solved={result['solved']}")
    print(f"[END] task={task_name} score={total_reward:.2f} steps={steps}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description="SRE OpenEnv Baseline with HF Models")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL of environment server")
    args = parser.parse_args()

    # Verify server is reachable
    try:
        test_client = httpx.Client(base_url=args.base_url, timeout=5)
        test_client.get("/")
        test_client.close()
    except Exception as e:
        print(f"ERROR: Cannot reach server at {args.base_url}")
        print(f"Details: {e}")
        print(f"Make sure to start the server first:")
        print(f"uvicorn app.main:app --port 7860")
        sys.exit(1)

    print(f"✓ Server reachable at {args.base_url}")

    results = []
    for task_id in TASKS:
        try:
            results.append(run_episode(args.base_url, task_id))
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\nERROR in task {task_id}: {e}")
            results.append({
                "task_id": task_id,
                "final_reward": 0.0,
                "steps_taken": 0,
                "solved": False,
            })

    print("\n" + "=" * 60)
    print("  BASELINE SUMMARY")
    print("=" * 60)

    if not results or all(r["final_reward"] == 0.0 for r in results):
        print("All tasks failed. Check that:")
        print("1. Server is running: uvicorn app.main:app --port 7860")
        print("2. HF_TOKEN is set (export HF_TOKEN='your_token')")
        print("3. Network connection is stable")
        avg = 0.0
    else:
        avg = sum(r["final_reward"] for r in results) / len(results)

    for r in results:
        difficulty = {1: "easy", 2: "medium", 3: "hard"}[r["task_id"]]
        status = "✅" if r["solved"] else "❌"
        print(f"  Task {r['task_id']} ({difficulty:6s}): reward={r['final_reward']:.2f}  solved={r['solved']} {status}")

    print(f"\n  Average reward: {avg:.3f}")
    print("=" * 60)

    with open("baseline_results.json", "w") as f:
        json.dump({"model": MODEL_NAME, "results": results, "average_reward": avg}, f, indent=2)
    print("\n  ✓ Results saved to baseline_results.json")


if __name__ == "__main__":
    main()
