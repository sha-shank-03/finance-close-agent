"""Run only U2-C pure components while forbidding sockets and child launches."""

import argparse
import ctypes
import hashlib
import io
import json
import os
import platform
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def own_peak_working_set():
    if os.name != "nt":
        return None
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in ["PeakWorkingSetSize", "WorkingSetSize",
            "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
            "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage"]]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return None
    return counters.PeakWorkingSetSize


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        raise ValueError("Use a fresh pure-check receipt directory")
    out.mkdir(parents=True)
    stream = io.StringIO()
    started = time.monotonic()
    denied = {"socket": 0, "process": 0}
    def deny(kind):
        def forbidden(*args, **kwargs):
            denied[kind] += 1
            raise AssertionError("Pure U2-C checks attempted a forbidden " + kind)
        return forbidden
    with patch("socket.socket", side_effect=deny("socket")), \
            patch("subprocess.Popen", side_effect=deny("process")), \
            patch("multiprocessing.get_context", side_effect=deny("process")):
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_u2c_pure.py")
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    receipt = {"schema_version": 1, "command": [sys.executable, "tools/u2c_pure.py", "--out", str(out)],
               "exit_code": 0 if result.wasSuccessful() else 1, "tests": result.testsRun,
               "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
               "wall_seconds": time.monotonic() - started, "own_process_peak_working_set_bytes": own_peak_working_set(),
               "python": platform.python_version(), "denied_launch_attempts": denied,
               "source_sha256": {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                                 for directory in [ROOT/"finance_close",ROOT/"evaluation",ROOT/"tests",ROOT/"tools"]
                                 for p in sorted(directory.glob("*.py"))},
               "actual_test_sockets": 0, "actual_test_children": 0, "live_model_calls": 0,
               "credential_accessed": False, "external_sandbox_calls": 0, "credential_presence_checked": False, "evidence": "Injected dispatch/oracle/clock and allowlisted public summary tests only; no native actor/corpus execution, actual subprocess/socket, live or external calls. The default-launch test separately mocks Popen to reject it.",
               "new_process_cleanup": "No owned test subprocess or socket created; nothing to reap."}
    (out / "unittest.log").write_text(stream.getvalue(), encoding="utf-8")
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k:receipt[k] for k in ['exit_code','tests','failures','errors','wall_seconds','own_process_peak_working_set_bytes','denied_launch_attempts']}))
    if not result.wasSuccessful():print(stream.getvalue())
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
