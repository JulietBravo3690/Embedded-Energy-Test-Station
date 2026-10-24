import json

import pytest

from energy_station.cli import main
from energy_station.protocol import Client, ProtocolError, decode, encode
from energy_station.runner import run_checks
from energy_station.simulator import Controller
from energy_station.transport import SimulatorTransport


def factory(defective=False):
    device = Controller(defective)
    return device, SimulatorTransport(device)


@pytest.mark.parametrize("result", run_checks(factory), ids=lambda r: r["test"])
def test_acceptance(result):
    assert result["status"] == "PASS", result


def test_mutant_detected():
    results = run_checks(lambda: factory(True))
    assert {r["test"] for r in results if r["status"] == "FAIL"} == {
        "voltage_boundary", "temperature_boundary"}
    assert not any(r["status"] == "ERROR" for r in results)


@pytest.mark.parametrize("scenario,exit_code,status", [
    ("normal", 0, "PASS"), ("defective", 1, "FAIL")])
def test_cli_reports(tmp_path, scenario, exit_code, status):
    path = tmp_path / "report.json"
    assert main(["--scenario", scenario, "--report", str(path)]) == exit_code
    report = json.loads(path.read_text())
    assert report["simulated"] is True
    assert report["status"] == status
    assert report["run_id"] and report["started_at"] and report["finished_at"]
    assert report["identity"]["firmware_version"] == "sim-0.1.0"
    assert len(report["results"]) == 27
    assert all(r["duration_s"] >= 0 for r in report["results"])


def test_transport_exception_is_error():
    class Broken:
        def exchange(self, request, timeout_s):
            raise TimeoutError("deadline")
    results = run_checks(lambda: (Controller(), Broken()))
    assert results[0]["status"] == "ERROR"
    assert "TimeoutError" in results[0]["failure_reason"]


@pytest.mark.parametrize("line,code", [
    (b"{\n", "MALFORMED"), (b"{}", "MALFORMED"),
    (b" " * 1025, "MALFORMED"),
    (encode({"v": 1, "id": True, "cmd": "identity", "params": {}}), "BAD_REQUEST"),
    (encode({"v": 2, "id": 1, "cmd": "identity", "params": {}}), "VERSION"),
    (encode({"v": 1, "id": 1, "cmd": "inject", "params": {}}), "UNKNOWN_COMMAND"),
    (encode({"v": 1, "id": 1, "cmd": "reset", "params": {"x": 1}}), "BAD_REQUEST"),
    (encode({"v": 1, "id": 1, "cmd": "identity", "params": []}), "BAD_REQUEST"),
])
def test_device_errors(line, code):
    response = decode(Controller().handle(line))
    assert response["ok"] is False
    assert response["error"]["code"] == code


@pytest.mark.parametrize("line", [b"NaN\n", b"[]\n", b"\xff\n", b"{}\n{}\n"])
def test_invalid_frames(line):
    with pytest.raises(ProtocolError):
        decode(line)


def test_config_does_not_advance_samples():
    device, transport = factory()
    client = Client(transport)
    device.inject(16, 25)
    device.inject(12, 25)
    assert client.request("telemetry")["state"] == "RECOVERY"
    client.request("config.set", {"voltage_limit_v": 20})
    assert client.request("telemetry")["state"] == "RECOVERY"
    device.inject(12, 25)
    assert client.request("telemetry")["state"] == "NORMAL"


@pytest.mark.parametrize("params", [
    {"voltage_limit_v": 1, "voltage_hysteresis_v": 0.5},
    {"voltage_limit_v": 60}, {"temperature_limit_c": -20},
    {"temperature_limit_c": 125}, {"temperature_hysteresis_c": 30},
])
def test_valid_config_edges(params):
    _, transport = factory()
    observed = Client(transport).request("config.set", params)
    assert all(observed[k] == v for k, v in params.items())


def test_configured_threshold_and_recovery():
    device, transport = factory()
    client = Client(transport)
    client.request("config.set", {"voltage_limit_v": 20, "voltage_hysteresis_v": 2})
    states = []
    for voltage in [19.999, 20, 18.001, 18, 18]:
        device.inject(voltage, 25)
        states.append(client.request("telemetry")["state"])
    assert states == ["NORMAL", "FAULT", "FAULT", "RECOVERY", "NORMAL"]


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_nonfinite_device_config(value):
    device = Controller()
    before = device.config.copy()
    wire = ('{"v":1,"id":1,"cmd":"config.set","params":'
            '{"voltage_limit_v":' + value + '}}\n').encode()
    assert decode(device.handle(wire))["ok"] is False
    assert device.config == before


def test_cli_error_report(tmp_path, monkeypatch):
    from energy_station import cli

    class BrokenSampling(Controller):
        def inject(self, *args):
            raise OSError("simulated sampling failure")
    monkeypatch.setattr(cli, "Controller", BrokenSampling)
    path = tmp_path / "error.json"
    assert main(["--report", str(path)]) == 1
    report = json.loads(path.read_text())
    assert report["status"] == "ERROR"
    assert report["summary"]["ERROR"] > 0
    assert any("sampling failure" in (r["failure_reason"] or "") for r in report["results"])


def test_cli_report_write_failure(tmp_path):
    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(SystemExit) as exc:
        main(["--report", str(directory)])
    assert exc.value.code == 2
