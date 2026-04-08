def build_initial_state() -> dict:
    return {
        "mock_filesystem": {
            "/usr/local/bin/data_export.py": "# rogue export script\nimport time\nwhile True:\n    data = 'x' * (1024**3)\n    time.sleep(1)",
            "/var/log/postgresql/postgresql.log": "FATAL: out of memory\nDETAIL: Failed on request of size 131072.",
        },
        "mock_processes": [
            {"pid": 1, "name": "systemd", "cpu": 0.1, "mem": 0.5},
            {"pid": 2, "name": "sshd", "cpu": 0.0, "mem": 0.3},
            {"pid": 8821, "name": "data_export.py", "cpu": 12.0, "mem": 90.2},
        ],
        "mock_services": {
            "nginx": "active (running)",
            "sshd": "active (running)",
            "postgresql": "inactive (dead)",
        },
        "mock_memory": {
            "total_mb": 8192, "used_mb": 7990, "free_mb": 202, "available_mb": 150
        },
        "mock_disk": {
            "/": {"total": "50G", "used": "20G", "avail": "30G", "use_pct": 40},
            "/var": {"total": "20G", "used": "5G", "avail": "15G", "use_pct": 25},
        },
        "active_alerts": [
            "CRITICAL: High Memory Usage — DB Down",
            "WARNING: postgresql not responding to health checks",
        ],
    }