"""Local web demo: a single HTML page that streams the pipeline trace of one question.

`serve` is what `text2sql demo` runs; `create_app` builds the FastAPI app around any object
with `Pipeline.run`'s signature, which is how the tests drive it. Design notes: ADR-019.
"""

from text2sql.web.app import DemoServices, create_app
from text2sql.web.server import build_services, serve

__all__ = ["DemoServices", "build_services", "create_app", "serve"]
