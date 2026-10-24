"""Bounded JSON line framing and request/response correlation."""
import json
import math

VERSION = 1
MAX_BYTES = 1024


class ProtocolError(Exception):
    pass


class DeviceError(ProtocolError):
    pass


def encode(message):
    try:
        data = (json.dumps(message, allow_nan=False, separators=(",", ":")) + "\n").encode()
    except (ValueError, TypeError) as exc:
        raise ProtocolError("Non-JSON message") from exc
    if len(data) > MAX_BYTES:
        raise ProtocolError("Message too long")
    return data


def decode(data):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES or not data.endswith(b"\n"):
        raise ProtocolError("Expected bounded, complete JSON line")
    try:
        message = json.loads(data, parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(value)))
    except (ValueError, UnicodeError) as exc:
        raise ProtocolError("Malformed JSON") from exc
    if not isinstance(message, dict):
        raise ProtocolError("Expected JSON object")
    return message


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


class Client:
    def __init__(self, transport, timeout_s=1.0):
        if not number(timeout_s) or timeout_s <= 0:
            raise ValueError("Timeout must be positive")
        self.transport = transport
        self.timeout_s = timeout_s
        self.next_id = 1

    def request(self, command, params=None):
        request_id = self.next_id
        self.next_id += 1
        response = decode(self.transport.exchange(encode({
            "v": VERSION, "id": request_id, "cmd": command,
            "params": {} if params is None else params,
        }), self.timeout_s))
        if type(response.get("v")) is not int or response["v"] != VERSION:
            raise ProtocolError("Protocol version mismatch")
        if type(response.get("id")) is not int or response["id"] != request_id:
            raise ProtocolError("Request ID mismatch")
        if response.get("ok") is True and isinstance(response.get("result"), dict):
            return response["result"]
        error = response.get("error")
        if response.get("ok") is False and isinstance(error, dict):
            if isinstance(error.get("code"), str) and isinstance(error.get("message"), str):
                raise DeviceError(error["code"] + ": " + error["message"])
        raise ProtocolError("Invalid response envelope")
