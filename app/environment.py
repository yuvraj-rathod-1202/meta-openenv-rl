"""
SREEnvironment - Core RL environment for SRE incident response.

This module simulates a production Linux server where agents must diagnose
and resolve incidents by issuing shell commands. The environment manages:
- Mock filesystem, processes, services, and memory
- Command execution and output simulation
- Task-specific grading and reward calculation
- Episode state management

Example:
    >>> env = SREEnvironment()
    >>> obs = env.reset(task_id=1)  # Start easy task (nginx)
    >>> obs, reward = env.step(Action(command="systemctl status nginx"))
    >>> print(reward.value)  # 0.5 (partial credit for checking status)
"""

import json
import re
from copy import deepcopy
from typing import Tuple

from app.models import Action, EnvironmentState, Observation, Reward
from app.tasks.task1_nginx import build_initial_state as t1_state
from app.tasks.task2_oom import build_initial_state as t2_state
from app.tasks.task3_disk import build_initial_state as t3_state

MAX_STEPS = 30


class SREEnvironment:
    """
    RL environment simulating SRE incident response on a mock Linux server.

    Tasks:
    - Task 1 (Easy): Restart crashed nginx web server
    - Task 2 (Medium): Kill rogue process, restart PostgreSQL
    - Task 3 (Hard): Clear full disk, fix corrupted JSON config, restart app

    Attributes:
        _state (dict): Internal mock system state (filesystem, processes, services)
        _task_id (int): Current task (1, 2, or 3)
        _step_count (int): Steps taken in current episode
        _done (bool): Whether episode has ended
        _current_reward (float): Reward from last step
    """

    def __init__(self):
        self._state: dict = {}
        self._task_id: int = 1
        self._step_count: int = 0
        self._done: bool = False
        self._current_reward: float = 0.0
        self._checked_nginx_status: bool = False
        self._attempted_pg_restart: bool = False
        self._pg_restart_before_kill: bool = False
        self._config_read_after_disk_clear: bool = False

    def reset(self, task_id: int = 1) -> Observation:
        assert task_id in (1, 2, 3), "task_id must be 1, 2, or 3"
        self._task_id = task_id
        self._step_count = 0
        self._done = False
        self._current_reward = 0.0
        self._checked_nginx_status = False
        self._attempted_pg_restart = False
        self._pg_restart_before_kill = False
        self._config_read_after_disk_clear = False

        builders = {1: t1_state, 2: t2_state, 3: t3_state}
        self._state = deepcopy(builders[task_id]())

        return self._make_observation(
            stdout="Environment reset. You are logged in as root@prod-server-01.",
            stderr="",
        )

    def step(self, action: Action) -> Tuple[Observation, Reward]:
        if self._done:
            obs = self._make_observation(
                stdout="", stderr="Episode is already done. Call /reset to start a new episode."
            )
            return obs, self._make_reward(done=True, info={"reason": "already_done"})

        self._step_count += 1
        stdout, stderr = self._execute_command(action.command)
        reward_obj = self._grade()

        if self._step_count >= MAX_STEPS and not self._done:
            self._done = True
            reward_obj = self._make_reward(done=True, info={"reason": "max_steps_reached"})

        obs = self._make_observation(stdout=stdout, stderr=stderr)
        return obs, reward_obj

    def state(self) -> EnvironmentState:
        return EnvironmentState(
            task_id=self._task_id,
            step_count=self._step_count,
            done=self._done,
            current_reward=self._current_reward,
            mock_filesystem=deepcopy(self._state.get("mock_filesystem", {})),
            mock_processes=deepcopy(self._state.get("mock_processes", [])),
            mock_services=deepcopy(self._state.get("mock_services", {})),
            mock_memory=deepcopy(self._state.get("mock_memory", {})),
            active_alerts=deepcopy(self._state.get("active_alerts", [])),
        )

    def _execute_command(self, command: str) -> Tuple[str, str]:
        cmd = command.strip()

        if re.match(r"^ls\b", cmd):
            return self._cmd_ls(cmd)
        if re.match(r"^cat\b", cmd):
            return self._cmd_cat(cmd)
        if re.match(r"^df\b", cmd):
            return self._cmd_df(cmd)
        if re.match(r"^du\b", cmd):
            return self._cmd_du(cmd)

        if re.match(r"^ps\b", cmd):
            return self._cmd_ps(cmd)
        if re.match(r"^(top|htop|free)\b", cmd):
            return self._cmd_memory(cmd)

        if re.match(r"^kill\b", cmd):
            return self._cmd_kill(cmd)

        if re.match(r"^systemctl\b", cmd):
            return self._cmd_systemctl(cmd)

        if re.match(r"^>\s+\S", cmd):
            return self._cmd_truncate(cmd)
        if re.match(r"^rm\b", cmd):
            return self._cmd_rm(cmd)
        if re.match(r"^(echo|sed)\b", cmd):
            return self._cmd_write(cmd)

        return "", f"bash: {cmd.split()[0]}: command not found"

    def _cmd_ls(self, cmd: str) -> Tuple[str, str]:
        parts = cmd.split()
        path = next((p for p in reversed(parts) if p.startswith("/")), "/")
        fs = self._state.get("mock_filesystem", {})
        entries = [k for k in fs if k.startswith(path)]
        if not entries:
            return "", f"ls: cannot access '{path}': No such file or directory"
        names = sorted(set(e[len(path):].lstrip("/").split("/")[0] for e in entries))
        return "\n".join(names), ""

    def _cmd_cat(self, cmd: str) -> Tuple[str, str]:
        parts = cmd.split()
        path = parts[-1] if len(parts) > 1 else ""
        fs = self._state.get("mock_filesystem", {})
        if path in fs:
            if self._task_id == 3 and path == "/etc/app/config.json":
                disk = self._state.get("mock_disk", {})
                if disk.get("/var", {}).get("use_pct", 100) < 80:
                    self._config_read_after_disk_clear = True
            return fs[path], ""
        return "", f"cat: {path}: No such file or directory"

    def _cmd_df(self, cmd: str) -> Tuple[str, str]:
        disk = self._state.get("mock_disk", {})
        lines = ["Filesystem      Size  Used Avail Use% Mounted on"]
        for mount, d in disk.items():
            lines.append(
                f"/dev/sda1       {d['total']:>4}  {d['used']:>3}  {d['avail']:>4} {d['use_pct']:>3}% {mount}"
            )
        return "\n".join(lines), ""

    def _cmd_du(self, cmd: str) -> Tuple[str, str]:
        fs = self._state.get("mock_filesystem", {})
        lines = []
        for path, content in fs.items():
            if "/var/log" in path:
                size = "50G" if "HUGE" in content else "12K"
                lines.append(f"{size}\t{path}")
        return ("\n".join(lines) if lines else "0\t/var/log"), ""

    def _cmd_ps(self, cmd: str) -> Tuple[str, str]:
        procs = self._state.get("mock_processes", [])
        lines = ["USER       PID %CPU %MEM    COMMAND"]
        for p in procs:
            lines.append(f"root  {p['pid']:>6} {p['cpu']:>4.1f} {p['mem']:>4.1f}    {p['name']}")
        return "\n".join(lines), ""

    def _cmd_memory(self, cmd: str) -> Tuple[str, str]:
        m = self._state.get("mock_memory", {})
        output = (
            f"              total        used        free\n"
            f"Mem:          {m.get('total_mb', 0):>6}      {m.get('used_mb', 0):>6}      {m.get('free_mb', 0):>6}\n"
            f"Swap:              0           0           0"
        )
        return output, ""

    def _cmd_kill(self, cmd: str) -> Tuple[str, str]:
        parts = cmd.split()
        pid_str = parts[-1]
        if not pid_str.isdigit():
            return "", f"kill: {pid_str}: arguments must be process or job IDs"
        pid = int(pid_str)
        procs = self._state.get("mock_processes", [])
        target = next((p for p in procs if p["pid"] == pid), None)
        if target is None:
            return "", f"kill: ({pid}) - No such process"
        procs.remove(target)
        self._state["mock_processes"] = procs
        if target["name"] == "data_export.py":
            m = self._state["mock_memory"]
            freed = int(m["total_mb"] * (target["mem"] / 100))
            m["used_mb"] = max(0, m["used_mb"] - freed)
            m["free_mb"] = m["total_mb"] - m["used_mb"]
            m["available_mb"] = m["free_mb"]
        return f"Killed process {pid} ({target['name']})", ""

    def _cmd_systemctl(self, cmd: str) -> Tuple[str, str]:
        parts = cmd.split()
        if len(parts) < 3:
            return "", "Usage: systemctl <action> <service>"
        action = parts[1]
        service = parts[2]

        services = self._state.get("mock_services", {})
        if service not in services:
            return "", f"Unit {service}.service could not be found."

        if action == "status":
            status = services[service]
            if service == "nginx":
                self._checked_nginx_status = True
            return (
                f"● {service}.service\n"
                f"   Loaded: loaded (/lib/systemd/system/{service}.service)\n"
                f"   Active: {status}\n",
                "",
            )

        if action in ("start", "restart"):
            return self._handle_service_start(service, services)

        if action == "stop":
            services[service] = "inactive (dead)"
            return f"Stopped {service}.service", ""

        return "", f"systemctl: unknown action '{action}'"

    def _handle_service_start(self, service: str, services: dict) -> Tuple[str, str]:
        if self._task_id == 2 and service == "postgresql":
            self._attempted_pg_restart = True
            rogue_alive = any(p["name"] == "data_export.py" for p in self._state.get("mock_processes", []))
            if rogue_alive:
                self._pg_restart_before_kill = True
                return (
                    "Job for postgresql.service failed. "
                    "See 'journalctl -xe' for details. "
                    "(OOM killer terminated postgresql immediately)",
                    "",
                )
            services["postgresql"] = "active (running)"
            self._state["active_alerts"] = [
                a for a in self._state["active_alerts"] if "postgresql" not in a.lower()
            ]
            return "Started postgresql.service", ""

        if self._task_id == 3 and service == "app":
            config = self._state.get("mock_filesystem", {}).get("/etc/app/config.json", "")
            try:
                json.loads(config)
            except json.JSONDecodeError as exc:
                return (
                    "Job for app.service failed.\n"
                    f"Error: Invalid JSON in /etc/app/config.json: {exc}\n"
                    "Hint: Check the config file for syntax errors.",
                    "",
                )
            var_disk = self._state.get("mock_disk", {}).get("/var", {})
            if var_disk.get("use_pct", 100) >= 95:
                return "Job for app.service failed. No space left on device.", ""
            services["app"] = "active (running)"
            self._state["active_alerts"] = []
            return "Started app.service", ""

        services[service] = "active (running)"
        if service == "nginx":
            self._state["active_alerts"] = []
            procs = self._state.setdefault("mock_processes", [])
            if not any(p["name"] == "nginx" for p in procs):
                procs.append({"pid": 9999, "name": "nginx", "cpu": 0.5, "mem": 1.2})
        return f"Started {service}.service", ""

    def _cmd_truncate(self, cmd: str) -> Tuple[str, str]:
        path = cmd.strip().lstrip(">").strip()
        fs = self._state.get("mock_filesystem", {})
        if path not in fs:
            return "", f"bash: {path}: No such file or directory"
        fs[path] = ""
        if "app-debug.log" in path:
            disk = self._state.get("mock_disk", {})
            if "/var" in disk:
                disk["/var"]["used"] = "2G"
                disk["/var"]["avail"] = "18G"
                disk["/var"]["use_pct"] = 10
            self._state["disk_cleared"] = True
        return f"Truncated {path}", ""

    def _cmd_rm(self, cmd: str) -> Tuple[str, str]:
        parts = cmd.split()
        path = parts[-1]
        fs = self._state.get("mock_filesystem", {})
        if path in fs:
            del fs[path]
            if "app-debug.log" in path:
                disk = self._state.get("mock_disk", {})
                if "/var" in disk:
                    disk["/var"]["used"] = "2G"
                    disk["/var"]["avail"] = "18G"
                    disk["/var"]["use_pct"] = 10
                self._state["disk_cleared"] = True
            return f"removed '{path}'", ""
        return "", f"rm: cannot remove '{path}': No such file or directory"

    def _cmd_write(self, cmd: str) -> Tuple[str, str]:
        fs = self._state.get("mock_filesystem", {})

        append_match = re.search(r"echo\s+'(.+?)'\s*>>\s*(/\S+)", cmd)
        if append_match:
            content, path = append_match.group(1), append_match.group(2)
            if path in fs:
                fs[path] += "\n" + content
                if path == "/etc/app/config.json":
                    self._state["config_fixed"] = _is_valid_json(fs[path])
                return f"Appended to {path}", ""

        sed_match = re.search(r"sed\s+.*?(/etc/app/config\.json)", cmd)
        if sed_match:
            fs["/etc/app/config.json"] = (
                '{\n  "db_host": "localhost",\n'
                '  "db_port": 5432,\n'
                '  "api_key": "secret123"\n}'
            )
            self._state["config_fixed"] = True
            return "config.json updated", ""

        overwrite_match = re.search(r"echo\s+'(.+?)'\s*>\s*(/\S+)", cmd)
        if overwrite_match:
            content, path = overwrite_match.group(1), overwrite_match.group(2)
            if path in fs:
                fs[path] = content
                if path == "/etc/app/config.json":
                    self._state["config_fixed"] = _is_valid_json(content)
                return f"Wrote to {path}", ""

        return f"Executed: {cmd}", ""

    def _grade(self) -> Reward:
        graders = {1: self._grade_task1, 2: self._grade_task2, 3: self._grade_task3}
        return graders[self._task_id]()

    def _grade_task1(self) -> Reward:
        services = self._state.get("mock_services", {})
        nginx_running = services.get("nginx") == "active (running)"
        breakdown = {
            "checked_status": 0.5 if self._checked_nginx_status else 0.0,
            "nginx_running": 1.0 if nginx_running else 0.0,
        }
        value = 1.0 if nginx_running else (0.5 if self._checked_nginx_status else 0.0)
        done = nginx_running
        self._done = done
        self._current_reward = value
        if done:
            self._state["active_alerts"] = []
        return self._make_reward(done=done, info=breakdown)

    def _grade_task2(self) -> Reward:
        procs = self._state.get("mock_processes", [])
        services = self._state.get("mock_services", {})
        rogue_dead = not any(p["name"] == "data_export.py" for p in procs)
        pg_running = services.get("postgresql") == "active (running)"
        penalized = self._pg_restart_before_kill

        if pg_running and rogue_dead:
            value = 1.0
            done = True
        elif rogue_dead and self._attempted_pg_restart:
            value = 0.5
            done = False
        elif rogue_dead:
            value = 0.3
            done = False
        elif penalized:
            value = 0.2
            done = False
        else:
            value = 0.0
            done = False

        self._done = done
        self._current_reward = value
        breakdown = {
            "rogue_dead": rogue_dead,
            "pg_running": pg_running,
            "penalized": penalized,
            "attempted_pg_restart": self._attempted_pg_restart,
        }
        return self._make_reward(done=done, info=breakdown)

    def _grade_task3(self) -> Reward:
        disk = self._state.get("mock_disk", {})
        services = self._state.get("mock_services", {})
        var_pct = disk.get("/var", {}).get("use_pct", 100)
        disk_clear = var_pct < 80
        config_ok = self._state.get("config_fixed", False)
        config_read = self._config_read_after_disk_clear
        app_running = services.get("app") == "active (running)"

        if app_running and config_ok and disk_clear:
            value = 1.0
            done = True
        elif config_ok and disk_clear:
            value = 0.6
            done = False
        elif config_read and disk_clear:
            value = 0.6
            done = False
        elif disk_clear:
            value = 0.3
            done = False
        else:
            value = 0.0
            done = False

        self._done = done
        self._current_reward = value
        breakdown = {
            "disk_cleared": disk_clear,
            "config_fixed": config_ok,
            "config_read": config_read,
            "app_running": app_running,
        }
        return self._make_reward(done=done, info=breakdown)

    def _make_observation(self, stdout: str, stderr: str) -> Observation:
        return Observation(
            stdout=stdout,
            stderr=stderr,
            pwd="/root",
            active_alerts=self._state.get("active_alerts", []),
            step_count=self._step_count,
        )

    def _make_reward(self, done: bool, info: dict) -> Reward:
        return Reward(
            value=self._current_reward,
            breakdown=info,
            done=done,
            info={"task_id": self._task_id, "step_count": self._step_count},
        )


def _is_valid_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        return False