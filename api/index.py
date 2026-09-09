import os
import sys
from urllib.parse import parse_qs

# Ensure the project root directory is in Python's search path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app as flask_app


class VercelPathFixMiddleware:
    """
    Ensures that Vercel routes all client requests accurately to Flask
    by reading the original captured path from the __path__ query param or headers.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        query_string = environ.get("QUERY_STRING", "")
        params = parse_qs(query_string)
        if "__path__" in params:
            captured = params["__path__"][0].strip("/")
            environ["PATH_INFO"] = f"/{captured}"
        elif environ.get("HTTP_X_FORWARDED_URI"):
            environ["PATH_INFO"] = environ["HTTP_X_FORWARDED_URI"].split("?")[0]
        elif environ.get("PATH_INFO") in ("/api/index.py", "/api/index", "/api"):
            environ["PATH_INFO"] = "/"
        return self.wsgi_app(environ, start_response)


app = VercelPathFixMiddleware(flask_app)
