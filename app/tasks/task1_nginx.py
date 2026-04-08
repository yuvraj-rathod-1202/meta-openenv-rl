def build_initial_state() -> dict:
    return {
        "mock_filesystem": {
            "/etc/nginx/nginx.conf": "worker_processes auto;\nevents {}\nhttp { server { listen 80; } }",
            "/var/log/nginx/error.log": "2024-01-15 03:22:11 [crit] bind() to 0.0.0.0:80 failed",
            "/var/log/nginx/access.log": "",
        },
        "mock_processes": [
            {"pid": 1, "name": "systemd", "cpu": 0.1, "mem": 0.5},
            {"pid": 2, "name": "sshd", "cpu": 0.0, "mem": 0.3},
        ],
        "mock_services": {
            "nginx": "inactive (dead)",
            "sshd": "active (running)",
            "postgresql": "active (running)",
        },
        "mock_memory": {
            "total_mb": 8192, "used_mb": 1200, "free_mb": 6992, "available_mb": 6800
        },
        "mock_disk": {
            "/": {"total": "50G", "used": "20G", "avail": "30G", "use_pct": 40},
            "/var": {"total": "20G", "used": "5G", "avail": "15G", "use_pct": 25},
            "/var/log": {"total": "10G", "used": "1G", "avail": "9G", "use_pct": 10},
        },
        "active_alerts": ["CRITICAL: 502 Bad Gateway — load balancer reports nginx is down"],
    }