"""Deterministic simulation. Inputs are synthetic, never physical measurements."""
from .protocol import ProtocolError, decode, encode, number

DEFAULTS = {"voltage_limit_v": 15.0, "voltage_hysteresis_v": 1.0,
            "temperature_limit_c": 60.0, "temperature_hysteresis_c": 5.0}


class Controller:
    def __init__(self, defective=False):
        self.defective = defective
        self.config = DEFAULTS.copy()
        self.state = "NORMAL"
        self.safe_samples = 0
        self.voltage = 12.0
        self.temperature = 25.0

    def inject(self, voltage_v, temperature_c):
        """Simulation fixture only: one injection advances exactly one sample."""
        if not number(voltage_v) or not number(temperature_c):
            raise ValueError("Finite numeric inputs required")
        self.voltage, self.temperature = voltage_v, temperature_c
        c = self.config
        if self.defective:
            trip = voltage_v > c["voltage_limit_v"] or temperature_c > c["temperature_limit_c"]
        else:
            trip = voltage_v >= c["voltage_limit_v"] or temperature_c >= c["temperature_limit_c"]
        safe = (voltage_v <= c["voltage_limit_v"] - c["voltage_hysteresis_v"]
                and temperature_c <= c["temperature_limit_c"] - c["temperature_hysteresis_c"])
        if trip:
            self.state, self.safe_samples = "FAULT", 0
        elif self.state != "NORMAL":
            if safe:
                self.safe_samples += 1
                self.state = "NORMAL" if self.safe_samples >= 2 else "RECOVERY"
                if self.state == "NORMAL":
                    self.safe_samples = 0
            else:
                self.state, self.safe_samples = "FAULT", 0

    def handle(self, line):
        request_id = None
        try:
            request = decode(line)
            candidate = request.get("id")
            if type(candidate) is int and 1 <= candidate <= 2147483647:
                request_id = candidate
            if request_id is None or not isinstance(request.get("cmd"), str):
                return self.error(request_id, "BAD_REQUEST", "Invalid id or command")
            if type(request.get("v")) is not int or request["v"] != 1:
                return self.error(request_id, "VERSION", "Only version 1 is supported")
            params = request.get("params")
            if not isinstance(params, dict):
                return self.error(request_id, "BAD_REQUEST", "params must be an object")
            command = request["cmd"]
            if command not in {"identity", "telemetry", "config.get", "config.set", "reset"}:
                return self.error(request_id, "UNKNOWN_COMMAND", "Unsupported command")
            if command != "config.set" and params:
                return self.error(request_id, "BAD_REQUEST", "Command takes no parameters")
            if command == "identity":
                result = {"device_id": "SIM-001", "firmware_version": "sim-0.1.0",
                          "protocol_version": 1, "simulated": True,
                          "model": "defective-boundary" if self.defective else "reference"}
            elif command == "config.get":
                result = self.config.copy()
            elif command == "config.set":
                proposed = self.config | params
                if not params or set(params) - set(DEFAULTS) or not self.valid(proposed):
                    return self.error(request_id, "INVALID_CONFIG", "Invalid configuration")
                self.config = proposed
                result = self.config.copy()
            elif command == "reset":
                self.config = DEFAULTS.copy()
                self.state, self.safe_samples = "NORMAL", 0
                self.voltage, self.temperature = 12.0, 25.0
                result = {"reset": True, "config_persisted": False}
            else:
                result = {"voltage_v": self.voltage, "temperature_c": self.temperature,
                          "state": self.state, "safe_samples": self.safe_samples,
                          "simulated": True}
            return encode({"v": 1, "id": request_id, "ok": True, "result": result})
        except ProtocolError:
            return self.error(request_id, "MALFORMED", "Invalid JSON line or length")

    @staticmethod
    def valid(c):
        return (all(number(v) for v in c.values())
                and 1 <= c["voltage_limit_v"] <= 60
                and 0 < c["voltage_hysteresis_v"] < c["voltage_limit_v"]
                and -20 <= c["temperature_limit_c"] <= 125
                and 0 < c["temperature_hysteresis_c"] <= 30
                and c["temperature_limit_c"] - c["temperature_hysteresis_c"] >= -40)

    @staticmethod
    def error(request_id, code, message):
        return encode({"v": 1, "id": request_id, "ok": False,
                       "error": {"code": code, "message": message}})
