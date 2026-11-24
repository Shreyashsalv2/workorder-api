"""Entry point for Vercel, gunicorn (Docker) and `flask run`."""
from pathlib import Path

from flask import send_from_directory

from workorders import create_app

app = create_app()
PUBLIC = Path(__file__).resolve().parent / "public"

# Vercel serves public/ from its CDN and leaves it out of the Python function;
# locally and in Docker the API serves the demo page itself.
if (PUBLIC / "index.html").is_file():
    @app.get("/")
    def index():
        return send_from_directory(PUBLIC, "index.html")
