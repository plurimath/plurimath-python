"""Prepare a locally built Windows facade component from its actual sealed inputs."""
import argparse
import ctypes
from hashlib import sha256
import json
from pathlib import Path
import shutil
import struct
import sys
import sysconfig

p = argparse.ArgumentParser(description=__doc__)
for key in ("library", "build-receipt", "metadata", "canonical-receipt", "out"):
    p.add_argument("--" + key, type=Path, required=True)
p.add_argument("--canonical-notices", type=Path, required=True)
p.add_argument("--canonical-metadata", type=Path, required=True)
a = p.parse_args()
if sys.platform != "win32" or sysconfig.get_platform() != "win-amd64":
    raise RuntimeError("Prepare the Windows component on its actual Windows AMD64 build host")
info = json.loads(a.canonical_receipt.read_bytes())
built = json.loads(a.build_receipt.read_bytes())
image = a.library.read_bytes()
if (built["exit"] != 0 or built["metadata_exit"] != 0
        or built["source"] != info["native_source_commit"]
        or sha256(image).hexdigest() != built["dll_sha256"]):
    raise RuntimeError("Windows library/build/source pins disagree")
pe = struct.unpack_from("<I", image, 0x3c)[0]
if image[pe:pe + 4] != b"PE\0\0" or struct.unpack_from("<H", image, pe + 4)[0] != 0x8664:
    raise RuntimeError("Facade library is not an AMD64 PE image")
version = ctypes.CDLL(str(a.library.resolve())).plurimath_facade_abi_version
version.argtypes = []
version.restype = ctypes.c_uint32
if version() != 1:
    raise RuntimeError("Unsupported native facade ABI")
if sha256(a.canonical_metadata.read_bytes()).hexdigest() != info["cargo_metadata_sha256"]:
    raise RuntimeError("Canonical source metadata changed")
canonical_packages = {(x["name"], x["version"]): x for x in json.loads(a.canonical_metadata.read_bytes())["packages"]}
canonical_notices = {(x["name"], x["version"]): x for x in json.loads((a.canonical_notices / "manifest.json").read_bytes())}
metadata = json.loads(a.metadata.read_bytes())
a.out.mkdir()
notices = a.out / "licenses"
notices.mkdir()
inventory = []
for package in metadata["packages"]:
    base = Path(package["manifest_path"]).parent
    destination = notices / (package["name"] + "-" + package["version"])
    destination.mkdir()
    available = {f.name: f.read_bytes() for f in base.iterdir()
                 if f.is_file() and f.name.upper().startswith(("LICENSE", "COPYING", "NOTICE"))}
    if package.get("license_file"):
        f = base / package["license_file"]
        available[f.name] = f.read_bytes()
    # Source archives contain multi-crate Git roots. Read their actual root
    # notices only when the build proves that root belongs to the canonical seal.
    provenance = built.get("path_sources", {}).get(package["name"] + "@" + package["version"])
    if package.get("source") is None and provenance is not None:
        roots = {dependency["head"] for dependency in info.get("source_closure", [])}
        roots.add(info["native_source_commit"])
        repository = Path(provenance["repository"]).resolve()
        if (provenance["head"] not in roots or not base.resolve().is_relative_to(repository)
                or sha256((base / "Cargo.toml").read_bytes()).hexdigest() != provenance["manifest_sha256"]):
            raise RuntimeError("Path dependency notice source differs from the sealed build")
        for path in repository.iterdir():
            if path.is_file() and path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                available.setdefault(path.name, path.read_bytes())
    identity = (package["name"], package["version"])
    canonical = canonical_packages.get(identity, {})
    texts = canonical_notices.get(identity, {})
    if (not available and (package.get("source") or "").startswith("git+")
            and canonical.get("source") == package["source"] and texts and not texts["spdx_only"]):
        for name, expected in texts["notices"].items():
            data = (a.canonical_notices / name).read_bytes()
            if sha256(data).hexdigest() != expected:
                raise RuntimeError("Canonical dependency notice changed")
            available[Path(name).name] = data
    spdx_only = not available
    if spdx_only:
        if not package.get("license"):
            raise RuntimeError("Source has neither license text nor SPDX declaration")
        available["Cargo.toml"] = (base / "Cargo.toml").read_bytes()
        available["SOURCE-LICENSE.json"] = (json.dumps({
            "name": package["name"], "version": package["version"],
            "spdx": package["license"], "source": package.get("source"),
            "notice": "Source supplies SPDX metadata but no standalone license text; no text was synthesized.",
        }, indent=2) + "\n").encode()
    recorded = {}
    for name, data in sorted(available.items()):
        target = destination / name
        target.write_bytes(data)
        recorded[target.relative_to(notices).as_posix()] = sha256(data).hexdigest()
    inventory.append({"name": package["name"], "version": package["version"],
                      "license": package.get("license"), "notices": recorded, "spdx_only": spdx_only})
(notices / "manifest.json").write_text(json.dumps(inventory, indent=2) + "\n")
info.update(library="plurimath_facade.dll", sha256=sha256(image).hexdigest(), platform_tag="win_amd64",
            cargo_metadata_linux_sha256=info["cargo_metadata_sha256"],
            cargo_metadata_sha256=sha256(a.metadata.read_bytes()).hexdigest(),
            windows_build_receipt_sha256=sha256(a.build_receipt.read_bytes()).hexdigest(),
            windows_build_profile=built["profile"])
(a.out / "build-info.json").write_text(json.dumps(info, indent=2) + "\n")
shutil.copyfile(a.library, a.out / info["library"])
print(json.dumps({"source": info["native_source_commit"], "sha256": info["sha256"],
                  "notice_groups": len(inventory), "platform": "win_amd64"}))
