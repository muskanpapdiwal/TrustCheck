import os
import sys

# Ensure the project root directory is in Python's search path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app as flask_app


class VercelPathFixMiddleware:
    """
    Normalizes PATH_INFO so Flask correctly matches routes regardless of
    whether Vercel forwards the rewritten destination (/api/index.py) or the
    original client URL, using Vercel's HTTP_X_MATCHED_PATH header when available.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        original_path = environ.get("HTTP_X_MATCHED_PATH") or environ.get("HTTP_X_FORWARDED_URI")
        if original_path:
            path_only = original_path.split("?")[0]
            for prefix in ("/api/index.py", "/api/index", "/api"):
                if path_only == prefix:
                    path_only = "/"
                    break
                elif path_only.startswith(prefix + "/"):
                    path_only = path_only[len(prefix):]
                    break
            environ["PATH_INFO"] = path_only
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
