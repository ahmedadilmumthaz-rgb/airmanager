from __future__ import annotations

"""
AirManager Central Backend — FastAPI Application Entrypoint & Built-in HTTP Server Fallback.
Run with Uvicorn in Ubuntu production:
    uvicorn app.main:app --host 127.0.0.1 --port 8000
Or run directly with standard library HTTP server for local dev:
    python3 -m app.main
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.services.dispatcher import AirManagerDispatcher

dispatcher = AirManagerDispatcher()

try:
    from fastapi import FastAPI, Header, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, StreamingResponse

    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        description="Ubiquiti airOS 8 Multi-Subnet Network & Connected Client Manager",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/events/stream")
    async def sse_events_stream() -> StreamingResponse:
        async def event_generator():
            summary = dispatcher.repo.get_dashboard_summary()
            yield f"event: summary\ndata: {json.dumps(summary['kpis'])}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def catch_all_api(request: Request, full_path: str) -> JSONResponse:
        body_bytes = await request.body()
        body_json: dict[str, Any] | None = None
        if body_bytes:
            try:
                body_json = json.loads(body_bytes.decode("utf-8"))
            except Exception as exc:
                raise HTTPException(status_code=400, detail="Invalid JSON request body") from exc

        path_with_query = request.url.path
        if request.url.query:
            path_with_query = f"{path_with_query}?{request.url.query}"

        status_code, response_data = dispatcher.handle_request(
            method=request.method,
            path_with_query=path_with_query,
            body=body_json,
            headers=dict(request.headers),
        )
        return JSONResponse(status_code=status_code, content=response_data)

except ImportError:
    app = None  # type: ignore


class _StdlibHTTPHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Agent-Token")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/v1/events/stream"):
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            summary = dispatcher.repo.get_dashboard_summary()
            payload = f"event: summary\ndata: {json.dumps(summary['kpis'])}\n\n"
            self.wfile.write(payload.encode("utf-8"))
            return
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._handle("POST")

    def do_DELETE(self) -> None:  # noqa: N802
        self._handle("DELETE")

    def _handle(self, method: str) -> None:
        content_len = int(self.headers.get("Content-Length", "0") or "0")
        body_json: dict[str, Any] | None = None
        if content_len > 0:
            raw = self.rfile.read(content_len)
            try:
                body_json = json.loads(raw.decode("utf-8"))
            except Exception:
                self.send_response(400)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"detail":"Invalid JSON body"}')
                return

        hdrs = {k.lower(): v for k, v in self.headers.items()}
        status_code, resp = dispatcher.handle_request(
            method=method,
            path_with_query=self.path,
            body=body_json,
            headers=hdrs,
        )
        encoded = json.dumps(resp).encode("utf-8")
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return


def run_stdlib_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), _StdlibHTTPHandler)
    print(f"AirManager Backend listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    run_stdlib_server(host="127.0.0.1", port=port)
