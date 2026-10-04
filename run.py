from app import create_app
import argparse
import os

app = create_app()

def main(argv=None):
    parser = argparse.ArgumentParser(description='Run Bin Spa with automatic email processing.')
    parser.add_argument('--web-only', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.web_only and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        from run_dev import run
        return run()

    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
