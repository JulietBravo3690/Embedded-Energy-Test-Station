"""Independent, literal acceptance vectors; no simulator decision logic imported."""
from dataclasses import dataclass
from time import perf_counter

from .protocol import Client, DeviceError, ProtocolError, encode


@dataclass
class Check:
    name: str
    requirement: str
    expected: object
    observe: object


def state_vector(device, client, samples):
    states = []
    for voltage, temperature in samples:
        device.inject(voltage, temperature)
        states.append(client.request("telemetry")["state"])
    return states


def reject_config(client, params):
    before = client.request("config.get")
    try:
        client.request("config.set", params)
    except DeviceError as exc:
        return {"code": str(exc).split(":")[0],
                "unchanged": before == client.request("config.get")}
    return {"code": "ACCEPTED", "unchanged": False}


def reset_result(device, client):
    client.request("config.set", {"voltage_limit_v": 20.0})
    device.inject(30, 70)
    ack = client.request("reset")
    return [ack, client.request("config.get")["voltage_limit_v"],
            client.request("telemetry")["state"]]


def bad_response(payload, expected_exception):
    class BrokenTransport:
        def exchange(self, request, timeout_s):
            if payload is None:
                raise TimeoutError("Simulated deadline expiry")
            return payload
    try:
        Client(BrokenTransport()).request("identity")
    except expected_exception:
        return "rejected"
    return "accepted"


def checks():
    items = [
        Check("identity", "REQ-001", ["SIM-001", "sim-0.1.0", 1, True],
              lambda d, c: [c.request("identity")[k] for k in
                            ("device_id", "firmware_version", "protocol_version", "simulated")]),
        Check("valid_config", "REQ-002", 16.0,
              lambda d, c: c.request("config.set", {"voltage_limit_v": 16.0})["voltage_limit_v"]),
        Check("normal_telemetry", "REQ-003", [12.0, 25.0, "NORMAL", True],
              lambda d, c: [c.request("telemetry")[k] for k in
                            ("voltage_v", "temperature_c", "state", "simulated")]),
        Check("voltage_boundary", "REQ-004", ["NORMAL", "FAULT"],
              lambda d, c: state_vector(d, c, [(14.999, 25), (15, 25)])),
        Check("temperature_boundary", "REQ-004", ["NORMAL", "FAULT"],
              lambda d, c: state_vector(d, c, [(12, 59.999), (12, 60)])),
        Check("hysteresis_recovery", "REQ-005",
              ["FAULT", "FAULT", "RECOVERY", "FAULT", "RECOVERY", "NORMAL"],
              lambda d, c: state_vector(d, c, [(16, 25), (14.001, 25), (14, 55),
                                              (14, 55.001), (14, 55), (14, 55)])),
        Check("retrip_during_recovery", "REQ-005", ["FAULT", "RECOVERY", "FAULT"],
              lambda d, c: state_vector(d, c, [(12, 61), (12, 50), (16, 50)])),
        Check("reset_volatile_config", "REQ-006",
              [{"reset": True, "config_persisted": False}, 15.0, "NORMAL"], reset_result),
    ]
    for name, params in [
        ("voltage_low", {"voltage_limit_v": 0}),
        ("voltage_high", {"voltage_limit_v": 61}),
        ("temperature_low", {"temperature_limit_c": -21}),
        ("temperature_high", {"temperature_limit_c": 126}),
        ("zero_hysteresis", {"voltage_hysteresis_v": 0}),
        ("large_hysteresis", {"voltage_hysteresis_v": 15}),
        ("temperature_hysteresis", {"temperature_hysteresis_c": 31}),
        ("temperature_floor", {"temperature_limit_c": -20, "temperature_hysteresis_c": 30}),
        ("boolean", {"voltage_limit_v": True}),
        ("string", {"temperature_limit_c": "60"}),
        ("unknown_key", {"extra": 1}),
        ("empty", {}),
    ]:
        items.append(Check("invalid_config_" + name, "REQ-002",
                           {"code": "INVALID_CONFIG", "unchanged": True},
                           lambda d, c, p=params: reject_config(c, p)))
    for name, payload, exception in [
        ("malformed", b"not json\n", ProtocolError),
        ("incomplete", b'{"v":1}', ProtocolError),
        ("oversized", b" " * 1024 + b"\n", ProtocolError),
        ("wrong_id", encode({"v": 1, "id": 999, "ok": True, "result": {}}), ProtocolError),
        ("wrong_version", encode({"v": 2, "id": 1, "ok": True, "result": {}}), ProtocolError),
        ("bad_envelope", encode({"v": 1, "id": 1, "ok": "yes"}), ProtocolError),
        ("timeout", None, TimeoutError),
    ]:
        items.append(Check(name, "REQ-007", "rejected",
                           lambda d, c, p=payload, e=exception: bad_response(p, e)))
    return items


def run_checks(factory):
    results = []
    for check in checks():
        start = perf_counter()
        observed, reason = None, None
        try:
            device, transport = factory()
            observed = check.observe(device, Client(transport))
            status = "PASS" if observed == check.expected else "FAIL"
            if status == "FAIL":
                reason = "Observed value differs from requirement expectation"
        except Exception as exc:
            status, reason = "ERROR", f"{type(exc).__name__}: {exc}"
        results.append({"test": check.name, "requirement": check.requirement,
                        "required": True, "status": status, "expected": check.expected,
                        "observed": observed, "failure_reason": reason,
                        "duration_s": perf_counter() - start})
    return results
