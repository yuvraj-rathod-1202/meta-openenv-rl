from app.environment import SREEnvironment
from app.models import Action


def _env(task_id: int) -> SREEnvironment:
    e = SREEnvironment()
    e.reset(task_id=task_id)
    return e


def test_task1_initial_reward_is_zero():
    e = _env(1)
    _, r = e.step(Action(command="ls /"))
    assert r.value == 0.0


def test_task1_status_gives_partial_reward():
    e = _env(1)
    e.step(Action(command="systemctl status nginx"))
    _, r = e.step(Action(command="ls /"))
    assert r.value == 0.5


def test_task1_solved_on_start():
    e = _env(1)
    e.step(Action(command="systemctl status nginx"))
    _, r = e.step(Action(command="systemctl start nginx"))
    assert r.value == 1.0
    assert r.done is True


def test_task1_solved_without_status_check():
    e = _env(1)
    _, r = e.step(Action(command="systemctl start nginx"))
    assert r.value == 1.0
    assert r.done is True


def test_task2_kill_rogue_gives_0_3():
    e = _env(2)
    _, r = e.step(Action(command="kill -9 8821"))
    assert r.value == 0.3


def test_task2_full_solve():
    e = _env(2)
    e.step(Action(command="kill -9 8821"))
    _, r = e.step(Action(command="systemctl start postgresql"))
    assert r.value == 1.0
    assert r.done is True


def test_task2_penalty_for_early_pg_restart():
    e = _env(2)
    e.step(Action(command="systemctl start postgresql"))
    _, r = e.step(Action(command="ls /"))
    assert r.value <= 0.2


def test_task2_penalized_agent_can_still_recover():
    e = _env(2)
    e.step(Action(command="systemctl start postgresql"))
    e.step(Action(command="kill -9 8821"))
    _, r = e.step(Action(command="systemctl start postgresql"))
    assert r.value == 1.0
    assert r.done is True


def test_task3_clear_disk_gives_0_3():
    e = _env(3)
    _, r = e.step(Action(command="> /var/log/app-debug.log"))
    assert r.value == 0.3


def test_task3_app_fails_with_bad_config():
    e = _env(3)
    e.step(Action(command="> /var/log/app-debug.log"))
    _, r = e.step(Action(command="systemctl start app"))
    assert r.done is False


def test_task3_full_solve_with_echo():
    e = _env(3)
    e.step(Action(command="> /var/log/app-debug.log"))
    e.step(Action(command="echo '}' >> /etc/app/config.json"))
    _, r = e.step(Action(command="systemctl start app"))
    assert r.value == 1.0
    assert r.done is True


def test_task3_full_solve_with_sed():
    e = _env(3)
    e.step(Action(command="rm /var/log/app-debug.log"))
    e.step(Action(command="sed -i 's/broken/fixed/' /etc/app/config.json"))
    _, r = e.step(Action(command="systemctl start app"))
    assert r.value == 1.0
    assert r.done is True


def test_step_after_done_returns_done():
    e = _env(1)
    e.step(Action(command="systemctl start nginx"))
    _, r2 = e.step(Action(command="ls /"))
    assert r2.done is True


def test_max_steps_ends_episode():
    e = _env(1)
    for _ in range(30):
        _, r = e.step(Action(command="ls /"))
    assert r.done is True


def test_reset_clears_state():
    e = _env(1)
    e.step(Action(command="systemctl start nginx"))
    e.reset(task_id=1)
    assert e._step_count == 0
    assert e._done is False
    services = e._state.get("mock_services", {})
    assert services.get("nginx") == "inactive (dead)"