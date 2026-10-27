"""Actual, receiver-approved file transfer over a trusted private LAN.

Security notes: HTTP is unencrypted. Use only on a trusted private Wi-Fi/LAN.
Each incoming file requires local receiver approval; max file size is bounded.
"""
from __future__ import annotations
import http.client
import json
import os
import queue
import re
import socket
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote
from urllib.request import Request, urlopen

PORT = 47831
MAX_FILE_BYTES = 200 * 1024 * 1024  # 200 MiB safety limit for this first LAN version
CHUNK_SIZE = 256 * 1024


def local_ip() -> str:
    """Best-effort LAN address for instructions; does not send traffic to that address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def safe_filename(name: str) -> str:
    name = Path(name.replace("\\", "/")).name
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name[:180] or "received_file"


class TransferReceiver:
    def __init__(self, inbox: Path | None = None, port: int = PORT):
        self.inbox = Path(inbox or (Path.home() / "AirLink Received"))
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.port = port
        self._lock = threading.Lock()
        self._offers: dict[str, dict] = {}
        self._pending: queue.Queue[str] = queue.Queue()
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "AirLinkLAN/1.0"
            def log_message(self, *_args):
                pass
            def send_json(self, code, obj):
                body = json.dumps(obj).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def do_GET(self):
                if self.path == "/health":
                    return self.send_json(200, {"app":"AirLink", "version":1, "name":socket.gethostname(), "max_bytes":MAX_FILE_BYTES})
                if self.path.startswith("/decision/"):
                    transfer_id = self.path.rsplit("/", 1)[-1]
                    with receiver._lock:
                        item = receiver._offers.get(transfer_id)
                        status = item["status"] if item else "unknown"
                    return self.send_json(200 if item else 404, {"status": status})
                return self.send_json(404, {"error":"not found"})
            def do_POST(self):
                if self.path == "/offer":
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        if length <= 0 or length > 16_384:
                            return self.send_json(400, {"error":"invalid offer size"})
                        data = json.loads(self.rfile.read(length).decode("utf-8"))
                        filename = safe_filename(str(data.get("filename", "file")))
                        size = int(data.get("size", -1))
                        sender = str(data.get("sender", "Another device"))[:80]
                        if size < 0 or size > MAX_FILE_BYTES:
                            return self.send_json(413, {"error":f"Max file size is {MAX_FILE_BYTES // (1024*1024)} MiB"})
                        transfer_id = uuid.uuid4().hex
                        with receiver._lock:
                            receiver._offers[transfer_id] = {"status":"pending", "filename":filename, "size":size, "sender":sender, "created":time.time()}
                        receiver._pending.put(transfer_id)
                        return self.send_json(200, {"id":transfer_id, "status":"pending"})
                    except Exception as exc:
                        return self.send_json(400, {"error":str(exc)[:160]})
                if self.path.startswith("/upload/"):
                    transfer_id = self.path.rsplit("/", 1)[-1]
                    with receiver._lock:
                        offer = receiver._offers.get(transfer_id)
                        if not offer or offer["status"] != "accepted":
                            return self.send_json(403, {"error":"receiver has not accepted this transfer"})
                        expected = int(offer["size"])
                        filename = offer["filename"]
                        offer["status"] = "receiving"
                    try:
                        length = int(self.headers.get("Content-Length", "-1"))
                        if length != expected or length > MAX_FILE_BYTES:
                            with receiver._lock: offer["status"] = "failed"
                            return self.send_json(400, {"error":"file size mismatch"})
                        target = receiver.inbox / filename
                        stem, suffix = target.stem, target.suffix
                        n = 1
                        while target.exists():
                            target = receiver.inbox / f"{stem} ({n}){suffix}"
                            n += 1
                        written = 0
                        with target.open("xb") as f:
                            while written < expected:
                                chunk = self.rfile.read(min(CHUNK_SIZE, expected - written))
                                if not chunk:
                                    raise ConnectionError("connection ended before file completed")
                                f.write(chunk)
                                written += len(chunk)
                        with receiver._lock:
                            offer["status"] = "complete"
                            offer["saved_path"] = str(target)
                        return self.send_json(200, {"status":"complete", "saved_path":str(target), "bytes":written})
                    except Exception as exc:
                        try:
                            with receiver._lock: offer["status"] = "failed"
                        except Exception: pass
                        return self.send_json(500, {"error":str(exc)[:180]})
                return self.send_json(404, {"error":"not found"})

        class Server(ThreadingHTTPServer):
            allow_reuse_address = True
            daemon_threads = True
        self.server = Server(("0.0.0.0", port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, name="AirLinkReceiver", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def next_pending(self):
        try:
            transfer_id = self._pending.get_nowait()
        except queue.Empty:
            return None
        with self._lock:
            offer = self._offers.get(transfer_id)
            if not offer or offer["status"] != "pending":
                return None
            return {"id":transfer_id, **offer}

    def decide(self, transfer_id: str, accept: bool):
        with self._lock:
            offer = self._offers.get(transfer_id)
            if offer and offer["status"] == "pending":
                offer["status"] = "accepted" if accept else "declined"

    def status(self, transfer_id: str):
        with self._lock:
            item = self._offers.get(transfer_id)
            return dict(item) if item else None


def _json_request(url: str, payload: dict | None = None, timeout=5) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type":"application/json"} if data is not None else {}
    req = Request(url, data=data, headers=headers, method="GET" if data is None else "POST")
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_receiver(host: str, port: int = PORT) -> dict:
    return _json_request(f"http://{host}:{port}/health", timeout=3)


def send_file(host: str, file_path: str, sender_name: str, events, job_id: str, port: int = PORT):
    """Offer, wait for user approval, then stream bytes in chunks in a worker thread."""
    path = Path(file_path)
    size = path.stat().st_size
    if not path.is_file():
        raise ValueError("Choose a regular file first.")
    if size > MAX_FILE_BYTES:
        raise ValueError(f"This first version supports files up to {MAX_FILE_BYTES // (1024*1024)} MiB.")
    base = f"http://{host}:{port}"
    events.progress.emit(job_id, "Contacting receiver…", 0)
    offer = _json_request(base + "/offer", {"filename":path.name, "size":size, "sender":sender_name}, timeout=8)
    transfer_id = offer["id"]
    events.progress.emit(job_id, "Waiting for the receiver to approve…", 0)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = _json_request(base + "/decision/" + transfer_id, timeout=5)
        status = result.get("status")
        if status == "accepted":
            break
        if status in ("declined", "unknown", "failed"):
            raise PermissionError("The receiver declined or the transfer request expired.")
        time.sleep(0.8)
    else:
        raise TimeoutError("No approval received within 2 minutes.")

    conn = http.client.HTTPConnection(host, port, timeout=30)
    try:
        conn.putrequest("POST", "/upload/" + transfer_id)
        conn.putheader("Content-Type", "application/octet-stream")
        conn.putheader("Content-Length", str(size))
        conn.endheaders()
        sent = 0
        with path.open("rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                conn.send(chunk)
                sent += len(chunk)
                pct = 100 if size == 0 else int(sent * 100 / size)
                events.progress.emit(job_id, f"Sending {path.name}… {sent:,} / {size:,} bytes", pct)
        response = conn.getresponse()
        reply = json.loads(response.read().decode("utf-8"))
        if response.status != 200 or reply.get("status") != "complete":
            raise RuntimeError(reply.get("error", f"Receiver returned HTTP {response.status}"))
        events.progress.emit(job_id, "Transfer complete", 100)
        events.finished.emit(job_id, True, f"Sent {path.name} to {host}. The receiver saved it to: {reply.get('saved_path', 'AirLink Received')}.")
    finally:
        conn.close()
