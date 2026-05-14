#!/usr/bin/env python
import os
import socket
import struct
import signal
import threading
import queue

from . import protocol


MAX_QUEUE_SIZE = 10000


class CallBusDaemon:
    def __init__(self, socket_path):
        self.socket_path = socket_path
        self.running = True
        self.handlers = {}

        # bounded queue = bounded memory
        self.queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)

    def register(self, name: str, fn):
        self.handlers[name] = fn

    def _recv_exact(self, conn, n):
        buf = bytearray()

        while len(buf) < n:
            chunk = conn.recv(n - len(buf))

            if not chunk:
                return None

            buf.extend(chunk)

        return bytes(buf)

    def _read_msg(self, conn):
        raw_len = self._recv_exact(conn, 4)

        if not raw_len:
            return None

        msg_len = struct.unpack("!I", raw_len)[0]

        data = self._recv_exact(conn, msg_len)

        if data is None:
            return None

        return protocol.decode(data)

    def _handle(self, msg: dict):
        method = msg.get("method")
        args = msg.get("args", [])
        kwargs = msg.get("kwargs", {})

        fn = self.handlers.get(method)

        if not fn:
            return

        try:
            fn(*args, **kwargs)

        except Exception as e:
            print(f"[callbus] handler error ({method}): {e}")

    def _worker_loop(self):
        while self.running:
            try:
                msg = self.queue.get(timeout=0.5)

            except queue.Empty:
                continue

            try:
                self._handle(msg)

            except Exception as e:
                print(f"[callbus] worker error: {e}")

    def _client_handler(self, conn):
        with conn:
            while self.running:
                try:
                    msg = self._read_msg(conn)

                except Exception as e:
                    print(f"[callbus] read error: {e}")
                    break

                if msg is None:
                    break

                # best effort enqueue
                try:
                    self.queue.put_nowait(msg)

                except queue.Full:
                    # intentionally drop under pressure
                    print("[callbus] queue full, dropping message")

                # IMPORTANT:
                # no response sent
                # client write completes once kernel buffer accepts data

    def serve(self):
        install_signal_handlers(self)

        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)

            except OSError:
                raise RuntimeError(
                    f"Cannot remove socket: {self.socket_path}"
                )

        server = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
        )

        self.server = server

        server.bind(self.socket_path)

        os.chmod(self.socket_path, 0o600)

        server.listen()

        worker = threading.Thread(
            target=self._worker_loop,
            daemon=True,
        )

        worker.start()

        print(f"[callbus] listening on {self.socket_path}")

        try:
            while self.running:
                try:
                    conn, _ = server.accept()

                except OSError:
                    break

                t = threading.Thread(
                    target=self._client_handler,
                    args=(conn,),
                    daemon=True,
                )

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

        # unblock accept()
        try:
            dummy = socket.socket(
                socket.AF_UNIX,
                socket.SOCK_STREAM,
            )

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
