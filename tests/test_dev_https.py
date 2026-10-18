from pathlib import Path
import socket
import ssl
import threading
import time
import urllib.request

from flask import Flask
from werkzeug.serving import make_server

from dev_https import TimeoutRequestHandler, certificate_paths, ssl_context


def test_reload_reuses_certificate_and_key(tmp_path, monkeypatch):
    created = []
    def make(base, **kwargs):
        created.append(base)
        Path(base + '.crt').write_text('test-certificate')
        Path(base + '.key').write_text('test-private-key')
    monkeypatch.setattr('dev_https.make_ssl_devcert', make)
    assert certificate_paths(tmp_path) == certificate_paths(tmp_path)
    assert len(created) == 1


def test_stuck_client_does_not_block_other_requests(tmp_path):
    app = Flask(__name__)
    app.add_url_rule('/ping', 'ping', lambda: 'pong')
    server = make_server('127.0.0.1', 0, app, threaded=True, ssl_context=ssl_context(tmp_path), request_handler=TimeoutRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = ssl.create_default_context(); client.check_hostname = False; client.verify_mode = ssl.CERT_NONE
    url = f'https://127.0.0.1:{server.port}/ping'
    try:
        # A phone stuck on the certificate warning: TCP open, TLS never started.
        idle = socket.create_connection(('127.0.0.1', server.port))
        started = time.monotonic()
        assert urllib.request.urlopen(url, context=client, timeout=5).read() == b'pong'
        assert time.monotonic() - started < 3
        # http:// typed on the HTTPS port gets a redirect, and the server keeps serving.
        plain = socket.create_connection(('127.0.0.1', server.port), timeout=5)
        plain.sendall(b'GET /admin/login HTTP/1.1\r\nHost: 192.168.1.5:5000\r\n\r\n')
        answer = plain.recv(512)
        assert answer.startswith(b'HTTP/1.1 301') and b'Location: https://192.168.1.5:5000/admin/login' in answer
        assert urllib.request.urlopen(url, context=client, timeout=5).read() == b'pong'
        idle.close(); plain.close()
    finally:
        server.shutdown()
