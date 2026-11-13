"""Run repository fixture tests against a fresh installed platform wheel."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--wheel-dir", type=Path, required=True)
a = p.parse_args()
wheels = list(a.wheel_dir.resolve().glob("*.whl"))
if len(wheels) != 1:
    raise RuntimeError("Expected exactly one wheel")
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="plurimath-installed-") as directory:
    environment = Path(directory) / "venv"
    venv.create(environment, with_pip=True)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    excluded = {"PYTHONPATH", "PYTHONHOME", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH",
                "DYLD_FALLBACK_LIBRARY_PATH", "PARSANOL_LIB", "RUST_MIN_STACK"}
    clean = {k: v for k, v in os.environ.items() if not k.startswith("PLURIMATH_") and k not in excluded}
    if os.name == "nt":
        system = clean.get("SystemRoot", r"C:\Windows")
        clean["PATH"] = system + r"\System32;" + system
    subprocess.run([str(python), "-m", "pip", "install", "--no-index", "--no-deps", "--no-compile", str(wheels[0])], env=clean, check=True)
    subprocess.run([str(python), "-I", "-m", "unittest", "discover", "-s", str(root / "tests"), "-p", "test_*.py"],
                   cwd=directory, env=clean, check=True)
