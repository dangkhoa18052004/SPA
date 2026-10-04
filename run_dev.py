"""Run the web server and notification worker as two supervised processes."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent


def stop_process(process):
    if process.poll() is not None:
        return
    try:
        if os.name == 'nt':
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        if os.name == 'nt':
            # Restrict cleanup to the child tree launched by this supervisor.
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def run(interval=15, appointment_id=None):
    load_dotenv(ROOT / '.env')
    if not os.getenv('RESEND_API_KEY', '').strip():
        print('RESEND_API_KEY is not configured for notification worker.', file=sys.stderr)
        return 1
    worker = [sys.executable, '-u', '-m', 'flask', '--app', 'wsgi:app',
              'notification-worker', '--interval', str(interval)]
    if appointment_id is not None:
        worker += ['--appointment-id', str(appointment_id)]
    commands = [('worker', worker), ('web', [sys.executable, '-u', 'run.py', '--web-only'])]
    options = dict(cwd=ROOT, env=dict(os.environ, PYTHONUNBUFFERED='1'))
    if os.name == 'nt':
        options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options['start_new_session'] = True
    processes = []
    previous_handlers = {}

    def stop(signum, frame):
        raise KeyboardInterrupt

    try:
        for number in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[number] = signal.signal(number, stop)
        if hasattr(signal, 'SIGBREAK'):
            previous_handlers[signal.SIGBREAK] = signal.signal(signal.SIGBREAK, stop)
        for name, command in commands:
            process = subprocess.Popen(command, **options)
            processes.append((name, process))
            print(f'[run-dev] {name} started pid={process.pid}', flush=True)
        while True:
            for name, process in processes:
                code = process.poll()
                if code is not None:
                    print(f'[run-dev] {name} exited ({code}); stopping both processes.', flush=True)
                    return code or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print('[run-dev] Stopping web and worker...', flush=True)
        return 0
    finally:
        for _, process in reversed(processes):
            stop_process(process)
        for number, handler in previous_handlers.items():
            signal.signal(number, handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interval', type=int, choices=range(5, 301), metavar='5..300', default=15)
    parser.add_argument('--appointment-id', type=int, help='Restrict the worker to one integration-test appointment.')
    args = parser.parse_args()
    raise SystemExit(run(args.interval, args.appointment_id))
