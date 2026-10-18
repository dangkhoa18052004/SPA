"""Local HTTPS for development (GPS on LAN phones needs a secure origin).

The certificate is reused so Flask reloads do not invalidate open tabs.

Werkzeug wraps the *listening* socket, so by default the TLS handshake runs inside accept() on the
single serving thread. One client that connects but never finishes the handshake — a phone sitting
on the certificate warning, a browser's speculative pre-connection, or http:// typed on this port —
then blocks every other request until it gives up. Here the handshake is deferred to the
per-connection thread and idle connections time out, so one stuck client cannot stall the server.
"""
from pathlib import Path
import socket
import ssl

from werkzeug.serving import WSGIRequestHandler, make_ssl_devcert

# Seconds a connection may stay silent (handshake or request) before it is dropped.
CONNECTION_TIMEOUT = 15


class _DeferredHandshakeContext(ssl.SSLContext):
    def wrap_socket(self, sock, *args, **kwargs):
        # Accepted connections inherit this, so the handshake happens on first read in the
        # connection's own thread instead of in the shared accept loop.
        kwargs['do_handshake_on_connect'] = False
        return super().wrap_socket(sock, *args, **kwargs)


PLAIN_HTTP = (b'GET ', b'POST', b'HEAD', b'PUT ', b'DELE', b'OPTI', b'PATC')


class TimeoutRequestHandler(WSGIRequestHandler):
    """Drop silent connections and treat a failed handshake as a closed connection, not a crash."""
    timeout = CONNECTION_TIMEOUT

    def _redirect_plain_http(self):
        """http:// typed on the HTTPS port: answer with a redirect instead of a dead connection."""
        raw = socket.socket  # bypass TLS: the handshake has not started yet
        try:
            if raw.recv(self.request, 4, socket.MSG_PEEK) not in PLAIN_HTTP:
                return False
            head = raw.recv(self.request, 8192).decode('latin-1')
            line, _, rest = head.partition('\r\n')
            path = line.split(' ')[1] if line.count(' ') >= 2 else '/'
            host = next((h.split(':', 1)[1].strip() for h in rest.split('\r\n') if h.lower().startswith('host:')), '')
            location = f'https://{host}{path if path.startswith("/") else "/"}'
            body = f'Use HTTPS: {location}\n'.encode()
            raw.sendall(self.request, (f'HTTP/1.1 301 Moved Permanently\r\nLocation: {location}\r\nContent-Length: {len(body)}\r\n'
                                       'Connection: close\r\n\r\n').encode('latin-1') + body)
            return True
        except OSError:
            return True

    def handle(self):
        if self._redirect_plain_http():
            return
        try:
            super().handle()
        except (ssl.SSLError, TimeoutError, ConnectionError, OSError) as error:
            # Plain HTTP on the HTTPS port, an untrusted certificate the user has not accepted
            # yet, or a client that went away: nothing to answer, keep serving others.
            self.log('info', 'connection closed during TLS: %s', type(error).__name__)


def certificate_paths(instance_path):
    """Create the self-signed certificate once and reuse it on every reload."""
    directory = Path(instance_path)
    directory.mkdir(parents=True, exist_ok=True)
    base = directory / 'dev-localhost'
    cert, key = str(base) + '.crt', str(base) + '.key'
    if not Path(cert).is_file() or not Path(key).is_file():
        make_ssl_devcert(str(base), host='localhost')
    return cert, key


def ssl_context(instance_path):
    cert, key = certificate_paths(instance_path)
    context = _DeferredHandshakeContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    return context
