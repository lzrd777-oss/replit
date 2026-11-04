"""Serve the imported website without exposing workspace or configuration files."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent
PUBLIC_DIRECTORIES = {"_next", "bg", "brand", "storage"}
PUBLIC_FILES = {"index.html", "hhc-store-logo.svg", "icon.svg", "age-gate.js"}


class WebsiteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_head(self):
        path = unquote(urlsplit(self.path).path)
        if path in {"/", "/bg", "/bg/", "/bg.html"}:
            path = "/index.html"
        candidate = (ROOT / path.lstrip("/")).resolve()
        try:
            relative = candidate.relative_to(ROOT)
        except ValueError:
            self.send_error(404)
            return None
        if not relative.parts or (
            relative.parts[0] not in PUBLIC_DIRECTORIES
            and relative.as_posix() not in PUBLIC_FILES
        ) or any(part.startswith(".") for part in relative.parts):
            self.send_error(404)
            return None
        if not candidate.is_file() and not candidate.suffix:
            candidate = candidate.with_suffix(".html")
        if not candidate.is_file():
            self.send_error(404, "This file was not included in the website import.")
            return None
        if candidate.suffix == ".html":
            content = candidate.read_bytes().replace(
                b"</body>",
                b'<script src="/age-gate.js" defer></script></body>',
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            return BytesIO(content)
        self.path = "/" + candidate.relative_to(ROOT).as_posix()
        return super().send_head()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 5000), WebsiteHandler)
    print("Imported website running on port 5000", flush=True)
    server.serve_forever()
