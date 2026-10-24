"""Traceable simulation reports with UTC times and source provenance."""
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def revision():
    root = Path(__file__).resolve().parents[2]
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True,
                                      stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root,
                                            text=True, stderr=subprocess.DEVNULL).strip())
        return {"revision": sha, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"revision": None, "dirty": None}


def make_report(identity, results, started_at):
    counts = {status: sum(r["status"] == status for r in results)
              for status in ("PASS", "FAIL", "ERROR")}
    outcome = "ERROR" if counts["ERROR"] else "FAIL" if counts["FAIL"] else "PASS"
    return {"schema_version": 1, "run_id": str(uuid4()), "started_at": started_at,
            "finished_at": utc_now(), "simulated": True,
            "measurement_source": "synthetic simulator inputs; no physical hardware",
            "identity": identity, "test_software": {"version": "0.1.0", **revision()},
            "status": outcome, "summary": counts, "results": results}
