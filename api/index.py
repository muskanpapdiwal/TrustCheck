import os
import sys
from urllib.parse import parse_qs, urlencode

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app as flask_app


class VercelPathFixMiddleware:
    """
    Extracts the original request path passed by Vercel via the ?path=$1 query param
    and restores it into PATH_INFO for Flask's router.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        query_string = environ.get("QUERY_STRING", "")
        params = parse_qs(query_string)

        if "path" in params:
            raw_path = params["path"][0]
            environ["PATH_INFO"] = "/" + raw_path.lstrip("/")

            # Clean 'path' out of QUERY_STRING so Flask sees only original user query params
            remaining_params = {k: v for k, v in params.items() if k != "path"}
            environ["QUERY_STRING"] = urlencode(remaining_params, doseq=True)
        elif not environ.get("PATH_INFO") or environ.get("PATH_INFO") in ("/api/index", "/api/index.py"):
            environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


app = VercelPathFixMiddleware(flask_app)
