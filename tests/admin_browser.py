"""Shared headless-Chrome harness for admin React browser checks (run as scripts, not by pytest).

serve(app, tokens) starts the Flask app on a random port with one sqlite:// connection shared
safely (a lock serialises requests and the script's own DB checks), and injects the token for
app.config['BROWSER_ROLE'] into every HTML page.
"""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import urllib.request

import websocket
from werkzeug.serving import make_server, WSGIRequestHandler


class QuietHandler(WSGIRequestHandler):
    def log(self, *args, **kwargs):
        pass


class Harness:
    def __init__(self, app, tokens, artifacts: Path):
        self.app, self.tokens, self.artifacts = app, tokens, artifacts
        self.lock = threading.Lock()

        @app.after_request
        def bootstrap(response):
            if response.mimetype == 'text/html':
                token = tokens.get(app.config.get('BROWSER_ROLE'))
                init = ('localStorage.setItem("admin_token",' + json.dumps(token) + ');') if token else ''
                init += 'window.__uiErrors=[];window.addEventListener("error",e=>{if(e.message)window.__uiErrors.push(e.message)});'
                init += 'window.addEventListener("unhandledrejection",e=>window.__uiErrors.push(String(e.reason)));'
                response.set_data(response.get_data(as_text=True).replace('<head>', '<head><script>' + init + '</script>', 1))
            return response

        def serve_locked(environ, start_response):
            with self.lock:
                return list(app(environ, start_response))

        self.server = make_server('127.0.0.1', 0, serve_locked, threaded=False, request_handler=QuietHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        chrome = os.environ.get('CHROME_PATH') or shutil.which('google-chrome') or r'C:\Program Files\Google\Chrome\Application\chrome.exe'
        self.profile = artifacts / 'chrome-profile'
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        self.process = subprocess.Popen([chrome, '--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
            '--remote-allow-origins=*', '--remote-debugging-port=0', '--user-data-dir=' + str(self.profile), 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
        self.browser = Browser(self)

    def query(self, fn):
        """Read/write the database from the script without racing a request."""
        with self.lock, self.app.app_context():
            return fn()

    def close(self):
        self.process.terminate()
        self.server.shutdown()


class Browser:
    def __init__(self, harness):
        self.h = harness
        active = harness.profile / 'DevToolsActivePort'
        port = None
        for _ in range(100):
            try:
                port = int(active.read_text().splitlines()[0]); break
            except (OSError, IndexError, ValueError):  # Chrome may still be writing the file (Windows)
                time.sleep(.1)
        targets = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
        target = next(t for t in targets if t['type'] == 'page')
        self.ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=30)
        self.index = 0
        self.call('Page.enable')

    def call(self, method, params=None):
        self.index += 1
        self.ws.send(json.dumps(dict(id=self.index, method=method, params=params or {})))
        while True:
            response = json.loads(self.ws.recv())
            if response.get('id') == self.index:
                if response.get('error'):
                    raise RuntimeError(response['error'])
                return response.get('result', {})

    def js(self, expression):
        result = self.call('Runtime.evaluate', dict(expression=expression, returnByValue=True, awaitPromise=True))
        if result.get('exceptionDetails'):
            raise AssertionError(result['exceptionDetails'].get('exception', {}).get('description') or result['exceptionDetails'])
        return result.get('result', {}).get('value')

    def wait(self, expression, label=None, seconds=12):
        rounds = int(seconds / .05)
        for _ in range(20):
            try:
                return self.js(f"(async()=>{{for(let n=0;n<{rounds};n++){{try{{if({expression})return true;}}catch(e){{}}"
                               "await new Promise(r=>setTimeout(r,50));}throw new Error('UI wait: ' + " + json.dumps(label or expression) + ");})()")
            except RuntimeError as error:
                if 'navigated or closed' not in str(error):
                    raise
                time.sleep(.2)

    def navigate(self, path, ready="document.querySelector('.admin-shell h1')"):
        self.call('Page.navigate', dict(url=self.h.base + path))
        self.wait(f"document.readyState==='complete' && {ready} && !document.querySelector('.ant-skeleton')", 'page ' + path)

    def viewport(self, width):
        self.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=900, deviceScaleFactor=1, mobile=width < 768))

    def click(self, selector):
        point = {'covered': True}
        for _ in range(20):  # drawers/modals animate in; wait until the target is on top
            self.js(f'document.querySelector({json.dumps(selector)}).scrollIntoView({{block:"center",behavior:"instant"}})')
            time.sleep(.15)
            point = self.js(f'(()=>{{const e=document.querySelector({json.dumps(selector)}),r=e.getBoundingClientRect();const x=r.left+r.width/2,y=r.top+r.height/2,h=document.elementFromPoint(x,y);return {{x,y,covered:!(e===h||e.contains(h)||h?.contains(e))}}}})()')
            if not point['covered']:
                break
        if point['covered']:
            hit = self.js(f'(()=>{{const e=document.querySelector({json.dumps(selector)}),r=e.getBoundingClientRect();return document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)?.outerHTML.slice(0,200)}})()')
            raise AssertionError(f'Element covered: {selector} by {hit}')
        for kind in ['mousePressed', 'mouseReleased']:
            self.call('Input.dispatchMouseEvent', dict(type=kind, x=point['x'], y=point['y'], button='left', clickCount=1))

    def button(self, text, scope='document'):
        found = self.js(f"""(()=>{{const b=[...{scope}.querySelectorAll('button')].find(b=>b.offsetParent&&b.textContent.includes({json.dumps(text)})&&!b.disabled);
            if(!b)return false;b.setAttribute('data-click-target','1');return true}})()""")
        assert found, f'button not found: {text}'
        self.click('[data-click-target="1"]')
        self.js("document.querySelector('[data-click-target]')?.removeAttribute('data-click-target')")

    def type(self, selector, value):
        self.click(selector)
        self.js(f"document.querySelector({json.dumps(selector)}).select?.()")
        self.call('Input.insertText', dict(text=value))

    def key(self, name, code):
        for kind in ['keyDown', 'keyUp']:
            self.call('Input.dispatchKeyEvent', dict(type=kind, key=name, code=name, windowsVirtualKeyCode=code))

    def choose(self, aria, text, search=None):
        """Pick an antd Select option; searchable selects get `search` (or `text`) typed first."""
        selector = f'input[aria-label="{aria}"]'
        self.wait(f"document.querySelector({json.dumps(selector)})", aria)
        self.js(f"document.querySelector({json.dumps(selector)}).closest('.ant-select').querySelector('.ant-select-selector').dispatchEvent(new MouseEvent('mousedown',{{bubbles:true}}))")
        if not self.js(f"document.querySelector({json.dumps(selector)}).readOnly"):
            # A chosen value's label sits on top of the search input, so focus it directly.
            self.js(f"document.querySelector({json.dumps(selector)}).focus()")
            self.call('Input.insertText', dict(text=search or text))
        option = ".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option"
        self.wait(f"[...document.querySelectorAll('{option}')].some(o=>o.textContent.includes({json.dumps(text)}))", 'option ' + text)
        self.js(f"[...document.querySelectorAll('{option}')].find(o=>o.textContent.includes({json.dumps(text)})).click()")
        self.js("document.activeElement?.blur?.()")
        time.sleep(.2)

    def date(self, aria, value):
        """Set a native date input the way React notices (value setter + input/change events)."""
        self.js(f"""(()=>{{const i=document.querySelector('input[aria-label="{aria}"]');
            Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(i,{json.dumps(value)});
            i.dispatchEvent(new Event('input',{{bubbles:true}}));i.dispatchEvent(new Event('change',{{bubbles:true}}));}})()""")

    def confirm_modal(self, text):
        self.wait("document.querySelector('.ant-modal-confirm')", 'confirm dialog')
        self.button(text, "document.querySelector('.ant-modal-confirm')")
        self.wait("!document.querySelector('.ant-modal-confirm')", 'confirm closed')

    def close_modals(self):
        """Escape every open antd modal/drawer and wait until none is visible."""
        open_ = "[...document.querySelectorAll('.ant-modal-wrap,.ant-drawer-open')].some(w=>getComputedStyle(w).display!=='none'&&w.getBoundingClientRect().width>0)"
        for attempt in range(6):
            if not self.js(open_):
                return
            if attempt % 2:  # Esc only reaches a drawer that holds focus; use its close button too
                self.js("[...document.querySelectorAll('.ant-modal-close,.ant-drawer-close')].filter(b=>b.getBoundingClientRect().width>0).pop()?.click()")
            else:
                self.key('Escape', 27)
            time.sleep(.4)
        self.wait('!' + open_, 'modals closed')

    def upload(self, selector, path):
        """Put a local file into an <input type=file> (hidden inputs included) and fire change."""
        root = self.call('DOM.getDocument')['root']['nodeId']
        node = self.call('DOM.querySelector', dict(nodeId=root, selector=selector))['nodeId']
        self.call('DOM.setFileInputFiles', dict(nodeId=node, files=[str(path)]))

    def drop_response(self, url, method='POST'):
        """The next matching request reaches the server, but the page never sees the reply."""
        self.js(f"""(()=>{{const real=window.fetch;window.fetch=async(u,o)=>{{const r=await real(u,o);
            if(String(u)==={json.dumps(url)}&&(o?.method||'GET')==={json.dumps(method)}){{window.fetch=real;throw new TypeError('Failed to fetch');}}return r;}};}})()""")

    def screenshot(self, label):
        self.wait("!document.querySelector('.ant-skeleton')")
        time.sleep(.4)
        state = self.js('({width:innerWidth,scroll:document.documentElement.scrollWidth,errors:window.__uiErrors})')
        assert state['scroll'] <= state['width'] + 1, (label, state)
        assert not state['errors'], (label, state)
        image = self.call('Page.captureScreenshot', dict(format='png'))['data']
        (self.h.artifacts / f'{label}.png').write_bytes(base64.b64decode(image))
