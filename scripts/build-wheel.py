"""Package the pinned native Plurimath build in a host-platform wheel."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import struct
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--rust-source", required=True, type=Path)
    cli.add_argument("--library", required=True, type=Path)
    cli.add_argument("--cargo-metadata", required=True, type=Path)
    cli.add_argument("--wheel-dir", type=Path)
    cli.add_argument("--prepare-dir", type=Path, help="Validate and emit native receipt/notices without building a wheel")
    cli.add_argument("--platform-tag", choices=("linux_x86_64", "win_amd64"))
    cli.add_argument("--target-metadata", type=Path, help="Exact target metadata when preparing on another platform")
    args = cli.parse_args()
    source = args.rust_source.resolve()
    platform_tag = args.platform_tag or sysconfig.get_platform().replace("-", "_").replace(".", "_")
    if args.platform_tag and not args.prepare_dir:
        raise RuntimeError("Explicit target platforms are only supported for receipt preparation")
    if not args.prepare_dir and not args.wheel_dir:
        cli.error("--wheel-dir or --prepare-dir is required")
    pin_file = ROOT / ("native-source.win_amd64.json" if platform_tag == "win_amd64" else "native-source.json")
    pins = json.loads(pin_file.read_bytes())
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if revision != pins["native_source_commit"]:
        raise RuntimeError("Rust checkout is at a different revision")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=source):
        raise RuntimeError("Rust checkout must be clean")
    if digest(source / "Cargo.lock") != pins["cargo_lock_sha256"]:
        raise RuntimeError("Cargo.lock differs from the pinned bytes")
    binary = args.library.resolve()
    expected_library = "plurimath_numeric.dll" if platform_tag == "win_amd64" else "libplurimath_numeric.so"
    if platform_tag != pins["platform_tag"] or binary.name != expected_library:
        raise RuntimeError("Native library does not target this wheel platform")
    if digest(binary) != pins["library_sha256"]:
        raise RuntimeError("Library differs from the pinned native build")
    if platform_tag == "win_amd64":
        image = binary.read_bytes()
        pe = struct.unpack_from("<I", image, 0x3c)[0]
        if image[:2] != b"MZ" or image[pe:pe+4] != b"PE\0\0" or struct.unpack_from("<H", image, pe+4)[0] != 0x8664:
            raise RuntimeError("Native library is not a Windows AMD64 PE image")
    metadata_pin = pins.get("source_metadata_sha256", pins.get("cargo_metadata_sha256"))
    if metadata_pin and digest(args.cargo_metadata) != metadata_pin:
        raise RuntimeError("Cargo metadata differs from the pinned native build")
    metadata = json.loads(args.cargo_metadata.read_bytes())
    if Path(metadata["workspace_root"]).resolve() != source:
        raise RuntimeError("Cargo metadata belongs to a different checkout")
    packages = {package["name"]: package for package in metadata["packages"]}
    for name, expected in pins.get("native_source_dependencies", {}).items():
        checkout = Path(packages[name]["manifest_path"]).parent
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"], cwd=checkout, text=True
        ).splitlines()
        package_source = packages[name]["source"]
        if package_source and package_source.startswith("git+"):
            if not package_source.endswith("#" + expected):
                raise RuntimeError(f"Cargo resolved a different dependency revision: {name}")
            status = [line for line in status if line != "?? .cargo-ok"]
        if revision != expected or status:
            raise RuntimeError(f"Native source dependency differs from its pinned clean checkout: {name}")
    for name, assets in pins.get("native_data", {}).items():
        checkout = Path(packages[name]["manifest_path"]).parent
        for asset, expected in assets.items():
            if digest(checkout / asset) != expected:
                raise RuntimeError(f"Bundled native data differs from its pin: {name}/{asset}")
    target_metadata = metadata
    if args.target_metadata:
        if digest(args.target_metadata) != pins["cargo_metadata_sha256"]:
            raise RuntimeError("Target metadata differs from its pinned native build")
        target_metadata = json.loads(args.target_metadata.read_bytes())
        identity = lambda package: (package["name"], package["version"], package["source"])
        known = {identity(package) for package in metadata["packages"]}
        if any(identity(package) not in known for package in target_metadata["packages"]):
            raise RuntimeError("Target metadata contains an unverified source dependency")
    elif pins.get("source_metadata_sha256"):
        raise RuntimeError("This target requires its sealed --target-metadata")
    target_names = {package["name"] for package in target_metadata["packages"]}
    target_root = target_metadata["resolve"]["root"]
    target_node = next(node for node in target_metadata["resolve"]["nodes"] if node["id"] == target_root)
    if not set(pins.get("features", ())).issubset(target_node["features"]):
        raise RuntimeError("Target metadata lacks required native features")
    root_id = metadata["resolve"]["root"]
    root_node = next(node for node in metadata["resolve"]["nodes"] if node["id"] == root_id)
    if not set(pins.get("features", ())).issubset(root_node["features"]):
        raise RuntimeError("Cargo metadata lacks required native features")
    env = os.environ.copy()
    with TemporaryDirectory(prefix="plurimath-wheel-") as temporary:
        staging = Path(temporary)
        notices = staging / "licenses"
        notices.mkdir()
        dependencies = []
        for package in metadata["packages"]:
            if package["name"] not in target_names:
                continue
            base = Path(package["manifest_path"]).parent
            name_version = f"{package['name']}-{package['version']}"
            files = {path for path in base.iterdir() if path.is_file() and
                     path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE"))}
            if package.get("license_file"):
                files.add(base / package["license_file"])
            if package["name"] in ("parsanol", "parsanol-derive"):
                # The Parsanol workspace license covers both nested crates.
                workspace = Path(subprocess.check_output(
                    ["git", "rev-parse", "--show-toplevel"], cwd=base, text=True
                ).strip())
                files.update(path for path in workspace.iterdir() if path.is_file()
                             and path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")))
            if not files:
                raise RuntimeError(f"Native dependency license notice is missing: {name_version}")
            recorded = {}
            for path in sorted(files):
                destination = notices / name_version / path.name
                destination.parent.mkdir(exist_ok=True)
                shutil.copyfile(path, destination)
                recorded[str(destination.relative_to(notices))] = digest(destination)
            dependencies.append({
                "name": package["name"], "version": package["version"],
                "license": package.get("license"), "notices": recorded,
            })
        (notices / "manifest.json").write_text(json.dumps(dependencies, indent=2) + "\n")
        receipt = staging / "build-info.json"
        receipt.write_text(json.dumps({
            **pins, "library": binary.name, "sha256": digest(binary), "abi_version": 1,
            "cargo_metadata_sha256": digest(args.target_metadata or args.cargo_metadata),
        }, indent=2) + "\n")
        if args.prepare_dir:
            shutil.copytree(staging, args.prepare_dir)
            return
        env["PLURIMATH_NATIVE"] = str(binary)
        env["PLURIMATH_NATIVE_RECEIPT"] = str(receipt)
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps",
             "--wheel-dir", str(args.wheel_dir.resolve()), "."],
            cwd=ROOT, env=env, check=True,
        )


if __name__ == "__main__":
    main()
