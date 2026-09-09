import json
import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app as flask_app


class VercelPathFixMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        raw_env = " ".join(str(v) for v in environ.values() if isinstance(v, str))
        if "check-headers" in raw_env:
            start_response("200 OK", [("Content-Type", "application/json")])
            data = {k: str(v) for k, v in environ.items() if isinstance(v, (str, int, float, bool))}
            return [json.dumps(data, indent=2).encode("utf-8")]

        # Determine path
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
