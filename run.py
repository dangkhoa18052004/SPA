# run.py

from app import create_app
from waitress import serve 

app = create_app()

if __name__ == "__main__":
    if app.debug:
        app.run(debug=True)
    else:
        print("Serving production app with Waitress on port 8000...")
        serve(app, host='0.0.0.0', port=8000)