"""Stage exact native components and notices for the reusable installed-wheel CI."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil

p = argparse.ArgumentParser(description=__doc__)
for name in ("numeric-library", "numeric-receipt", "facade-library", "facade-receipt", "out"):
    p.add_argument("--" + name, required=True, type=Path)
a = p.parse_args()
components = {}
platform = None
source = None
# Validate first; receipt production remains the source/native owner's job.
for name, library, receipt in (("numeric", a.numeric_library, a.numeric_receipt),
                               ("facade", a.facade_library, a.facade_receipt)):
    info = json.loads(receipt.read_bytes())
    if type(info.get("abi_version")) is not int or info["abi_version"] != 1:
        raise RuntimeError("Unsupported component ABI")
    tag = info.get("platform_tag")
    if tag not in ("linux_x86_64", "win_amd64") or (platform and tag != platform):
        raise RuntimeError("Components must target one supported platform")
    platform = tag
    filename = ("plurimath_" + ("numeric" if name == "numeric" else "facade") + ".dll"
                if tag == "win_amd64" else
                "libplurimath_" + ("numeric" if name == "numeric" else "facade") + ".so")
    if (library.name != filename or info.get("library") != filename
            or sha256(library.read_bytes()).hexdigest() != info.get("sha256")):
        raise RuntimeError("Component bytes or native filename disagree with receipt")
    if not (receipt.parent / "licenses" / "manifest.json").is_file():
        raise RuntimeError("Component notice inventory is missing")
    if name == "facade":
        source = info.get("native_source_commit")
        if not isinstance(source, str) or len(source) != 40 or any(c not in "0123456789abcdef" for c in source):
            raise RuntimeError("Missing exact facade source identity")
    components[name] = (library, receipt)
a.out.mkdir()
manifest = {"schema": "plurimath.python-native-inputs/1", "platform_tag": platform,
            "facade_source_commit": source, "components": {}, "files": {}}
for name, (library, receipt) in components.items():
    destination = a.out / name
    destination.mkdir()
    shutil.copyfile(library, destination / library.name)
    shutil.copyfile(receipt, destination / "build-info.json")
    shutil.copytree(receipt.parent / "licenses", destination / "licenses")
    manifest["components"][name] = {"library": name + "/" + library.name,
                                    "receipt": name + "/build-info.json"}
for path in sorted(a.out.rglob("*")):
    if path.is_file():
        manifest["files"][path.relative_to(a.out).as_posix()] = sha256(path.read_bytes()).hexdigest()
(a.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"platform_tag": platform, "facade_source_commit": source,
                  "files": len(manifest["files"]),
                  "manifest_sha256": sha256((a.out / "manifest.json").read_bytes()).hexdigest()}))
