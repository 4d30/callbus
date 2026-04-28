import socket
import struct
from callbus import protocol

SOCKET_PATH = "/tmp/callbus.sock"


class CallBusClient:
    def __init__(self, socket_path=SOCKET_PATH):
        self.socket_path = socket_path

    def call(self, method, *args, **kwargs):
        req = protocol.make_request(method, *args, **kwargs)
        data = protocol.encode(req)

        msg = struct.pack("!I", len(data)) + data

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(self.socket_path)
            s.sendall(msg)

            return self._recv(s)

    def _recv(self, s):
        raw_len = s.recv(4)
        if not raw_len:
            return None

        msg_len = struct.unpack("!I", raw_len)[0]
        data = b""

        while len(data) < msg_len:
            chunk = s.recv(msg_len - len(data))
            if not chunk:
                break
            data += chunk

        resp = protocol.decode(data)

        if resp.get("error"):
            raise RuntimeError(resp["error"])

        return resp.get("result")
