#!/usr/bin/env python3
"""Docker socket proxy for autobox.

Sits between Claude's Docker CLI and the real Docker daemon, inspecting
container creation requests and blocking dangerous configurations
(privileged mode, host PID namespace, sensitive bind mounts, etc.).

All other Docker API traffic passes through transparently, including
streaming responses (build output, logs) and connection upgrades
(docker exec -it).
"""

import json
import os
import re
import select
import signal
import socket
import sys
import threading

LISTEN_SOCK = "/var/run/docker.sock"
UPSTREAM_SOCK = "/var/run/docker-host.sock"
BUF_SIZE = 65536

HOST_WORKSPACE = os.environ.get("HOST_WORKSPACE", "")
CREATE_RE = re.compile(r"^(/v[\d.]+)?/containers/create")
MAX_CREATE_BODY = 10 * 1024 * 1024  # 10 MB sanity limit for create payloads


def log(msg):
    print(f"[docker-proxy] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Buffered socket reader — lets us parse HTTP line-by-line while tracking
# leftover bytes that haven't been consumed yet. drain() returns those
# leftovers so we can hand them off before switching to raw relay mode
# (needed for docker exec -it / connection upgrades).
# ---------------------------------------------------------------------------


class BufferedSocket:
    def __init__(self, sock):
        self.sock = sock
        self.buf = b""

    def _fill(self, minimum=1):
        while len(self.buf) < minimum:
            data = self.sock.recv(BUF_SIZE)
            if not data:
                return False
            self.buf += data
        return True

    def readline(self):
        while b"\n" not in self.buf:
            data = self.sock.recv(BUF_SIZE)
            if not data:
                result = self.buf
                self.buf = b""
                return result
            self.buf += data
        idx = self.buf.index(b"\n") + 1
        line, self.buf = self.buf[:idx], self.buf[idx:]
        return line

    def read(self, n):
        self._fill(n)
        result, self.buf = self.buf[:n], self.buf[n:]
        return result

    def drain(self):
        data, self.buf = self.buf, b""
        return data


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def is_path_blocked(host_path):
    """Return a reason string if this host path must not be bind-mounted, else None.

    Uses an allowlist approach: only paths under HOST_WORKSPACE are permitted.
    This is strictly stronger than a blocklist — symlinks, alternative names,
    and unanticipated paths are all blocked by default.
    """
    path = os.path.normpath(host_path)

    if path == "/":
        return "root filesystem"

    if HOST_WORKSPACE:
        ws = os.path.normpath(HOST_WORKSPACE)
        if path == ws or path.startswith(ws + "/"):
            return None

    return f"path not under allowed workspace ({HOST_WORKSPACE or 'unset'})"


def validate_create(body):
    """Check a container-creation payload. Return error message or None."""
    hc = body.get("HostConfig") or {}

    if hc.get("Privileged"):
        return "privileged mode is not allowed"

    if hc.get("PidMode") == "host":
        return "host PID namespace is not allowed"

    caps = [c.upper() for c in (hc.get("CapAdd") or [])]
    if "SYS_ADMIN" in caps or "ALL" in caps:
        return "SYS_ADMIN/ALL capabilities are not allowed"

    # Binds: ["/host:/container:opts", ...]
    for bind in hc.get("Binds") or []:
        reason = is_path_blocked(bind.split(":")[0])
        if reason:
            return f"bind mount blocked: {reason}"

    # Mounts: [{"Type":"bind","Source":"/host","Target":"/ct"}, ...]
    for mount in hc.get("Mounts") or []:
        if mount.get("Type") == "bind":
            reason = is_path_blocked(mount.get("Source", ""))
            if reason:
                return f"bind mount blocked: {reason}"

    for dev in hc.get("Devices") or []:
        path = dev.get("PathOnHost", "") if isinstance(dev, dict) else str(dev)
        if path.startswith("/dev/"):
            return f"device mount blocked: {path}"

    return None


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def read_headers(reader):
    """Read an HTTP request or response line + headers.

    Returns (first_line, headers_dict, raw_bytes) or (None, {}, b"") on EOF.
    """
    first_line = reader.readline()
    if not first_line:
        return None, {}, b""

    raw = first_line
    headers = {}
    while True:
        line = reader.readline()
        raw += line
        if line in (b"\r\n", b"\n", b""):
            break
        decoded = line.decode("latin-1")
        if ":" in decoded:
            key, val = decoded.split(":", 1)
            headers[key.strip().lower()] = val.strip()

    return first_line.decode("latin-1").strip(), headers, raw


def read_full_body(reader, headers):
    """Read an entire HTTP body into memory (Content-Length or chunked)."""
    cl = headers.get("content-length")
    if cl:
        n = int(cl)
        if n <= 0 or n > MAX_CREATE_BODY:
            return b""
        return reader.read(n)
    if headers.get("transfer-encoding", "").lower() == "chunked":
        body = b""
        while True:
            size_line = reader.readline()
            size = int(size_line.strip().split(b";")[0], 16)
            if size == 0:
                reader.readline()
                break
            body += reader.read(size)
            reader.read(2)
            if len(body) > MAX_CREATE_BODY:
                return body
        return body
    return b""


def forward_body(reader, dst_sock, headers):
    """Forward an HTTP body (Content-Length or chunked) from reader to socket."""
    cl = headers.get("content-length")
    if cl:
        remaining = int(cl)
        while remaining > 0:
            data = reader.read(min(remaining, BUF_SIZE))
            if not data:
                break
            dst_sock.sendall(data)
            remaining -= len(data)
    elif headers.get("transfer-encoding", "").lower() == "chunked":
        while True:
            size_line = reader.readline()
            dst_sock.sendall(size_line)
            size = int(size_line.strip().split(b";")[0], 16)
            if size == 0:
                trailer = reader.readline()
                dst_sock.sendall(trailer)
                break
            data = reader.read(size)
            dst_sock.sendall(data)
            crlf = reader.read(2)
            dst_sock.sendall(crlf)


def relay(sock_a, sock_b):
    """Bidirectional raw byte relay until one side closes."""
    pair = [sock_a, sock_b]
    while True:
        try:
            readable, _, _ = select.select(pair, [], [], 60)
        except (ValueError, OSError):
            break
        if not readable:
            continue
        for s in readable:
            try:
                data = s.recv(BUF_SIZE)
            except (ConnectionError, OSError):
                return
            if not data:
                return
            target = sock_b if s is sock_a else sock_a
            try:
                target.sendall(data)
            except (ConnectionError, OSError):
                return


# ---------------------------------------------------------------------------
# Per-connection handler (runs in its own thread)
# ---------------------------------------------------------------------------


def handle_connection(client_sock):
    upstream_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        upstream_sock.connect(UPSTREAM_SOCK)
    except (ConnectionError, OSError) as e:
        log(f"upstream connect failed: {e}")
        client_sock.close()
        return

    client = BufferedSocket(client_sock)
    upstream = BufferedSocket(upstream_sock)

    try:
        while True:
            # -- request --------------------------------------------------
            req_line, req_headers, req_raw = read_headers(client)
            if req_line is None:
                break

            parts = req_line.split()
            if len(parts) < 2:
                break
            method = parts[0]
            path = parts[1].split("?")[0]

            if method == "POST" and CREATE_RE.match(path):
                body_raw = read_full_body(client, req_headers)

                try:
                    body = json.loads(body_raw)
                except (json.JSONDecodeError, ValueError):
                    reason = "failed to parse container creation payload"
                else:
                    reason = validate_create(body)

                if reason:
                    log(f"BLOCKED: {reason}")
                    err = json.dumps({"message": f"autobox: {reason}"}).encode()
                    resp = (
                        f"HTTP/1.1 403 Forbidden\r\n"
                        f"Content-Type: application/json\r\n"
                        f"Content-Length: {len(err)}\r\n"
                        f"\r\n"
                    ).encode() + err
                    client_sock.sendall(resp)
                    continue

                # Re-encode with Content-Length (body may have been chunked originally)
                patched_headers = re.sub(
                    rb"(?i)transfer-encoding:[^\r\n]*\r\n",
                    b"",
                    req_raw,
                )
                patched_headers = re.sub(
                    rb"(?i)content-length:[^\r\n]*\r\n",
                    b"",
                    patched_headers,
                )
                # Insert Content-Length before the final \r\n
                patched_headers = (
                    patched_headers[:-2]
                    + (f"Content-Length: {len(body_raw)}\r\n\r\n").encode()
                )
                upstream_sock.sendall(patched_headers + body_raw)
            else:
                upstream_sock.sendall(req_raw)
                if method in ("POST", "PUT", "PATCH"):
                    forward_body(client, upstream_sock, req_headers)

            # -- response -------------------------------------------------
            resp_line, resp_headers, resp_raw = read_headers(upstream)
            if resp_line is None:
                break
            client_sock.sendall(resp_raw)

            # Connection upgrade (e.g. docker exec -it) → raw relay
            if "101" in resp_line:
                leftover = upstream.drain()
                if leftover:
                    client_sock.sendall(leftover)
                leftover = client.drain()
                if leftover:
                    upstream_sock.sendall(leftover)
                relay(client_sock, upstream_sock)
                return

            forward_body(upstream, client_sock, resp_headers)

            if resp_headers.get("connection", "").lower() == "close":
                break
    except Exception as e:
        log(f"connection error: {e}")
    finally:
        client_sock.close()
        upstream_sock.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    try:
        os.unlink(LISTEN_SOCK)
    except FileNotFoundError:
        pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(LISTEN_SOCK)
    os.chmod(LISTEN_SOCK, 0o666)
    server.listen(16)

    log(f"listening on {LISTEN_SOCK}, upstream {UPSTREAM_SOCK}")
    if HOST_WORKSPACE:
        log(f"allowed workspace: {HOST_WORKSPACE}")

    running = True

    def on_sigterm(_sig, _frame):
        nonlocal running
        running = False
        server.close()

    signal.signal(signal.SIGTERM, on_sigterm)

    while running:
        try:
            conn, _ = server.accept()
        except OSError:
            break
        threading.Thread(target=handle_connection, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    main()
