import argparse
import json
from pathlib import Path

from .protocol import Client
from .reporting import make_report, utc_now
from .runner import run_checks
from .simulator import Controller
from .transport import SimulatorTransport


def main(argv=None):
    parser = argparse.ArgumentParser(description="SIMULATION ONLY energy controller test station")
    parser.add_argument("--scenario", choices=["normal", "defective"], default="normal")
    parser.add_argument("--report", type=Path, default=Path("reports/simulation.json"))
    args = parser.parse_args(argv)
    started = utc_now()

    def factory():
        device = Controller(defective=args.scenario == "defective")
        return device, SimulatorTransport(device)

    _, transport = factory()
    identity = Client(transport).request("identity")
    report = make_report(identity, run_checks(factory), started)
    try:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    except OSError as exc:
        parser.exit(2, f"Report write ERROR: {exc}\n")
    print(f"SIMULATION {report['status']}: {report['summary']} -> {args.report}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
