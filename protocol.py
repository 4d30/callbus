import json

# ---- message format ----
# request:
# { "method": str, "args": list, "kwargs": dict }
#
# response:
# { "result": any, "error": str | None }

def encode(msg: dict) -> bytes:
    return json.dumps(msg).encode("utf-8")


def decode(raw: bytes) -> dict:
    return json.loads(raw.decode("utf-8"))


def make_request(method, *args, **kwargs):
    return {
        "method": method,
        "args": args,
        "kwargs": kwargs,
    }


def make_response(result=None, error=None):
    return {
        "result": result,
        "error": error,
    }
