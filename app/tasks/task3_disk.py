def build_initial_state() -> dict:
    return {
        "mock_filesystem": {
            "/var/log/app-debug.log": "[HUGE FILE — 50GB of debug output]",
            "/var/log/syslog": "Jan 15 04:01:12 kernel: EXT4-fs error: No space left",
            "/etc/app/config.json": '{\n  "db_host": "localhost",\n  "db_port": 5432,\n  "api_key": "secret123"\n',
            "/usr/local/bin/start_app": "#!/bin/bash\npython3 /opt/app/server.py",
        },
        "mock_processes": [
            {"pid": 1, "name": "systemd", "cpu": 0.1, "mem": 0.5},
            {"pid": 2, "name": "sshd", "cpu": 0.0, "mem": 0.3},
        ],
        "mock_services": {
            "nginx": "active (running)",
            "sshd": "active (running)",
            "postgresql": "active (running)",
            "app": "failed",
        },
        "mock_memory": {
            "total_mb": 8192, "used_mb": 2000, "free_mb": 6192, "available_mb": 6000
        },
        "mock_disk": {
            "/": {"total": "50G", "used": "20G", "avail": "30G", "use_pct": 40},
            "/var": {"total": "20G", "used": "20G", "avail": "0G", "use_pct": 100},
        },
        "disk_cleared": False,
        "config_fixed": False,
        "active_alerts": [
            "CRITICAL: No space left on device — API returning 500s",
            "ERROR: app service failed to start",
        ],
    }