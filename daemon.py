#!/usr/bin/env python
import os
import socket
import struct
import signal
import threading
from . import protocol


class CallBusDaemon:
    def __init__(self, socket_path):
        self.socket_path = socket_path
        self.running = True
        self.handlers = {}
        self.lock = threading.Lock()

    def register(self, name: str, fn):
        self.handlers[name] = fn

    def _recv_exact(self, conn, n):
        data = b""
        while len(data) < n:
            chunk = conn.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data


    def _read_msg(self, conn):
        # 4-byte length prefix
        raw_len = self._recv_exact(conn, 4)
        if not raw_len:
            return None

        msg_len = struct.unpack("!I", raw_len)[0]
        data = b""

        while len(data) < msg_len:
            chunk = conn.recv(msg_len - len(data))
            if not chunk:
                break
            data += chunk

        return protocol.decode(data)

    def _send_msg(self, conn, msg: dict):
        data = protocol.encode(msg)
        conn.sendall(struct.pack("!I", len(data)) + data)

    def _handle(self, msg: dict) -> dict:
        method = msg.get("method")
        args = msg.get("args", [])
        kwargs = msg.get("kwargs", {})

        fn = self.handlers.get(method)
        if not fn:
            return protocol.make_response(error=f"unknown method: {method}")

        try:
            result = fn(*args, **kwargs)
            return protocol.make_response(result=result)
        except Exception as e:
            return protocol.make_response(error=str(e))


    def _client_handler(self, conn):
        with conn:
            while True:
                msg = self._read_msg(conn)
                if msg is None:
                    break
                with self.lock:
                    response = self._handle(msg)
                self._send_msg(conn, response)


    def serve(self):
        install_signal_handlers(self)
        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
            except OSError:
                raise RuntimeError(f"Cannot remove socket: {self.socket_path}")

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server = server
        server.bind(self.socket_path)
        os.chmod(self.socket_path, 0o600)
        server.listen()
        
        print(f"[callbus] listening on {self.socket_path}")
        try:
            while self.running:
                try:
                    conn, _ = server.accept()
                except OSError:
                    break
                t = threading.Thread(target=self._client_handler, args=(conn,), daemon=True)
                t.start()
        finally:
            server.close()
            if os.path.exists(self.socket_path):
                os.remove(self.socket_path)
            print("[callbus] clean shutdown complete")


def install_signal_handlers(daemon):
    def shutdown(signum, frame):
        print("[callbus] shutting down...")
        daemon.running = False

        # force unblock accept() if needed
        try:
            dummy = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            dummy.connect(daemon.socket_path)
            dummy.close()
        except Exception:
            pass
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    


def run(socket_path, handlers: dict):
    daemon = CallBusDaemon(socket_path=socket_path)
    for name, fn in handlers.items():
        daemon.register(name, fn)
    daemon.serve()
