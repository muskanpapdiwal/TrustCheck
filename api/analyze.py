import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app as flask_app


class AnalyzeMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        environ["PATH_INFO"] = "/analyze"
        return self.wsgi_app(environ, start_response)


app = AnalyzeMiddleware(flask_app)
