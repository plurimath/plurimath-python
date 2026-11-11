"""Build from a producer's sealed, platform-specific native input directory."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--bundle", type=Path, required=True)
p.add_argument("--wheel-dir", type=Path, required=True)
p.add_argument("--facade-source", default=os.environ.get("EXPECTED_FACADE_SOURCE"))
a = p.parse_args()
root = a.bundle.resolve()
manifest = json.loads((root / "manifest.json").read_bytes())
platform = sysconfig.get_platform().replace("-", "_").replace(".", "_")
if (manifest.get("schema") != "plurimath.python-native-inputs/1"
        or manifest.get("platform_tag") != platform
        or not a.facade_source or manifest.get("facade_source_commit") != a.facade_source):
    raise RuntimeError("Native input schema, platform or expected source disagrees")
files = manifest["files"]
def owned(relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise RuntimeError("Native input path escapes its bundle")
    return path
for relative, expected in files.items():
    if sha256(owned(relative).read_bytes()).hexdigest() != expected:
        raise RuntimeError("Native input checksum disagrees: " + relative)
environment = os.environ.copy()
for name, prefix in (("numeric", "PLURIMATH"), ("facade", "PLURIMATH_FACADE")):
    component = manifest["components"][name]
    for key in ("library", "receipt"):
        if component[key] not in files:
            raise RuntimeError("Unsealed component input")
    receipt = json.loads(owned(component["receipt"]).read_bytes())
    if receipt["platform_tag"] != platform:
        raise RuntimeError("Component platform disagrees")
    if name == "facade" and receipt["native_source_commit"] != a.facade_source:
        raise RuntimeError("Component source disagrees")
    # The notice inventory and every actual file are sealed alongside the binary.
    notices = owned(component["receipt"]).parent / "licenses"
    if not notices.is_dir():
        raise RuntimeError("Missing native dependency notices")
    for path in notices.rglob("*"):
        if path.is_file() and path.relative_to(root).as_posix() not in files:
            raise RuntimeError("Unsealed native notice")
    environment[prefix + "_NATIVE"] = str(owned(component["library"]))
    environment[prefix + "_NATIVE_RECEIPT" if name == "numeric" else prefix + "_RECEIPT"] = str(owned(component["receipt"]))
subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps",
                "--wheel-dir", str(a.wheel_dir.resolve()), str(Path(__file__).resolve().parents[1])],
               env=environment, check=True)
