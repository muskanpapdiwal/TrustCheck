import os
import sys

# Ensure the project root directory is in Python's search path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app as flask_app


class VercelPathFixMiddleware:
    """
    Ensures that Vercel routes all client requests accurately to Flask
    by reading the original captured path from HTTP_X_FORWARDED_URI or PATH_INFO.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        forwarded = environ.get("HTTP_X_FORWARDED_URI")
        if forwarded:
            path = forwarded.split("?")[0]
            environ["PATH_INFO"] = path
        else:
            path = environ.get("PATH_INFO", "")
            for prefix in ("/api/index.py", "/api/index", "/api"):
                if path == prefix:
                    environ["PATH_INFO"] = "/"
                    break
                elif path.startswith(prefix + "/"):
                    environ["PATH_INFO"] = path[len(prefix):]
                    break
        return self.wsgi_app(environ, start_response)


app = VercelPathFixMiddleware(flask_app)
