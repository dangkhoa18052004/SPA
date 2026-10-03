import signal

import run_dev


def configure_launcher(monkeypatch):
    monkeypatch.setattr(run_dev, 'load_dotenv', lambda *a: None)
    monkeypatch.setenv('RESEND_API_KEY', 'launcher-test-key')
    handlers = {}
    monkeypatch.setattr(run_dev.signal, 'signal', lambda number, handler: handlers.setdefault(number, handler))
    return handlers


class Child:
    def __init__(self, pid, exit_code=None):
        self.pid = pid
        self.exit_code = exit_code
        self.stopped = False

    def poll(self):
        return self.exit_code

    def send_signal(self, number):
        self.stopped = True
        self.exit_code = 0

    def wait(self, timeout):
        return self.exit_code


def test_launcher_refuses_to_start_web_without_worker_key(monkeypatch):
    configure_launcher(monkeypatch)
    monkeypatch.delenv('RESEND_API_KEY')
    starts = []
    monkeypatch.setattr(run_dev.subprocess, 'Popen', lambda *a, **kw: starts.append(a))
    assert run_dev.run() == 1
    assert not starts


def test_launcher_stops_web_when_worker_exits(monkeypatch):
    configure_launcher(monkeypatch)
    children = [Child(100, 1), Child(200)]
    starts = []
    monkeypatch.setattr(run_dev.subprocess, 'Popen', lambda command, **kw: starts.append(command) or children[len(starts)-1])
    if run_dev.os.name != 'nt':
        monkeypatch.setattr(run_dev.os, 'killpg', lambda pid, number: children[1].send_signal(number))
    assert run_dev.run() == 1
    assert children[1].stopped
    assert len(starts) == 2


def test_launcher_ctrl_c_stops_both_and_starts_only_one_worker(monkeypatch):
    handlers = configure_launcher(monkeypatch)
    children = [Child(100), Child(200)]
    starts = []
    monkeypatch.setattr(run_dev.subprocess, 'Popen', lambda command, **kw: starts.append(command) or children[len(starts)-1])
    monkeypatch.setattr(run_dev.time, 'sleep', lambda seconds: handlers[signal.SIGINT](signal.SIGINT, None))
    if run_dev.os.name != 'nt':
        monkeypatch.setattr(run_dev.os, 'killpg', lambda pid, number: next(child for child in children if child.pid == pid).send_signal(number))
    assert run_dev.run(appointment_id=64) == 0
    assert all(child.stopped for child in children)
    assert sum('notification-worker' in command for command in starts) == 1
    assert starts[0][-2:] == ['--appointment-id', '64']
