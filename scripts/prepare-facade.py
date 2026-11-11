"""Prepare a checksum-sealed canonical facade component and actual source notices."""
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import shutil
import subprocess
import sysconfig
import tarfile


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--seal", required=True, type=Path)
    cli.add_argument("--workspace", required=True, type=Path)
    cli.add_argument("--out", required=True, type=Path)
    args = cli.parse_args()
    workspace = args.workspace.resolve()
    seal = json.loads(args.seal.read_bytes())
    def sealed_file(key):
        item = seal[key]
        path = Path(item["path"])
        if not path.is_absolute():
            path = workspace / path
        if digest(path) != item["sha256"]:
            raise RuntimeError(f"Sealed facade input changed: {key}")
        return path
    binary = sealed_file("native")
    bundle = sealed_file("source_bundle")
    metadata_path = sealed_file("cargo_metadata_linux")
    sealed_file("header")
    sealed_file("proof")
    head = seal["head"]
    heads = subprocess.check_output(["git", "bundle", "list-heads", str(bundle)], text=True)
    if head not in [line.split()[0] for line in heads.splitlines()]:
        raise RuntimeError("Source bundle does not retain the sealed commit")
    source = workspace / seal["source"]
    archive = subprocess.check_output(["git", "archive", head], cwd=source)
    # Read the immutable source object, never a later dirty producer worktree.
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        root_files = {entry.name: tree.extractfile(entry).read() for entry in tree if entry.isfile()}
    if sha256(root_files["Cargo.lock"]).hexdigest() != seal["cargo_lock"]["sha256"]:
        raise RuntimeError("Sealed source Cargo.lock disagrees with producer receipt")
    platform = sysconfig.get_platform().replace("-", "_").replace(".", "_")
    if platform != "linux_x86_64" or binary.name != "libplurimath_facade.so":
        raise RuntimeError("This source seal qualifies the Linux x86_64 component only")
    image = binary.read_bytes()
    if image[:4] != b"\x7fELF" or image[4:6] != b"\x02\x01" or int.from_bytes(image[18:20], "little") != 62:
        raise RuntimeError("Facade component is not a little-endian ELF64 x86_64 image")
    metadata = json.loads(metadata_path.read_bytes())
    root_id = metadata["resolve"]["root"]
    args.out.mkdir()
    notices = args.out / "licenses"
    notices.mkdir()
    inventory = []
    for package in metadata["packages"]:
        name = f"{package['name']}-{package['version']}"
        destination = notices / name
        destination.mkdir()
        base = Path(package["manifest_path"]).parent
        if package["id"] == root_id:
            available = {key: value for key, value in root_files.items()
                         if "/" not in key and key.upper().startswith(("LICENSE", "COPYING", "NOTICE"))}
            manifest_bytes = root_files["Cargo.toml"]
            revision = head
        else:
            available = {path.name: path.read_bytes() for path in base.iterdir()
                         if path.is_file() and path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE"))}
            if package.get("license_file"):
                path = base / package["license_file"]
                available[path.name] = path.read_bytes()
            revision = None
            if package.get("source", "") and package["source"].startswith("git+"):
                revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=base, text=True).strip()
                if not package["source"].endswith("#" + revision):
                    raise RuntimeError(f"Dependency checkout changed: {name}")
                repository = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=base, text=True).strip())
                for path in repository.iterdir():
                    if path.is_file() and path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                        available.setdefault(path.name, path.read_bytes())
            if package["name"] == "plurimath-amath":
                revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=base, text=True).strip()
                if revision != seal["stage_amath"] or subprocess.check_output(["git", "status", "--porcelain"], cwd=base):
                    raise RuntimeError("Stage source differs from its sealed clean revision")
            manifest_bytes = (base / "Cargo.toml").read_bytes()
        spdx_only = not available
        if spdx_only:
            if not package.get("license"):
                raise RuntimeError(f"Dependency has neither notice text nor SPDX metadata: {name}")
            available["Cargo.toml"] = manifest_bytes
            available["SOURCE-LICENSE.json"] = (json.dumps({
                "name": package["name"], "version": package["version"], "spdx": package["license"],
                "source": package.get("source"), "source_revision": revision,
                "notice": "Source declares SPDX metadata but supplies no standalone license text; no text was synthesized.",
            }, indent=2) + "\n").encode()
        recorded = {}
        for filename, data in sorted(available.items()):
            path = destination / filename
            path.write_bytes(data)
            recorded[str(path.relative_to(notices))] = sha256(data).hexdigest()
        inventory.append({"name": package["name"], "version": package["version"],
                          "license": package.get("license"), "notices": recorded, "spdx_only": spdx_only})
    (notices / "manifest.json").write_text(json.dumps(inventory, indent=2) + "\n")
    receipt = {"abi_version": 1, "library": binary.name, "sha256": digest(binary),
               "platform_tag": platform, "native_source_commit": head,
               "cargo_lock_sha256": seal["cargo_lock"]["sha256"],
               "cargo_metadata_sha256": digest(metadata_path), "source_bundle_sha256": digest(bundle),
               "producer_receipt_sha256": digest(args.seal), "scope": seal["status"],
               "qualification": seal["qualification"], "limits": seal["limits"], "full_facade_complete": False}
    (args.out / "build-info.json").write_text(json.dumps(receipt, indent=2) + "\n")
    shutil.copyfile(binary, args.out / binary.name)
    print(json.dumps({"source": head, "sha256": receipt["sha256"], "notice_groups": len(inventory)}))


if __name__ == "__main__":
    main()
