import socket
import struct
from callbus import protocol


class CallBusClient:
    def __init__(self, socket_path):
        self.socket_path = socket_path
        self.sock = None

    def connect(self):
        if self.sock is None:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self.socket_path)
            self.sock = s

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def call(self, method, *args, **kwargs):
        if self.sock is None:
            self.connect()

        req = protocol.make_request(method, *args, **kwargs)
        data = protocol.encode(req)

        msg = struct.pack("!I", len(data)) + data
        self.sock.sendall(msg)

        return self._recv(self.sock)

    def _recv_exact(self, s, n):
        data = b""
        while len(data) < n:
            chunk = s.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _recv(self, s):
        raw_len = self._recv_exact(s, 4)
        if not raw_len:
            raise ConnectionError("connection closed")

        msg_len = struct.unpack("!I", raw_len)[0]

        data = self._recv_exact(s, msg_len)
        if not data:
            raise ConnectionError("connection closed")

        resp = protocol.decode(data)

        if resp.get("error"):
            raise RuntimeError(resp["error"])

        return resp.get("result")
