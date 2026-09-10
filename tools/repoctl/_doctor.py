"""Inspect only local prerequisites; do not start a Skill host or a model."""
import importlib.util
import json
import os
import platform
import shutil
import sys


def main() -> int:
    missing = [name for name in ("ruff", "yaml") if importlib.util.find_spec(name) is None]
    diagnostics = [{"code": "ASKILLS-DEPENDENCY", "path": "requirements-dev.txt",
                    "reason": f"missing module: {name}", "repair": "python -m pip install -r requirements-dev.txt"}
                   for name in missing]
    if shutil.which("git") is None:
        diagnostics.append({"code": "ASKILLS-DEPENDENCY", "path": "Git", "reason": "Git unavailable",
                            "repair": "Install Git and make it available on PATH"})
    print(json.dumps({"diagnostics": diagnostics, "facts": {
        "python": platform.python_version(), "executable": sys.executable,
        "system": platform.system(), "git_available": shutil.which("git") is not None,
        "installer": "BLOCKED: POSIX backend required" if os.name == "nt" else "local tests required",
        "host_eval": "NOT_REQUESTED", "model_eval": "NOT_REQUESTED",
    }}))
    return 3 if diagnostics else 0


if __name__ == "__main__":
    raise SystemExit(main())
