from app import create_app
import argparse
import os

app = create_app()

def main(argv=None):
    parser = argparse.ArgumentParser(description='Run Bin Spa with automatic email processing.')
    parser.add_argument('--web-only', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--https', action='store_true', help='Serve HTTPS with a self-signed cert (GPS on LAN phones).')
    args = parser.parse_args(argv)
    if args.https:
        # Child processes spawned by run_dev inherit this.
        os.environ['DEV_HTTPS'] = '1'
    if not args.web_only and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        from run_dev import run
        return run()

    port = int(os.environ.get('PORT', 5000))
    debug = app.config.get('APP_ENV') != 'production' and os.environ.get('FLASK_ENV') != 'production'
    # Browsers only expose GPS on secure origins; DEV_HTTPS=1 serves a self-signed cert for LAN phones.
    options = {}
    if os.environ.get('DEV_HTTPS') == '1':
        from dev_https import TimeoutRequestHandler, ssl_context as development_ssl_context
        options = dict(ssl_context=development_ssl_context(app.instance_path), request_handler=TimeoutRequestHandler)
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True, **options)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
