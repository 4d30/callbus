# callbus
A minimal local RPC system over Unix domain sockets.

`callbus` lets you expose Python functions from a daemon and call them from a client as if they were local.

---

## Features
 - Unix socket transport (AF_UNIX)
 - Simple request/response protocol (JSON)
 - Length-prefixed framing (safe, no partial reads)
 - Clean shutdown via signals (SIGINT, SIGTERM)
 - No dependencies (stdlib only)

---

## Installation
No install required (yet). Just ensure callbus/ is on your PYTHONPATH, or install in editable mode:

`pip install -e .`

---

## Usage

### Start a server
```shell
$ cat > server_example.py
from callbus import run

def add(a, b):
    return a + b

def echo(x):
    return x

run(
    socket_path="/tmp/callbus.sock",
    handlers={
        "add": add,
        "echo": echo,
    }
)
^D
```
Run:

```shell
$ python server_example.py
```

---
### Call from a client
```python
from callbus import CallBusClient

c = CallBusClient("/tmp/callbus.sock")

print(c.call("add", 2, 3))      # 5
print(c.call("echo", "hello"))  # "hello"
```
---

## Protocol

### Requests:
```json
{
  "method": "add",
  "args": [2, 3],
  "kwargs": {}
}
```

### Responses:

```json
{
  "result": 5,
  "error": null
}
```
Messages are sent as:

[4-byte big-endian length][JSON payload]

---

## Shutdown
The daemon handles:
 - Ctrl+C (SIGINT)
 - kill -TERM <pid>

On shutdown it:

 - exits the loop cleanly
 - closes the socket
 - removes the socket file

## Design
`callbus` is intentionally small and explicit:
 - `daemon.py` ->  server + dispatch loop
 - `client.py` -> request interface
 - `protocol.py` -> message encoding/decoding

No hidden state, no framework abstractions.

## Notes
 - Single-threaded (one request per connection)
 - Local IPC only (not for network use)
 - JSON can be swapped for msgpack if needed
 - Safe for trusted environments (no auth layer)

## Future ideas
 - persistent connections
 - async/event loop support
 - batching
 - pluggable serializers (msgpack)
 - namespaced methods

## License
BSD-2
